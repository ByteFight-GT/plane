# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for cross-project parents.

A work item may have a parent in another project of the same workspace, but
only when the acting user is an active member of the parent's project. The
sub-issue endpoints then expose cross-project children only to viewers who are
members of the child's project.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, User, Workspace, WorkspaceMember

ISSUE_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/"
SUB_ISSUES_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/sub-issues/"


def _make_issue(name, project, workspace, author, parent=None):
    issue = Issue(name=name, project=project, workspace=workspace, parent=parent)
    issue.save(created_by_id=author.id)
    return issue


@pytest.fixture
def project_a(db, workspace, create_user):
    project = Project.objects.create(name="Project A", identifier="PA", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def project_b(db, workspace, create_user):
    """Caller is a member of B as well."""
    project = Project.objects.create(name="Project B", identifier="PB", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    return project


@pytest.fixture
def project_c(db, workspace, create_user):
    """Caller is NOT a member of C."""
    return Project.objects.create(name="Project C", identifier="PC", workspace=workspace, created_by=create_user)


@pytest.fixture
def other_workspace_issue(db, create_user):
    other_ws = Workspace.objects.create(name="Other", owner=create_user, slug="other-ws")
    WorkspaceMember.objects.create(workspace=other_ws, member=create_user, role=20)
    project = Project.objects.create(name="Other P", identifier="OP", workspace=other_ws, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=other_ws, role=20)
    return _make_issue("other ws issue", project, other_ws, create_user)


@pytest.fixture
def issue_a(db, workspace, project_a, create_user):
    return _make_issue("A issue", project_a, workspace, create_user)


@pytest.fixture
def parent_b(db, workspace, project_b, create_user):
    return _make_issue("B parent", project_b, workspace, create_user)


@pytest.fixture
def parent_c(db, workspace, project_c, create_user):
    return _make_issue("C parent", project_c, workspace, create_user)


@pytest.mark.contract
class TestCrossProjectParentAssignment:
    @pytest.mark.django_db
    def test_parent_in_other_project_allowed_when_member(self, session_client, workspace, project_a, issue_a, parent_b):
        url = ISSUE_URL.format(slug=workspace.slug, project_id=project_a.id, issue_id=issue_a.id)
        response = session_client.patch(url, {"parent_id": str(parent_b.id)}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT, getattr(response, "data", None)
        issue_a.refresh_from_db()
        assert issue_a.parent_id == parent_b.id

    @pytest.mark.django_db
    def test_parent_in_project_without_membership_rejected(
        self, session_client, workspace, project_a, issue_a, parent_c
    ):
        url = ISSUE_URL.format(slug=workspace.slug, project_id=project_a.id, issue_id=issue_a.id)
        response = session_client.patch(url, {"parent_id": str(parent_c.id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        issue_a.refresh_from_db()
        assert issue_a.parent_id is None

    @pytest.mark.django_db
    def test_parent_in_other_workspace_rejected(
        self, session_client, workspace, project_a, issue_a, other_workspace_issue
    ):
        url = ISSUE_URL.format(slug=workspace.slug, project_id=project_a.id, issue_id=issue_a.id)
        response = session_client.patch(url, {"parent_id": str(other_workspace_issue.id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        issue_a.refresh_from_db()
        assert issue_a.parent_id is None

    @pytest.mark.django_db
    def test_same_project_parent_still_allowed(self, session_client, workspace, project_a, issue_a, create_user):
        sibling = _make_issue("A sibling", project_a, workspace, create_user)
        url = ISSUE_URL.format(slug=workspace.slug, project_id=project_a.id, issue_id=issue_a.id)
        response = session_client.patch(url, {"parent_id": str(sibling.id)}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT, getattr(response, "data", None)


@pytest.mark.contract
class TestCrossProjectChildren:
    @pytest.mark.django_db
    def test_children_from_other_projects_listed_for_members(
        self, session_client, workspace, project_a, project_b, parent_b, issue_a, create_user
    ):
        """Viewing parent B (caller in A and B) lists the child that lives in A."""
        issue_a.parent = parent_b
        issue_a.save(created_by_id=create_user.id)
        url = SUB_ISSUES_URL.format(slug=workspace.slug, project_id=project_b.id, issue_id=parent_b.id)
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        returned = {str(row["id"]) for row in response.data["sub_issues"]}
        assert str(issue_a.id) in returned

    @pytest.mark.django_db
    def test_children_from_projects_without_membership_hidden(
        self, session_client, workspace, project_b, project_c, parent_b, create_user
    ):
        """A child in project C (caller not a member) is hidden from the parent's list."""
        child_c = _make_issue("C child", project_c, workspace, create_user, parent=parent_b)
        url = SUB_ISSUES_URL.format(slug=workspace.slug, project_id=project_b.id, issue_id=parent_b.id)
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        returned = {str(row["id"]) for row in response.data["sub_issues"]}
        assert str(child_c.id) not in returned

    @pytest.mark.django_db
    def test_bulk_add_existing_child_from_other_project(
        self, session_client, workspace, project_a, project_b, parent_b, issue_a, mocker
    ):
        """POST sub-issues accepts a child from another project the caller belongs to,
        and dispatches the activity under the child's own project."""
        mock_activity = mocker.patch("plane.app.views.issue.sub_issue.issue_activity.delay")
        url = SUB_ISSUES_URL.format(slug=workspace.slug, project_id=project_b.id, issue_id=parent_b.id)
        response = session_client.post(url, {"sub_issue_ids": [str(issue_a.id)]}, format="json")
        assert response.status_code == status.HTTP_200_OK, getattr(response, "data", None)
        issue_a.refresh_from_db()
        assert issue_a.parent_id == parent_b.id
        assert {str(row["id"]) for row in response.data["sub_issues"]} == {str(issue_a.id)}
        dispatched = {call.kwargs["issue_id"]: call.kwargs["project_id"] for call in mock_activity.call_args_list}
        assert dispatched[str(issue_a.id)] == str(project_a.id)

    @pytest.mark.django_db
    def test_bulk_add_cannot_make_parent_its_own_child(self, session_client, workspace, project_b, parent_b):
        url = SUB_ISSUES_URL.format(slug=workspace.slug, project_id=project_b.id, issue_id=parent_b.id)
        response = session_client.post(url, {"sub_issue_ids": [str(parent_b.id)]}, format="json")
        assert response.status_code == status.HTTP_200_OK
        parent_b.refresh_from_db()
        assert parent_b.parent_id is None

    @pytest.mark.django_db
    def test_other_member_without_child_project_access_sees_nothing(
        self, api_client, workspace, project_a, project_b, parent_b, issue_a, create_user
    ):
        """A different user who is in B but not A must not see A's child under parent B."""
        issue_a.parent = parent_b
        issue_a.save(created_by_id=create_user.id)
        viewer = User.objects.create(email="viewer@plane.so", username="viewer")
        viewer.set_password("x")
        viewer.save()
        WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15)
        ProjectMember.objects.create(project=project_b, member=viewer, workspace=workspace, role=15)
        api_client.force_authenticate(user=viewer)
        url = SUB_ISSUES_URL.format(slug=workspace.slug, project_id=project_b.id, issue_id=parent_b.id)
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        returned = {str(row["id"]) for row in response.data["sub_issues"]}
        assert str(issue_a.id) not in returned
