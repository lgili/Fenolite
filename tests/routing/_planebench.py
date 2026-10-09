# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The four-layer plane bench and the two-layer edge bench of change c0107 (capability kicad-oracle, "Plane
routing passes the oracle").

Authored for Fenolite with round invented values; every part comes from the built-in catalog, so the bench
needs no KiCad library. The plane bench is a 40 mm by 30 mm board of four copper layers:

- ``U1`` (``SOIC_8``), ``C1``, ``C2`` and ``R1`` (``Chip_0603``), ``J1`` and ``J2``
  (``Header_1x4_P2.5``), ``J3`` and ``J4`` (``Header_1x2_P2.5``);
- the plane nets ``GND`` (a zone over the board on ``In1.Cu``) and ``VCC`` (``In2.Cu``), class ``PWR``; their
  six SMD pads are ``C1-1``, ``C1-2``, ``C2-1``, ``C2-2``, ``U1-4`` and ``U1-8``, and ``J1`` and ``J2`` join
  both through their through-hole pads;
- the signals ``SIG1`` to ``SIG6`` (class ``SIG``, 0.2 mm width and clearance) and ``HV1``, ``HV2`` between
  ``J3`` and ``J4`` (class ``HV``, 0.5 mm and 0.3 mm);
- a rule of 1 mm between ``HV`` and ``SIG``, and a board edge clearance of 0.5 mm.

``bench_design`` gives the script's design, with ``planes=`` or without it and with or without its rules;
``build_project`` builds it in process into a folder, for target 9 or 10; ``load`` reads a built board with
what the routing code needs beside it; ``with_dogbones`` adds one hand-made track and via per SMD pad of
``GND`` and ``VCC``. ``edge_bench`` is the two-layer board whose only route passes a slot cut out of the
board, so its shortest route runs along a board edge.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
from dataclasses import dataclass
from pathlib import Path

from _placed import Part as PlacedPart
from _placed import design_of, pt
from _specctra import Bench, bench

import fenolite.cli.main as cli_main
from fenolite.backends.base import BoardPad, DesignRules
from fenolite.backends.kicad import copperrules
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import plane_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Net, Part, connect, mm, select
from fenolite.model.board import Track, Via
from fenolite.model.design import Design as ModelDesign
from fenolite.model.rules import Rule, RuleSet, Selector

NAME = "planebench"
WIDTH_MM, HEIGHT_MM = 40, 30
PLANE_LAYERS = ("In1.Cu", "In2.Cu")
PLANES = {"In1.Cu": "GND", "In2.Cu": "VCC"}
PLANE_PADS = ("C1-1", "C1-2", "C2-1", "C2-2", "U1-4", "U1-8")
"""The SMD pads of the two plane nets, in board footprint order then pad order."""
SIGNALS = ("SIG1", "SIG2", "SIG3", "SIG4", "SIG5", "SIG6")
HIGH = ("HV1", "HV2")
FOOTPRINTS = {
    "U1": "Fenolite:SOIC_8",
    "C1": "Fenolite:Chip_0603",
    "C2": "Fenolite:Chip_0603",
    "R1": "Fenolite:Chip_0603",
    "J1": "Fenolite:Header_1x4_P2.5",
    "J2": "Fenolite:Header_1x4_P2.5",
    "J3": "Fenolite:Header_1x2_P2.5",
    "J4": "Fenolite:Header_1x2_P2.5",
}
SIZES = {"width": 400_000, "via_diameter": 600_000, "via_drill": 300_000, "neck": 200_000}
"""The fan-out sizes of the bench: the values of the class ``PWR``."""
EDGE_CLEARANCE = 500_000
HV_SIG = 1_000_000
DOGBONES: dict[str, tuple[float, float]] = {
    "U1-4": (15.9, 13.095),
    "U1-8": (24.1, 16.905),
    "C1-1": (17.9, 8.0),
    "C1-2": (22.1, 8.0),
    "C2-1": (17.9, 22.0),
    "C2-2": (22.1, 22.0),
}
"""The via centre of the hand-made dog-bone of each SMD plane pad, in millimetres from the upper-left corner
of the outline: 1.3 mm or 1.4 mm outward from the pad's centre."""
SCRIPT = "from _planebench import bench_design\n\ndesign = bench_design({planes!r}, {rules!r}, {hv_near!r})\n"
"""A design script for ``fenolite build``: ``tests/routing`` is on the import path of the suites."""


