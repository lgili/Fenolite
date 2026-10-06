# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads of a board paired with the records of KiCad's IPC-D-356 export (change c0020 Decision 9).

The export truncates references to 6 characters, pins to 4 and net names to their last 14, and its
coordinates are quantised to export units with an unknown origin (``docs/formats/kicad/board.md``,
S-0019, S-0020). A record is therefore paired with a pad of the same truncated key, the nearest one within
``BOUND_UNITS`` export units per axis, with positions taken relative to an anchor record whose key is
unique in the export and in the board. This is c0009's verified comparison, moved here from
``tests/kicad/board/_frame.py``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.base import PadAssignment, PadNetList, Uncovered
from fenolite.backends.kicad.ipcd356 import Ipcd356, Ipcd356Record
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import Point, Transform
from fenolite.model.board import Pad
from fenolite.model.circuit import Component
from fenolite.model.design import Design

REF_WIDTH = 6
PIN_WIDTH = 4
NET_WIDTH = 14
BOUND_UNITS = 2
FULL_TURN = 360_000_000
EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-NET-IPC",))
"""``KICAD-VERIFIED``: ``H-K-NET-IPC`` holds on 9.0.9 and 10.0.6 (c0020 task 9.2)."""


@dataclass(frozen=True, slots=True)
class MatchedPad:
    """A record paired with a pad: the pad's element ``REF-PIN``, absolute position and stored angle."""

    record: Ipcd356Record
    element: str
    ref: str
    pad: Pad
    absolute: Point
    stored_angle: int


@dataclass(frozen=True, slots=True)
class _Candidate:
    element: str
    ref: str
    pad: Pad
    absolute: Point
    stored_angle: int

    @property
    def key(self) -> tuple[str, str]:
        return self.ref[:REF_WIDTH], self.pad.number[:PIN_WIDTH]


@dataclass(frozen=True, slots=True)
class PadMatch:
    """Records paired with pads, the records and numbered pads left over, and the counts of the match."""

    pairs: tuple[MatchedPad, ...]
    unmatched: tuple[Ipcd356Record, ...]
    unpaired: tuple[str, ...]
    vias: int
    truncated_keys: int
    ambiguous_keys: int
    problems: tuple[str, ...]


def _pads(design: Design) -> list[_Candidate]:
    board = design.board
    if board is None:
        return []
    found: list[_Candidate] = []
    for fp in board.footprints:
        component = design.by_id.get(fp.component_id)
        ref = component.ref if isinstance(component, Component) else ""
        placement = Transform.placement(fp.position, fp.rotation)
        for pad in fp.pads:
            stored = (pad.rotation + fp.rotation) % FULL_TURN
            element = f"{ref}-{pad.number}"
            found.append(_Candidate(element, ref, pad, placement.apply(pad.position), stored))
    return found


def _export_frame(point: Point, unit_nm: int) -> tuple[Fraction, Fraction]:
    """File frame (nm, Y down) to export units (Y up), before the unknown origin."""
    return Fraction(point.x, unit_nm), Fraction(-point.y, unit_nm)


def _match(
    records: list[Ipcd356Record],
    by_key: dict[tuple[str, str], list[_Candidate]],
    anchor: tuple[Ipcd356Record, _Candidate],
    unit: int,
) -> tuple[list[MatchedPad], list[Ipcd356Record], list[str]]:
    """Pair every record with a distinct pad of its key, positions relative to ``anchor``."""
    reference, reference_pad = anchor
    ref_x, ref_y = _export_frame(reference_pad.absolute, unit)
    origin = (reference.x - ref_x, reference.y - ref_y)
    taken: set[int] = set()
    pairs: list[MatchedPad] = []
    unmatched: list[Ipcd356Record] = []
    problems: list[str] = []
    for record in records:
        best: tuple[Fraction, _Candidate] | None = None
        for candidate in by_key.get((record.ref, record.pin), []):
            if id(candidate) in taken:
                continue
            x, y = _export_frame(candidate.absolute, unit)
            dx, dy = abs(record.x - origin[0] - x), abs(record.y - origin[1] - y)
            if dx <= BOUND_UNITS and dy <= BOUND_UNITS and (best is None or dx + dy < best[0]):
                best = (dx + dy, candidate)
        if best is None:
            problems.append(f"{record.ref} pin {record.pin}: no model pad within the bound")
            unmatched.append(record)
            continue
        taken.add(id(best[1]))
        pad = best[1]
        pairs.append(MatchedPad(record, pad.element, pad.ref, pad.pad, pad.absolute, pad.stored_angle))
    return pairs, unmatched, problems


