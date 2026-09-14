# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the identity-provider group sync engine."""

import pytest

from plane.db.models import (
    GroupSyncMembership,
    Project,
    ProjectGroupRoleMapping,
    ProjectMember,
    User,
    Workspace,
    WorkspaceGroupRoleMapping,
    WorkspaceGroupSyncConfig,
    WorkspaceMember,
)
from plane.utils.group_sync import (
    ADMIN,
    GUEST,
    MEMBER,
    claims_match_any_mapping,
    constrain_project_role,
    extract_groups,
    normalize_group,
    sync_user_groups,
    sync_workspace_user,
)


@pytest.mark.unit
class TestClaimHelpers:
    def test_normalize_strips_whitespace_and_leading_slash(self):
        assert normalize_group("  /plane/admins ") == "plane/admins"

    def test_extract_list_claim(self):
        assert extract_groups({"groups": ["/a", "b "]}, "groups") == ["a", "b"]

    def test_extract_string_claim_splits_on_comma_and_space(self):
        assert extract_groups({"groups": "a, b c"}, "groups") == ["a", "b", "c"]

    def test_extract_literal_key_with_colon(self):
        assert extract_groups({"custom:groups": ["x"]}, "custom:groups") == ["x"]

    def test_extract_dotted_path(self):
        claims = {"realm_access": {"roles": ["admin", "user"]}}
        assert extract_groups(claims, "realm_access.roles") == ["admin", "user"]

    def test_extract_missing_or_wrong_type(self):
        assert extract_groups({}, "groups") == []
        assert extract_groups({"groups": 42}, "groups") == []
        assert extract_groups(None, "groups") == []

    def test_constrain_project_role(self):
        assert constrain_project_role(GUEST, ADMIN) == GUEST
        assert constrain_project_role(ADMIN, GUEST) == ADMIN
        assert constrain_project_role(MEMBER, ADMIN) == ADMIN
        assert constrain_project_role(MEMBER, GUEST) == GUEST


@pytest.fixture
def owner(db):
    user = User.objects.create(email="owner@plane.so", username="owner")
    user.set_password("x")
    user.save()
    return user


@pytest.fixture
def alice(db):
    user = User.objects.create(email="alice@plane.so", username="alice")
    user.set_password("x")
    user.save()
    return user


@pytest.fixture
def ws(owner):
    workspace = Workspace.objects.create(name="Sync WS", owner=owner, slug="sync-ws")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=ADMIN)
    return workspace


@pytest.fixture
def config(ws):
    return WorkspaceGroupSyncConfig.objects.create(workspace=ws)


@pytest.fixture
def project(ws, owner):
    project = Project.objects.create(name="Proj", identifier="PRJ", workspace=ws)
    ProjectMember.objects.create(project=project, member=owner, role=ADMIN)
    return project


def _ws_member(ws, user):
    return WorkspaceMember.objects.filter(workspace=ws, member=user).first()


def _pm(project, user):
    return ProjectMember.objects.filter(project=project, member=user).first()


@pytest.mark.unit
@pytest.mark.django_db
class TestWorkspaceMapping:
    def test_creates_membership_with_highest_role(self, config, ws, alice):
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="/leads", role=ADMIN)

        result = sync_workspace_user(config, alice, {"groups": ["/devs", "/leads"]})

        assert result.workspace_action == "created"
        assert _ws_member(ws, alice).role == ADMIN
        assert GroupSyncMembership.objects.filter(workspace=ws, member=alice, project__isnull=True).exists()

    def test_no_matching_group_does_nothing(self, config, ws, alice):
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        result = sync_workspace_user(config, alice, {"groups": ["other"]})
        assert result.workspace_action == "none"
        assert _ws_member(ws, alice) is None

    def test_manual_membership_is_never_downgraded(self, config, ws, alice):
        WorkspaceMember.objects.create(workspace=ws, member=alice, role=ADMIN)
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=GUEST)

        result = sync_workspace_user(config, alice, {"groups": ["devs"]})

        assert result.workspace_action == "kept"
        assert _ws_member(ws, alice).role == ADMIN

    def test_manual_membership_is_upgraded(self, config, ws, alice):
        WorkspaceMember.objects.create(workspace=ws, member=alice, role=GUEST)
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)

        sync_workspace_user(config, alice, {"groups": ["devs"]})

        assert _ws_member(ws, alice).role == MEMBER

    def test_sync_managed_membership_follows_mapping_down(self, config, ws, alice):
        mapping = WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=ADMIN)
        sync_workspace_user(config, alice, {"groups": ["devs"]})
        mapping.role = GUEST
        mapping.save()

        result = sync_workspace_user(config, alice, {"groups": ["devs"]})

        assert result.workspace_action == "updated"
        assert _ws_member(ws, alice).role == GUEST

    def test_reactivates_deactivated_member(self, config, ws, alice):
        WorkspaceMember.objects.create(workspace=ws, member=alice, role=MEMBER, is_active=False)
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)

        result = sync_workspace_user(config, alice, {"groups": ["devs"]})

        assert result.workspace_action == "reactivated"
        assert _ws_member(ws, alice).is_active is True

    def test_auto_remove_off_keeps_access(self, config, ws, alice):
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        sync_workspace_user(config, alice, {"groups": ["devs"]})

        sync_workspace_user(config, alice, {"groups": []})

        assert _ws_member(ws, alice).is_active is True

    def test_auto_remove_revokes_only_sync_granted_access(self, config, ws, alice, project):
        config.auto_remove = True
        config.save()
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="devs", role=MEMBER)
        sync_workspace_user(config, alice, {"groups": ["devs"]})
        assert _pm(project, alice).is_active is True

        result = sync_workspace_user(config, alice, {"groups": []})

        assert result.workspace_action == "removed"
        assert _ws_member(ws, alice).is_active is False
        assert _pm(project, alice).is_active is False
        assert not GroupSyncMembership.objects.filter(workspace=ws, member=alice).exists()

    def test_auto_remove_leaves_manual_membership_alone(self, config, ws, alice):
        config.auto_remove = True
        config.save()
        WorkspaceMember.objects.create(workspace=ws, member=alice, role=MEMBER)
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)

        sync_workspace_user(config, alice, {"groups": []})

        assert _ws_member(ws, alice).is_active is True

    def test_last_admin_is_protected(self, config, ws, alice, owner):
        config.auto_remove = True
        config.save()
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="admins", role=ADMIN)
        sync_workspace_user(config, alice, {"groups": ["admins"]})
        # Make alice the only admin
        WorkspaceMember.objects.filter(workspace=ws, member=owner).update(role=MEMBER)

        result = sync_workspace_user(config, alice, {"groups": []})

        assert result.workspace_action == "kept"
        assert _ws_member(ws, alice).is_active is True
        assert _ws_member(ws, alice).role == ADMIN


