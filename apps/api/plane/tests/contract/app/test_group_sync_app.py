# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for the workspace group sync settings endpoints."""

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import (
    Project,
    ProjectGroupRoleMapping,
    User,
    WorkspaceGroupRoleMapping,
    WorkspaceGroupSyncConfig,
    WorkspaceMember,
)


def _base(slug):
    return f"/api/workspaces/{slug}/group-sync/"


@pytest.fixture
def member_client(api_client, workspace):
    """A client authenticated as a non-admin workspace member."""
    user = User.objects.create(email="member@plane.so", username="member")
    user.set_password("x")
    user.save()
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.contract
class TestGroupSyncConfig:
    @pytest.mark.django_db
    def test_get_creates_default_config(self, session_client, workspace):
        response = session_client.get(_base(workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["sync_on_login"] is True
        assert response.data["offline_sync"] is False
        assert response.data["auto_remove"] is False
        assert response.data["group_attribute_key"] == "groups"
        assert WorkspaceGroupSyncConfig.objects.filter(workspace=workspace).exists()

    @pytest.mark.django_db
    def test_patch_updates_config(self, session_client, workspace):
        payload = {"auto_remove": True, "group_attribute_key": "realm_access.roles", "default_workspace_role": 15}
        response = session_client.patch(_base(workspace.slug), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["auto_remove"] is True
        assert response.data["group_attribute_key"] == "realm_access.roles"
        assert response.data["default_workspace_role"] == 15

    @pytest.mark.django_db
    def test_patch_rejects_invalid_role_and_empty_key(self, session_client, workspace):
        response = session_client.patch(_base(workspace.slug), {"default_workspace_role": 7}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response = session_client.patch(_base(workspace.slug), {"group_attribute_key": "  "}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_non_admin_is_forbidden(self, member_client, workspace):
        assert member_client.get(_base(workspace.slug)).status_code == status.HTTP_403_FORBIDDEN
        assert member_client.get(_base(workspace.slug) + "workspace-mappings/").status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_run_queues_offline_sync(self, session_client, workspace):
        with patch("plane.bgtasks.group_sync_task.offline_group_sync.delay") as delay:
            response = session_client.post(_base(workspace.slug) + "run/")
        assert response.status_code == status.HTTP_202_ACCEPTED
        delay.assert_called_once_with(workspace_id=str(workspace.id))


@pytest.mark.contract
class TestWorkspaceMappings:
    @pytest.mark.django_db
    def test_crud(self, session_client, workspace):
        url = _base(workspace.slug) + "workspace-mappings/"

        response = session_client.post(url, {"group_name": " devs ", "role": 15}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["group_name"] == "devs"
        mapping_id = response.data["id"]

        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert [m["id"] for m in response.data] == [mapping_id]

        response = session_client.patch(f"{url}{mapping_id}/", {"role": 20}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == 20

        response = session_client.delete(f"{url}{mapping_id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not WorkspaceGroupRoleMapping.objects.filter(pk=mapping_id).exists()

    @pytest.mark.django_db
    def test_duplicate_group_conflicts(self, session_client, workspace):
        url = _base(workspace.slug) + "workspace-mappings/"
        assert session_client.post(url, {"group_name": "devs", "role": 15}, format="json").status_code == 201
        response = session_client.post(url, {"group_name": "devs", "role": 5}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.django_db
    def test_validation(self, session_client, workspace):
        url = _base(workspace.slug) + "workspace-mappings/"
        assert session_client.post(url, {"group_name": "", "role": 15}, format="json").status_code == 400
        assert session_client.post(url, {"group_name": "x", "role": 99}, format="json").status_code == 400


@pytest.mark.contract
class TestProjectMappings:
    @pytest.fixture
    def project(self, workspace, create_user):
        return Project.objects.create(name="P", identifier="P", workspace=workspace)

    @pytest.mark.django_db
    def test_crud_with_project(self, session_client, workspace, project):
        url = _base(workspace.slug) + "project-mappings/"

        response = session_client.post(
            url, {"group_name": "team", "role": 15, "project": str(project.id)}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project_identifier"] == "P"
        mapping_id = response.data["id"]

        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

        response = session_client.delete(f"{url}{mapping_id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProjectGroupRoleMapping.objects.filter(pk=mapping_id).exists()

    @pytest.mark.django_db
    def test_all_projects_mapping(self, session_client, workspace):
        url = _base(workspace.slug) + "project-mappings/"
        response = session_client.post(url, {"group_name": "everyone", "role": 5, "project": None}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] is None
        # Duplicate "all projects" mapping for the same group conflicts
        response = session_client.post(url, {"group_name": "everyone", "role": 15, "project": None}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.django_db
    def test_project_from_other_workspace_is_rejected(self, session_client, workspace, create_user):
        from plane.db.models import Workspace

        other_ws = Workspace.objects.create(name="Other", owner=create_user, slug="other-ws")
        foreign = Project.objects.create(name="F", identifier="F", workspace=other_ws)
        url = _base(workspace.slug) + "project-mappings/"
        response = session_client.post(
            url, {"group_name": "team", "role": 15, "project": str(foreign.id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
