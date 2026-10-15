# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edge clearance benches of change c0169 (capability kicad-oracle, "Edge clearance agrees with KiCad";
hypotheses H-K-EDGE-CENTRE, H-K-EDGE-RESOLVE and H-K-EDGE-AGREE).

Every board is authored here with round values and built by ``build_design`` from a script:

- **Centre.** A 60 × 30 mm board with a milled slot ``S1`` 54 mm long and 2 mm wide about (30, 10) mm, its
  lower edge at y = 11 mm, and five plated hole parts of 1 mm drill and 2 mm copper whose copper lies
  0.47, 0.52, 0.548, 0.552 and 0.6 mm below that edge. The project is the template's (edge clearance
  0.5 mm) without a custom rule. A probe ``edge-centre-<gap>`` is ``present`` when ``pcb drc`` gives a
  ``copper_edge_clearance`` that names the pad at that gap.
- **Resolve.** The same board with two parts, 0.4 and 0.7 mm from the slot, and a rules file of one
  board-wide ``edge_clearance`` rule of 0.3 or 0.8 mm beside the project's minimum of 0.5 mm. A probe
  ``edge-resolve-<rule>-<gap>`` is ``present`` when the pad at that gap is reported.
- **Agreement.** An 80 × 50 mm board with a round cut-out of 4 mm about (20, 25) mm, the slot ``S1`` of
  10 × 2 mm about (40, 25) mm, and an L of two slots drawn as its merged ring (seven vertices, three
  arcs; drawn by hand, so the build needs no ``geo`` extra). Each item comes in pairs 0.45 mm (``_in``)
  and 0.55 mm (``_out``) from a ring, on a net of its own: tracks and arcs by the board ring, vias by the
  board ring, the slot and the L, plated hole parts by the board ring, tracks by the round cut-out and
  along the L, and two zones whose stored fill is added to the built board through the model. The probe
  ``edge-agree`` is ``equal`` when the items that ``pcb drc`` names in ``copper_edge_clearance`` entries
  are those of Fenolite's ``copper.edge-clearance`` findings on the same board read back, fills left out;
  ``edge-agree-fill`` compares the fills alone (KiCad 9.0 is not claimed to judge stored fills,
  ``H-K-COPPER-ZONES``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from functools import cache

from _outlinebench import drc, target
from _outlinehelp import build_script

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.checks.copper import EDGE_CODE, check_copper
from fenolite.core.coords import Point
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import Net, arc_to, copper, mm, shape
from fenolite.model.board import Zone, ZoneFill, ZoneSettings
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
EDGE = "copper_edge_clearance"
CENTRE_GAPS = {"047": 0.47, "052": 0.52, "0548": 0.548, "0552": 0.552, "060": 0.6}
"""Probe label → the gap in mm from the copper of a part to the slot's lower edge."""
RESOLVE_GAPS = {"04": 0.4, "07": 0.7}
RESOLVE_RULES = {"03": "0.3", "08": "0.8"}
"""Probe label → the ``min`` in mm of the board-wide ``edge_clearance`` rule of a resolve board."""
SLOT_EDGE = 11.0
"""The y of the slot's lower edge, in mm of the script."""


def slot_board(name: str, gaps: Mapping[str, float]) -> DslDesign:
    """The 60 × 30 mm board with the slot ``S1`` and one plated hole part ``H<k>`` per gap, its 2 mm copper
    that far below the slot's lower edge."""
    d = DslDesign(name)
    d.board(mm(60), mm(30))
    d.slot(mm(30), mm(10), length=mm(54), width=mm(2), name="S1")
    for k, gap in enumerate(gaps.values()):
        d.hole(f"H{k + 1}", mm(6 + 12 * k), mm(SLOT_EDGE + 1 + gap), drill=mm(1), pad=mm(2))
    return d


@cache
def built(name: str, labels: tuple[str, ...]) -> tuple[tuple[str, str | bytes], ...]:
    """The files of the board ``name`` built for the running major, ``.fenolite/`` left out."""
    gaps = {**CENTRE_GAPS, **RESOLVE_GAPS}
    design = slot_board(name, {label: gaps[label] for label in labels})
    output = build_script(design, target())
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return tuple((k, v) for k, v in output.files.items() if not k.startswith(".fenolite/"))


def pad_uuids(text: str) -> dict[str, str]:
    """Reference → the KiCad uuid of the one pad of that part, on the board ``text``."""
    design = read_board(text)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, str] = {}
    for footprint in design.board.footprints:
        ref = refs.get(footprint.component_id, footprint.id)
        for pad in footprint.pads:
            found[ref] = kicad_uuid(pad)
    return found


