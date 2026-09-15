# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for grouped pagination on the workspace-level issues endpoint.

``/workspaces/<slug>/issues/`` backs the workspace views ("All work items").
With ``group_by`` it must return grouped results across projects (used by the
workspace-level kanban), and without it the flat list is unchanged.
"""

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State

URL = "/api/workspaces/{slug}/issues/"


def _state(project, workspace, name, group, author):
    return State.objects.create(name=name, group=group, project=project, workspace=workspace, created_by=author)


def _issue(name, project, workspace, author, state=None, priority="none"):
    issue = Issue(name=name, project=project, workspace=workspace, state=state, priority=priority)
    issue.save(created_by_id=author.id)
    return issue


@pytest.fixture
def two_projects(db, workspace, create_user):
    projects = []
    for ident in ("PA", "PB"):
        project = Project.objects.create(
            name=f"Project {ident}", identifier=ident, workspace=workspace, created_by=create_user
        )
        ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
        projects.append(project)
    return projects


@pytest.fixture
def seeded(two_projects, workspace, create_user):
    a, b = two_projects
    started_a = _state(a, workspace, "In progress", "started", create_user)
    backlog_a = _state(a, workspace, "Backlog", "backlog", create_user)
    started_b = _state(b, workspace, "Doing", "started", create_user)
    return {
        "a_started": _issue("A started", a, workspace, create_user, state=started_a, priority="high"),
        "a_backlog": _issue("A backlog", a, workspace, create_user, state=backlog_a, priority="low"),
        "b_started": _issue("B started", b, workspace, create_user, state=started_b, priority="high"),
    }


@pytest.mark.contract
class TestWorkspaceViewIssuesGrouped:
    @pytest.mark.django_db
    def test_flat_list_unchanged_without_group_by(self, session_client, workspace, seeded):
        response = session_client.get(URL.format(slug=workspace.slug))
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data["results"], list)
        ids = {str(row["id"]) for row in response.data["results"]}
        assert {str(i.id) for i in seeded.values()} <= ids

    @pytest.mark.django_db
    def test_group_by_state_group_spans_projects(self, session_client, workspace, seeded):
        response = session_client.get(URL.format(slug=workspace.slug), {"group_by": "state__group"})
        assert response.status_code == status.HTTP_200_OK, getattr(response, "data", None)
        results = response.data["results"]
        assert isinstance(results, dict), results
        started = {str(row["id"]) for row in results["started"]["results"]}
        assert started == {str(seeded["a_started"].id), str(seeded["b_started"].id)}
        backlog = {str(row["id"]) for row in results["backlog"]["results"]}
        assert backlog == {str(seeded["a_backlog"].id)}

    @pytest.mark.django_db
    def test_group_by_priority(self, session_client, workspace, seeded):
        response = session_client.get(URL.format(slug=workspace.slug), {"group_by": "priority"})
        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert {str(row["id"]) for row in results["high"]["results"]} == {
            str(seeded["a_started"].id),
            str(seeded["b_started"].id),
        }

    @pytest.mark.django_db
    def test_sub_group_by(self, session_client, workspace, seeded):
        response = session_client.get(
            URL.format(slug=workspace.slug), {"group_by": "state__group", "sub_group_by": "priority"}
        )
        assert response.status_code == status.HTTP_200_OK, getattr(response, "data", None)
        results = response.data["results"]
        assert "started" in results
        assert "high" in results["started"]["results"]

    @pytest.mark.django_db
    def test_same_group_and_sub_group_rejected(self, session_client, workspace, seeded):
        response = session_client.get(
            URL.format(slug=workspace.slug), {"group_by": "priority", "sub_group_by": "priority"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_grouped_results_respect_project_membership(self, session_client, workspace, seeded, create_user):
        """Issues in a project the caller does not belong to never appear in any group."""
        hidden_project = Project.objects.create(
            name="Hidden", identifier="HID", workspace=workspace, created_by=create_user
        )
        hidden_state = _state(hidden_project, workspace, "Doing", "started", create_user)
        hidden = _issue("hidden", hidden_project, workspace, create_user, state=hidden_state)
        response = session_client.get(URL.format(slug=workspace.slug), {"group_by": "state__group"})
        assert response.status_code == status.HTTP_200_OK
        all_ids = {str(row["id"]) for group in response.data["results"].values() for row in group["results"]}
        assert str(hidden.id) not in all_ids
