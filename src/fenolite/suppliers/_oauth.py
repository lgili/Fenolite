# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Per-lookup client-credentials tokens; public protocol facts, no persistent token cache."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode

from fenolite.suppliers.base import text_at
from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.errors import ResponseShapeError
from fenolite.suppliers.http import Client, Request


def bearer(client: Client, keys: Mapping[str, Secret], url: str, *, scope: str | None = None) -> Secret:
    """Obtain one token through the same bounded client/deadline as the subsequent search."""
    form = {
        "client_id": keys["CLIENT_ID"].reveal(),
        "client_secret": keys["CLIENT_SECRET"].reveal(),
        "grant_type": "client_credentials",
    }
    if scope is not None:
        form["scope"] = scope
    data = client.request_json(
        Request(
            url,
            "POST",
            {"Content-Type": "application/x-www-form-urlencoded"},
            urlencode(form).encode("ascii"),
        )
    )
    token = text_at(data, "access_token", client.policy.name)
    kind = text_at(data, "token_type", client.policy.name)
    if (
        not token
        or len(token) > 8192
        or any(not 33 <= ord(char) <= 126 for char in token)
        or kind.casefold() != "bearer"
    ):
        raise ResponseShapeError(f"{client.policy.name}: response has no usable Bearer token")
    secret = Secret(token)
    client.secrets.append(secret)
    return secret
