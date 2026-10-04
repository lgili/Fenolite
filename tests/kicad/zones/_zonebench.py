# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The zone bench of change c0031 (capability kicad-oracle, "Zone settings pass the oracle").

The canary is built through the model API: a two-layer 40 × 30 mm board with a ``GND`` pour on ``F.Cu``
over one footprint whose pads are on ``GND`` (a 2 × 2 mm SMD pad and a 1.7 mm round through-hole pad),
one footprint whose pads are on ``SIG`` (a 1 × 1 mm SMD pad and a 1.7 mm through-hole pad), a closed
``SIG`` track ring around an island of the pour, and two ``SIG`` tracks that leave a 0.2 mm channel of
pour between their clearances. A case sets the zone's settings, a pad's or the footprint's
``zone_connect``, or a ``.kicad_dru`` rule. Settings are written by ``write_board`` from the model; only
the footprint-level ``zone_connect``, which the model does not hold, is a token edit.

Refilled fills are measured with the exact predicates of ``fenolite.geometry`` (``point_in_ring``, exact
segment crossings and squared distances), never by counting DRC messages.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import _gerber
from _boards import created_board

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_fragment
from fenolite.core.coords import Point, Size
from fenolite.geometry import Location, dist2_point_segment, dist2_segment_segment, floor_sqrt, point_in_ring
from fenolite.geometry.predicates import intersection_point, round_point
from fenolite.model.board import (
    Board,
    FootprintInstance,
    Outline,
    Pad,
    Track,
    Zone,
    ZoneConnection,
    ZoneFill,
    ZoneHatch,
    ZoneSettings,
)
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design

MM = 1_000_000
PROJECT = "{}\n"
BOARD_NAME = "zones.kicad_pcb"
LAYER = "F.Cu"
ZONE_NAME = "GND_POUR"
WIDTH = 250_000
CLASS_CLEARANCE = 200_000
"""The clearance of the ``Default`` class of an empty project."""
DEFAULTS_T10 = (
    "(connect_pads (clearance 0.5)) (min_thickness 0.25)"
    " (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))"
)
"""What a 10.0.6 re-save writes for a zone without setting children (``H-K-ZONE-DEFAULTS``); pinned to
``zones.emit_settings(ZoneSettings(), filled=False, locked=False, major=10)`` by ``test_zonebench.py``."""
SETTING_HEADS = ("connect_pads", "min_thickness", "fill")
SIG_RULE = (
    "(version 1)\n(rule zone_bench_sig\n\t(condition \"A.NetName == 'SIG'\")\n"
    "\t(constraint clearance (min 0.6mm))\n)\n"
)
DEFAULTS = ZoneSettings()


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


# --- the canary -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Spot:
    """One pad of the bench in board coordinates."""

    label: str
    centre: Point
    size: int
    round: bool


GND_SMD = Spot("gnd_smd", mm(8, 8), 2 * MM, False)
GND_THT = Spot("gnd_tht", mm(16, 8), 1_700_000, True)
SIG_SMD = Spot("sig_smd", mm(24, 8), 1 * MM, False)
SIG_THT = Spot("sig_tht", mm(32, 8), 1_700_000, True)
RING = (mm(6, 16), mm(12, 16), mm(12, 22), mm(6, 22))
ISLAND = mm(9, 19)
"""The centre of the island of pour that the ``SIG`` ring encloses (about 22 mm² with a 0.5 mm clearance)."""
CHANNEL_Y = (18 * MM, 19_450_000)
"""The two channel tracks: 1.2 mm apart edge to edge, so two 0.5 mm clearances leave 0.2 mm of pour."""
CHANNEL = Point(26 * MM, 18_725_000)
HATCH_ROWS = tuple(22 * MM + k * 250_000 + 1 for k in range(24))
"""Scan lines over the free lower right of the board, at odd nanometres so that none runs along an edge."""
HATCH_X = (15 * MM, 37 * MM)
THT_LAYERS = ("F.Cu", "B.Cu", "F.Mask", "B.Mask")


