# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import (
    Project,
    ProjectGroupRoleMapping,
    WorkspaceGroupRoleMapping,
    WorkspaceGroupSyncConfig,
)

from .base import BaseSerializer

ROLE_VALUES = (20, 15, 5)


class WorkspaceGroupSyncConfigSerializer(BaseSerializer):
    class Meta:
        model = WorkspaceGroupSyncConfig
        fields = [
            "id",
            "workspace",
            "sync_on_login",
            "offline_sync",
            "auto_remove",
            "group_attribute_key",
            "default_workspace_role",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "last_synced_at", "created_at", "updated_at"]

    def validate_group_attribute_key(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Group attribute key is required.")
        return value

    def validate_default_workspace_role(self, value):
        if value is not None and value not in ROLE_VALUES:
            raise serializers.ValidationError("Invalid role.")
        return value


class WorkspaceGroupRoleMappingSerializer(BaseSerializer):
    class Meta:
        model = WorkspaceGroupRoleMapping
        fields = ["id", "workspace", "group_name", "role", "created_at", "updated_at"]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]

    def validate_group_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Group name is required.")
        return value

    def validate_role(self, value):
        if value not in ROLE_VALUES:
            raise serializers.ValidationError("Invalid role.")
        return value


class ProjectGroupRoleMappingSerializer(BaseSerializer):
    project_identifier = serializers.CharField(source="project.identifier", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectGroupRoleMapping
        fields = [
            "id",
            "workspace",
            "project",
            "project_identifier",
            "project_name",
            "group_name",
            "role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]

    def validate_group_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Group name is required.")
        return value

    def validate_role(self, value):
        if value not in ROLE_VALUES:
            raise serializers.ValidationError("Invalid role.")
        return value

    def validate_project(self, value):
        workspace_id = self.context.get("workspace_id")
        if (
            value is not None
            and workspace_id
            and not Project.objects.filter(pk=value.pk, workspace_id=workspace_id).exists()
        ):
            raise serializers.ValidationError("Project does not belong to this workspace.")
        return value
