# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The length benches (capability kicad-oracle, "Net length parity canaries"; change c0106).

Boards built through the model and written by ``write_board`` for a major, one net per measured behaviour.
Every value is authored for the benches: tracks of 0.25 mm, vias of 0.6 mm, the pads of ``Mini_R_0603``
(0.9 mm × 0.95 mm, 0.8 mm from the part's origin) and of ``Mini_LED_THT_3mm``, round lengths, and
stack-ups of round thicknesses. The hermetic half is ``tests/unit/backends/kicad/test_lengths.py`` and
``tests/unit/analysis/test_length.py``; the oracle half is ``tests/kicad/length/test_length_parity.py``.

A case is a board, the text of its project file and the nets it measures:

- ``two``: two layers, a 1.6 mm board without a stack-up;
- ``two-stackup``: the same copper with a stack-up of 35 µm, 1230 µm and 35 µm;
- ``two-noheight``: ``two`` with ``use_height_for_length_calcs`` set to ``false`` in the project;
- ``four``: four layers without a stack-up;
- ``four-explicit``: the same copper with the stack-up ``FOUR_EXPLICIT``;
- ``four-unprojected``: ``four-explicit`` whose stack-up node lost its silkscreen and paste rows, so the
  reader projects no stack-up (``kicad.board.stackup-unused``);
- ``six`` and ``eight``: six and eight layers without a stack-up (the layer counts of change c0100);
- ``rules``: the nets of the skew and length rules.

Every board holds the canary pair of the rules benches, two tracks on ``CANARY_A`` and ``CANARY_B`` 1 mm
apart, for the scoped canary rule of c0071.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from _boards import stack_entry, stack_of

from fenolite.backends.base import ProjectSet
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.model.board import (
    Arc,
    Board,
    FootprintInstance,
    Outline,
    Side,
    Stackup,
    Track,
    Via,
    ViaType,
    Zone,
    ZoneFill,
)
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "tests" / "data" / "libs"
CANARY_FILE = ROOT / "tests" / "data" / "kicad" / "tokens" / "canary" / "canary.kicad_dru"
MM = 1_000_000
UM = 1_000
WIDTH = 250_000
STEM = "bench"
PROJECT = "{}\n"
NO_HEIGHT_PROJECT = (
    json.dumps({"board": {"design_settings": {"rules": {"use_height_for_length_calcs": False}}}}, indent=2)
    + "\n"
)
CANARY_NETS = ("CANARY_A", "CANARY_B")
DIE_PAD = ("R12", "2")
DIE_TEXT = "1.5"
CASES = (
    "two", "two-stackup", "two-noheight", "four", "four-explicit", "four-unprojected", "six", "eight",
    "rules",
)  # fmt: skip
VIA_CASES = ("four", "four-explicit", "four-unprojected", "six", "eight")
"""The cases whose probe is ``length-via-<case>``; the others are ``length-total-<case>``."""

TWO_NETS = (
    "L_ARC", "L_BRANCH", "L_CC", "L_COL", "L_DIE", "L_EE", "L_PASS", "L_THT", "L_THT2", "L_VIA2", "L_VIAPAD",
)  # fmt: skip
FOUR_NETS = (
    "DOGBONE", "VIP", "VIP_BOT", "V_BLIND", "V_F_B", "V_F_F", "V_F_IN1", "V_F_IN2", "V_IN1_B", "V_IN1_IN2",
    "V_SERIES", "V_THREE", "V_ZONE",
)  # fmt: skip
MANY_NETS = ("M_BLIND", "M_F_B", "M_F_IN1", "M_INNER", "M_IN1_LAST")
RULES_NETS = ("BUS0", "BUS1", "BUS2", "NOTRK", "OPTONLY", "SHORT", "SK_N", "SK_P")


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


TWO_STACKUP = stack_of(
    stack_entry("F.Cu", "copper", 35 * UM),
    stack_entry("dielectric 1", "dielectric", 1230 * UM, dielectric_kind="core", material="FR4"),
    stack_entry("B.Cu", "copper", 35 * UM),
)
FOUR_EXPLICIT = stack_of(
    stack_entry("F.Cu", "copper", 35 * UM),
    stack_entry("dielectric 1", "dielectric", 110 * UM, dielectric_kind="prepreg", material="FR4"),
    stack_entry("In1.Cu", "copper", 17_500),
    stack_entry("dielectric 2", "dielectric", 1230 * UM, dielectric_kind="core", material="FR4"),
    stack_entry("In2.Cu", "copper", 17_500),
    stack_entry("dielectric 3", "dielectric", 155 * UM, dielectric_kind="prepreg", material="FR4"),
    stack_entry("B.Cu", "copper", 35 * UM),
)
"""The explicit stack-up of the four-layer bench: 1.6 mm of copper and dielectric."""


@dataclass
class Builder:
    """Collects nets, copper and parts of one bench board."""

    target: int
    copper: int = 2
    stackup: Stackup | None = None
    nets: dict[str, Net] = field(default_factory=lambda: {})
    tracks: list[Track] = field(default_factory=lambda: [])
    arcs: list[Arc] = field(default_factory=lambda: [])
    vias: list[Via] = field(default_factory=lambda: [])
    zones: list[Zone] = field(default_factory=lambda: [])
    footprints: list[FootprintInstance] = field(default_factory=lambda: [])
    components: list[Component] = field(default_factory=lambda: [])
    members: dict[str, list[PinRef]] = field(default_factory=lambda: {})

    def net(self, name: str) -> str:
        if name not in self.nets:
            self.nets[name] = Net(id=_id("net", len(self.nets) + 1), name=name)
        return self.nets[name].id

    def track(self, net: str, a: Point, b: Point, layer: str = "F.Cu") -> Track:
        made = Track(
            id=_id("trk", len(self.tracks) + 1),
            start=a,
            end=b,
            width=WIDTH,
            layer=layer,
            net_id=self.net(net),
        )
        self.tracks.append(made)
        return made

    def arc(self, net: str, a: Point, m: Point, b: Point, layer: str = "F.Cu") -> Arc:
        made = Arc(
            id=_id("arc", len(self.arcs) + 1), start=a, mid=m, end=b, width=WIDTH, layer=layer,
            net_id=self.net(net),
        )  # fmt: skip
        self.arcs.append(made)
        return made

    def via(
        self, net: str, at: Point, layers: tuple[str, str] = ("F.Cu", "B.Cu"), kind: ViaType = "through"
    ) -> Via:
        made = Via(
            id=_id("via", len(self.vias) + 1), position=at, diameter=600_000, drill=300_000, layers=layers,
            net_id=self.net(net), via_type=kind,
        )  # fmt: skip
        self.vias.append(made)
        return made

    def zone_fill(self, net: str, layer: str, ring: Sequence[Point]) -> Zone:
        """A zone whose stored fill is its own outline."""
        made = Zone(
            id=_id("zon", len(self.zones) + 1), outline=tuple(ring), name=net, layers=(layer,),
            net_id=self.net(net), fills=(ZoneFill(layer, tuple(ring)),), filled=True,
        )  # fmt: skip
        self.zones.append(made)
        return made

    def _layers(self) -> tuple[str, ...]:
        return tuple(la.name for la in created_layers(self.copper) if la.kind == "copper")  # type: ignore[arg-type]

    def _place(self, ref: str, at: Point, footprint: str, side: Side) -> tuple[Component, FootprintInstance]:
        folder = "Mini.pretty" if self.target >= 10 else "Mini_v9.pretty"
        defn = read_footprint(LIBS / folder / f"{footprint}.kicad_mod", library="Mini")
        component = Component(
            id=_id("cmp", len(self.components) + 1), ref=ref, value=footprint, lib_footprint_ref=defn.lib_id
        )
        placed = place_footprint(defn, component=component, at=at, key=ref, side=side, copper=self._layers())
        return component, placed

    def _pad_points(self, component: Component, placed: FootprintInstance) -> dict[str, Point]:
        base = Design.new("probe", seed=0)
        board = Board(id=_id("brd", 9), layers=created_layers(self.copper), footprints=(placed,))  # type: ignore[arg-type]
        probe = dataclasses.replace(base, circuit=Circuit(components=(component,)), board=board)
        return {pad.number: pad.position for pad in board_pads(probe)}

    def part(
        self,
        ref: str,
        at: Point,
        nets: Mapping[str, str],
        *,
        footprint: str = "Mini_R_0603",
        side: Side = "top",
        pad_at: str | None = None,
    ) -> dict[str, Point]:
        """One placed part whose pad ``number`` is on the net ``nets[number]``; the pad positions in the
        board frame. With ``pad_at``, the part is moved so that this pad lies at ``at``."""
        component, placed = self._place(ref, at, footprint, side)
        if pad_at is not None:
            found = self._pad_points(component, placed)[pad_at]
            component, placed = self._place(
                ref, Point(2 * at.x - found.x, 2 * at.y - found.y), footprint, side
            )
        pads = tuple(
            dataclasses.replace(pad, net_id=self.net(nets[pad.number]) if pad.number in nets else None)
            for pad in placed.pads
        )
        placed = dataclasses.replace(placed, pads=pads)
        for pad in pads:
            if pad.net_id is not None:
                self.members.setdefault(pad.net_id, []).append(PinRef(component.id, pad.number))
        self.components.append(component)
        self.footprints.append(placed)
        return self._pad_points(component, placed)

    def canary(self) -> None:
        self.track(CANARY_NETS[0], mm(10, 5), mm(20, 5))
        self.track(CANARY_NETS[1], mm(10, 6), mm(20, 6))

    def build(self, name: str, size: tuple[int, int] = (85, 120)) -> Design:
        nets = tuple(
            dataclasses.replace(n, members=tuple(self.members.get(n.id, ()))) for n in self.nets.values()
        )
        board = Board(
            id=_id("brd", 1),
            outline=Outline(id=_id("out", 1), points=(mm(0, 0), mm(size[0], 0), mm(*size), mm(0, size[1]))),
            layers=created_layers(self.copper),  # type: ignore[arg-type]
            stackup=self.stackup,
            footprints=tuple(self.footprints),
            tracks=tuple(self.tracks),
            arcs=tuple(self.arcs),
            vias=tuple(self.vias),
            zones=tuple(self.zones),
        )
        base = Design.new(name, seed=0)
        return dataclasses.replace(
            base, circuit=Circuit(components=tuple(self.components), nets=nets), board=board
        )


def _two(target: int, stackup: Stackup | None) -> Design:
    b = Builder(target, 2, stackup)
    b.canary()
    # a track through a pad, ending 0.8 mm beyond its centre
    left = b.part("R16", mm(50, 20), {"2": "L_PASS"})
    right = b.part("R17", mm(70, 20), {"1": "L_PASS"})
    assert (left["2"], right["1"]) == (mm(50.8, 20), mm(69.2, 20))
    b.track("L_PASS", mm(50, 20), mm(69.2, 20))
    # 4.2 mm, a half circle of radius 3 mm, 8.2 mm
    b.part("R3", mm(10, 30), {"2": "L_ARC"})
    b.part("R4", mm(30, 30), {"1": "L_ARC"})
    b.track("L_ARC", mm(10.8, 30), mm(15, 30))
    b.arc("L_ARC", mm(15, 30), mm(18, 33), mm(21, 30))
    b.track("L_ARC", mm(21, 30), mm(29.2, 30))
    # pad centre to pad centre
    b.part("R1", mm(10, 40), {"2": "L_CC"})
    b.part("R2", mm(30, 40), {"1": "L_CC"})
    b.track("L_CC", mm(10.8, 40), mm(29.2, 40))
    # pad edge to pad edge
    b.part("R5", mm(10, 50), {"2": "L_EE"})
    b.part("R6", mm(30, 50), {"1": "L_EE"})
    b.track("L_EE", mm(11.25, 50), mm(28.75, 50))
    # two collinear segments
    b.part("R13", mm(10, 60), {"2": "L_COL"})
    b.part("R14", mm(30, 60), {"1": "L_COL"})
    b.track("L_COL", mm(10.8, 60), mm(20, 60))
    b.track("L_COL", mm(20, 60), mm(29.2, 60))
    # two tracks of 9.2 mm between two pads, and a 5 mm stub to a third pad
    b.part("R9", mm(10, 70), {"2": "L_BRANCH"})
    b.part("R10", mm(30, 70), {"1": "L_BRANCH"})
    b.part("R11", mm(20, 75), {"1": "L_BRANCH"}, pad_at="1")
    b.track("L_BRANCH", mm(10.8, 70), mm(20, 70))
    b.track("L_BRANCH", mm(20, 70), mm(29.2, 70))
    b.track("L_BRANCH", mm(20, 70), mm(20, 75))
    # a die length on one pad (the token is put into the written text)
    b.part("R12", mm(10, 85), {"2": "L_DIE"})
    b.part("R15", mm(30, 85), {"1": "L_DIE"})
    b.track("L_DIE", mm(10.8, 85), mm(29.2, 85))
    # 10 mm on F.Cu, a through via, 10 mm on B.Cu
    b.track("L_VIA2", mm(10, 95), mm(20, 95))
    b.via("L_VIA2", mm(20, 95))
    b.track("L_VIA2", mm(20, 95), mm(30, 95), "B.Cu")
    # a top pad, a via, the pad of a part on the bottom side
    b.part("R7", mm(10, 105), {"2": "L_VIAPAD"})
    b.part("R8", mm(29.2, 105), {"1": "L_VIAPAD"}, side="bottom", pad_at="1")
    b.track("L_VIAPAD", mm(10.8, 105), mm(20, 105))
    b.via("L_VIAPAD", mm(20, 105))
    b.track("L_VIAPAD", mm(20, 105), mm(29.2, 105), "B.Cu")
    # through-hole pads joined on F.Cu
    b.part("D1", mm(52.54, 40), {"2": "L_THT"}, footprint="Mini_LED_THT_3mm", pad_at="2")
    b.part("D2", mm(72.54, 40), {"1": "L_THT"}, footprint="Mini_LED_THT_3mm", pad_at="1")
    b.track("L_THT", mm(52.54, 40), mm(72.54, 40))
    # 10 mm on F.Cu into a through-hole pad, 10 mm on B.Cu out of it
    b.part("D3", mm(52.54, 55), {"2": "L_THT2"}, footprint="Mini_LED_THT_3mm", pad_at="2")
    b.part("D4", mm(62.54, 55), {"1": "L_THT2"}, footprint="Mini_LED_THT_3mm", pad_at="1")
    b.part("D5", mm(62.54, 65), {"1": "L_THT2"}, footprint="Mini_LED_THT_3mm", pad_at="1")
    b.track("L_THT2", mm(52.54, 55), mm(62.54, 55))
    b.track("L_THT2", mm(62.54, 55), mm(62.54, 65), "B.Cu")
    return b.build("length-two")


def _four(target: int, stackup: Stackup | None) -> Design:
    b = Builder(target, 4, stackup)
    b.canary()

    def joined(net: str, y: int, first: str, second: str, layers: tuple[str, str] = ("F.Cu", "B.Cu"),
               kind: ViaType = "through") -> None:  # fmt: skip
        b.track(net, mm(10, y), mm(20, y), first)
        b.via(net, mm(20, y), layers, kind)
        b.track(net, mm(20, y), mm(30, y), second)

    joined("V_F_IN1", 20, "F.Cu", "In1.Cu")
    joined("V_F_IN2", 30, "F.Cu", "In2.Cu")
    joined("V_F_B", 40, "F.Cu", "B.Cu")
    joined("V_IN1_IN2", 50, "In1.Cu", "In2.Cu")
    joined("V_IN1_B", 60, "In1.Cu", "B.Cu")
    joined("V_BLIND", 70, "F.Cu", "In1.Cu", ("F.Cu", "In1.Cu"), "blind")
    joined("V_F_F", 80, "F.Cu", "F.Cu")
    joined("V_THREE", 90, "F.Cu", "B.Cu")
    b.track("V_THREE", mm(20, 90), mm(20, 95), "In1.Cu")
    # two vias in series: F.Cu, In1.Cu, B.Cu
    b.track("V_SERIES", mm(10, 105), mm(20, 105))
    b.via("V_SERIES", mm(20, 105))
    b.track("V_SERIES", mm(20, 105), mm(30, 105), "In1.Cu")
    b.via("V_SERIES", mm(30, 105))
    b.track("V_SERIES", mm(30, 105), mm(40, 105), "B.Cu")
    # a via in each end pad, the track on In1.Cu
    b.part("R1", mm(50, 20), {"2": "VIP"})
    b.part("R2", mm(70, 20), {"1": "VIP"})
    b.via("VIP", mm(50.8, 20))
    b.track("VIP", mm(50.8, 20), mm(69.2, 20), "In1.Cu")
    b.via("VIP", mm(69.2, 20))
    # a dog-bone: 1 mm on F.Cu, a via, 16.4 mm on In1.Cu, a via, 1 mm on F.Cu
    b.part("R3", mm(50, 30), {"2": "DOGBONE"})
    b.part("R4", mm(70, 30), {"1": "DOGBONE"})
    b.track("DOGBONE", mm(50.8, 30), mm(51.8, 30))
    b.via("DOGBONE", mm(51.8, 30))
    b.track("DOGBONE", mm(51.8, 30), mm(68.2, 30), "In1.Cu")
    b.via("DOGBONE", mm(68.2, 30))
    b.track("DOGBONE", mm(68.2, 30), mm(69.2, 30))
    # an F.Cu track to a via in the pad of a part on the bottom side
    b.part("R5", mm(50, 40), {"2": "VIP_BOT"})
    b.part("R6", mm(69.2, 40), {"1": "VIP_BOT"}, side="bottom", pad_at="1")
    b.track("VIP_BOT", mm(50.8, 40), mm(69.2, 40))
    b.via("VIP_BOT", mm(69.2, 40))
    # an F.Cu track to a via whose In2.Cu copper is a stored zone fill of its net
    b.track("V_ZONE", mm(50, 55), mm(60, 55))
    b.via("V_ZONE", mm(60, 55))
    b.zone_fill("V_ZONE", "In2.Cu", (mm(58, 53), mm(62, 53), mm(62, 57), mm(58, 57)))
    return b.build("length-four")


def _many(target: int, copper: int) -> Design:
    """Six or eight layers without a stack-up: two 10 mm tracks joined by one via per net."""
    b = Builder(target, copper)
    b.canary()
    last = f"In{copper - 2}.Cu"
    rows: tuple[tuple[str, str, str, tuple[str, str], ViaType], ...] = (
        ("M_F_IN1", "F.Cu", "In1.Cu", ("F.Cu", "B.Cu"), "through"),
        ("M_F_B", "F.Cu", "B.Cu", ("F.Cu", "B.Cu"), "through"),
        ("M_INNER", "In2.Cu", "In3.Cu", ("F.Cu", "B.Cu"), "through"),
        ("M_IN1_LAST", "In1.Cu", last, ("F.Cu", "B.Cu"), "through"),
        ("M_BLIND", "F.Cu", "In2.Cu", ("F.Cu", "In2.Cu"), "blind"),
    )
    for k, (net, first, second, layers, kind) in enumerate(rows):
        y = 20 + 10 * k
        b.track(net, mm(10, y), mm(20, y), first)
        b.via(net, mm(20, y), layers, kind)
        b.track(net, mm(20, y), mm(30, y), second)
    return b.build(f"length-{copper}", (45, 80))


def _rules(target: int) -> Design:
    b = Builder(target, 2)
    b.canary()
    b.track("SK_P", mm(10, 20), mm(30, 20))
    b.track("SK_N", mm(10, 25), mm(31, 25))
    b.track("BUS0", mm(10, 35), mm(30, 35))
    b.track("BUS1", mm(10, 40), mm(31, 40))
    b.track("BUS2", mm(10, 45), mm(33, 45))
    for k, net in enumerate(("SHORT", "NOTRK", "OPTONLY")):
        y = 55 + 7 * k
        b.part(f"R{2 * k + 1}", mm(10, y), {"2": net})
        b.part(f"R{2 * k + 2}", mm(14, y), {"1": net})
        if net != "NOTRK":
            b.track(net, mm(10.8, y), mm(13.2, y))
    return b.build("length-rules", (45, 85))


@cache
def bench(case: str, target: int) -> Design:
    """The model design of ``case`` for ``target`` (the die length is only in the written text)."""
    if case in ("two", "two-noheight"):
        return _two(target, None)
    if case == "two-stackup":
        return _two(target, TWO_STACKUP)
    if case == "four":
        return _four(target, None)
    if case in ("four-explicit", "four-unprojected"):
        return _four(target, FOUR_EXPLICIT)
    if case in ("six", "eight"):
        return _many(target, 6 if case == "six" else 8)
    if case == "rules":
        return _rules(target)
    raise KeyError(case)


def nets_of(case: str) -> tuple[str, ...]:
    """The measured nets of a case, in name order."""
    if case.startswith("two"):
        return TWO_NETS
    if case in ("six", "eight"):
        return MANY_NETS
    return FOUR_NETS if case.startswith("four") else RULES_NETS


def project_text(case: str) -> str:
    return NO_HEIGHT_PROJECT if case == "two-noheight" else PROJECT


def _with_die(text: str, design: Design) -> str:
    """``text`` with ``(die_length 1.5)`` in the pad ``DIE_PAD``, right before its uuid."""
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    for footprint in design.board.footprints:
        if refs[footprint.component_id] != DIE_PAD[0]:
            continue
        for pad in footprint.pads:
            if pad.number == DIE_PAD[1]:
                line = f'(uuid "{kicad_uuid(pad)}")'
                assert text.count(line) == 1
                return text.replace(line, f"(die_length {DIE_TEXT})\n\t\t\t{line}")
    raise AssertionError("the bench has no die pad")


def _without_outer_rows(text: str) -> str:
    """The board text whose stack-up node holds no silkscreen and no paste row."""
    root = parse(text)
    setup = root.find("setup")
    assert setup is not None
    node = setup.find("stackup")
    assert node is not None

    def outer(child: Node | Atom) -> bool:
        if not (isinstance(child, Node) and child.name == "layer"):
            return False
        first = child.children[0]
        return isinstance(first, Atom) and first.value.endswith((".SilkS", ".Paste"))

    kept = node.with_children(c for c in node.children if not outer(c))
    assert len(kept.children) == len(node.children) - 4
    new_setup = setup.with_children(kept if c is node else c for c in setup.children)
    return dumps(root.with_children(new_setup if c is setup else c for c in root.children))


@cache
def bench_text(case: str, target: int) -> str:
    """The board file of ``case`` written for ``target``."""
    design = bench(case, target)
    text = write_board(design, target=target).text
    if case.startswith("two"):
        text = _with_die(text, design)
    if case == "four-unprojected":
        text = _without_outer_rows(text)
    return text


def read_bench(case: str, target: int) -> Design:
    """The bench as the reader gives it back from its written text."""
    return read_board(bench_text(case, target))


def write_case(case: str, target: int, folder: Path, rules: str | None = None) -> ProjectSet:
    """The board, the project file and, when given, the rules file of ``case`` in ``folder``."""
    board = folder / f"{STEM}.kicad_pcb"
    board.write_text(bench_text(case, target), encoding="utf-8", newline="\n")
    project = folder / f"{STEM}.kicad_pro"
    project.write_text(project_text(case), encoding="utf-8", newline="\n")
    files = {board.name: board, project.name: project}
    if rules is not None:
        dru = folder / f"{STEM}.kicad_dru"
        dru.write_text(rules, encoding="utf-8", newline="\n")
        files[dru.name] = dru
    return ProjectSet(folder, board.name, files, has_project=True, has_rules=rules is not None)


# --- rules texts ------------------------------------------------------------------------------------


@cache
def scoped_canary() -> str:
    """The canary rule of ``canary.kicad_dru`` with the condition ``A.NetName == 'CANARY_A'`` (c0071)."""
    lines = CANARY_FILE.read_text(encoding="utf-8").splitlines()
    rule = "\n".join(line for line in lines if not line.startswith("(version")).strip() + "\n"
    head, sep, rest = rule.partition("\n")
    return f"{head}{sep}\t(condition \"A.NetName == '{CANARY_NETS[0]}'\")\n{rest}"


def _mm_text(value: int) -> str:
    """``value`` nm as a decimal of millimetres with six places."""
    return f"{value // MM}.{value % MM:06d}"


def bracket_rules(totals: Mapping[str, int], delta: int) -> str:
    """A rules file with the scoped canary and one rule ``length (max total + delta)`` per net."""
    parts = ["(version 1)\n", scoped_canary()]
    for net in sorted(totals):
        limit = max(totals[net] + delta, 0)
        parts.append(
            f'(rule "len_{net}"\n\t(constraint length (max {_mm_text(limit)}mm))\n'
            f"\t(condition \"A.NetName == '{net}'\")\n)\n"
        )
    return "".join(parts)


RULES_TEXTS: Mapping[str, str] = {
    "skew-pair": '(rule "sk"\n\t(constraint skew (max 0.1mm) (within_diff_pairs))\n'
    "\t(condition \"A.inDiffPair('SK')\")\n)\n",
    "skew-bus": '(rule "bus"\n\t(constraint skew (max 0.1mm))\n\t(condition "A.NetName == \'BUS*\'")\n)\n',
    "length-range": '(rule "range"\n\t(constraint length (min 5mm) (max 50mm))\n'
    "\t(condition \"A.NetName == 'SHORT' || A.NetName == 'NOTRK'\")\n)\n",
    "length-opt": '(rule "opt"\n\t(constraint length (opt 5mm))\n'
    "\t(condition \"A.NetName == 'OPTONLY'\")\n)\n",
    "length-opt-max": '(rule "optmax"\n\t(constraint length (opt 5mm) (max 50mm))\n'
    "\t(condition \"A.NetName == 'OPTONLY'\")\n)\n",
}
"""The rule of each rules case, as KiCad's rules file holds it (c0104 writes these from model rules)."""
RULES_EXPECTED: Mapping[str, tuple[tuple[str, str], ...]] = {
    "skew-pair": (("skew_out_of_range", "SK_P"),),
    "skew-bus": (("skew_out_of_range", "BUS0"), ("skew_out_of_range", "BUS1")),
    "length-range": (("length_out_of_range", "NOTRK"), ("length_out_of_range", "SHORT")),
    "length-opt": (),
    "length-opt-max": (),
}
"""The (violation type, net) pairs that ``H-K-NETLEN-RULES`` predicts for each rules case."""


def rules_case_text(case: str) -> str:
    return "(version 1)\n" + scoped_canary() + RULES_TEXTS[case]


def net_uuids(design: Design) -> dict[str, str]:
    """KiCad uuid → net name, for every track, arc, via and pad of the bench."""
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    found: dict[str, str] = {}
    items: list[Track | Arc | Via] = [*design.board.tracks, *design.board.arcs, *design.board.vias]
    for item in items:
        if item.net_id is not None:
            found[kicad_uuid(item)] = names[item.net_id]
    for footprint in design.board.footprints:
        for pad in footprint.pads:
            if pad.net_id is not None:
                found[kicad_uuid(pad)] = names[pad.net_id]
    return found
