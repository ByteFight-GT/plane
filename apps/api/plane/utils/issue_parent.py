# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validation for assigning a parent work item, including cross-project parents."""

from plane.db.models import Issue


def is_valid_parent(parent, project_id, user=None):
    """
    Return True if ``parent`` may become the parent of a work item in ``project_id``.

    * Same project: always allowed (the caller already has access to it).
    * Another project in the same workspace: allowed only when ``user`` is an
      active member of the parent's project, so nobody can attach their work
      item under (and thereby read the title of) an issue they cannot see.
      When no user is available the check falls back to same-project only.
    """
    if parent is None:
        return True
    if str(parent.project_id) == str(project_id):
        return True
    if user is None:
        return False
    return Issue.objects.filter(
        pk=parent.id,
        workspace__workspace_project__id=project_id,
        project__archived_at__isnull=True,
        project__project_projectmember__member=user,
        project__project_projectmember__is_active=True,
    ).exists()