@dataclass(frozen=True)
class Case:
    """One bench case: zone settings by ``ZoneSettings`` field name, pad overrides by pad label, a
    footprint-level ``zone_connect`` code for the ``GND`` footprint, and a rules text."""

    name: str
    settings: Mapping[str, Any] = field(default_factory=lambda: {})
    pads: Mapping[str, ZoneConnection] = field(default_factory=lambda: {})
    footprint: int | None = None
    rules: str | None = None
    fills: tuple[ZoneFill, ...] = ()
    filled: bool = False

    @property
    def zone_settings(self) -> ZoneSettings:
        return dataclasses.replace(DEFAULTS, **self.settings)


CASES: Mapping[str, Case] = {
    case.name: case
    for case in (
        Case("thermal"),
        Case("solid", {"connection": "solid"}),
        Case("none", {"connection": "none"}),
        Case("thru-hole-only", {"connection": "thru_hole_only"}),
        Case("pad-0", {"connection": "solid"}, {"gnd_smd": "none", "gnd_tht": "none"}),
        Case("pad-1", {"connection": "solid"}, {"gnd_smd": "thermal", "gnd_tht": "thermal"}),
        Case("pad-2", {}, {"gnd_smd": "solid", "gnd_tht": "solid"}),
        Case("pad-3", {"connection": "none"}, {"gnd_smd": "thru_hole_only", "gnd_tht": "thru_hole_only"}),
        Case("fp-2", footprint=2),
        Case("fp-2-pad-1", pads={"gnd_smd": "thermal"}, footprint=2),
        Case("clearance-0.3", {"clearance": 300_000}),
        Case("clearance-0.1", {"clearance": 100_000}),
        Case("clearance-rule", {"clearance": 300_000}, rules=SIG_RULE),
        Case("spoke-0.35", {"thermal_spoke_width": 350_000, "thermal_gap": 400_000}),
        Case("spoke-0.25", {"thermal_spoke_width": 250_000, "thermal_gap": 300_000}),
        Case("island-never", {"island_removal": "never"}),
        Case("island-below-10", {"island_removal": "below_area", "min_island_area": 10 * MM * MM}),
        Case("island-below-50", {"island_removal": "below_area", "min_island_area": 50 * MM * MM}),
        Case("channel-0.15", {"min_thickness": 150_000}),
        Case("hatch", {"fill_mode": "hatched", "hatch": ZoneHatch(thickness=1 * MM, gap=1_500_000)}),
    )
}


def _pad(n: int, number: str, spot: Spot, origin: Point, net: str, case: Case) -> Pad:
    common: dict[str, Any] = {
        "zone_connection": case.pads.get(spot.label),
        "id": _id("pad", n),
        "number": number,
        "size": Size(spot.size, spot.size),
        "position": Point(spot.centre.x - origin.x, spot.centre.y - origin.y),
        "net_id": net,
    }
    if spot.round:
        return Pad(shape="circle", kind="thru_hole", drill=1 * MM, layers=THT_LAYERS, **common)
    return Pad(shape="rect", layers=("F.Cu", "F.Mask"), **common)


