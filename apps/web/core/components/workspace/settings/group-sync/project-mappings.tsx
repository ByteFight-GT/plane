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
import { useProject } from "@/hooks/store/use-project";

type Props = {
  workspaceSlug: string;
};

const ALL_PROJECTS = "all";

export const GroupSyncProjectMappings = observer(function GroupSyncProjectMappings(props: Props) {
  const { workspaceSlug } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getProjectMappings, createProjectMapping, updateProjectMapping, deleteProjectMapping } = useGroupSync();
  const { workspaceProjectIds, getProjectById } = useProject();
  // derived values
  const mappings = getProjectMappings(workspaceSlug) ?? [];
  const projectIds = workspaceProjectIds ?? [];
  // states
  const [groupName, setGroupName] = useState("");
  const [projectId, setProjectId] = useState<string>(ALL_PROJECTS);
  const [role, setRole] = useState<TGroupSyncRole>(EUserWorkspaceRoles.MEMBER);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const projectLabel = (id: string | null | undefined, fallback?: string | null) => {
    if (!id) return t("workspace_settings.settings.group_sync.project_mappings.all_projects");
    const project = getProjectById(id);
    return project ? `${project.identifier} · ${project.name}` : (fallback ?? id);
  };

  const handleAdd = async () => {
    const name = groupName.trim();
    if (!name) return;
    setIsSubmitting(true);
    try {
      await createProjectMapping(workspaceSlug, {
        group_name: name,
        role,
        project: projectId === ALL_PROJECTS ? null : projectId,
      });
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
      await updateProjectMapping(workspaceSlug, mappingId, { role: value });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.group_sync.toasts.mapping_failed") });
    }
  };

  const handleDelete = async (mappingId: string) => {
    try {
      await deleteProjectMapping(workspaceSlug, mappingId);
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("workspace_settings.settings.group_sync.toasts.mapping_removed") });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("workspace_settings.settings.group_sync.toasts.mapping_failed") });
    }
  };

  const roleOptions = Object.entries(ROLE).map(([key, label]) => (
    <CustomSelect.Option key={key} value={key}>
      {label}
    </CustomSelect.Option>
  ));

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <h4 className="text-body-sm-medium text-primary">
          {t("workspace_settings.settings.group_sync.project_mappings.title")}
        </h4>
        <p className="text-body-xs-regular text-tertiary">
          {t("workspace_settings.settings.group_sync.project_mappings.description")}
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
        <div className="flex w-56 flex-col gap-1">
          <label className="text-body-xs-medium text-secondary">
            {t("workspace_settings.settings.group_sync.fields.project")}
          </label>
          <CustomSelect
            value={projectId}
            onChange={(value: string) => setProjectId(value)}
            label={<span className="truncate">{projectLabel(projectId === ALL_PROJECTS ? null : projectId)}</span>}
            buttonClassName="w-full justify-between"
            className="w-full"
            input
          >
            <CustomSelect.Option value={ALL_PROJECTS}>
              {t("workspace_settings.settings.group_sync.project_mappings.all_projects")}
            </CustomSelect.Option>
            {projectIds.map((id) => (
              <CustomSelect.Option key={id} value={id}>
                {projectLabel(id)}
              </CustomSelect.Option>
            ))}
          </CustomSelect>
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
            {roleOptions}
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
          {t("workspace_settings.settings.group_sync.project_mappings.empty")}
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle">
          {mappings.map((mapping) => (
            <div key={mapping.id} className="flex items-center gap-3 px-4 py-2">
              <span className="font-mono w-1/3 truncate text-body-sm-regular text-primary">{mapping.group_name}</span>
              <span className="grow truncate text-body-sm-regular text-secondary">
                {projectLabel(mapping.project, mapping.project_identifier)}
              </span>
              <div className="w-40">
                <CustomSelect
                  value={mapping.role}
                  onChange={(value: string) => void handleRoleChange(mapping.id, Number(value) as TGroupSyncRole)}
                  label={<span>{ROLE[mapping.role]}</span>}
                  buttonClassName="w-full justify-between"
                  className="w-full"
                  input
                >
                  {roleOptions}
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
