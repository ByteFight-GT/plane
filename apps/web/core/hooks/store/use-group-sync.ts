/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
// context
import { StoreContext } from "@/lib/store-context";
// types
import type { IGroupSyncStore } from "@/store/workspace/group-sync.store";

export const useGroupSync = (): IGroupSyncStore => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useGroupSync must be used within StoreProvider");
  return context.workspaceRoot.groupSync;
};
