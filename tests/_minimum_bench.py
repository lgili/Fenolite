# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board-setup minimums bench (c0026 Decision 10; capability kicad-oracle, "Board-setup minimums
are proved by kicad-cli").

A 60 × 100 mm board with one probe item per rule kind, each at least 4 mm from other copper and between
the bench rule of its kind and the minimum of the template runs:

- ``clearance``: two 0.25 mm tracks with a 0.15 mm gap;
- ``track_width``: a 0.15 mm track;
- ``via_diameter``: a via of 0.45 mm diameter and 0.24 mm drill;
- ``hole_size``: a via of 0.6 mm diameter and 0.25 mm drill;
- ``edge_clearance``: a 0.25 mm track whose copper edge is 0.35 mm from the board edge.

A row of class HV (clearance 2 mm) runs beside a ``GND`` track with a 1.0 mm gap, and a model class
``Default`` with clearance 0.05 mm keeps every probe item free of class violations. The five board-wide
rules (severity ``error``, priority 0) sit below every item. The canary is c0010's: a 3 mm clearance rule
on ``net CANARY_A`` with priority 1, written last, whose track runs 0.75 mm from ``CANARY_B``. Outcomes
are judged from the DRC report by violation type and item uuid, never by exit code.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

import pytest

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.lowering import MINIMUM_KEYS
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.pro import MINIMUM_POINTER, template
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.model.board import Board, Outline, Track, Via
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

