/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { ROLE } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { Switch } from "@makeplane/propel/components/switch";
import type { TGroupSyncRole, TWorkspaceGroupSyncConfig } from "@plane/types";
import { CustomSelect } from "@plane/ui";
import { renderFormattedDate, renderFormattedTime } from "@plane/utils";
// hooks
import { useGroupSync } from "@/hooks/store/use-group-sync";

type Props = {
  workspaceSlug: string;
};

type TToggleKey = "sync_on_login" | "offline_sync" | "auto_remove";

const TOGGLES: TToggleKey[] = ["sync_on_login", "offline_sync", "auto_remove"];

export const GroupSyncSettingsForm = observer(function GroupSyncSettingsForm(props: Props) {
  const { workspaceSlug } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getConfig, updateConfig, runSync } = useGroupSync();
  // derived values
  const config = getConfig(workspaceSlug);
  // states
  const [attributeKey, setAttributeKey] = useState(config?.group_attribute_key ?? "groups");
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    setAttributeKey(config?.group_attribute_key ?? "groups");
  }, [config?.group_attribute_key]);

  if (!config) return null;

  const save = async (data: Partial<TWorkspaceGroupSyncConfig>) => {
    try {
      await updateConfig(workspaceSlug, data);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("workspace_settings.settings.group_sync.toasts.saved"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("workspace_settings.settings.group_sync.toasts.save_failed"),
      });
    }
  };

  const handleAttributeKeyBlur = () => {
    const value = attributeKey.trim();
    if (!value || value === config.group_attribute_key) {
      setAttributeKey(config.group_attribute_key);
      return;
    }
    void save({ group_attribute_key: value });
  };

  const handleSyncNow = async () => {
    setIsSyncing(true);
    try {
      await runSync(workspaceSlug);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("workspace_settings.settings.group_sync.settings.sync_queued"),
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("workspace_settings.settings.group_sync.toasts.save_failed"),
      });
    } finally {
      setIsSyncing(false);
    }
  };

  const defaultRoleLabel = config.default_workspace_role
    ? ROLE[config.default_workspace_role]
    : t("workspace_settings.settings.group_sync.settings.default_workspace_role.none");

  return (
    <section className="flex flex-col gap-6">
      <h4 className="text-body-sm-medium text-primary">{t("workspace_settings.settings.group_sync.settings.title")}</h4>

      <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle">
        {TOGGLES.map((key) => (
          <div key={key} className="flex items-center justify-between gap-6 px-4 py-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-body-sm-medium text-primary">
                {t(`workspace_settings.settings.group_sync.settings.${key}.label`)}
              </span>
              <span className="text-body-xs-regular text-tertiary">
                {t(`workspace_settings.settings.group_sync.settings.${key}.description`)}
              </span>
            </div>
            <Switch checked={config[key]} onCheckedChange={(value) => void save({ [key]: value })} size="sm" />
          </div>
        ))}

        <div className="flex items-center justify-between gap-6 px-4 py-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-body-sm-medium text-primary">
              {t("workspace_settings.settings.group_sync.settings.group_attribute_key.label")}
            </span>
            <span className="text-body-xs-regular text-tertiary">
              {t("workspace_settings.settings.group_sync.settings.group_attribute_key.description")}
            </span>
          </div>
          <div className="w-56 shrink-0">
            <InputGroup size="lg">
              <Input
                value={attributeKey}
                onChange={(e) => setAttributeKey(e.target.value)}
                onBlur={handleAttributeKeyBlur}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                placeholder={t("workspace_settings.settings.group_sync.settings.group_attribute_key.placeholder")}
                size="lg"
              />
            </InputGroup>
          </div>
        </div>

        <div className="flex items-center justify-between gap-6 px-4 py-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-body-sm-medium text-primary">
              {t("workspace_settings.settings.group_sync.settings.default_workspace_role.label")}
            </span>
            <span className="text-body-xs-regular text-tertiary">
              {t("workspace_settings.settings.group_sync.settings.default_workspace_role.description")}
            </span>
          </div>
          <div className="w-56 shrink-0">
            <CustomSelect
              value={config.default_workspace_role ?? "none"}
              onChange={(value: string) =>
                void save({ default_workspace_role: value === "none" ? null : (Number(value) as TGroupSyncRole) })
              }
              label={<span>{defaultRoleLabel}</span>}
              buttonClassName="w-full justify-between"
              className="w-full"
              input
            >
              <CustomSelect.Option value="none">
                {t("workspace_settings.settings.group_sync.settings.default_workspace_role.none")}
              </CustomSelect.Option>
              {Object.entries(ROLE).map(([key, label]) => (
                <CustomSelect.Option key={key} value={key}>
                  {label}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4">
        <span className="text-body-xs-regular text-tertiary">
          {config.last_synced_at
            ? `${t("workspace_settings.settings.group_sync.settings.last_synced")}: ${renderFormattedDate(config.last_synced_at)} ${renderFormattedTime(config.last_synced_at)}`
            : t("workspace_settings.settings.group_sync.settings.never_synced")}
        </span>
        <Button variant="secondary" size="base" onClick={() => void handleSyncNow()} loading={isSyncing}>
          {t("workspace_settings.settings.group_sync.settings.sync_now")}
        </Button>
      </div>
    </section>
  );
});
