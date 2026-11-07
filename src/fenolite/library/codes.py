# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of a library made from a board (capability design-conversion, "Library made from a board";
``docs/cli-contract.md``, "library"; change c0223), and of the library repository and ``fenolite get``
(change c0279, ``docs/library-repo.md``)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        **{
            f"proposal.{name}": "error"
            for name in (
                "datasheet-mismatch",
                "unknown-family",
                "duplicate-pin",
                "pin-count",
                "pin-outside",
                "depopulated-used",
                "range",
                "second-required",
                "not-independent",
                "disagree",
                "review-doubt",
                "review-uncited",
                "review-datasheet",
                "review-unchecked",
            )
        },
        **{
            f"proposal.{name}": "warning"
            for name in (
                "exposed-pad",
                "sides",
                "uncited",
                "doubt",
            )
        },
        "library.drift": "error",
        "library.instances-differ": "warning",
        "library.not-local": "warning",
        "library.not-shippable": "error",
        "library.import-skipped": "info",
        "library.import-symbol-regenerated": "info",
        "library.import-step-unchecked": "info",
        "library.import-step-placement": "info",
        "library.import-terms": "info",
        "library.import-family-unknown": "info",
        "library.import-crosscheck-skipped": "info",
        "library.import-package-mismatch": "error",
        "library.import-pad-count": "error",
        "library.import-numbering": "error",
        "library.import-pin1": "error",
        "library.import-pitch": "warning",
        "library.import-land": "warning",
        "library.import-sources-disagree": "warning",
        # the library repository and fenolite get (change c0279)
        "library.depends-conflict": "error",
        "library.duplicate-id": "error",
        "library.family-mismatch": "error",
        "library.item-extra-file": "error",
        "library.item-missing": "error",
        "library.item-conflict": "error",
        "library.overrides-item": "info",
        "library.seed-renamed": "info",
        "library.seed-function-normalized": "warning",
        "library.seed-angle-normalized": "warning",
        "library.seed-skipped": "warning",
        "library.item-modified": "error",
        "library.licence-denied": "error",
        "library.licence-text": "error",
        "library.notice-missing": "error",
        "library.proof-failed": "error",
        "library.provenance-invalid": "error",
        "library.replay-differs": "error",
        "library.version-rule": "error",
    }
)
"""Every code that ``fenolite.library`` and ``fenolite library`` report, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a library issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