def edge_uuids(report: DrcReport) -> set[str]:
    """The uuids of every item that a ``copper_edge_clearance`` entry names."""
    return {item.uuid for v in report.violations if v.type == EDGE for item in v.items}


def _text(files: Mapping[str, str | bytes], board: str) -> str:
    data = files[board]
    return data.decode("utf-8") if isinstance(data, bytes) else data


# --- centre ---------------------------------------------------------------------------------------------

CENTRE = "edgecentre"


@cache
def centre_report() -> DrcReport | None:
    files = dict(built(CENTRE, tuple(CENTRE_GAPS)))
    return drc(files, f"{CENTRE}.kicad_pcb")


def centre(label: str) -> str:
    """``present`` when the part at the gap ``label`` gets a ``copper_edge_clearance``."""
    report = centre_report()
    if report is None:
        return "inconclusive"
    files = dict(built(CENTRE, tuple(CENTRE_GAPS)))
    pads = pad_uuids(_text(files, f"{CENTRE}.kicad_pcb"))
    ref = f"H{list(CENTRE_GAPS).index(label) + 1}"
    return "present" if pads[ref] in edge_uuids(report) else "absent"


# --- resolve --------------------------------------------------------------------------------------------


def rules_text(minimum: str) -> str:
    """A rules file of one board-wide ``edge_clearance`` rule of ``minimum`` mm."""
    return f'(version 1)\n(rule "edge_probe"\n\t(constraint edge_clearance (min {minimum}mm)))\n'


@cache
def resolve_files(rule: str) -> tuple[tuple[str, str | bytes], ...]:
    """The resolve board of the rule ``rule`` (a label of ``RESOLVE_RULES``): the template project, whose
    edge clearance is 0.5 mm, and the rules file of that rule."""
    name = f"edgeresolve{rule}"
    files = dict(built(name, tuple(RESOLVE_GAPS)))
    files[f"{name}.kicad_dru"] = rules_text(RESOLVE_RULES[rule])
    return tuple(files.items())


@cache
def resolve_report(rule: str) -> DrcReport | None:
    return drc(dict(resolve_files(rule)), f"edgeresolve{rule}.kicad_pcb")


def resolve(rule: str, gap: str) -> str:
    """``present`` when the part at ``gap`` gets a ``copper_edge_clearance`` beside the rule ``rule``."""
    report = resolve_report(rule)
    if report is None:
        return "inconclusive"
    files = dict(resolve_files(rule))
    pads = pad_uuids(_text(files, f"edgeresolve{rule}.kicad_pcb"))
    ref = f"H{list(RESOLVE_GAPS).index(gap) + 1}"
    return "present" if pads[ref] in edge_uuids(report) else "absent"


# --- agreement --------------------------------------------------------------------------------------------

AGREE = "edgeagree"
WIDTH = 0.25
"""The width of every track and arc of the agreement bench, in mm."""
IN, OUT = 0.45, 0.55
MM_NM = 1_000_000
VIA = {"diameter": mm(0.6), "drill": mm(0.3)}
ELL = (
    (mm(55), mm(24)),
    (mm(65), mm(24)),
    arc_to((mm(65.707107), mm(24.292893)), (mm(66), mm(25))),
    (mm(66), mm(35)),
    arc_to((mm(65), mm(36)), (mm(64), mm(35))),
    (mm(64), mm(26)),
    (mm(55), mm(26)),
    arc_to((mm(54), mm(25)), (mm(55), mm(24))),
)
"""The L of two slots 2 mm wide, (55, 25)–(65, 25) mm and (65, 25)–(65, 35) mm, as its merged ring."""
FILLS = {"f_in": IN, "f_out": OUT}
"""Zone name → the gap of its stored fill from the board ring's left side."""
DIAGONAL = 0.7071067811865476