def bench_design(planes: bool = True, rules: bool = True, hv_near: bool = False) -> Design:
    """The bench as a design script gives it. Without ``planes`` the inner layers stay signal layers (the
    zones stay); without ``rules`` the classes, the 1 mm rule and the edge clearance are left out. With
    ``hv_near`` the header ``J3`` stands in the upper right corner, so the ``HV`` nets must pass the pads
    and the wires of ``SIG`` on their way to ``J4``: the variant of the class-to-class gate."""
    design = Design(NAME)
    nets = {name: Net(name) for name in ("GND", "VCC", *SIGNALS, *HIGH)}
    gnd, vcc = nets["GND"], nets["VCC"]
    if planes:
        design.board(mm(WIDTH_MM), mm(HEIGHT_MM), copper=4, planes={"In1.Cu": gnd, "In2.Cu": vcc})
    else:
        design.board(mm(WIDTH_MM), mm(HEIGHT_MM), copper=4)
    u1 = Part("U1", "Fenolite:Microcontroller", footprint=FOOTPRINTS["U1"], value="MCU")
    c1 = Part("C1", "Fenolite:Capacitor", footprint=FOOTPRINTS["C1"], value="100n")
    c2 = Part("C2", "Fenolite:Capacitor", footprint=FOOTPRINTS["C2"], value="100n")
    r1 = Part("R1", "Fenolite:Resistor", footprint=FOOTPRINTS["R1"], value="1k")
    j1 = Part("J1", "Fenolite:Connector_4", footprint=FOOTPRINTS["J1"], value="IN")
    j2 = Part("J2", "Fenolite:Connector_4", footprint=FOOTPRINTS["J2"], value="OUT")
    j3 = Part("J3", "Fenolite:Connector_2", footprint=FOOTPRINTS["J3"], value="HV")
    j4 = Part("J4", "Fenolite:Connector_2", footprint=FOOTPRINTS["J4"], value="HV")
    design.add(u1, c1, c2, r1, j1, j2, j3, j4)
    connect(vcc, j1[1], u1[8], c1[1], c2[1], j2[4])
    connect(gnd, j1[2], u1[4], c1[2], c2[2], j2[3])
    connect(nets["SIG1"], u1[1], j1[3])
    connect(nets["SIG2"], u1[2], j1[4])
    connect(nets["SIG3"], u1[3], r1[1])
    connect(nets["SIG4"], u1[5], r1[2])
    connect(nets["SIG5"], u1[6], j2[1])
    connect(nets["SIG6"], u1[7], j2[2])
    connect(nets["HV1"], j3[1], j4[1])
    connect(nets["HV2"], j3[2], j4[2])
    if rules:
        design.rules.netclass(
            "PWR", clearance=mm(0.2), track_width=mm(0.4), via_diameter=mm(0.6), via_drill=mm(0.3),
            nets=(gnd, vcc),
        )  # fmt: skip
        design.rules.netclass(
            "SIG", clearance=mm(0.2), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3),
            nets=tuple(nets[name] for name in SIGNALS),
        )  # fmt: skip
        design.rules.netclass(
            "HV", clearance=mm(0.3), track_width=mm(0.5), via_diameter=mm(0.6), via_drill=mm(0.3),
            nets=tuple(nets[name] for name in HIGH),
        )  # fmt: skip
        design.rules.rule(
            "hv-sig", "clearance", where=select.netclass("HV"), between=select.netclass("SIG"), min=mm(1)
        )
        design.rules.minimum(edge_clearance=mm(0.5))
    design.zone(gnd, layers=("In1.Cu",))
    design.zone(vcc, layers=("In2.Cu",))
    u1.place(mm(20), mm(15))
    c1.place(mm(20), mm(8))
    c2.place(mm(20), mm(22))
    r1.place(mm(28), mm(9))
    j1.place(mm(5), mm(15))
    j2.place(mm(35), mm(15))
    j3.place(*((mm(28), mm(4)) if hv_near else (mm(10), mm(26))))
    j4.place(mm(30), mm(26))
    return design