def bench(case: Case) -> Design:
    """The canary of ``case`` as a created design."""
    gnd, sig = Net(id=_id("net", 1), name="GND"), Net(id=_id("net", 2), name="SIG")
    components = (
        Component(id=_id("cmp", 1), ref="G1", value="GND", path="/g1", lib_footprint_ref="fenolite:ZoneG"),
        Component(id=_id("cmp", 2), ref="S1", value="SIG", path="/s1", lib_footprint_ref="fenolite:ZoneS"),
    )
    footprints = (
        FootprintInstance(
            id=_id("fp", 1), component_id=components[0].id, lib_ref="fenolite:ZoneG",
            position=GND_SMD.centre, attributes=("through_hole",),
            pads=(_pad(1, "1", GND_SMD, GND_SMD.centre, gnd.id, case),
                  _pad(2, "2", GND_THT, GND_SMD.centre, gnd.id, case)),
        ),
        FootprintInstance(
            id=_id("fp", 2), component_id=components[1].id, lib_ref="fenolite:ZoneS",
            position=SIG_SMD.centre, attributes=("through_hole",),
            pads=(_pad(3, "1", SIG_SMD, SIG_SMD.centre, sig.id, case),
                  _pad(4, "2", SIG_THT, SIG_SMD.centre, sig.id, case)),
        ),
    )  # fmt: skip
    segments = [(RING[k], RING[(k + 1) % 4]) for k in range(4)]
    segments += [(Point(18 * MM, y), Point(34 * MM, y)) for y in CHANNEL_Y]
    tracks = tuple(
        Track(id=_id("trk", n + 1), start=a, end=b, width=WIDTH, layer=LAYER, net_id=sig.id)
        for n, (a, b) in enumerate(segments)
    )
    zone = Zone(
        id=_id("zon", 1),
        outline=(mm(1, 1), mm(39, 1), mm(39, 29), mm(1, 29)),
        name=ZONE_NAME,
        layers=(LAYER,),
        net_id=gnd.id,
        fills=case.fills,
        settings=case.zone_settings,
        filled=case.filled,
    )
    board = Board(
        id=_id("brd", 1),
        outline=Outline(id=_id("out", 1), points=(mm(0, 0), mm(40, 0), mm(40, 30), mm(0, 30))),
        layers=created_layers(2),
        footprints=footprints,
        tracks=tracks,
        zones=(zone,),
    )
    members = {
        gnd.id: (PinRef(components[0].id, "1"), PinRef(components[0].id, "2")),
        sig.id: (PinRef(components[1].id, "1"), PinRef(components[1].id, "2")),
    }
    nets = tuple(dataclasses.replace(n, members=members[n.id]) for n in (gnd, sig))
    base = Design.new("zones", seed=0)
    return dataclasses.replace(base, circuit=Circuit(components=components, nets=nets), board=board)


# --- token edits --------------------------------------------------------------------------------------


def _fragments(text: str) -> list[Node]:
    wrapped = parse_fragment(f"(x {text})")
    assert isinstance(wrapped, Node)
    return list(wrapped.nodes())


def zone_node(root: Node, name: str = ZONE_NAME) -> Node:
    """The zone named ``name`` of a parsed board."""
    for zone in root.nodes("zone"):
        found = zone.find("name")
        if found is not None and found.atoms() and found.atoms()[0].value == name:
            return zone
    raise KeyError(name)


def edit_zone(text: str, *, name: str = ZONE_NAME, remove: Sequence[str] = (), insert: str = "") -> str:
    """``text`` with the children ``remove`` of the zone taken out, and the children of ``insert`` put
    before its ``polygon``."""
    root = parse(text)
    zone = zone_node(root, name)
    children = [c for c in zone.children if not (isinstance(c, Node) and c.name in remove)]
    at = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "polygon")
    children[at:at] = _fragments(insert)
    rebuilt = [zone.with_children(children) if child is zone else child for child in root.children]
    return dumps(root.with_children(rebuilt))


def _with_zone_connect(node: Node, code: int) -> Node:
    children = list(node.children)
    at = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "uuid")
    children.insert(at, _fragments(f"(zone_connect {code})")[0])
    return node.with_children(children)


def with_footprint_connect(text: str, code: int) -> str:
    """``text`` with ``(zone_connect N)`` on the ``GND`` footprint itself (a child the model does not
    hold)."""
    root = parse(text)
    target = root.nodes("footprint")[0]
    new = _with_zone_connect(target, code)
    return dumps(root.with_children([new if child is target else child for child in root.children]))


def case_text(case: Case, target: int) -> str:
    """The board of ``case`` for ``target``."""
    text = write_board(bench(case), target=target).text
    if case.footprint is not None:
        text = with_footprint_connect(text, case.footprint)
    return text


def write_case(case: Case, target: int, folder: Path) -> tuple[Path, dict[str, Path]]:
    """The board of ``case`` written into ``folder`` with its ``{}`` project file and its rules file."""
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / BOARD_NAME
    board.write_text(case_text(case, target), encoding="utf-8")
    files = {"zones.kicad_pro": folder / "zones.kicad_pro"}
    files["zones.kicad_pro"].write_text(PROJECT, encoding="utf-8")
    if case.rules is not None:
        files["zones.kicad_dru"] = folder / "zones.kicad_dru"
        files["zones.kicad_dru"].write_text(case.rules, encoding="utf-8")
    return board, files


# --- measurement (exact) ---------------------------------------------------------------------------