@pytest.mark.unit
@pytest.mark.django_db
class TestProjectMapping:
    def test_project_mapping_adds_workspace_membership_with_default_role(self, config, ws, alice, project):
        config.default_workspace_role = MEMBER
        config.save()
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="proj-team", role=ADMIN)

        result = sync_workspace_user(config, alice, {"groups": ["proj-team"]})

        assert _ws_member(ws, alice).role == MEMBER
        assert _pm(project, alice).role == ADMIN
        assert result.project_actions[project.id] == "created"

    def test_default_workspace_role_falls_back_to_guest_and_caps_project_role(self, config, ws, alice, project):
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="proj-team", role=ADMIN)

        sync_workspace_user(config, alice, {"groups": ["proj-team"]})

        assert _ws_member(ws, alice).role == GUEST
        assert _pm(project, alice).role == GUEST  # guests never get project admin

    def test_workspace_admin_is_always_project_admin(self, config, ws, alice, project):
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="admins", role=ADMIN)
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="admins", role=GUEST)

        sync_workspace_user(config, alice, {"groups": ["admins"]})

        assert _pm(project, alice).role == ADMIN

    def test_apply_to_all_projects(self, config, ws, alice, project, owner):
        other = Project.objects.create(name="Other", identifier="OTH", workspace=ws)
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=None, group_name="everyone", role=MEMBER)
        config.default_workspace_role = MEMBER
        config.save()

        sync_workspace_user(config, alice, {"groups": ["everyone"]})

        assert _pm(project, alice).role == MEMBER
        assert _pm(other, alice).role == MEMBER

    def test_specific_and_all_projects_highest_wins(self, config, ws, alice, project):
        config.default_workspace_role = MEMBER
        config.save()
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=None, group_name="everyone", role=GUEST)
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="everyone", role=ADMIN)

        sync_workspace_user(config, alice, {"groups": ["everyone"]})

        assert _pm(project, alice).role == ADMIN

    def test_auto_remove_project_only(self, config, ws, alice, project):
        config.auto_remove = True
        config.default_workspace_role = MEMBER
        config.save()
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="staff", role=MEMBER)
        ProjectGroupRoleMapping.objects.create(workspace=ws, project=project, group_name="proj-team", role=MEMBER)
        sync_workspace_user(config, alice, {"groups": ["staff", "proj-team"]})

        result = sync_workspace_user(config, alice, {"groups": ["staff"]})

        assert _ws_member(ws, alice).is_active is True
        assert _pm(project, alice).is_active is False
        assert result.project_actions[project.id] == "removed"


@pytest.mark.unit
@pytest.mark.django_db
class TestEntryPoints:
    def test_sync_user_groups_respects_trigger_flags(self, config, ws, alice):
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        config.sync_on_login = False
        config.offline_sync = True
        config.save()

        assert sync_user_groups(alice, {"groups": ["devs"]}, trigger="login") == []
        assert _ws_member(ws, alice) is None

        results = sync_user_groups(alice, {"groups": ["devs"]}, trigger="offline")
        assert results[0]["workspace_action"] == "created"

    def test_sync_user_groups_never_raises(self, config, ws, alice, monkeypatch):
        import plane.utils.group_sync as mod

        def boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(mod, "sync_workspace_user", boom)
        assert sync_user_groups(alice, {"groups": ["x"]}) == []

    def test_claims_match_any_mapping(self, config, ws):
        assert claims_match_any_mapping({"groups": ["devs"]}) is False
        WorkspaceGroupRoleMapping.objects.create(workspace=ws, group_name="devs", role=MEMBER)
        assert claims_match_any_mapping({"groups": ["devs"]}) is True
        assert claims_match_any_mapping({"groups": ["nope"]}) is False
