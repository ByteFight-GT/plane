# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Identity-provider group sync engine.

Given the claims an identity provider asserted for a user, reconcile the
user's workspace and project memberships against the group mappings that
workspace admins configured. Rules (mirroring the documented behaviour of
Plane's hosted group sync):

* A user in several groups mapped to the same target gets the highest role.
* Access an admin granted by hand is never downgraded or removed; only
  memberships this engine created (tracked in ``GroupSyncMembership``) are
  managed, and those are only revoked when ``auto_remove`` is on.
* The last admin of a workspace or project is never removed or downgraded.
* Workspace guests never receive a project role above Guest, and workspace
  admins are always project admins (the same rule the members API enforces).
* Sync errors never block sign-in: every entry point swallows and logs.
"""

import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    GroupSyncMembership,
    Project,
    ProjectGroupRoleMapping,
    ProjectMember,
    WorkspaceGroupRoleMapping,
    WorkspaceGroupSyncConfig,
    WorkspaceMember,
)
from plane.utils.cache import invalidate_cache_directly
from plane.utils.exception_logger import log_exception

logger = logging.getLogger("plane.authentication")

ADMIN, MEMBER, GUEST = 20, 15, 5


# --------------------------------------------------------------------------- #
# Claim helpers
# --------------------------------------------------------------------------- #
def normalize_group(name):
    """Compare group names ignoring surrounding whitespace and a leading path slash."""
    return str(name).strip().lstrip("/")


def extract_groups(claims, key):
    """
    Pull a list of group names out of ``claims`` using ``key``.

    ``key`` is tried literally first (``custom:groups``), then as a dotted path
    into nested objects (``realm_access.roles``). The value may be a list or a
    comma / space separated string.
    """
    if not claims or not key:
        return []

    value = claims.get(key)
    if value is None and "." in key:
        node = claims
        for part in key.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        value = node

    if value is None:
        return []
    if isinstance(value, str):
        value = value.replace(",", " ").split()
    if not isinstance(value, (list, tuple, set)):
        return []
    return [normalize_group(v) for v in value if str(v).strip()]


# --------------------------------------------------------------------------- #
# Role helpers
# --------------------------------------------------------------------------- #
def constrain_project_role(workspace_role, desired_role):
    """Apply the workspace-role ceiling/floor the members API enforces."""
    if workspace_role == GUEST:
        return GUEST
    if workspace_role == ADMIN:
        return ADMIN
    return desired_role


def _other_active_workspace_admin_exists(workspace_id, user_id):
    return (
        WorkspaceMember.objects.filter(workspace_id=workspace_id, role=ADMIN, is_active=True)
        .exclude(member_id=user_id)
        .exists()
    )


def _other_active_project_admin_exists(project_id, user_id):
    return (
        ProjectMember.objects.filter(project_id=project_id, role=ADMIN, is_active=True)
        .exclude(member_id=user_id)
        .exists()
    )


def _invalidate_member_caches(workspace_slug, project_ids=()):
    invalidate_cache_directly(
        path=f"/api/workspaces/{workspace_slug}/members/", url_params=False, user=False, multiple=True
    )
    for project_id in project_ids:
        invalidate_cache_directly(
            path=f"/api/workspaces/{workspace_slug}/projects/{project_id}/members/",
            url_params=False,
            user=False,
            multiple=True,
        )


# --------------------------------------------------------------------------- #
# Result bookkeeping
# --------------------------------------------------------------------------- #
@dataclass
class SyncResult:
    workspace_slug: str
    groups: list = field(default_factory=list)
    workspace_role: int | None = None
    workspace_action: str = "none"  # none | created | reactivated | updated | removed | kept
    project_actions: dict = field(default_factory=dict)  # project_id -> action

    def as_dict(self):
        return {
            "workspace": self.workspace_slug,
            "groups": self.groups,
            "workspace_role": self.workspace_role,
            "workspace_action": self.workspace_action,
            "project_actions": {str(k): v for k, v in self.project_actions.items()},
        }


# --------------------------------------------------------------------------- #
# Desired-state computation
# --------------------------------------------------------------------------- #
def _desired_state(config, groups):
    """Return (workspace_role | None, {project_id: role}) for the given groups."""
    group_set = {normalize_group(g) for g in groups}
    if not group_set:
        return None, {}

    workspace_role = None
    for mapping in WorkspaceGroupRoleMapping.objects.filter(workspace_id=config.workspace_id):
        if normalize_group(mapping.group_name) in group_set:
            workspace_role = max(workspace_role or 0, mapping.role)

    project_roles = {}
    all_projects_role = None
    for mapping in ProjectGroupRoleMapping.objects.filter(workspace_id=config.workspace_id):
        if normalize_group(mapping.group_name) not in group_set:
            continue
        if mapping.project_id is None:
            all_projects_role = max(all_projects_role or 0, mapping.role)
        else:
            project_roles[mapping.project_id] = max(project_roles.get(mapping.project_id, 0), mapping.role)

    if all_projects_role is not None:
        for project_id in Project.objects.filter(
            workspace_id=config.workspace_id, archived_at__isnull=True
        ).values_list("id", flat=True):
            project_roles[project_id] = max(project_roles.get(project_id, 0), all_projects_role)

    # A project mapping implies workspace membership; use the configured default role.
    if workspace_role is None and project_roles:
        workspace_role = config.default_workspace_role or GUEST

    return workspace_role, project_roles


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #
def _apply_workspace_membership(config, user, desired_role, result):
    workspace_id = config.workspace_id
    tracked = GroupSyncMembership.objects.filter(workspace_id=workspace_id, project__isnull=True, member=user).first()
    membership = WorkspaceMember.objects.filter(workspace_id=workspace_id, member=user).first()

    if desired_role is None:
        # Nothing grants access anymore.
        if tracked and config.auto_remove and membership and membership.is_active:
            if membership.role == ADMIN and not _other_active_workspace_admin_exists(workspace_id, user.id):
                result.workspace_action = "kept"  # last admin protection
                return membership
            membership.is_active = False
            membership.save(update_fields=["is_active", "updated_at"])
            # Removing workspace access removes project access as well, like the members API does.
            ProjectMember.objects.filter(workspace_id=workspace_id, member=user, is_active=True).update(
                is_active=False, updated_at=timezone.now()
            )
            GroupSyncMembership.objects.filter(workspace_id=workspace_id, member=user).delete()
            result.workspace_action = "removed"
            return None
        result.workspace_action = "none"
        return membership if membership and membership.is_active else None

    if membership is None:
        membership = WorkspaceMember.objects.create(workspace_id=workspace_id, member=user, role=desired_role)
        GroupSyncMembership.objects.create(workspace_id=workspace_id, member=user, role=desired_role)
        result.workspace_action = "created"
        return membership

    if not membership.is_active:
        membership.is_active = True
        membership.role = desired_role
        membership.save(update_fields=["is_active", "role", "updated_at"])
        GroupSyncMembership.objects.update_or_create(
            workspace_id=workspace_id, project=None, member=user, defaults={"role": desired_role}
        )
        result.workspace_action = "reactivated"
        return membership

    if tracked:
        # Sync-managed membership: follow the mapping up or down, except for the last admin.
        if membership.role != desired_role:
            if membership.role == ADMIN and not _other_active_workspace_admin_exists(workspace_id, user.id):
                result.workspace_action = "kept"
                return membership
            membership.role = desired_role
            membership.save(update_fields=["role", "updated_at"])
            tracked.role = desired_role
            tracked.save(update_fields=["role", "updated_at"])
            result.workspace_action = "updated"
            return membership
        result.workspace_action = "kept"
        return membership

    # Manually granted membership: only ever raise the role, never lower it.
    if desired_role > membership.role:
        membership.role = desired_role
        membership.save(update_fields=["role", "updated_at"])
        result.workspace_action = "updated"
    else:
        result.workspace_action = "kept"
    return membership


def _apply_project_memberships(config, user, workspace_role, desired_projects, result):
    workspace_id = config.workspace_id
    tracked_rows = {
        row.project_id: row
        for row in GroupSyncMembership.objects.filter(workspace_id=workspace_id, project__isnull=False, member=user)
    }
    existing = {
        pm.project_id: pm
        for pm in ProjectMember.objects.filter(workspace_id=workspace_id, member=user).select_related("project")
    }
    touched = []

    # Grant / update
    for project_id, desired in desired_projects.items():
        role = constrain_project_role(workspace_role, desired)
        membership = existing.get(project_id)
        tracked = tracked_rows.get(project_id)

        if membership is None:
            project = Project.objects.filter(pk=project_id, workspace_id=workspace_id).first()
            if project is None:
                continue
            ProjectMember.objects.create(project=project, member=user, role=role)
            GroupSyncMembership.objects.create(workspace_id=workspace_id, project=project, member=user, role=role)
            result.project_actions[project_id] = "created"
            touched.append(project_id)
        elif not membership.is_active:
            membership.is_active = True
            membership.role = role
            membership.save(update_fields=["is_active", "role", "updated_at"])
            GroupSyncMembership.objects.update_or_create(
                workspace_id=workspace_id, project_id=project_id, member=user, defaults={"role": role}
            )
            result.project_actions[project_id] = "reactivated"
            touched.append(project_id)
        elif tracked:
            if membership.role != role:
                if membership.role == ADMIN and not _other_active_project_admin_exists(project_id, user.id):
                    result.project_actions[project_id] = "kept"
                    continue
                membership.role = role
                membership.save(update_fields=["role", "updated_at"])
                tracked.role = role
                tracked.save(update_fields=["role", "updated_at"])
                result.project_actions[project_id] = "updated"
                touched.append(project_id)
            else:
                result.project_actions[project_id] = "kept"
        elif role > membership.role:
            membership.role = role
            membership.save(update_fields=["role", "updated_at"])
            result.project_actions[project_id] = "updated"
            touched.append(project_id)
        else:
            result.project_actions[project_id] = "kept"

    # Revoke sync-granted project access that is no longer justified
    if config.auto_remove:
        for project_id, tracked in tracked_rows.items():
            if project_id in desired_projects:
                continue
            membership = existing.get(project_id)
            if membership and membership.is_active:
                if membership.role == ADMIN and not _other_active_project_admin_exists(project_id, user.id):
                    result.project_actions[project_id] = "kept"
                    continue
                membership.is_active = False
                membership.save(update_fields=["is_active", "updated_at"])
                result.project_actions[project_id] = "removed"
                touched.append(project_id)
            tracked.delete()

    return touched


def sync_workspace_user(config, user, claims):
    """Reconcile one user's access in one workspace. Returns a SyncResult."""
    groups = extract_groups(claims, config.group_attribute_key)
    result = SyncResult(workspace_slug=config.workspace.slug, groups=groups)
    workspace_role, desired_projects = _desired_state(config, groups)
    result.workspace_role = workspace_role

    with transaction.atomic():
        membership = _apply_workspace_membership(config, user, workspace_role, result)
        touched = []
        if membership is not None:
            touched = _apply_project_memberships(config, user, membership.role, desired_projects, result)

    if result.workspace_action != "none" or touched:
        _invalidate_member_caches(result.workspace_slug, touched)
    return result


def sync_user_groups(user, claims, trigger="login"):
    """
    Entry point used by the SSO callback (``trigger="login"``) and the periodic
    task (``trigger="offline"``). Never raises.
    """
    results = []
    try:
        flag = "sync_on_login" if trigger == "login" else "offline_sync"
        configs = WorkspaceGroupSyncConfig.objects.filter(**{flag: True}).select_related("workspace")
        for config in configs:
            try:
                results.append(sync_workspace_user(config, user, claims).as_dict())
            except Exception as e:  # one broken workspace must not block the others
                log_exception(e)
                logger.warning("Group sync failed for workspace %s user %s", config.workspace_id, user.id)
    except Exception as e:
        log_exception(e)
    return results


def claims_match_any_mapping(claims):
    """True if the asserted groups would grant access somewhere (used to let SSO users sign up)."""
    try:
        for config in WorkspaceGroupSyncConfig.objects.filter(sync_on_login=True):
            groups = extract_groups(claims, config.group_attribute_key)
            if not groups:
                continue
            workspace_role, projects = _desired_state(config, groups)
            if workspace_role is not None or projects:
                return True
    except Exception as e:
        log_exception(e)
    return False
