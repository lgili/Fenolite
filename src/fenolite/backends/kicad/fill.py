# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lift KiCad 10's derived zone copper onto the original board model and write its own format.

KiCad's refill runs on a private copy (S-0020, S-0022). Only the fill polygons and the filled flag
cross back; the original board supplies every editable input and opaque slot.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.base import ZoneFills
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.roundtrip import rt1
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, LegacyEditRefusedError, inspect
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Zone, ZoneFill
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-FILL-SAVE", "H-K-FILL-LIFT", "H-K-FILL-REPEAT"))
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {"zone.fill-mismatch": "error", "zone.fill-unstable": "warning", "zone.none": "info"}
)


@dataclass(frozen=True, slots=True)
class LiftResult:
    design: Design
    changed: tuple[str, ...]
    unmatched: tuple[str, ...]
    counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FillResult:
    text: str | None
    changed: tuple[str, ...]
    zones: tuple[ZoneFills, ...]
    issues: tuple[Issue, ...] = ()


def _ring(fill: ZoneFill) -> tuple[tuple[int, int], ...]:
    points = tuple((point.x, point.y) for point in fill.polygon)
    if points and points[0] == points[-1]:
        points = points[:-1]
    if not points:
        return ()
    first = min(range(len(points)), key=lambda index: points[index])
    return points[first:] + points[:first]


def fill_set(zone: Zone) -> frozenset[tuple[str, bool, tuple[tuple[int, int], ...]]]:
    """Order-independent fill comparison, retaining layer, island state and ring direction."""
    return frozenset((fill.layer, fill.island, _ring(fill)) for fill in zone.fills)


def zone_fills(design: Design) -> tuple[ZoneFills, ...]:
    if design.board is None:
        return ()
    return tuple(ZoneFills(zone.id, zone.fills, zone.filled) for zone in design.board.zones)


def lift_fills(original: Design, refilled: Design) -> LiftResult:
    if original.board is None or refilled.board is None:
        raise FormatError("zone fill requires two boards")
    found = {zone.id: zone for zone in refilled.board.zones}
    prior = {zone.id: zone for zone in original.board.zones}
    unmatched = tuple(sorted(prior.keys() ^ found.keys()))
    changed: list[str] = []
    counts: dict[str, int] = {}
    zones: list[Zone] = []
    for zone in original.board.zones:
        refill = found.get(zone.id)
        if refill is None:
            zones.append(zone)
            continue
        counts[zone.id] = len(refill.fills)
        if fill_set(zone) != fill_set(refill) or zone.filled != refill.filled:
            changed.append(zone.id)
        zones.append(dataclasses.replace(zone, fills=refill.fills, filled=refill.filled))
    design = dataclasses.replace(original, board=dataclasses.replace(original.board, zones=tuple(zones)))
    return LiftResult(design, tuple(sorted(changed)), unmatched, MappingProxyType(counts))


def fill_board(text: str, refilled_text: str, *, file: str = "") -> FillResult:
    original = read_board(text, file=file)
    refilled = read_board(refilled_text, file=file)
    lifted = lift_fills(original, refilled)
    if lifted.unmatched:
        issues = tuple(
            Issue("zone.fill-mismatch", "error", f"zone {zone_id} differs between the boards", where=zone_id)
            for zone_id in lifted.unmatched
        )
        return FillResult(None, lifted.changed, zone_fills(lifted.design), issues)
    info = inspect(parse(text, file=file), file=file)
    major = info.major
    if major is None:
        raise FormatError("cannot determine the board's KiCad major", file=file)
    if major < 9:
        raise LegacyEditRefusedError(FileKind.BOARD, info.version)
    written = write_board(lifted.design, target=major)
    reread = read_board(written.text, file=file)
    expected = {zone.id: zone for zone in lifted.design.board.zones} if lifted.design.board else {}
    actual = {zone.id: zone for zone in reread.board.zones} if reread.board else {}
    for zone_id, zone in expected.items():
        result = actual.get(zone_id)
        if result is None or fill_set(result) != fill_set(zone) or result.filled != zone.filled:
            raise FormatError(f"writer cannot express fill for zone {zone_id}", file=file)
    verdict = rt1(written.text, file=file)
    if not verdict.passed:
        raise FormatError(f"filled board failed RT1 at {verdict.difference}", file=file)
    return FillResult(written.text, lifted.changed, zone_fills(lifted.design), written.issues)


__all__ = [
    "EVIDENCE",
    "ISSUE_CODES",
    "FillResult",
    "LiftResult",
    "fill_board",
    "fill_set",
    "lift_fills",
    "zone_fills",
]
