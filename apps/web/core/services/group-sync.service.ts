/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TProjectGroupRoleMapping, TWorkspaceGroupRoleMapping, TWorkspaceGroupSyncConfig } from "@plane/types";
import { APIService } from "@/services/api.service";

export class GroupSyncService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/group-sync/`;
  }

  async fetchConfig(workspaceSlug: string): Promise<TWorkspaceGroupSyncConfig> {
    return this.get(this.base(workspaceSlug))
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateConfig(
    workspaceSlug: string,
    data: Partial<TWorkspaceGroupSyncConfig>
  ): Promise<TWorkspaceGroupSyncConfig> {
    return this.patch(this.base(workspaceSlug), data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async runSync(workspaceSlug: string): Promise<void> {
    return this.post(`${this.base(workspaceSlug)}run/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchWorkspaceMappings(workspaceSlug: string): Promise<TWorkspaceGroupRoleMapping[]> {
    return this.get(`${this.base(workspaceSlug)}workspace-mappings/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkspaceMapping(
    workspaceSlug: string,
    data: Partial<TWorkspaceGroupRoleMapping>
  ): Promise<TWorkspaceGroupRoleMapping> {
    return this.post(`${this.base(workspaceSlug)}workspace-mappings/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkspaceMapping(
    workspaceSlug: string,
    mappingId: string,
    data: Partial<TWorkspaceGroupRoleMapping>
  ): Promise<TWorkspaceGroupRoleMapping> {
    return this.patch(`${this.base(workspaceSlug)}workspace-mappings/${mappingId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkspaceMapping(workspaceSlug: string, mappingId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}workspace-mappings/${mappingId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchProjectMappings(workspaceSlug: string): Promise<TProjectGroupRoleMapping[]> {
    return this.get(`${this.base(workspaceSlug)}project-mappings/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createProjectMapping(
    workspaceSlug: string,
    data: Partial<TProjectGroupRoleMapping>
  ): Promise<TProjectGroupRoleMapping> {
    return this.post(`${this.base(workspaceSlug)}project-mappings/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProjectMapping(
    workspaceSlug: string,
    mappingId: string,
    data: Partial<TProjectGroupRoleMapping>
  ): Promise<TProjectGroupRoleMapping> {
    return this.patch(`${this.base(workspaceSlug)}project-mappings/${mappingId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteProjectMapping(workspaceSlug: string, mappingId: string): Promise<void> {
    return this.delete(`${this.base(workspaceSlug)}project-mappings/${mappingId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
