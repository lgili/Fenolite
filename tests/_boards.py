# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored boards for the board tests: the CC0 fixture, small inline boards per scenario, and the
created test board of the writer (built through the model API, no library definition)."""

from __future__ import annotations

import dataclasses
import json
import os
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import opaque_count, opaque_digests, read_board, rebuild_board
from fenolite.backends.kicad.sexpr import dumps, first_difference, parse, tree_equal
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id, new_id
from fenolite.model.board import (
    Arc,
    Board,
    FootprintField,
    FootprintInstance,
    Graphic,
    Keepout,
    Outline,
    Pad,
    StackKind,
    StackLayer,
    Stackup,
    Text,
    Track,
    Via,
    Zone,
    ZoneFill,
    ZoneHatch,
    ZoneSettings,
)
from fenolite.model.canonical import to_data
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef, TitleBlock

FIXTURE = Path(__file__).resolve().parent / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
STACKUP_FIXTURE = FIXTURE.with_name("stackup_four.kicad_pcb")
"""The authored four-layer board with a stack-up (c0101): ``four_layer_stackup()`` on a created board."""
LAYERS = (
    '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (2 "B.Cu" signal) (1 "F.Mask" user) (3 "B.Mask" user)'
    ' (25 "Edge.Cuts" user))'
)


def uid(n: int) -> str:
    """An authored uuid, distinct per ``n``."""
    return f"00000000-0000-4000-8000-{n:012d}"


def board(*items: str, version: int = 20241229, nets: Sequence[str] | None = ("", "A", "B")) -> str:
    """A board with the given root items; ``nets`` is the numbered table (``None`` for the name form)."""
    major = "10.0" if version > 20241229 else "9.0"
    table = "" if nets is None else " ".join(f'(net {i} "{name}")' for i, name in enumerate(nets))
    return (
        f'(kicad_pcb (version {version}) (generator "fenolite-tests") (generator_version "{major}")'
        f' (general (thickness 1.6)) (paper "A4") {LAYERS} (setup (pad_to_mask_clearance 0))'
        f" {table} {' '.join(items)})"
    )


def segment(
    n: int, *, start: str = "0 0", end: str = "1 0", net: str = "(net 1)", uuid: str | None = None
) -> str:
    return (
        f'(segment (start {start}) (end {end}) (width 0.25) (layer "F.Cu") {net} (uuid "{uuid or uid(n)}"))'
    )


def pad(
    n: int, number: str = "1", *, extra: str = "", drill: str = "", layers: str = '"F.Cu" "F.Mask"'
) -> str:
    return (
        f'(pad "{number}" smd rect (at 0 0) (size 1 1){drill} (layers {layers}) (net 1 "A"){extra}'
        f' (uuid "{uid(n)}"))'
    )


def footprint(n: int, *, at: str = "10 10", attr: str = "(attr smd)", pads: str = "", ref: str = "U1") -> str:
    return (
        f'(footprint "Lib:FP" (layer "F.Cu") (uuid "{uid(n)}") (at {at})'
        f' (property "Reference" "{ref}" (at 0 0 0) (layer "F.SilkS") (uuid "{uid(n + 1)}")'
        f" (effects (font (size 1 1) (thickness 0.15)))) {attr} {pads})"
    )


ZONE_SETTINGS = "(connect_pads (clearance 0.5)) (min_thickness 0.25)"


def zone(
    n: int,
    *,
    inner: str,
    net: str = "(net 1)",
    layer: str = '(layer "F.Cu")',
    settings: str = ZONE_SETTINGS,
    head: str = "",
) -> str:
    """A zone; ``settings`` is the text of its setting children (before ``inner``), and ``head`` is put
    between ``net_name`` and ``layer`` (where KiCad writes ``(locked yes)``)."""
    return f'(zone {net} (net_name "A") {head} {layer} (uuid "{uid(n)}") (hatch edge 0.5) {settings} {inner})'


SQUARE = "(polygon (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10)))"

SCENARIOS: dict[str, str] = {
    "blind-via": board(
        f'(via blind (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") (net 1) (uuid "{uid(1)}"))'
    ),
    "unknown-net": board(segment(1, net="(net 7)"), nets=("", "A")),
    "name-form": board(segment(1, net='(net "GND")'), version=20260206, nets=None),
    "spelling": board(segment(1, start="12.000000 0")),
    "sub-nm": board(segment(1, start="0.0000001 0")),
    "fp-angle": board(footprint(1, at="10 10 30.0000001")),
    "repeat-uuid": board(segment(1, uuid=uid(9)), segment(2, uuid=uid(9), start="2 0")),
    "attr": board(footprint(1, attr="(attr smd frobnicate)")),
    "oval-drill": board(footprint(1, pads=pad(5, drill=" (drill oval 1.2 2.0)"))),
    "pintype": board(footprint(1, pads=pad(5, extra=' (pintype "passive+no_connect")'))),
    "padstack": board(
        footprint(
            1,
            pads=pad(
                5, extra=' (padstack (mode front_inner_back) (layer "In1.Cu" (shape circle) (size 1 1)))'
            ),
        )
    ),
    "teardrop": board(zone(1, inner=f"(attr (teardrop (type padvia))) {SQUARE}")),
    "zone-arc": board(
        zone(1, inner="(polygon (pts (xy 0 0) (arc (start 0 0) (mid 1 1) (end 2 0)) (xy 2 5)))")
    ),
    "zone-two-polygons": board(zone(1, inner=f"{SQUARE} {SQUARE}")),
    "paper-unmodelled": board().replace('(paper "A4")', '(paper "USLetter")'),
    "net-collision": board(segment(1, net="(net 1)"), nets=("", "a/b", "a{slash}b")),
    "island-10": board(
        zone(
            1,
            net='(net "A")',
            inner=(
                f'{SQUARE} (filled_polygon (layer "F.Cu") (island yes) (pts (xy 0 0) (xy 1 0) (xy 1 1)))'
                ' (filled_polygon (layer "F.Cu") (island no) (pts (xy 2 2) (xy 3 2) (xy 3 3)))'
            ),
        ),
        version=20260206,
        nets=None,
    ),
}


def _stack_scenario(node: str) -> str:
    """A board whose ``setup`` holds ``node`` (the table of ``LAYERS``: three copper layers, two masks)."""
    return board().replace("(setup (pad_to_mask_clearance 0))", f"(setup {node} (pad_to_mask_clearance 0))")


_STACK_ROWS = (
    '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))'
    ' (layer "F.Cu" (type "copper") {top})'
    ' (layer "dielectric 1" (type "core") (thickness 0.7))'
    ' (layer "In1.Cu" (type "copper") (thickness 0.035))'
    ' (layer "dielectric 2" (type "prepreg") (thickness 0.775))'
    ' (layer "B.Cu" (type "copper") (thickness 0.035))'
    ' (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))'
)
SCENARIOS.update(
    {
        "stackup-unused": _stack_scenario('(stackup (layer "F.Cu" (type "copper") (thickness 0.035)))'),
        "stackup-unmodelled": _stack_scenario(f"(stackup {_STACK_ROWS.format(top='')})"),
        "stackup-thickness": _stack_scenario(
            f'(stackup {_STACK_ROWS.format(top="(thickness 0.07)")} (copper_finish "None"))'
        ),
    }
)
"""The three ``kicad.board.stackup-*`` codes of a read (c0101): a node KiCad ignores, a copper row without
a thickness, and rows that sum to 1.635 mm on a board that states 1.6 mm."""


def _without_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_provenance(v) for k, v in value.items() if k != "provenance"}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_without_provenance(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def canonical(design: Design) -> Any:
    """The canonical data of a design read from a board, every provenance removed."""
    return _without_provenance([to_data(design.header), to_data(design.circuit), to_data(design.board)])


def rt1_problems(text: str, design: Design | None = None) -> list[str]:
    """The RT1 conditions that fail for one board text (empty when all three hold)."""
    design = design if design is not None else read_board(text)
    problems: list[str] = []
    rebuilt = rebuild_board(design)
    original = parse(text)
    if not tree_equal(rebuilt, original):
        problems.append(f"(a) rebuild differs at {first_difference(rebuilt, original)}")
    again = read_board(dumps(rebuilt))
    # The header name comes from the file name, not from the content: a text has none.
    again = dataclasses.replace(again, header=dataclasses.replace(again.header, name=design.header.name))
    if canonical(again) != canonical(design):
        problems.append("(b) the re-read model differs")
    if opaque_count(again) != opaque_count(design) or opaque_digests(again) != opaque_digests(design):
        problems.append("(c) opaque counts or digests differ")
    return problems


def census(section: str, key: str, data: Any) -> None:
    """Merge ``data`` under ``section/key`` into the JSON file named by ``FENOLITE_CENSUS_OUT``."""
    target = os.environ.get("FENOLITE_CENSUS_OUT")
    if not target:
        return
    path = Path(target)
    current: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    current.setdefault(section, {})[key] = data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")


MM = 1_000_000
CREATED_TITLE_BLOCK = TitleBlock(
    title="Created", date="2026-10-02", revision="A", organization="Fenolite", doc_id="FEN-1",
    responsible="Ann", approver="Bob",
)  # fmt: skip
"""The seven-field title block of the created test board (c0012), so it writes every title-block head."""
CREATED_NETS = ("GND", "LED_A", "VIN")
CREATED_HATCH_SETTINGS = ZoneSettings(
    fill_mode="hatched",
    hatch=ZoneHatch(smoothing_level=1),
    smoothing="fillet",
    smoothing_radius=500_000,
    island_removal="below_area",
)
"""The settings of zone ``GND_HATCH`` of the created test board (c0031): together with its lock they
write every zone setting name of ``pcb.FLOOR_HEADS``."""


def mm(x: float, y: float) -> Point:
    """A point in millimetres (test helper; the values used are exact in nm)."""
    return Point(round(x * MM), round(y * MM))


def square(x0: float, y0: float, x1: float, y1: float) -> tuple[Point, ...]:
    return (mm(x0, y0), mm(x1, y0), mm(x1, y1), mm(x0, y1))


def created_board(copper: int = 2) -> Design:
    """The created test board of the writer (c0017 Decision 19): ``created_layers(copper)``, a 50 × 30 mm
    outline, the nets GND, LED_A and VIN, one created entity of every ``CANONICAL_ORDER`` head (its
    footprint with a ``Reference`` field at (0, −1.5 mm) and a hidden ``Value`` field, c0030), an A4
    sheet and a seven-field title block (c0012) and the stack-up ``created_stackup(copper)`` (c0101), so
    that every name of ``pcb.FLOOR_HEADS`` is written for target 9."""
    rng = random.Random(copper)
    design = Design.new("created", seed=copper)
    nets = {name: Net(id=new_id("net", rng), name=name) for name in CREATED_NETS}
    gnd, led, _vin = (nets[name].id for name in CREATED_NETS)
    u1 = Component(
        id=new_id("cmp", rng), ref="U1", value="TEST", path="/u1", lib_footprint_ref="fenolite:Created"
    )
    size = Size(MM, 3 * MM // 2)
    pads = (
        Pad(id=new_id("pad", rng), number="1", shape="rect", size=size, position=mm(-1.27, 0),
            layers=("F.Cu", "F.Mask"), net_id=gnd, zone_connection="solid"),
        Pad(id=new_id("pad", rng), number="2", shape="rect", size=size, position=mm(1.27, 0),
            layers=("F.Cu", "F.Mask"), net_id=led),
    )  # fmt: skip
    fields = (
        FootprintField(id=new_id("fld", rng), name="Reference", position=mm(0, -1.5), layer="F.SilkS",
                       size=Size(MM, MM), thickness=150_000),
        FootprintField(id=new_id("fld", rng), name="Value", position=mm(0, 1.5), layer="F.Fab",
                       size=Size(MM, MM), thickness=150_000, visible=False),
    )  # fmt: skip
    footprint = FootprintInstance(
        id=new_id("fp", rng), component_id=u1.id, lib_ref="fenolite:Created", position=mm(10, 10),
        locked=True, attributes=("smd",), pads=pads, fields=fields,
    )  # fmt: skip
    fill = ZoneFill("B.Cu", square(26, 6, 34, 14), island=True)
    zone = Zone(
        id=new_id("zon", rng), outline=square(25, 5, 35, 15), name="GND_POUR", layers=("B.Cu",), net_id=gnd,
        priority=1, fills=(fill,),
    )  # fmt: skip
    rule = Keepout(id=new_id("kpo", rng), outline=square(40, 5, 45, 10), layers=("F.Cu",), no_tracks=True)
    hatched = Zone(
        id=derived_id("zon", "created", f"GND_HATCH:{copper}"), outline=square(36, 16, 48, 28),
        name="GND_HATCH", layers=("F.Cu",), net_id=gnd, locked=True, settings=CREATED_HATCH_SETTINGS,
    )  # fmt: skip
    silk = "F.SilkS"
    w = 120_000
    graphics = (
        Graphic(id=new_id("gfx", rng), kind="line", layer=silk, points=(mm(2, 2), mm(8, 2)), width=w),
        Graphic(id=new_id("gfx", rng), kind="arc", layer=silk, points=(mm(2, 4), mm(5, 5), mm(8, 4)),
                width=w),
        Graphic(id=new_id("gfx", rng), kind="circle", layer=silk, points=(mm(5, 8), mm(6, 8)), width=w),
        Graphic(id=new_id("gfx", rng), kind="rect", layer=silk, points=(mm(2, 10), mm(8, 12)), width=w),
        Graphic(id=new_id("gfx", rng), kind="polygon", layer=silk, points=(mm(2, 14), mm(8, 14), mm(5, 17)),
                width=w, filled=True),
    )  # fmt: skip
    text = Text(
        id=new_id("txt", rng), text="BACK", position=mm(40, 25), layer="B.SilkS", size=Size(MM, MM),
        thickness=150_000,
    )  # fmt: skip
    board = Board(
        id=design.board.id if design.board else new_id("brd", rng),
        outline=Outline(id=new_id("out", rng), points=square(0, 0, 50, 30)),
        layers=created_layers(copper),
        footprints=(footprint,),
        tracks=(Track(id=new_id("trk", rng), start=mm(5, 20), end=mm(15, 20), width=250_000, layer="F.Cu",
                      net_id=gnd),),
        arcs=(Arc(id=new_id("arc", rng), start=mm(20, 20), mid=mm(22, 22), end=mm(24, 20), width=250_000,
                  layer="F.Cu", net_id=led),),
        vias=(Via(id=new_id("via", rng), position=mm(30, 20), diameter=600_000, drill=300_000,
                  layers=("F.Cu", "B.Cu"), net_id=gnd),),
        zones=(zone, hatched),
        keepouts=(rule,),
        texts=(text,),
        graphics=graphics,
        sheet=SheetFrameRef("A4"),
        title_block=CREATED_TITLE_BLOCK,
        stackup=created_stackup(copper),
    )  # fmt: skip
    members = {gnd: (PinRef(u1.id, "1"),), led: (PinRef(u1.id, "2"),)}
    circuit = Circuit(
        components=(u1,),
        nets=tuple(dataclasses.replace(n, members=members.get(n.id, ())) for n in nets.values()),
    )
    return dataclasses.replace(design, circuit=circuit, board=board)


def stack_entry(name: str, kind: StackKind, thickness: int, **more: Any) -> StackLayer:
    """A stack-up entry with an id derived from its name, kind and values."""
    key = f"{name}:{kind}:{thickness}:{sorted(more.items())}"
    return StackLayer(id=derived_id("sly", "tests", key), name=name, kind=kind, thickness=thickness, **more)


def stack_of(*entries: StackLayer, finish: str = "", impedance_controlled: bool = False) -> Stackup:
    key = ":".join(e.id for e in entries)
    return Stackup(
        id=derived_id("stk", "tests", key), layers=entries, finish=finish,
        impedance_controlled=impedance_controlled,
    )  # fmt: skip


def four_layer_stackup(*, outer: bool = True) -> Stackup:
    """The stack-up of ``stackup_four.kicad_pcb`` (2.025 mm): masks of 10 µm (the top one ``Green``), a
    prepreg, a core of two sheets (the second 0.3 mm of ``Laminate B``) and a prepreg, finish ``ENIG``,
    impedance controlled. ``outer=False`` leaves out the four silkscreen and paste entries."""
    fr4 = {"material": "FR4", "epsilon_r": "4.5", "loss_tangent": "0.02"}
    top = (stack_entry("F.SilkS", "silkscreen", 0), stack_entry("F.Paste", "solderpaste", 0))
    bottom = (stack_entry("B.Paste", "solderpaste", 0), stack_entry("B.SilkS", "silkscreen", 0))
    middle = (
        stack_entry("F.Mask", "soldermask", 10_000, color="Green"),
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 200_000, dielectric_kind="prepreg", **fr4),
        stack_entry("In1.Cu", "copper", 17_500),
        stack_entry("dielectric 2", "dielectric", 1_200_000, dielectric_kind="core", **fr4),
        stack_entry("dielectric 2", "dielectric", 300_000, dielectric_kind="core", material="Laminate B",
                    epsilon_r="3.66", loss_tangent="0.004"),
        stack_entry("In2.Cu", "copper", 17_500),
        stack_entry("dielectric 3", "dielectric", 200_000, dielectric_kind="prepreg", **fr4),
        stack_entry("B.Cu", "copper", 35_000),
        stack_entry("B.Mask", "soldermask", 10_000),
    )  # fmt: skip
    entries = (*top, *middle, *bottom) if outer else middle
    return stack_of(*entries, finish="ENIG", impedance_controlled=True)


def created_stackup(copper: int = 2) -> Stackup:
    """The stack-up of the created test board (c0101), 1.6 mm for every created copper count (c0100): masks
    of 10 µm (the top one with a colour), 35 µm copper, a core of two sheets with a material and both
    decimals in the middle gap, and a prepreg of 0.1 mm in every other gap."""
    fr4 = {"material": "FR4", "epsilon_r": "4.5", "loss_tangent": "0.02"}
    names = [la.name for la in created_layers(copper) if la.kind == "copper"]
    rest = 1_600_000 - 20_000 - 35_000 * copper - 100_000 * (copper - 2) - 500_000
    entries: list[StackLayer] = [stack_entry("F.Mask", "soldermask", 10_000, color="Green")]
    for k, name in enumerate(names, 1):
        entries.append(stack_entry(name, "copper", 35_000))
        if k == copper // 2:
            entries += [
                stack_entry(f"dielectric {k}", "dielectric", sheet, dielectric_kind="core", **fr4)
                for sheet in (500_000, rest)
            ]
        elif k < copper:
            entries.append(
                stack_entry(f"dielectric {k}", "dielectric", 100_000, dielectric_kind="prepreg", **fr4)
            )
    entries.append(stack_entry("B.Mask", "soldermask", 10_000))
    return stack_of(*entries, finish="ENIG")


def bare_board(copper: int = 2, stackup: Stackup | None = None) -> Design:
    """A created 50 × 30 mm board with one track per copper layer and no net (the stack-up benches)."""
    design = Design.new("bare", seed=copper)
    layers = created_layers(copper)
    names = [la.name for la in layers if la.kind == "copper"]
    tracks = tuple(
        Track(id=derived_id("trk", "bare", name), start=mm(5, 5 + 3 * k), end=mm(45, 5 + 3 * k),
              width=250_000, layer=name)
        for k, name in enumerate(names)
    )  # fmt: skip
    board = Board(
        id=derived_id("brd", "bare", str(copper)),
        outline=Outline(id=derived_id("out", "bare", str(copper)), points=square(0, 0, 50, 30)),
        layers=layers,
        tracks=tracks,
        stackup=stackup,
    )
    return dataclasses.replace(design, board=board)


TWO_LAYER_NODE = (
    '(stackup (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))'
    ' (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))'
    ' (layer "F.Cu" (type "copper") (thickness 0.035))'
    ' (layer "dielectric 1" (type "core") (thickness 1.5))'
    ' (layer "B.Cu" (type "copper") (thickness 0.035))'
    ' (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))'
    ' (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen"))'
    ' (copper_finish "None") (dielectric_constraints no))'
)
"""A complete two-layer node: 35 µm copper, a 1.5 mm core and 10 µm masks (1.59 mm)."""


def with_two_layer_node(text: str) -> str:
    """The text of ``two_layer.kicad_pcb`` with ``TWO_LAYER_NODE`` in its ``setup`` and the board thickness
    1.59 mm, by token edit (c0101: the boards of the ``analyze`` and ``export`` scenarios)."""
    assert text.count("(setup") == 1 and text.count("(thickness 1.6)") == 1
    return text.replace("(setup", f"(setup {TWO_LAYER_NODE}", 1).replace(
        "(thickness 1.6)", "(thickness 1.59)", 1
    )


def large_board(*, min_bytes: int = 5 * 2**20) -> Design:
    """A two-copper board of created tracks and vias whose target-10 text is at least ``min_bytes`` long
    (c0020, the throughput measurement). Ids are derived, so the board is the same on every run."""
    design = Design.new("large", seed=0)
    nets = tuple(Net(id=derived_id("net", "large", name), name=name) for name in CREATED_NETS)

    def items(count: int) -> tuple[tuple[Track, ...], tuple[Via, ...]]:
        tracks: list[Track] = []
        vias: list[Via] = []
        for n in range(count):
            x, y = 1_000_000 + (n % 400) * 500_000, 1_000_000 + (n // 400) * 500_000
            net = nets[n % len(nets)].id
            layer = "F.Cu" if n % 2 == 0 else "B.Cu"
            tracks.append(
                Track(id=derived_id("trk", "large", str(n)), start=Point(x, y), end=Point(x + 300_000, y),
                      width=200_000, layer=layer, net_id=net)
            )  # fmt: skip
            if n % 4 == 0:
                vias.append(
                    Via(id=derived_id("via", "large", str(n)), position=Point(x, y + 250_000),
                        diameter=600_000, drill=300_000, layers=("F.Cu", "B.Cu"), net_id=net)
                )  # fmt: skip
        return tuple(tracks), tuple(vias)

    def built(count: int) -> Design:
        tracks, vias = items(count)
        height = 2_000_000 + (count // 400 + 1) * 500_000
        board = Board(
            id=derived_id("brd", "large", "0"),
            outline=Outline(
                id=derived_id("out", "large", "0"),
                points=(Point(0, 0), Point(202_000_000, 0), Point(202_000_000, height), Point(0, height)),
            ),
            layers=created_layers(2),
            tracks=tracks,
            vias=vias,
        )
        return dataclasses.replace(design, circuit=Circuit(nets=nets), board=board)

    from fenolite.backends.kicad.pcb import write_board

    sample = 2_000
    per_item = len(write_board(built(sample), target=10).text.encode("utf-8")) / sample
    return built(int(min_bytes / per_item * 1.02) + sample)
