# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The finding codes of picks and generators (change c0254; ``docs/cli-contract.md``, "pick")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "pick.no-match": "error",
        "pick.stale": "error",
        "pick.row-missing": "error",
        "pick.row-changed": "warning",
        "pick.query-changed": "info",
        "pick.new": "info",
        "pick.attribute-unknown": "info",
        "pick.row-unverified": "info",
        "gen.unachievable": "error",
        "gen.achieved": "info",
    }
)
"""Code → severity of every finding of ``fenolite.pick``; each is explained by ``fenolite explain``."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """The finding ``code`` with its severity of ``ISSUE_CODES``."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
