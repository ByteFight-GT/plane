# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the proxy-aware anonymous throttle."""

import pytest
from django.test import RequestFactory

from plane.authentication.rate_limit import AuthenticationThrottle
from plane.utils.throttling import ClientAnonRateThrottle, client_ident


def _request(**meta):
    request = RequestFactory().get("/api/instances/")
    request.META.update(meta)
    return request


@pytest.mark.unit
class TestClientIdent:
    def test_prefers_cloudflare_header(self):
        request = _request(
            HTTP_CF_CONNECTING_IP="203.0.113.7",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 172.18.0.5",
            REMOTE_ADDR="172.18.0.9",
        )
        assert client_ident(request) == "203.0.113.7"

    def test_uses_first_forwarded_hop_without_cloudflare(self):
        request = _request(HTTP_X_FORWARDED_FOR=" 198.51.100.4 , 172.18.0.5", REMOTE_ADDR="172.18.0.9")
        assert client_ident(request) == "198.51.100.4"

    def test_falls_back_to_remote_addr(self):
        request = _request(REMOTE_ADDR="10.0.0.2")
        assert client_ident(request) == "10.0.0.2"

    def test_two_clients_behind_same_proxy_get_distinct_buckets(self):
        throttle = ClientAnonRateThrottle()
        a = _request(HTTP_X_FORWARDED_FOR="203.0.113.1, 172.18.0.5", REMOTE_ADDR="172.18.0.9")
        b = _request(HTTP_X_FORWARDED_FOR="203.0.113.2, 172.18.0.5", REMOTE_ADDR="172.18.0.9")
        assert throttle.get_ident(a) != throttle.get_ident(b)

    def test_authentication_throttle_uses_client_ident(self):
        throttle = AuthenticationThrottle()
        request = _request(HTTP_CF_CONNECTING_IP="203.0.113.7", REMOTE_ADDR="172.18.0.9")
        assert throttle.get_ident(request) == "203.0.113.7"