def write_script(
    folder: Path, *, planes: bool = True, rules: bool = True, hv_near: bool = False, append: str = ""
) -> Path:
    """``design.py`` under ``folder`` that builds the bench; ``append`` adds lines to it."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    text = SCRIPT.format(planes=planes, rules=rules, hv_near=hv_near)
    script.write_text(text + append, encoding="utf-8")
    return script


def run_cli(*args: str) -> tuple[int, dict[str, object], str]:
    """One command of the CLI in this process: its exit code, its reply and its error text."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main.main([*args, "--json"])
    return code, (json.loads(out.getvalue()) if out.getvalue() else {}), err.getvalue()


def build_project(
    folder: Path,
    *,
    target: int = 10,
    planes: bool = True,
    rules: bool = True,
    hv_near: bool = False,
    append: str = "",
) -> Path:
    """The bench built into ``folder / "out"`` for ``target``; returns the board file."""
    script = write_script(folder, planes=planes, rules=rules, hv_near=hv_near, append=append)
    out = folder / "out"
    code, env, err = run_cli(
        "--kicad-version", str(target), "build", str(script), "--out", str(out), "--confirm"
    )
    errors = [i for i in env.get("issues", ()) if i["severity"] == "error"]  # type: ignore[union-attr, index]
    assert code == 0, (err, errors)
    return out / f"{NAME}.kicad_pcb"


@dataclass(frozen=True)
class Loaded:
    """A built bench: the board design with the project's classes and rules, its board-frame pads, its
    outline rings, its plane layers and the project's rules as the copper check takes them."""

    design: ModelDesign
    pads: tuple[BoardPad, ...]
    outline: tuple[tuple[Point, ...], ...]
    plane_layers: tuple[str, ...]
    rules: DesignRules

    def net_id(self, name: str) -> str:
        return next(net.id for net in self.design.circuit.nets if net.name == name)

    def pad(self, where: str) -> BoardPad:
        return next(pad for pad in self.pads if f"{pad.ref}-{pad.number}" == where)


def load(board: Path) -> Loaded:
    """The built board at ``board`` with its project and rules files applied."""
    design = read_board(board)
    texts = {
        suffix: board.with_suffix(suffix).read_text(encoding="utf-8")
        if board.with_suffix(suffix).is_file()
        else None
        for suffix in (".kicad_pro", ".kicad_dru")
    }
    rules = copperrules.design_rules_from_texts(
        design,
        project_text=texts[".kicad_pro"],
        rules_text=texts[".kicad_dru"],
        major=copperrules.project_major(texts[".kicad_pro"]),
        file_stem=board.stem,
    )
    assert rules.unread == (), rules.unread
    return loaded(rules.design, rules)


def loaded(design: ModelDesign, rules: DesignRules | None = None) -> Loaded:
    rings = tuple(tuple(ring) for ring in board_outline(design).rings)
    return Loaded(
        design, board_pads(design), rings, plane_layers(design), rules or DesignRules(design=design)
    )


def with_rules(found: Loaded, *rules: Rule, replace: bool = False) -> Loaded:
    """``found`` with ``rules`` added to its design's rules (or in their place)."""
    held = () if replace or found.design.rules is None else found.design.rules.rules
    ruleset = RuleSet(id=derived_id("rst", "planebench", "rules"), rules=(*held, *rules))
    design = dataclasses.replace(found.design, rules=ruleset if ruleset.rules else None)
    return dataclasses.replace(found, design=design, rules=dataclasses.replace(found.rules, design=design))


def no_tracks(name: str, selector: Selector, *layers: str) -> Rule:
    return Rule(
        id=derived_id("rul", "planebench", name), name=name, kind="no_tracks", selector_a=selector,
        layers=layers,
    )  # fmt: skip


def at(x: float, y: float, design: ModelDesign) -> Point:
    """A point in millimetres from the upper-left corner of the outline, in the board frame."""
    ring = board_outline(design).rings[0]
    return Point(min(p.x for p in ring) + round(x * 1_000_000), min(p.y for p in ring) + round(y * 1_000_000))