def _r(value: float) -> object:
    return mm(round(value, 6))


def agree_script() -> DslDesign:
    """The agreement bench before its fills (see the module's docstring)."""
    d = DslDesign(AGREE)
    d.board(mm(80), mm(50))
    d.cutout(shape.circle(mm(20), mm(25), mm(4)))
    d.slot(mm(40), mm(25), length=mm(10), width=mm(2), name="S1")
    d.cutout(ELL)
    nets: dict[str, Net] = {}

    def net(key: str) -> Net:
        if key not in nets:
            nets[key] = Net(key.upper())
            d.add(nets[key])
        return nets[key]

    def track(key: str, a: tuple[float, float], b: tuple[float, float]) -> None:
        d.track(key, (_r(a[0]), _r(a[1])), (_r(b[0]), _r(b[1])), width=mm(WIDTH), net=net(key))

    def via(key: str, x: float, y: float) -> None:
        d.via(key, _r(x), _r(y), net=net(key), **VIA)

    half = WIDTH / 2
    for key, gap, x in (("t_in", IN, 5), ("t_out", OUT, 12)):  # the board ring's lower side
        track(key, (x, 50 - gap - half), (x + 5, 50 - gap - half))
    for key, gap, x in (("a_in", IN, 20), ("a_out", OUT, 35)):  # arcs whose apex faces the upper side
        top = gap + half
        d.track(
            key, (_r(x), _r(top + 1.5)), arc_to((_r(x + 5), _r(top)), (_r(x + 10), _r(top + 1.5))),
            width=mm(WIDTH), net=net(key),
        )  # fmt: skip
    for key, gap, y in (("v_in", IN, 10), ("v_out", OUT, 15)):  # the left side
        via(key, gap + 0.3, y)
    for ref, gap, y in (("P1", IN, 10), ("P2", OUT, 16)):  # the right side
        d.hole(ref, _r(80 - gap - 1), mm(y), drill=mm(1), pad=mm(2))
    track("c_in", (22 + IN + half, 23), (22 + IN + half, 27))  # the round cut-out, radius 2 mm
    track("c_out", (18 - OUT - half, 23), (18 - OUT - half, 27))
    via("s_in", 40, 24 - IN - 0.3)  # the long sides of S1 lie at y = 24 and 26 mm
    via("s_out", 40, 26 + OUT + 0.3)
    reach = 1 + IN + 0.3  # beyond the L's outer round corner about (65, 25) mm
    via("l_in", 65 + reach * DIAGONAL, 25 - reach * DIAGONAL)
    via("l_out", 65, 36 + OUT + 0.3)
    track("l_track", (56, 26 + IN + half), (62, 26 + IN + half))
    return d


def _fill_zones() -> tuple[Zone, ...]:
    """Two zones without a net on ``F.Cu``, 6 mm wide and 3 mm high, whose stored fill is their outline,
    ``FILLS`` away from the board ring's left side (board frame: the script's origin at 100 mm)."""
    zones: list[Zone] = []
    for k, (name, gap) in enumerate(FILLS.items()):
        top = (140 + 4 * k) * MM_NM
        left = round((100 + gap) * MM_NM)
        ring = (Point(left, top), Point(106 * MM_NM, top), Point(106 * MM_NM, top + 3 * MM_NM))
        ring = (*ring, Point(left, top + 3 * MM_NM))
        zones.append(
            Zone(
                id=f"zon_00000000-0000-4000-8000-0000000c0{k:03d}",
                outline=ring,
                name=name,
                layers=("F.Cu",),
                fills=(ZoneFill("F.Cu", ring),),
                settings=ZoneSettings(island_removal="never"),
            )
        )
    return tuple(zones)