Rings = Sequence[Sequence[Point]]
Exact = tuple[Fraction, Fraction]


def fill_rings(design: Design, *, name: str = ZONE_NAME, layer: str = LAYER) -> list[tuple[Point, ...]]:
    """The fill polygons of the zone ``name`` on ``layer``."""
    assert design.board is not None
    zone = next(z for z in design.board.zones if z.name == name)
    return [fill.polygon for fill in zone.fills if fill.layer == layer]


def in_fill(point: Point, rings: Rings) -> bool:
    """Whether ``point`` is in a fill (on a boundary counts: KiCad joins a hole to its outline by a slit of
    no width, which is copper)."""
    return any(point_in_ring(point, ring) is not Location.OUTSIDE for ring in rings)


def crossings(a: Point, b: Point, rings: Rings) -> list[Exact]:
    """The exact points where the axis-aligned segment ``a``–``b`` meets an edge of ``rings``, sorted from
    ``a`` to ``b``, each once."""
    if a.x != b.x and a.y != b.y:
        raise ValueError("crossings takes an axis-aligned segment")
    found: set[Exact] = set()
    for ring in rings:
        for k, start in enumerate(ring):
            point = intersection_point(a, b, start, ring[(k + 1) % len(ring)])
            if point is not None:
                found.add(point)
    return sorted(found, key=lambda p: abs(p[0] - a.x) + abs(p[1] - a.y))


def spans(a: Point, b: Point, rings: Rings) -> list[tuple[bool, Fraction]]:
    """The stretches of the axis-aligned segment ``a``–``b`` as ``(inside the fill, length in nm)``, from
    ``a`` to ``b``; neighbours of the same kind are merged, so a slit of no width disappears."""
    stops: list[Exact] = [
        (Fraction(a.x), Fraction(a.y)),
        *crossings(a, b, rings),
        (Fraction(b.x), Fraction(b.y)),
    ]
    out: list[tuple[bool, Fraction]] = []
    for p, q in zip(stops, stops[1:], strict=False):
        length = abs(q[0] - p[0]) + abs(q[1] - p[1])
        if length < 2:
            continue
        inside = in_fill(round_point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), rings)
        if out and out[-1][0] == inside:
            out[-1] = (inside, out[-1][1] + length)
        else:
            out.append((inside, length))
    return out


def rect_probes(spot: Spot, gap: int) -> dict[str, Point]:
    """Probe points half a relief ``gap`` outside a rectangular pad: four on its axes (``e``, ``s``, ``w``,
    ``n``, where spokes lie) and four at the corners of the relief ring (``ne`` …)."""
    c, r = spot.centre, spot.size // 2 + gap // 2
    return {
        "e": Point(c.x + r, c.y), "s": Point(c.x, c.y + r),
        "w": Point(c.x - r, c.y), "n": Point(c.x, c.y - r),
        "se": Point(c.x + r, c.y + r), "sw": Point(c.x - r, c.y + r),
        "nw": Point(c.x - r, c.y - r), "ne": Point(c.x + r, c.y - r),
    }  # fmt: skip


def round_probes(spot: Spot, gap: int) -> dict[str, Point]:
    """Probe points half a relief ``gap`` outside a round pad: four on its axes and four on its diagonals
    (where the spokes of a round through-hole pad lie)."""
    c, r = spot.centre, spot.size // 2 + gap // 2
    d = floor_sqrt(Fraction(r * r, 2))
    return {
        "e": Point(c.x + r, c.y), "s": Point(c.x, c.y + r),
        "w": Point(c.x - r, c.y), "n": Point(c.x, c.y - r),
        "se": Point(c.x + d, c.y + d), "sw": Point(c.x - d, c.y + d),
        "nw": Point(c.x - d, c.y - d), "ne": Point(c.x + d, c.y - d),
    }  # fmt: skip


AXES = ("e", "s", "w", "n")
DIAGONALS = ("se", "sw", "nw", "ne")


def pattern(spot: Spot, gap: int, rings: Rings) -> str:
    """How the fill meets a ``GND`` pad: ``solid`` (every probe in the fill), ``none`` (no probe),
    ``axes`` or ``diagonals`` (four spokes), or ``other``."""
    probes = round_probes(spot, gap) if spot.round else rect_probes(spot, gap)
    hit = {name for name, point in probes.items() if in_fill(point, rings)}
    if hit == set(probes):
        return "solid"
    if not hit:
        return "none"
    if hit == set(AXES):
        return "axes"
    if hit == set(DIAGONALS):
        return "diagonals"
    return "other"