def match_pads(design: Design, export: Ipcd356) -> PadMatch:
    """The records of ``export`` paired with the pads of ``design``'s board, vias skipped and counted."""
    unit = export.unit_nm
    records = [r for r in export.records if not (r.ref == "VIA" and r.pin == "")]
    vias = len(export.records) - len(records)
    pads = _pads(design)
    by_key: dict[tuple[str, str], list[_Candidate]] = defaultdict(list)
    for pad in pads:
        by_key[pad.key].append(pad)
    record_keys = Counter((r.ref, r.pin) for r in records)
    ambiguous = sum(1 for k, n in record_keys.items() if n > 1 or len(by_key.get(k, [])) > 1)
    truncated = sum(1 for p in pads if len(p.ref) > REF_WIDTH or len(p.pad.number) > PIN_WIDTH)
    unique = [
        r for r in records if record_keys[(r.ref, r.pin)] == 1 and len(by_key.get((r.ref, r.pin), [])) == 1
    ]
    if unique:
        anchors = [(unique[0], by_key[(unique[0].ref, unique[0].pin)][0])]
    else:  # no unique key: try each pad of the first record's key as the reference
        first = next((r for r in records if by_key.get((r.ref, r.pin))), None)
        anchors = [(first, pad) for pad in by_key[(first.ref, first.pin)]] if first is not None else []
    numbered = tuple(sorted({p.element for p in pads if p.pad.number}))
    if not anchors:
        problems = ("no record matches a model pad key",) if records else ()
        return PadMatch((), tuple(records), numbered, vias, truncated, ambiguous, problems)
    attempts = [_match(records, by_key, anchor, unit) for anchor in anchors]
    pairs, unmatched, problems = next((a for a in attempts if not a[2]), attempts[0])
    paired = {p.element for p in pairs}
    unpaired = tuple(e for e in numbered if e not in paired)
    return PadMatch(tuple(pairs), tuple(unmatched), unpaired, vias, truncated, ambiguous, tuple(problems))


NO_NET_LABEL = "N/C"
"""The net field of an IPC-D-356 record of a pad on no net (``docs/formats/kicad/board.md``)."""


def ambiguous_labels(design: Design) -> frozenset[str]:
    """The ids of the nets whose names share their last ``NET_WIDTH`` characters with another net's name,
    so the export gives them one label."""
    by_tail: dict[str, set[str]] = defaultdict(set)
    for net in design.circuit.nets:
        if net.name:
            by_tail[net.name[-NET_WIDTH:]].add(net.name)
    shared = {name for names in by_tail.values() if len(names) > 1 for name in names}
    return frozenset(net.id for net in design.circuit.nets if net.name in shared)


def export_netlist(design: Design, export: Ipcd356) -> PadNetList:
    """The export as a ``PadNetList`` (source ``export``) of full ``REF-PIN`` elements.

    A pad the export labels ``N/C`` is on no net (label ``""``), so it is a block of its own in the
    assignment compare. Pads on nets whose labels collide become ``net-label-ambiguous``; numbered pads
    that no record is paired with become ``not-exported``; records paired with no pad become
    ``unmatched-record`` (truncated fields).
    """
    match = match_pads(design, export)
    ambiguous_nets = ambiguous_labels(design)
    ambiguous = {p.element for p in _pads(design) if p.pad.net_id in ambiguous_nets and p.pad.number}
    named = {net.name[-NET_WIDTH:] for net in design.circuit.nets}
    assignments: list[PadAssignment] = []
    for pair in match.pairs:
        if pair.pad.number and pair.element not in ambiguous:
            label = pair.record.net
            if label == NO_NET_LABEL and NO_NET_LABEL not in named:
                label = ""  # the export's word for a pad on no net, unless a net of the board is named so
            assignments.append(PadAssignment(pair.element, label))
    assigned = {a.element for a in assignments}
    uncovered = [Uncovered(e, "net-label-ambiguous") for e in sorted(ambiguous)]
    uncovered += [Uncovered(e, "not-exported") for e in match.unpaired if e not in ambiguous]
    seen = assigned | {u.element for u in uncovered}
    for record in match.unmatched:
        element = f"{record.ref}-{record.pin}"
        if element not in seen:
            uncovered.append(Uncovered(element, "unmatched-record"))
            seen.add(element)
    return PadNetList("export", tuple(assignments), tuple(uncovered))


__all__ = [
    "BOUND_UNITS",
    "EVIDENCE",
    "NET_WIDTH",
    "NO_NET_LABEL",
    "PIN_WIDTH",
    "REF_WIDTH",
    "MatchedPad",
    "PadMatch",
    "ambiguous_labels",
    "export_netlist",
    "match_pads",
]
