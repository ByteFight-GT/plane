/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import type { TProjectGroupRoleMapping, TWorkspaceGroupRoleMapping, TWorkspaceGroupSyncConfig } from "@plane/types";
// services
import { GroupSyncService } from "@/services/group-sync.service";
// store
import type { CoreRootStore } from "../root.store";

export interface IGroupSyncStore {
  // observables
  configs: Record<string, TWorkspaceGroupSyncConfig>;
  workspaceMappings: Record<string, TWorkspaceGroupRoleMapping[]>;
  projectMappings: Record<string, TProjectGroupRoleMapping[]>;
  // computed actions
  getConfig: (workspaceSlug: string) => TWorkspaceGroupSyncConfig | undefined;
  getWorkspaceMappings: (workspaceSlug: string) => TWorkspaceGroupRoleMapping[] | undefined;
  getProjectMappings: (workspaceSlug: string) => TProjectGroupRoleMapping[] | undefined;
  // actions
  fetchAll: (workspaceSlug: string) => Promise<void>;
  updateConfig: (workspaceSlug: string, data: Partial<TWorkspaceGroupSyncConfig>) => Promise<TWorkspaceGroupSyncConfig>;
  runSync: (workspaceSlug: string) => Promise<void>;
  createWorkspaceMapping: (
    workspaceSlug: string,
    data: Partial<TWorkspaceGroupRoleMapping>
  ) => Promise<TWorkspaceGroupRoleMapping>;
  updateWorkspaceMapping: (
    workspaceSlug: string,
    mappingId: string,
    data: Partial<TWorkspaceGroupRoleMapping>
  ) => Promise<TWorkspaceGroupRoleMapping>;
  deleteWorkspaceMapping: (workspaceSlug: string, mappingId: string) => Promise<void>;
  createProjectMapping: (
    workspaceSlug: string,
    data: Partial<TProjectGroupRoleMapping>
  ) => Promise<TProjectGroupRoleMapping>;
  updateProjectMapping: (
    workspaceSlug: string,
    mappingId: string,
    data: Partial<TProjectGroupRoleMapping>
  ) => Promise<TProjectGroupRoleMapping>;
  deleteProjectMapping: (workspaceSlug: string, mappingId: string) => Promise<void>;
}

export class GroupSyncStore implements IGroupSyncStore {
  // observables
  configs: Record<string, TWorkspaceGroupSyncConfig> = {};
  workspaceMappings: Record<string, TWorkspaceGroupRoleMapping[]> = {};
  projectMappings: Record<string, TProjectGroupRoleMapping[]> = {};
  // services
  groupSyncService;
  // root store
  rootStore;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      configs: observable,
      workspaceMappings: observable,
      projectMappings: observable,
      fetchAll: action,
      updateConfig: action,
      runSync: action,
      createWorkspaceMapping: action,
      updateWorkspaceMapping: action,
      deleteWorkspaceMapping: action,
      createProjectMapping: action,
      updateProjectMapping: action,
      deleteProjectMapping: action,
    });
    this.groupSyncService = new GroupSyncService();
    this.rootStore = _rootStore;
  }

  getConfig = computedFn((workspaceSlug: string) => this.configs[workspaceSlug]);

  getWorkspaceMappings = computedFn((workspaceSlug: string) => this.workspaceMappings[workspaceSlug]);

  getProjectMappings = computedFn((workspaceSlug: string) => this.projectMappings[workspaceSlug]);

  fetchAll = async (workspaceSlug: string) => {
    const [config, workspaceMappings, projectMappings] = await Promise.all([
      this.groupSyncService.fetchConfig(workspaceSlug),
      this.groupSyncService.fetchWorkspaceMappings(workspaceSlug),
      this.groupSyncService.fetchProjectMappings(workspaceSlug),
    ]);
    runInAction(() => {
      this.configs[workspaceSlug] = config;
      this.workspaceMappings[workspaceSlug] = workspaceMappings;
      this.projectMappings[workspaceSlug] = projectMappings;
    });
  };

  updateConfig = async (workspaceSlug: string, data: Partial<TWorkspaceGroupSyncConfig>) => {
    const config = await this.groupSyncService.updateConfig(workspaceSlug, data);
    runInAction(() => {
      this.configs[workspaceSlug] = config;
    });
    return config;
  };

  runSync = async (workspaceSlug: string) => {
    await this.groupSyncService.runSync(workspaceSlug);
  };

  createWorkspaceMapping = async (workspaceSlug: string, data: Partial<TWorkspaceGroupRoleMapping>) => {
    const mapping = await this.groupSyncService.createWorkspaceMapping(workspaceSlug, data);
    runInAction(() => {
      this.workspaceMappings[workspaceSlug] = [...(this.workspaceMappings[workspaceSlug] ?? []), mapping];
    });
    return mapping;
  };

  updateWorkspaceMapping = async (
    workspaceSlug: string,
    mappingId: string,
    data: Partial<TWorkspaceGroupRoleMapping>
  ) => {
    const mapping = await this.groupSyncService.updateWorkspaceMapping(workspaceSlug, mappingId, data);
    runInAction(() => {
      this.workspaceMappings[workspaceSlug] = (this.workspaceMappings[workspaceSlug] ?? []).map((m) =>
        m.id === mappingId ? mapping : m
      );
    });
    return mapping;
  };

  deleteWorkspaceMapping = async (workspaceSlug: string, mappingId: string) => {
    await this.groupSyncService.deleteWorkspaceMapping(workspaceSlug, mappingId);
    runInAction(() => {
      this.workspaceMappings[workspaceSlug] = (this.workspaceMappings[workspaceSlug] ?? []).filter(
        (m) => m.id !== mappingId
      );
    });
  };

  createProjectMapping = async (workspaceSlug: string, data: Partial<TProjectGroupRoleMapping>) => {
    const mapping = await this.groupSyncService.createProjectMapping(workspaceSlug, data);
    runInAction(() => {
      this.projectMappings[workspaceSlug] = [...(this.projectMappings[workspaceSlug] ?? []), mapping];
    });
    return mapping;
  };

  updateProjectMapping = async (workspaceSlug: string, mappingId: string, data: Partial<TProjectGroupRoleMapping>) => {
    const mapping = await this.groupSyncService.updateProjectMapping(workspaceSlug, mappingId, data);
    runInAction(() => {
      this.projectMappings[workspaceSlug] = (this.projectMappings[workspaceSlug] ?? []).map((m) =>
        m.id === mappingId ? mapping : m
      );
    });
    return mapping;
  };

  deleteProjectMapping = async (workspaceSlug: string, mappingId: string) => {
    await this.groupSyncService.deleteProjectMapping(workspaceSlug, mappingId);
    runInAction(() => {
      this.projectMappings[workspaceSlug] = (this.projectMappings[workspaceSlug] ?? []).filter(
        (m) => m.id !== mappingId
      );
    });
  };
}
