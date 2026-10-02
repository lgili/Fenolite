# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net-class bench (c0010 Decision 14; capability kicad-oracle, "Net-class rules are enforced by
kicad-cli").

A 60 × 100 mm board with F.Cu tracks 0.25 mm wide and 20 mm long, in rows 5 mm apart. Each net of
``ROWS`` runs beside its own ``GND`` track with a 1.0 mm gap. Class HV (clearance 2 mm by default) holds
``+3V3`` and ``SIG1``; every other row is in ``Default``. The canary is a 3 mm clearance rule scoped by a
``net`` condition to ``CANARY_A``, whose track runs 0.75 mm from the ``CANARY_B`` track, at least 10 mm
from other copper. The scoped canary departs from c0018's unconditional one, which would flag every
1.0 mm row. Outcomes are judged from the DRC report by item uuids, never by exit code.

``kicad-cli`` 9.0.9 and 10.0.6 read a ``.kicad_dru`` next to the board even without a project file
(measured for c0010), so the canary must fire in every case, the no-project case included: there it
proves that DRC ran the rules while the classes, which live only in the project file, are absent.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from types import MappingProxyType

import pytest

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.model.board import Board, Outline, Track
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

MM = 1_000_000
WIDTH = 250_000
GAP = MM
ROW_PITCH = 5 * MM
LENGTH = 20 * MM
X0 = 20 * MM
FIRST_ROW = 25 * MM
HV_NETS: tuple[str, ...] = ("+3V3", "SIG1")
ANCHOR = "SIG10"
RAW_PATTERNS: tuple[str, ...] = ("Net-(R1-Pad1)", "D[0]", "IN+", "VCC_3.3", "SW?_*")
DECOYS: tuple[str, ...] = ("Net-R1-Pad1", "D0", "INN", "VCC_3V3")
ROWS: Mapping[str, str] = MappingProxyType(
    {net: "GND" for net in (*HV_NETS, ANCHOR, "Net-(R1-Pad1)", "D[0]", "IN+", "VCC_3.3", *DECOYS, "SW1_A")}
)
"""Row net → the net of its neighbour track (always ``GND``)."""
CANARY = ("CANARY_A", "CANARY_B")
CANARY_CLEARANCE = 3 * MM
CASES = (
    "full",
    "noproject",
    "noclass",
    "minimal",
    "patterns",
    "decoys",
    "anchor",
    "floor-template",
    "floor-raised",
)


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def bench_design(*, target: int, hv_clearance: Nm | None = 2 * MM) -> Design:
    """The bench as a model design; ``hv_clearance=None`` builds it without class HV.

    ``target`` is accepted for symmetry with the writers: the design is the same for 9 and 10.
    """
    del target
    nets: dict[str, Net] = {}

    def net(name: str) -> str:
        if name not in nets:
            nets[name] = Net(id=_id("net", len(nets) + 1), name=name)
        return nets[name].id

    tracks: list[Track] = []

    def track(name: str, y: int) -> None:
        tracks.append(
            Track(
                id=_id("trk", len(tracks) + 1),
                start=Point(X0, y),
                end=Point(X0 + LENGTH, y),
                width=WIDTH,
                layer="F.Cu",
                net_id=net(name),
            )
        )

    track(CANARY[0], 8 * MM)
    track(CANARY[1], 8 * MM + 750_000 + WIDTH)
    for row, name in enumerate(ROWS):
        y = FIRST_ROW + row * ROW_PITCH
        track(name, y)
        track(ROWS[name], y + GAP + WIDTH)
    classes: tuple[NetClass, ...] = ()
    if hv_clearance is not None:
        hv = NetClass(id=_id("cls", 1), name="HV", clearance=hv_clearance)
        classes = (hv,)
        for name in HV_NETS:
            nets[name] = dataclasses.replace(nets[name], netclass_id=hv.id)
    canary = Rule(
        id=_id("rul", 1),
        name="canary",
        kind="clearance",
        selector_a=Selector("net", CANARY[0]),
        min=CANARY_CLEARANCE,
        priority=1,
    )
    base = Design.new("bench", seed=0)
    board = Board(
        id=_id("brd", 1),
        outline=Outline(
            id=_id("out", 1),
            points=(Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 100 * MM), Point(0, 100 * MM)),
        ),
        layers=created_layers(2),
        tracks=tuple(tracks),
    )
    circuit = Circuit(nets=tuple(nets.values()), netclasses=classes)
    return dataclasses.replace(
        base, circuit=circuit, board=board, rules=RuleSet(id=_id("rst", 1), rules=(canary,))
    )


