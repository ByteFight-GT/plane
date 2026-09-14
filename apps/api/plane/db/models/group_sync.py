# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Identity-provider group sync.

Workspace admins map groups asserted by the SSO identity provider (the OIDC
``groups`` claim, or any other claim) to workspace roles and project roles.
Memberships granted this way are tracked in ``GroupSyncMembership`` so that
they can be revoked again when the user leaves the group, while access that an
admin granted by hand is never touched.
"""

from django.conf import settings
from django.db import models

from .base import BaseModel
from .workspace import ROLE_CHOICES


class WorkspaceGroupSyncConfig(BaseModel):
    workspace = models.OneToOneField("db.Workspace", on_delete=models.CASCADE, related_name="group_sync_config")
    # Update memberships every time the user signs in through SSO.
    sync_on_login = models.BooleanField(default=True)
    # Periodically refresh memberships in the background using the stored
    # refresh tokens, so users who leave a group lose access without logging in.
    offline_sync = models.BooleanField(default=False)
    # Revoke sync-granted access when the user is no longer in a mapped group.
    auto_remove = models.BooleanField(default=False)
    # Name of the claim / attribute carrying the group list. Dotted paths
    # ("realm_access.roles") are supported for nested claims.
    group_attribute_key = models.CharField(max_length=255, default="groups")
    # Workspace role for users added through a project mapping only.
    default_workspace_role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Workspace Group Sync Config"
        verbose_name_plural = "Workspace Group Sync Configs"
        db_table = "workspace_group_sync_configs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.workspace.slug} group sync"


class WorkspaceGroupRoleMapping(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="group_role_mappings")
    group_name = models.CharField(max_length=255)
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=15)

    class Meta:
        unique_together = ["workspace", "group_name", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "group_name"],
                condition=models.Q(deleted_at__isnull=True),
                name="workspace_group_role_mapping_unique_group_when_deleted_at_null",
            )
        ]
        verbose_name = "Workspace Group Role Mapping"
        verbose_name_plural = "Workspace Group Role Mappings"
        db_table = "workspace_group_role_mappings"
        ordering = ("group_name",)

    def __str__(self):
        return f"{self.workspace.slug} {self.group_name} -> {self.role}"


class ProjectGroupRoleMapping(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="project_group_role_mappings")
    # NULL means "apply to all projects" in the workspace, current and future.
    project = models.ForeignKey(
        "db.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="group_role_mappings"
    )
    group_name = models.CharField(max_length=255)
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, default=15)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "project", "group_name"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_group_role_mapping_unique_project_group_when_deleted_at_null",
            ),
            models.UniqueConstraint(
                fields=["workspace", "group_name"],
                condition=models.Q(deleted_at__isnull=True, project__isnull=True),
                name="project_group_role_mapping_unique_all_projects_group_when_deleted_at_null",
            ),
        ]
        verbose_name = "Project Group Role Mapping"
        verbose_name_plural = "Project Group Role Mappings"
        db_table = "project_group_role_mappings"
        ordering = ("group_name",)

    def __str__(self):
        target = self.project.identifier if self.project_id else "*"
        return f"{self.workspace.slug} {self.group_name} -> {target}:{self.role}"


class GroupSyncMembership(BaseModel):
    """A workspace or project membership that was granted by group sync."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="group_sync_memberships")
    # NULL means the workspace membership itself.
    project = models.ForeignKey(
        "db.Project", on_delete=models.CASCADE, null=True, blank=True, related_name="group_sync_memberships"
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_sync_memberships"
    )
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "project", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="group_sync_membership_unique_project_member_when_deleted_at_null",
            ),
            models.UniqueConstraint(
                fields=["workspace", "member"],
                condition=models.Q(deleted_at__isnull=True, project__isnull=True),
                name="group_sync_membership_unique_workspace_member_when_deleted_at_null",
            ),
        ]
        verbose_name = "Group Sync Membership"
        verbose_name_plural = "Group Sync Memberships"
        db_table = "group_sync_memberships"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.member_id} {self.workspace_id} {self.project_id or '*'}"