def gap_to_pad(spot: Spot, rings: Rings) -> int:
    """The distance in whole nanometres (rounded down) between the copper of a pad and the nearest fill
    edge."""
    c, h = spot.centre, spot.size // 2
    best: Fraction | None = None
    for ring in rings:
        for k, start in enumerate(ring):
            end = ring[(k + 1) % len(ring)]
            if spot.round:
                d2 = dist2_point_segment(c, start, end)
            else:
                corners = [
                    Point(c.x - h, c.y - h), Point(c.x + h, c.y - h),
                    Point(c.x + h, c.y + h), Point(c.x - h, c.y + h),
                ]  # fmt: skip
                d2 = min(
                    dist2_segment_segment(start, end, corners[i], corners[(i + 1) % 4]) for i in range(4)
                )
            best = d2 if best is None or d2 < best else best
    if best is None:
        raise ValueError("no fill")
    return floor_sqrt(best) - (h if spot.round else 0)


def spoke_width(spot: Spot, gap: int, rings: Rings) -> Fraction:
    """The width of the east spoke of a rectangular pad, measured across it in the middle of the relief."""
    c, r, h = spot.centre, spot.size // 2 + gap // 2, spot.size // 2
    found = [
        length for inside, length in spans(Point(c.x + r, c.y - h), Point(c.x + r, c.y + h), rings) if inside
    ]
    if len(found) != 1:
        raise ValueError(f"expected one spoke, found {len(found)}")
    return found[0]


def relief_gap(spot: Spot, rings: Rings) -> Fraction:
    """The gap of the relief east of a rectangular pad, measured from the pad edge beside the spoke."""
    c, h = spot.centre, spot.size // 2
    y = c.y + 3 * h // 4
    found = spans(Point(c.x + h, y), Point(c.x + h + 3 * MM, y), rings)
    if not found or found[0][0]:
        raise ValueError("the pad edge is not in the relief")
    return found[0][1]


def hatch_spans(rings: Rings) -> list[list[tuple[bool, Fraction]]]:
    """The inner stretches (the first and the last left out) of every scan line that crosses holes."""
    out: list[list[tuple[bool, Fraction]]] = []
    for y in HATCH_ROWS:
        found = spans(Point(HATCH_X[0], y), Point(HATCH_X[1], y), rings)
        if len(found) >= 5:
            out.append(found[1:-1])
    return out


# --- runs -------------------------------------------------------------------------------------------


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@cache
def refilled(name: str) -> Design:
    """The case board refilled and saved by ``pcb drc --refill-zones --save-board`` (10.0 only), read back."""
    case = CASES[name]
    target = runner().major()
    with tempfile.TemporaryDirectory() as tmp:
        board, files = write_case(case, target, Path(tmp))
        args = [
            "pcb",
            "drc",
            "--refill-zones",
            "--save-board",
            "--format",
            "json",
            "-o",
            "drc.json",
            board.name,
        ]
        run = runner().run(args, files={board.name: board, **files})
    assert run.ok, run.stderr
    assert board.name in run.outputs, "the refill saved no board"
    return read_board(run.outputs[board.name].decode("utf-8"), file=board.name, issues=[])


