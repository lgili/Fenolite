# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Findings layer: issues attached to a design, first-class like any other data."""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.errors import Issue
from fenolite.core.units import Nm


@dataclass(frozen=True, slots=True)
class Waiver:
    """The acceptance of one finding, with a reason (change c0114).

    ``code`` is a finding code (``copper.short``, ``copper.clearance``, ``copper.zone-overlap`` or
    ``<oracle>.drc.<suffix>``). ``items`` are the names of the finding's items as ``where`` prints them, or
    glob patterns of them. ``min_gap`` bounds a clearance waiver from below, in nanometres. What a waiver
    may say is checked where it is declared (``dsl.Design.waive``); how it matches is
    ``checks.waivers``."""

    name: str
    code: str
    items: tuple[str, ...]
    reason: str
    min_gap: Nm | None = None


@dataclass(frozen=True, slots=True)
class Findings:
    """The findings layer of a design (``findings.json``). ``waivers`` are sorted by name."""

    issues: tuple[Issue, ...] = ()
    waivers: tuple[Waiver, ...] = ()


__all__ = ["Findings", "Issue", "Waiver"]