def with_dogbones(found: Loaded) -> Loaded:
    """``found`` with one 0.4 mm track and one 0.6/0.3 mm through via per SMD pad of ``GND`` and ``VCC``,
    at the hand-chosen places of ``DOGBONES``."""
    board = found.design.board
    assert board is not None
    copper = tuple(
        layer.name for layer in sorted(board.layers, key=lambda la: la.ordinal) if layer.kind == "copper"
    )
    tracks: list[Track] = []
    vias: list[Via] = []
    for where, (x, y) in DOGBONES.items():
        pad = found.pad(where)
        centre = at(x, y, found.design)
        tracks.append(
            Track(
                id=derived_id("trk", "planebench", where),
                start=pad.position,
                end=centre,
                width=SIZES["width"],
                layer="F.Cu",
                net_id=pad.net_id,
            )  # fmt: skip
        )
        vias.append(
            Via(
                id=derived_id("via", "planebench", where),
                position=centre,
                diameter=SIZES["via_diameter"],
                drill=SIZES["via_drill"],
                layers=(copper[0], copper[-1]),
                net_id=pad.net_id,
            )  # fmt: skip
        )
    design = dataclasses.replace(
        found.design,
        board=dataclasses.replace(board, tracks=(*board.tracks, *tracks), vias=(*board.vias, *vias)),
    )
    return dataclasses.replace(found, design=design, rules=dataclasses.replace(found.rules, design=design))


# -- the edge bench

EDGE_PASSAGE = 2
"""The board left above and below the slot of the edge bench, in millimetres."""
EDGE_RULE = 500_000


def edge_slot(passage: float = EDGE_PASSAGE) -> tuple[Point, ...]:
    """A slot 1 mm wide cut out of the 30 mm by 20 mm board of ``_specctra.OUTLINE``, between the two pads
    of the net ``A``: ``passage`` millimetres of board stay above it and below it."""
    return (pt(14.5, passage), pt(15.5, passage), pt(15.5, 20 - passage), pt(14.5, 20 - passage))


EDGE_SLOT = edge_slot()


def edge_rule(minimum: int = EDGE_RULE) -> Rule:
    return Rule(
        id=derived_id("rul", "planebench", "edge"), name="edge", kind="edge_clearance",
        selector_a=Selector("all"), min=minimum,
    )  # fmt: skip


def edge_bench(minimum: int | None = EDGE_RULE, passage: float = EDGE_PASSAGE, *, target: int = 10) -> Bench:
    """Two 0603 parts 10 mm apart on a two-layer board with the slot of ``edge_slot(passage)`` between
    them: the one net ``A`` must pass an end of the slot, so its shortest route runs along that board
    edge. With ``minimum`` the design holds a board-wide ``edge_clearance`` rule of that value. ``target``
    is the KiCad major its board is written for (the footprint files of that major)."""
    made = bench(
        design_of(
            PlacedPart("R1", "Mini_R_0603", 10, 10, nets={"2": "A"}),
            PlacedPart("R2", "Mini_R_0603", 20, 10, nets={"1": "A"}),
            target=target,
        ),
        cutouts=(edge_slot(passage),),
    )
    if minimum is None:
        return made
    rules = RuleSet(id=derived_id("rst", "planebench", "edge"), rules=(edge_rule(minimum),))
    return dataclasses.replace(made, design=dataclasses.replace(made.design, rules=rules))


__all__ = [
    "DOGBONES",
    "EDGE_CLEARANCE",
    "EDGE_PASSAGE",
    "EDGE_RULE",
    "EDGE_SLOT",
    "FOOTPRINTS",
    "HIGH",
    "HV_SIG",
    "NAME",
    "PLANES",
    "PLANE_LAYERS",
    "PLANE_PADS",
    "SIGNALS",
    "SIZES",
    "Loaded",
    "at",
    "bench_design",
    "build_project",
    "edge_bench",
    "edge_rule",
    "edge_slot",
    "load",
    "loaded",
    "no_tracks",
    "run_cli",
    "with_dogbones",
    "with_rules",
    "write_script",
]