def _tracks(design: Design, name: str) -> list[Track]:
    ids = {n.id for n in design.circuit.nets if n.name == name}
    assert design.board is not None
    return [t for t in design.board.tracks if t.net_id in ids]


def track_uuid(design: Design, net: str) -> str:
    """The KiCad uuid of the track of ``net`` (a row net or a canary net)."""
    (found,) = _tracks(design, net)
    return kicad_uuid(found)


def row_uuids(design: Design, net: str) -> tuple[str, str]:
    """``(row track, its GND neighbour)`` uuids."""
    (own,) = _tracks(design, net)
    (neighbour,) = [t for t in _tracks(design, ROWS[net]) if t.start.y == own.start.y + GAP + WIDTH]
    return kicad_uuid(own), kicad_uuid(neighbour)


def _between(report: DrcReport, pair: Sequence[str]) -> list[DrcViolation]:
    wanted = set(pair)
    return [v for v in report.violations if v.type == "clearance" and {i.uuid for i in v.items} == wanted]


def canary_fired(report: DrcReport, design: Design) -> bool:
    return bool(_between(report, (track_uuid(design, CANARY[0]), track_uuid(design, CANARY[1]))))


def watched(case: str) -> tuple[str, ...]:
    """The rows a case watches (Decision 14)."""
    if case == "decoys":
        return DECOYS
    if case == "anchor":
        return (ANCHOR,)
    if case == "patterns":
        return (*RAW_PATTERNS[:4], "SW1_A")
    return HV_NETS


def violations_key(report: DrcReport) -> frozenset[tuple[str, frozenset[str]]]:
    return frozenset((v.type, frozenset(i.uuid for i in v.items)) for v in report.violations)


def judge(report: DrcReport | None, *, case: str, design: Design, reference: DrcReport | None = None) -> str:
    """The outcome of a case from its DRC report (c0017's closed set).

    ``inconclusive`` when the canary is missing (the rules file was not loaded; it is read with or
    without a project file); ``equal``/``different`` for ``minimal`` against the ``full`` ``reference``;
    otherwise ``present`` (every watched row has its HV violation), ``absent`` (none) or ``different``.
    """
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}")
    if report is None:
        return "inconclusive"
    if not canary_fired(report, design):
        return "inconclusive"
    if case == "minimal":
        if reference is None:
            raise ValueError("the minimal case needs the full report as reference")
        return "equal" if violations_key(report) == violations_key(reference) else "different"
    hits = [bool(_between(report, row_uuids(design, net))) for net in watched(case)]
    if all(hits):
        return "present"
    return "absent" if not any(hits) else "different"


def assert_loaded(outcome: str, case: str) -> None:
    """Fail the test when the rules file (and so the project) was not loaded."""
    if outcome == "inconclusive":
        pytest.fail(
            f"rules file not loaded: the canary violation is missing in case {case!r}",
            pytrace=False,
        )


__all__ = [
    "ANCHOR",
    "CASES",
    "DECOYS",
    "HV_NETS",
    "RAW_PATTERNS",
    "ROWS",
    "assert_loaded",
    "bench_design",
    "canary_fired",
    "judge",
    "row_uuids",
    "track_uuid",
    "watched",
]
