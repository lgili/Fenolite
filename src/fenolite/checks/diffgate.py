# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Gated differences (capability file-safety, "Gated differences"; change c0207).

``gate`` turns every change of a model difference whose kind is not allowed into one error finding
``diff.not-allowed``; the kind of a change is the first segment of its path (``/rule/0`` is a ``rule``).
``ISSUE_CODES`` also holds the two codes of ``fenolite diff --three-way``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from types import MappingProxyType

from fenolite.backends.base import DiffReport
from fenolite.checks.diff import CONTENT_KINDS, KEYED_KINDS
from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "diff.not-allowed": "error",
        "diff.conflict": "error",
        "diff.unmergeable": "error",
    }
)
KINDS = frozenset((*KEYED_KINDS, *CONTENT_KINDS))
"""Every kind a change of the model view can have: the names ``--allow`` takes."""


def parse_kinds(text: str) -> frozenset[str]:
    """The kinds of a comma-separated ``--allow`` value; ``ValueError`` names the first unknown kind. An
    empty value allows no kind."""
    kinds = frozenset(part.strip() for part in text.split(",") if part.strip())
    unknown = sorted(kinds - KINDS)
    if unknown:
        raise ValueError(f"unknown kind {unknown[0]!r}")
    return kinds


def kind_of(path: str) -> str:
    """The kind of the change at ``path``."""
    return path.split("/")[1]


def gate(report: DiffReport, allowed: Collection[str]) -> tuple[Issue, ...]:
    """One ``diff.not-allowed`` error for each change of ``report`` whose kind is not in ``allowed``."""
    return tuple(
        Issue(
            "diff.not-allowed",
            ISSUE_CODES["diff.not-allowed"],
            f"{change.change} {change.path}: the kind {kind_of(change.path)} is not allowed",
            where=change.path,
            hint=f"review this change, or add {kind_of(change.path)} to --allow when it is expected",
        )
        for change in report.changes
        if kind_of(change.path) not in allowed
    )


__all__ = ["ISSUE_CODES", "KINDS", "gate", "kind_of", "parse_kinds"]
