# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Rate limiting that survives reverse proxies and CDNs.

DRF's default ``get_ident`` uses the *entire* ``X-Forwarded-For`` chain as the
client identity when ``NUM_PROXIES`` is unset, and ``REMOTE_ADDR`` (the
reverse proxy) when the header is missing. Behind Caddy, cloudflared or any
load balancer that collapses every user into one or two buckets, so a handful
of people loading the login page trip the limit for everyone.

``client_ident`` resolves the real client address instead:

1. ``CF-Connecting-IP`` — set by Cloudflare and not forgeable through it.
2. The first address in ``X-Forwarded-For`` — the original client as recorded
   by the first trusted proxy.
3. ``REMOTE_ADDR``.
"""

from rest_framework.throttling import AnonRateThrottle


def client_ident(request):
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ClientAnonRateThrottle(AnonRateThrottle):
    """Anonymous throttle keyed on the real client address (see ``client_ident``)."""

    def get_ident(self, request):
        return client_ident(request) or super().get_ident(request)
