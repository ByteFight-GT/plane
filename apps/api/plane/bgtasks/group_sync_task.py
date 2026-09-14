# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Periodic (offline) identity-provider group sync.

For every workspace with ``offline_sync`` enabled, re-read the group claims of
each member who signed in through OIDC using their stored refresh token, and
reconcile their access. Users whose refresh token has expired are skipped
until they sign in again.
"""

import logging

from celery import shared_task
from django.utils import timezone

from plane.utils.exception_logger import log_exception

logger = logging.getLogger("plane.authentication")


class _OfflineRequest:
    """Minimal stand-in for an HttpRequest; the provider only needs a host to build a redirect URI."""

    META = {}

    def is_secure(self):
        return True

    def get_host(self):
        return "offline-sync"


def _sync_workspace(config):
    from plane.authentication.adapter.error import AuthenticationException
    from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider
    from plane.db.models import Account, WorkspaceMember
    from plane.utils.group_sync import sync_workspace_user

    try:
        provider = OIDCOAuthProvider(request=_OfflineRequest())
    except AuthenticationException:
        logger.warning("Offline group sync skipped: OIDC is not configured")
        return 0

    member_ids = WorkspaceMember.objects.filter(workspace_id=config.workspace_id, is_active=True).values_list(
        "member_id", flat=True
    )
    accounts = Account.objects.filter(provider="oidc", user_id__in=member_ids).select_related("user")

    synced = 0
    for account in accounts:
        try:
            claims = provider.refresh_claims(account)
            if claims is None:
                continue
            sync_workspace_user(config, account.user, claims)
            synced += 1
        except Exception as e:
            log_exception(e)
    return synced


@shared_task
def offline_group_sync(workspace_id=None):
    """Run the offline sync for every opted-in workspace (or a single one when ``workspace_id`` is given)."""
    from plane.db.models import WorkspaceGroupSyncConfig

    configs = WorkspaceGroupSyncConfig.objects.select_related("workspace")
    if workspace_id:
        configs = configs.filter(workspace_id=workspace_id)
    else:
        configs = configs.filter(offline_sync=True)

    for config in configs:
        try:
            count = _sync_workspace(config)
            config.last_synced_at = timezone.now()
            config.save(update_fields=["last_synced_at", "updated_at"])
            logger.info("Offline group sync: workspace %s, %s users", config.workspace.slug, count)
        except Exception as e:
            log_exception(e)
