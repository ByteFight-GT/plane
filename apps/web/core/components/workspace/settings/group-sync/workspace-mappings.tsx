/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Trash2 } from "lucide-react";
// plane imports
import { ROLE } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import type { TGroupSyncRole } from "@plane/types";
import { EUserWorkspaceRoles } from "@plane/types";
import { CustomSelect } from "@plane/ui";
// hooks
import { useGroupSync } from "@/hooks/store/use-group-sync";

type Props = {
  workspaceSlug: string;
};

export const GroupSyncWorkspaceMappings = observer(function GroupSyncWorkspaceMappings(props: Props) {
  const { workspaceSlug } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getWorkspaceMappings, createWorkspaceMapping, updateWorkspaceMapping, deleteWorkspaceMapping } =
    useGroupSync();
  // derived values
  const mappings = getWorkspaceMappings(workspaceSlug) ?? [];
  // states
  const [groupName, setGroupName] = useState("");
  const [role, setRole] = useState<TGroupSyncRole>(EUserWorkspaceRoles.MEMBER);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAdd = async () => {
    const name = groupName.trim();
    if (!name) return;
    setIsSubmitting(true);
    try {
      await createWorkspaceMapping(workspaceSlug, { group_name: name, role });
      setGroupName("");
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.group_sync.toasts.mapping_added") });
    } catch (error) {
      const message = (error as { error?: string })?.error;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("workspace_settings.settings.group_sync.toasts.mapping_failed"),
        message,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRoleChange = async (mappingId: string, value: TGroupSyncRole) => {
    try {
      await updateWorkspaceMapping(workspaceSlug, mappingId, { role: value });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.group_sync.toasts.mapping_failed") });
    }
  };

  const handleDelete = async (mappingId: string) => {
    try {
      await deleteWorkspaceMapping(workspaceSlug, mappingId);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.group_sync.toasts.mapping_removed") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.group_sync.toasts.mapping_failed") });
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <h4 className="text-body-sm-medium text-primary">
          {t("workspace_settings.settings.group_sync.workspace_mappings.title")}
        </h4>
        <p className="text-body-xs-regular text-tertiary">
          {t("workspace_settings.settings.group_sync.workspace_mappings.description")}
        </p>
      </div>

      <div className="flex items-end gap-3">
        <div className="flex grow flex-col gap-1">
          <label className="text-body-xs-medium text-secondary">
            {t("workspace_settings.settings.group_sync.fields.group")}
          </label>
          <InputGroup size="lg">
            <Input
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleAdd();
              }}
              placeholder={t("workspace_settings.settings.group_sync.fields.group_placeholder")}
              size="lg"
            />
          </InputGroup>
        </div>
        <div className="flex w-40 flex-col gap-1">
          <label className="text-body-xs-medium text-secondary">
            {t("workspace_settings.settings.group_sync.fields.role")}
          </label>
          <CustomSelect
            value={role}
            onChange={(value: string) => setRole(Number(value) as TGroupSyncRole)}
            label={<span>{ROLE[role]}</span>}
            buttonClassName="w-full justify-between"
            className="w-full"
            input
          >
            {Object.entries(ROLE).map(([key, label]) => (
              <CustomSelect.Option key={key} value={key}>
                {label}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
        </div>
        <Button
          variant="primary"
          size="base"
          onClick={() => void handleAdd()}
          disabled={!groupName.trim()}
          loading={isSubmitting}
        >
          {t("workspace_settings.settings.group_sync.actions.add")}
        </Button>
      </div>

      {mappings.length === 0 ? (
        <p className="rounded-lg border border-dashed border-subtle px-4 py-6 text-center text-body-xs-regular text-tertiary">
          {t("workspace_settings.settings.group_sync.workspace_mappings.empty")}
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle">
          {mappings.map((mapping) => (
            <div key={mapping.id} className="flex items-center gap-3 px-4 py-2">
              <span className="font-mono grow truncate text-body-sm-regular text-primary">{mapping.group_name}</span>
              <div className="w-40">
                <CustomSelect
                  value={mapping.role}
                  onChange={(value: string) => void handleRoleChange(mapping.id, Number(value) as TGroupSyncRole)}
                  label={<span>{ROLE[mapping.role]}</span>}
                  buttonClassName="w-full justify-between"
                  className="w-full"
                  input
                >
                  {Object.entries(ROLE).map(([key, label]) => (
                    <CustomSelect.Option key={key} value={key}>
                      {label}
                    </CustomSelect.Option>
                  ))}
                </CustomSelect>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(mapping.id)}
                className="grid size-7 place-items-center rounded text-tertiary hover:bg-layer-2 hover:text-danger-primary"
                aria-label={t("workspace_settings.settings.group_sync.actions.remove")}
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
});
