# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    ProjectGroupRoleMappingEndpoint,
    WorkspaceGroupRoleMappingEndpoint,
    WorkspaceGroupSyncConfigEndpoint,
    WorkspaceGroupSyncRunEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/group-sync/",
        WorkspaceGroupSyncConfigEndpoint.as_view(),
        name="workspace-group-sync",
    ),
    path(
        "workspaces/<str:slug>/group-sync/run/",
        WorkspaceGroupSyncRunEndpoint.as_view(),
        name="workspace-group-sync-run",
    ),
    path(
        "workspaces/<str:slug>/group-sync/workspace-mappings/",
        WorkspaceGroupRoleMappingEndpoint.as_view(),
        name="workspace-group-role-mappings",
    ),
    path(
        "workspaces/<str:slug>/group-sync/workspace-mappings/<uuid:pk>/",
        WorkspaceGroupRoleMappingEndpoint.as_view(),
        name="workspace-group-role-mappings",
    ),
    path(
        "workspaces/<str:slug>/group-sync/project-mappings/",
        ProjectGroupRoleMappingEndpoint.as_view(),
        name="project-group-role-mappings",
    ),
    path(
        "workspaces/<str:slug>/group-sync/project-mappings/<uuid:pk>/",
        ProjectGroupRoleMappingEndpoint.as_view(),
        name="project-group-role-mappings",
    ),
]