MM = 1_000_000
UM = 1_000
WIDTH = 250_000
X0 = 20 * MM
LENGTH = 20 * MM
KINDS: tuple[RuleKind, ...] = ("clearance", "track_width", "via_diameter", "hole_size", "edge_clearance")
VIOLATION_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "clearance": "clearance",
        "track_width": "track_width",
        "via_diameter": "via_diameter",
        "hole_size": "drill_out_of_range",
        "edge_clearance": "copper_edge_clearance",
    }
)
"""Rule kind → the violation type c0018 observed for its custom rule."""
RUNS = ("keys-template", "keys-lowered", "rules-template", "rules-lowered")
KEYS_LOWERED: Mapping[str, str] = MappingProxyType(
    {
        "min_clearance": "0.1",
        "min_track_width": "0.1",
        "min_via_diameter": "0.35",
        "min_through_hole_diameter": "0.2",
        "min_copper_edge_clearance": "0.2",
    }
)
"""Key → the mm text that ``keys-lowered`` sets (below every probe item)."""
RAISED_CLEARANCE = "0.2"
"""The ``min_clearance`` of the template runs: the template's 0 cannot block anything."""
BENCH_RULES: Mapping[RuleKind, Nm] = MappingProxyType(
    {
        "clearance": 100 * UM,
        "track_width": 100 * UM,
        "via_diameter": 350 * UM,
        "hole_size": 200 * UM,
        "edge_clearance": 200 * UM,
    }
)
"""The ``min`` of each board-wide bench rule."""
CANARY = ("CANARY_A", "CANARY_B")
CANARY_CLEARANCE = 3 * MM
HV = ("HV1", "GND")
NAME = "bench"


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def bench_design(*, target: int, board_wide: bool = True) -> Design:
    """The bench as a model design; ``board_wide=False`` leaves out the five board-wide rules.

    ``target`` is accepted for symmetry with the writers: the design is the same for 9 and 10.
    """
    del target
    nets: dict[str, Net] = {}

    def net(name: str) -> str:
        if name not in nets:
            nets[name] = Net(id=_id("net", len(nets) + 1), name=name)
        return nets[name].id

    tracks: list[Track] = []
    vias: list[Via] = []

    def track(name: str, start: Point, end: Point, width: Nm = WIDTH) -> None:
        tracks.append(
            Track(
                id=_id("trk", len(tracks) + 1),
                start=start,
                end=end,
                width=width,
                layer="F.Cu",
                net_id=net(name),
            )
        )

    def via(name: str, at: Point, diameter: Nm, drill: Nm) -> None:
        vias.append(
            Via(
                id=_id("via", len(vias) + 1),
                position=at,
                diameter=diameter,
                drill=drill,
                layers=("F.Cu", "B.Cu"),
                net_id=net(name),
            )
        )

    def row(name: str, y: Nm, width: Nm = WIDTH) -> None:
        track(name, Point(X0, y), Point(X0 + LENGTH, y), width)

    row(CANARY[0], 8 * MM)
    row(CANARY[1], 8 * MM + 750 * UM + WIDTH)
    row("P_CLR_A", 25 * MM)
    row("P_CLR_B", 25 * MM + 150 * UM + WIDTH)
    row("P_TW", 32 * MM, 150 * UM)
    via("P_VD", Point(30 * MM, 40 * MM), 450 * UM, 240 * UM)
    via("P_HS", Point(30 * MM, 48 * MM), 600 * UM, 250 * UM)
    edge_x = 350 * UM + WIDTH // 2
    track("P_EDGE", Point(edge_x, 55 * MM), Point(edge_x, 65 * MM))
    row(HV[0], 75 * MM)
    row(HV[1], 75 * MM + MM + WIDTH)
    default = NetClass(id=_id("cls", 1), name="Default", clearance=50 * UM)
    hv = NetClass(id=_id("cls", 2), name="HV", clearance=2 * MM)
    nets[HV[0]] = dataclasses.replace(nets[HV[0]], netclass_id=hv.id)
    rules: list[Rule] = []
    if board_wide:
        rules += [
            Rule(id=_id("rul", 10 + i), name=f"fab_{kind}", kind=kind, selector_a=Selector("all"), min=value)
            for i, (kind, value) in enumerate(BENCH_RULES.items())
        ]
    rules.append(
        Rule(
            id=_id("rul", 1),
            name="canary",
            kind="clearance",
            selector_a=Selector("net", CANARY[0]),
            min=CANARY_CLEARANCE,
            priority=1,
        )
    )
    board = Board(
        id=_id("brd", 1),
        outline=Outline(
            id=_id("out", 1),
            points=(Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 100 * MM), Point(0, 100 * MM)),
        ),
        layers=created_layers(2),
        tracks=tuple(tracks),
        vias=tuple(vias),
    )
    circuit = Circuit(nets=tuple(nets.values()), netclasses=(default, hv))
    return dataclasses.replace(
        Design.new(NAME, seed=0),
        circuit=circuit,
        board=board,
        rules=RuleSet(id=_id("rst", 1), rules=tuple(rules)),
    )


def _tracks(design: Design, name: str) -> list[Track]:
    ids = {n.id for n in design.circuit.nets if n.name == name}
    assert design.board is not None
    return [t for t in design.board.tracks if t.net_id in ids]


def _vias(design: Design, name: str) -> list[Via]:
    ids = {n.id for n in design.circuit.nets if n.name == name}
    assert design.board is not None
    return [v for v in design.board.vias if v.net_id in ids]


_PROBE_NETS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "clearance": ("P_CLR_A", "P_CLR_B"),
        "track_width": ("P_TW",),
        "via_diameter": ("P_VD",),
        "hole_size": ("P_HS",),
        "edge_clearance": ("P_EDGE",),
    }
)


def item_uuids(design: Design, kind: str) -> tuple[str, ...]:
    """The KiCad uuids of the probe item(s) of ``kind`` (``clearance``: both tracks)."""
    return tuple(
        kicad_uuid(item) for net in _PROBE_NETS[kind] for item in (*_tracks(design, net), *_vias(design, net))
    )


def _pair(report: DrcReport, pair: tuple[str, str]) -> list[DrcViolation]:
    wanted = set(pair)
    return [v for v in report.violations if v.type == "clearance" and {i.uuid for i in v.items} == wanted]


