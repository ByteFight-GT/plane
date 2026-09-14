# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace-admin endpoints for identity-provider group sync settings and mappings."""

from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    ProjectGroupRoleMappingSerializer,
    WorkspaceGroupRoleMappingSerializer,
    WorkspaceGroupSyncConfigSerializer,
)
from plane.db.models import (
    ProjectGroupRoleMapping,
    Workspace,
    WorkspaceGroupRoleMapping,
    WorkspaceGroupSyncConfig,
)

from ..base import BaseAPIView


class WorkspaceGroupSyncConfigEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        config, _ = WorkspaceGroupSyncConfig.objects.get_or_create(workspace=workspace)
        return Response(WorkspaceGroupSyncConfigSerializer(config).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        config, _ = WorkspaceGroupSyncConfig.objects.get_or_create(workspace=workspace)
        serializer = WorkspaceGroupSyncConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkspaceGroupSyncRunEndpoint(BaseAPIView):
    """Queue an offline sync for this workspace right now."""

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        from plane.bgtasks.group_sync_task import offline_group_sync

        workspace = Workspace.objects.get(slug=slug)
        WorkspaceGroupSyncConfig.objects.get_or_create(workspace=workspace)
        offline_group_sync.delay(workspace_id=str(workspace.id))
        return Response({"message": "Sync queued"}, status=status.HTTP_202_ACCEPTED)


class WorkspaceGroupRoleMappingEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, pk=None):
        if pk is None:
            mappings = WorkspaceGroupRoleMapping.objects.filter(workspace__slug=slug)
            return Response(WorkspaceGroupRoleMappingSerializer(mappings, many=True).data, status=status.HTTP_200_OK)
        mapping = WorkspaceGroupRoleMapping.objects.get(workspace__slug=slug, pk=pk)
        return Response(WorkspaceGroupRoleMappingSerializer(mapping).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = WorkspaceGroupRoleMappingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save(workspace_id=workspace.id)
        except IntegrityError:
            return Response(
                {"error": "A mapping for this group already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug, pk):
        mapping = WorkspaceGroupRoleMapping.objects.get(workspace__slug=slug, pk=pk)
        serializer = WorkspaceGroupRoleMappingSerializer(mapping, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": "A mapping for this group already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, pk):
        mapping = WorkspaceGroupRoleMapping.objects.get(workspace__slug=slug, pk=pk)
        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectGroupRoleMappingEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, pk=None):
        if pk is None:
            mappings = ProjectGroupRoleMapping.objects.filter(workspace__slug=slug).select_related("project")
            return Response(ProjectGroupRoleMappingSerializer(mappings, many=True).data, status=status.HTTP_200_OK)
        mapping = ProjectGroupRoleMapping.objects.select_related("project").get(workspace__slug=slug, pk=pk)
        return Response(ProjectGroupRoleMappingSerializer(mapping).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = ProjectGroupRoleMappingSerializer(data=request.data, context={"workspace_id": workspace.id})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save(workspace_id=workspace.id)
        except IntegrityError:
            return Response(
                {"error": "A mapping for this group and project already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug, pk):
        mapping = ProjectGroupRoleMapping.objects.get(workspace__slug=slug, pk=pk)
        serializer = ProjectGroupRoleMappingSerializer(
            mapping, data=request.data, partial=True, context={"workspace_id": mapping.workspace_id}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": "A mapping for this group and project already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, pk):
        mapping = ProjectGroupRoleMapping.objects.get(workspace__slug=slug, pk=pk)
        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
