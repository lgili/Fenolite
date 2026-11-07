# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Per-user credentials from environment or the optional keyring; never project files (c0267)."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, cast
from urllib.parse import quote, quote_plus

from fenolite.pick.supplier_policy import POLICIES
from fenolite.suppliers.errors import CredentialsMissing


class _Keyring(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class Secret:
    _value: str = field(repr=False)

    def __repr__(self) -> str:
        return "***"

    def __str__(self) -> str:
        return "***"

    def reveal(self) -> str:
        return self._value


def hint(source: str) -> str:
    names = POLICIES[source]["credentials"]
    variables = ", ".join(f"FENOLITE_{source.upper()}_{name}" for name in names)
    return f"set your own {variables}, or keyring service fenolite.suppliers.{source}; never project files"


def lookup(source: str) -> dict[str, Secret]:
    found: dict[str, Secret] = {}
    for name in POLICIES[source]["credentials"]:
        value = os.environ.get(f"FENOLITE_{source.upper()}_{name}")
        if not value:
            try:
                import keyring  # pyright: ignore[reportMissingImports]  # optional suppliers extra

                value = cast(_Keyring, keyring).get_password(f"fenolite.suppliers.{source}", name)
            except Exception:  # noqa: BLE001 - keyring backend errors may contain sensitive material
                value = None
        if not value:
            raise CredentialsMissing(f"{source}: credentials are missing", hint=hint(source))
        found[name] = Secret(value)
    return found


def redact(text: str, secrets: Iterable[Secret]) -> str:
    for secret in secrets:
        value = secret.reveal()
        if value:
            for encoded in (
                json.dumps(value)[1:-1],
                value,
                value.replace('"', '\\"'),
            ):
                text = text.replace(encoded, "***")
            for encoded in (quote(value, safe=""), quote_plus(value)):
                text = re.sub(_url_pattern(encoded), "***", text)
    return text


def _url_pattern(encoded: str) -> str:
    """Only percent-escape hex digits are case-insensitive; credential characters stay exact."""
    pieces: list[str] = []
    start = 0
    for match in re.finditer(r"%[0-9A-Fa-f]{2}", encoded):
        pieces.append(re.escape(encoded[start : match.start()]))
        digits = "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else c for c in match[0][1:])
        pieces.append("%" + digits)
        start = match.end()
    pieces.append(re.escape(encoded[start:]))
    return "".join(pieces)