def pair_uuids(design: Design, nets: tuple[str, str]) -> tuple[str, str]:
    """The uuids of the two tracks of a pair (``CANARY`` or ``HV``), the upper one first."""
    (a,) = _tracks(design, nets[0])
    (b,) = [t for t in _tracks(design, nets[1]) if t.start.y > a.start.y]
    return kicad_uuid(a), kicad_uuid(b)


def canary_fired(report: DrcReport, design: Design) -> bool:
    return bool(_pair(report, pair_uuids(design, CANARY)))


def judge_item(report: DrcReport | None, *, kind: str, design: Design) -> str:
    """``present`` when the probe item of ``kind`` has its violation, ``absent`` otherwise, and
    ``inconclusive`` without a report or without the canary violation."""
    if report is None or not canary_fired(report, design):
        return "inconclusive"
    uuids = item_uuids(design, kind)
    wanted = VIOLATION_TYPES[kind]
    if kind == "clearance":
        hit = any({i.uuid for i in v.items} == set(uuids) for v in report.violations if v.type == wanted)
    else:
        hit = any(uuids[0] in {i.uuid for i in v.items} for v in report.violations if v.type == wanted)
    return "present" if hit else "absent"


def judge_class(report: DrcReport | None, *, design: Design) -> str:
    """``present`` when the HV row has its clearance violation; ``inconclusive`` without the canary."""
    if report is None or not canary_fired(report, design):
        return "inconclusive"
    return "present" if _pair(report, pair_uuids(design, HV)) else "absent"


def found_types(report: DrcReport, design: Design, kind: str) -> list[str]:
    """The violation types on the probe item of ``kind`` (for failure messages)."""
    uuids = set(item_uuids(design, kind))
    return sorted({v.type for v in report.violations if uuids & {i.uuid for i in v.items}})


def _set_keys(project: str, values: Mapping[str, str]) -> str:
    data = _json.loads(project)
    rules = cast(JsonObject, _json.get(data, MINIMUM_POINTER))
    for key, text in values.items():
        rules[key] = JsonNumber(text)
    return _json.dumps(data)


def template_keys(target: int) -> dict[str, str]:
    """The five keys at the template's values, with ``min_clearance`` raised to ``RAISED_CLEARANCE``."""
    rules = cast(JsonObject, _json.get(template(target), MINIMUM_POINTER))
    keys = {key: cast(JsonNumber, rules[key]).text for key in MINIMUM_KEYS[target].values()}
    return keys | {"min_clearance": RAISED_CLEARANCE}


def run_files(run: str, target: int, *, issues: list[Issue] | None = None) -> dict[str, str]:
    """The three bench files of ``run`` for ``target`` (Decision 10)."""
    if run not in RUNS:
        raise ValueError(f"unknown run {run!r}")
    design = bench_design(target=target, board_wide=run.startswith("rules"))
    files = write_triad(design, name=NAME, target=target, issues=issues)
    project = f"{NAME}.kicad_pro"
    if run in ("keys-template", "rules-template"):
        files[project] = _set_keys(files[project], template_keys(target))
    elif run == "keys-lowered":
        files[project] = _set_keys(files[project], KEYS_LOWERED)
    return files


def assert_loaded(outcome: str, case: str) -> None:
    """Fail the test when the rules file was not loaded (the canary violation is missing)."""
    if outcome == "inconclusive":
        pytest.fail(f"rules file not loaded: the canary violation is missing in {case!r}", pytrace=False)


__all__ = [
    "BENCH_RULES",
    "CANARY",
    "HV",
    "KEYS_LOWERED",
    "KINDS",
    "RAISED_CLEARANCE",
    "RUNS",
    "VIOLATION_TYPES",
    "assert_loaded",
    "bench_design",
    "pair_uuids",
    "canary_fired",
    "found_types",
    "item_uuids",
    "judge_class",
    "judge_item",
    "run_files",
    "template_keys",
]
