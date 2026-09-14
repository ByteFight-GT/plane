/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { WebhookSettingsLoader } from "@/components/ui/loader/settings/web-hook";
import {
  GroupSyncProjectMappings,
  GroupSyncSettingsForm,
  GroupSyncWorkspaceMappings,
} from "@/components/workspace/settings/group-sync";
// hooks
import { useGroupSync } from "@/hooks/store/use-group-sync";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";
import { GroupSyncWorkspaceSettingsHeader } from "./header";

function GroupSyncSettingsPage({ params }: Route.ComponentProps) {
  // router
  const { workspaceSlug } = params;
  // plane hooks
  const { t } = useTranslation();
  // mobx store
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { fetchAll, getConfig } = useGroupSync();
  const { currentWorkspace } = useWorkspace();
  // derived values
  const canPerformWorkspaceAdminActions = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const config = getConfig(workspaceSlug);

  useSWR(
    canPerformWorkspaceAdminActions ? `GROUP_SYNC_${workspaceSlug}` : null,
    canPerformWorkspaceAdminActions ? () => fetchAll(workspaceSlug) : null
  );

  const pageTitle = currentWorkspace?.name
    ? `${currentWorkspace.name} - ${t("workspace_settings.settings.group_sync.title")}`
    : undefined;

  if (workspaceUserInfo && !canPerformWorkspaceAdminActions) {
    return <NotAuthorizedView section="settings" className="h-auto" />;
  }

  if (!config) return <WebhookSettingsLoader />;

  return (
    <SettingsContentWrapper header={<GroupSyncWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />
      <div className="flex w-full flex-col gap-10">
        <SettingsHeading
          title={t("workspace_settings.settings.group_sync.title")}
          description={t("workspace_settings.settings.group_sync.description")}
        />
        <GroupSyncSettingsForm workspaceSlug={workspaceSlug} />
        <GroupSyncWorkspaceMappings workspaceSlug={workspaceSlug} />
        <GroupSyncProjectMappings workspaceSlug={workspaceSlug} />
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(GroupSyncSettingsPage);
