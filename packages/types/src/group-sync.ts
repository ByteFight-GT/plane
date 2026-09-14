/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { EUserWorkspaceRoles } from "./workspace";

export type TGroupSyncRole = EUserWorkspaceRoles;

export type TWorkspaceGroupSyncConfig = {
  id: string;
  workspace: string;
  sync_on_login: boolean;
  offline_sync: boolean;
  auto_remove: boolean;
  group_attribute_key: string;
  default_workspace_role: TGroupSyncRole | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TWorkspaceGroupRoleMapping = {
  id: string;
  workspace: string;
  group_name: string;
  role: TGroupSyncRole;
  created_at: string;
  updated_at: string;
};

export type TProjectGroupRoleMapping = {
  id: string;
  workspace: string;
  /** null means the mapping applies to every project in the workspace */
  project: string | null;
  project_identifier?: string | null;
  project_name?: string | null;
  group_name: string;
  role: TGroupSyncRole;
  created_at: string;
  updated_at: string;
};