@cache
def agree_files() -> tuple[tuple[str, str | bytes], ...]:
    """The agreement bench built for the running major, with the two zones and their stored fills added
    to the built board through the model and the board written again."""
    script = agree_script()
    output = build_script(script, target(), copper_intents=copper(script))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    files = {k: v for k, v in output.files.items() if not k.startswith(".fenolite/")}
    board = read_board(_text(files, f"{AGREE}.kicad_pcb"))
    assert board.board is not None
    zones = (*board.board.zones, *_fill_zones())
    board = dataclasses.replace(board, board=dataclasses.replace(board.board, zones=zones))
    files[f"{AGREE}.kicad_pcb"] = write_board(board, target=target()).text
    return tuple(files.items())


def _labels(design: Design) -> dict[str, str]:
    """KiCad uuid → the label of each copper item of the bench: its net name, the zone's name or the
    pad's reference."""
    assert design.board is not None
    nets = {net.id: net.name for net in design.circuit.nets}
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, str] = {}
    for item in (*design.board.tracks, *design.board.arcs, *design.board.vias):
        found[kicad_uuid(item)] = nets.get(item.net_id or "", "")
    for zone in design.board.zones:
        found[kicad_uuid(zone)] = zone.name
    for footprint in design.board.footprints:
        for pad in footprint.pads:
            found[kicad_uuid(pad)] = refs.get(footprint.component_id, footprint.id)
    return found


def _uuids(design: Design) -> dict[str, str]:
    """Entity id → KiCad uuid of each copper item of ``design``."""
    assert design.board is not None
    board = design.board
    found = {item.id: kicad_uuid(item) for item in (*board.tracks, *board.arcs, *board.vias, *board.zones)}
    found |= {pad.id: kicad_uuid(pad) for footprint in board.footprints for pad in footprint.pads}
    return found


@cache
def agree_sides() -> tuple[frozenset[str], frozenset[str]] | None:
    """The labels of the items reported by ``pcb drc`` and by Fenolite's check of the board read back
    (with the rules of its project, the frame's pads and edges), or ``None`` without a report."""
    files = dict(agree_files())
    report = drc(files, f"{AGREE}.kicad_pcb")
    if report is None:
        return None
    design = read_board(_text(files, f"{AGREE}.kicad_pcb"))
    labels = _labels(design)
    kicad = frozenset(labels[uuid] for uuid in edge_uuids(report) if uuid in labels)
    rules = design_rules_from_texts(
        design, project_text=_text(files, f"{AGREE}.kicad_pro"), rules_text=None, major=target()
    )
    frame = KicadBackend()
    checked = check_copper(
        rules.design,
        pads=frame.board_pads(rules.design),
        edges=frame.board_edges(rules.design),
        min_edge_clearance=rules.min_edge_clearance,
        edge_floor_over_rules=rules.edge_floor_over_rules,
    )
    uuids = _uuids(design)
    ours = frozenset(labels[uuids[f.items[0].entity_id]] for f in checked.findings if f.code == EDGE_CODE)
    return kicad, ours


def agree(fills: bool) -> str:
    """``equal`` when both sides report the same items: the fills alone with ``fills``, else every other
    item."""
    sides = agree_sides()
    if sides is None:
        return "inconclusive"
    kicad, ours = (frozenset(x for x in side if x.startswith("f_") == fills) for side in sides)
    return "equal" if kicad == ours else "different"


def edge_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: Probes = {}
    for label in CENTRE_GAPS:
        probes[f"edge-centre-{label}"] = (lambda label=label: centre(label), both)
    for rule in RESOLVE_RULES:
        for gap in RESOLVE_GAPS:
            probes[f"edge-resolve-{rule}-{gap}"] = (lambda rule=rule, gap=gap: resolve(rule, gap), both)
    probes["edge-agree"] = (lambda: agree(False), both)
    probes["edge-agree-fill"] = (lambda: agree(True), both)
    return probes


__all__ = [
    "AGREE",
    "CENTRE_GAPS",
    "EDGE",
    "FILLS",
    "RESOLVE_GAPS",
    "RESOLVE_RULES",
    "agree",
    "agree_files",
    "agree_script",
    "agree_sides",
    "built",
    "centre",
    "edge_probes",
    "edge_uuids",
    "pad_uuids",
    "resolve",
    "resolve_files",
    "rules_text",
    "slot_board",
]