def loads(name: str, target: int) -> bool:
    """Whether ``pcb drc`` exits 0 and writes a report for the case board written for ``target``."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = write_case(CASES[name], target, Path(tmp))
        run = runner().drc(board, files=files)
    return run.run.ok and run.report is not None


# --- probes -----------------------------------------------------------------------------------------

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
FAT_ZONE = "GND_POUR"
FAT_LAYER = "B.Cu"
FLAG = "(filled_areas_thickness no)"


def defaults_t10() -> str:
    """``equal`` when a zone written without setting children is re-saved with ``DEFAULTS_T10``."""
    text = edit_zone(write_board(bench(CASES["thermal"]), target=10).text, remove=("hatch", *SETTING_HEADS))
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / BOARD_NAME
        board.write_text(text, encoding="utf-8")
        project = board.with_suffix(".kicad_pro")
        project.write_text(PROJECT, encoding="utf-8")
        saved = runner().upgrade_board(board, files={project.name: project}).decode("utf-8")
    zone = zone_node(parse(saved))
    found = [child for child in zone.nodes() if child.name in SETTING_HEADS]
    return "equal" if found == _fragments(DEFAULTS_T10) else "different"


def _plot_extent(text: str) -> _gerber.Extent | None:
    """The extent, in board coordinates, of the one region of the ``B.Cu`` plot of a board text."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "fat.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        project = board.with_suffix(".kicad_pro")
        project.write_text(PROJECT, encoding="utf-8")
        args = ["pcb", "export", "gerbers", "-l", FAT_LAYER, "-o", "out/"]
        run = runner().export(args, board, files={project.name: project}, out="out")
    plots = [data for name, data in run.outputs.items() if name.startswith("out/") and b"G36" in data]
    if not run.ok or len(plots) != 1:
        return None
    regions = _gerber.region_extents(plots[0].decode("utf-8"))
    if len(regions) != 1:
        return None
    x0, y0, x1, y1 = regions[0]
    return (x0, -y1, x1, -y0)  # the plot's Y axis points up


def fat9() -> str:
    """``equal`` when the target-9 fill with ``(filled_areas_thickness no)`` is plotted as written and the
    copy without the flag is plotted ``min_thickness / 2`` larger on each side; ``different`` otherwise."""
    design = created_board()
    assert design.board is not None
    zone = next(z for z in design.board.zones if z.name == FAT_ZONE)
    xs = [p.x for p in zone.fills[0].polygon]
    ys = [p.y for p in zone.fills[0].polygon]
    written = (min(xs), min(ys), max(xs), max(ys))
    grow = DEFAULTS.min_thickness // 2
    fat = (written[0] - grow, written[1] - grow, written[2] + grow, written[3] + grow)
    text = write_board(design, target=9).text
    without = edit_zone(text, name=FAT_ZONE, remove=("filled_areas_thickness",))
    with_flag = edit_zone(without, name=FAT_ZONE, insert=FLAG)
    if _plot_extent(with_flag) == written and _plot_extent(without) == fat:
        return "equal"
    return "different"


def clearance_case(clearance: int) -> Case:
    """The bench with an authored fill 0.3 mm from the ``SIG`` SMD pad and the zone clearance given."""
    x = SIG_SMD.centre.x + SIG_SMD.size // 2 + 300_000
    fill = ZoneFill(
        LAYER, (Point(x, 6 * MM), Point(28 * MM, 6 * MM), Point(28 * MM, 10 * MM), Point(x, 10 * MM))
    )
    return Case(f"drc-{clearance}", {"clearance": clearance}, fills=(fill,), filled=True)


def _clearance_reported(clearance: int) -> bool | None:
    with tempfile.TemporaryDirectory() as tmp:
        board, files = write_case(clearance_case(clearance), runner().major(), Path(tmp))
        run = runner().drc(board, files=files)
    if run.report is None:
        return None
    return any("SIG" in item.description for v in run.report.of_type("clearance") for item in v.items)


def clearance_drc() -> str:
    """``present`` when ``pcb drc`` without a refill reports the authored fill with a zone clearance of
    0.5 mm and not with 0.1 mm."""
    wide, narrow = _clearance_reported(500_000), _clearance_reported(100_000)
    if wide is None or narrow is None:
        return "reject"
    if wide and not narrow:
        return "present"
    return "absent" if not wide else "different"


def zone_probes() -> Probes:
    return {
        "zone-defaults-t10": (defaults_t10, (10,)),
        "zone-fat9": (fat9, (9, 10)),
        "zone-clearance-drc": (clearance_drc, (10,)),
    }


__all__ = [
    "CASES",
    "DEFAULTS_T10",
    "Case",
    "Spot",
    "bench",
    "case_text",
    "crossings",
    "fill_rings",
    "gap_to_pad",
    "in_fill",
    "pattern",
    "rect_probes",
    "refilled",
    "round_probes",
    "spans",
    "write_case",
    "zone_probes",
]
