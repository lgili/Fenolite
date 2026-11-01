# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Findings layer: issues attached to a design, first-class like any other data."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fenolite.core.errors import Issue
from fenolite.core.units import Nm

CIRCUIT_PREFIX = "circuit."
"""The prefix of the circuit finding codes, whose waivers carry a digest (change c0274)."""
DIGEST = re.compile(r"[0-9a-f]{16}")
"""A requirement row's digest: the first 16 hexadecimal digits of a SHA-256 (change c0274)."""


@dataclass(frozen=True, slots=True)
class Waiver:
    """The acceptance of one finding, with a reason (change c0114).

    ``code`` is a finding code (``copper.short``, ``copper.clearance``, ``copper.zone-overlap`` or
    ``<oracle>.drc.<suffix>``, or since change c0274 a ``circuit.*`` code). ``items`` are the names of the
    finding's items as ``where`` prints them, or glob patterns of them; for a ``circuit.*`` code the one row
    id of the finding without its code. ``min_gap`` bounds a clearance waiver from below, in nanometres.
    ``digest`` is the requirement row's digest at waiver time (16 lowercase hexadecimal digits), set for a
    ``circuit.*`` code and for no other: when the judged value or limit changes, the digest differs and the
    waiver expires. What a waiver may say is checked where it is declared (``dsl.Design.waive``); how it
    matches is ``checks.waivers``."""

    name: str
    code: str
    items: tuple[str, ...]
    reason: str
    min_gap: Nm | None = None
    digest: str | None = None

    def __post_init__(self) -> None:
        circuit = self.code.startswith(CIRCUIT_PREFIX)
        if circuit and self.digest is None:
            raise ValueError(f"waiver {self.name!r}: a {self.code} waiver needs the digest of its row")
        if not circuit and self.digest is not None:
            raise ValueError(f"waiver {self.name!r}: only a circuit.* waiver has a digest, not {self.code}")
        if self.digest is not None and not DIGEST.fullmatch(self.digest):
            raise ValueError(
                f"waiver {self.name!r}: the digest is 16 lowercase hexadecimal digits, not {self.digest!r}"
            )


@dataclass(frozen=True, slots=True)
class Findings:
    """The findings layer of a design (``findings.json``). ``waivers`` are sorted by name."""

    issues: tuple[Issue, ...] = ()
    waivers: tuple[Waiver, ...] = ()


__all__ = ["CIRCUIT_PREFIX", "DIGEST", "Findings", "Issue", "Waiver"]
