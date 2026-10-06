# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fresh-fill bench (change c0068; capability kicad-oracle, "Fresh fills stay clean under the zone
clearance"; ``H-K-COPPER-ZONECLR``).

One ``GND`` pour on ``F.Cu`` whose zone clearance (0.5 mm) is above the class clearance (0.2 mm), around
copper of other nets of every kind the copper check shapes: a track, an arc track, a via, an SMD pad, a
round and a rectangular through-hole pad, and a through-hole pad whose drill has an offset. The board is
written without fills through the triad path and refilled on a copy with ``pcb drc --refill-zones
--save-board``, as the benches of ``_zonebench`` are. ``check_copper`` must not report what KiCad's filler
has just produced.

(The design names ``_zonebench.py`` for this bench; it is a module of its own beside it, registered through
``_zonebench.zone_probes``, because it is built with ``_rulebench.Builder`` and judged with the copper
check, which ``_zonebench`` does not import.)
"""

from __future__ import annotations

import dataclasses
import tempfile
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_fragment
from fenolite.backends.kicad.triad import write_triad
from fenolite.checks.copper import CopperFinding, check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Zone, ZoneSettings
from fenolite.model.circuit import Component, PinRef

NAME = "fresh"
BOARD, PROJECT, RULES = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro", f"{NAME}.kicad_dru"
ZONE_CLEARANCE = 500_000
CLASS_CLEARANCE = 200_000
CLASS = "FRESH"
POUR = "FRESH_POUR"
TRACK = "track"
STALE_SHIFT = 300_000
"""How far the track is moved towards the kept fill: the fill was cut 0.5 mm from it, so 0.2 mm remain,
which the class clearance allows and the zone's does not."""
KINDS = ("track", "arc", "via", "pad")
"""The kinds of the other items of the bench, as ``CopperRef.kind`` names them."""


@dataclasses.dataclass(frozen=True)
class FreshBench:
    target: int
    bench: rb.Bench
    files: dict[str, str]


@cache
def fresh_bench(target: int) -> FreshBench:
    """The bench for ``target``: its zone has no fill."""
    made = rb.Builder()
    nets: list[str] = []
    made.single(TRACK, "F_TRACK")
    made.arc_pair("arc", "F_ARC", "F_ARC_T")
    made.lone_via("via", "F_VIA")
    x = (rb.LEFT + rb.RIGHT) // 2
    made.part("smd", "R1", Point(x, made.row()), target=target, nets={"1": "F_SMD1", "2": "F_SMD2"})
    made.part(
        "tht", "D1", Point(x, made.row()), target=target, nets={"1": "F_THT1", "2": "F_THT2"},
        footprint="Mini_LED_THT_3mm",
    )  # fmt: skip
    defn = read_footprint(rb.LIBS / "Frame.pretty" / "Frame_Offset.kicad_mod", library="Frame")
    component = Component(
        id=f"cmp_00000000-0000-4000-8000-{len(made.components) + 1:012d}",
        ref="J1",
        value="offset",
        lib_footprint_ref=defn.lib_id,
    )
    placed = place_footprint(defn, component=component, at=Point(x, made.row()), key="J1")
    net_id = made.net("F_OFFSET")
    placed = dataclasses.replace(
        placed, pads=tuple(dataclasses.replace(pad, net_id=net_id) for pad in placed.pads)
    )
    made.members[net_id] = [PinRef(component.id, pad.number) for pad in placed.pads]
    made.components.append(component)
    made.footprints.append(placed)
    made.items["offset"] = tuple(kicad_uuid(pad) for pad in placed.pads)
    nets += [net.name for net in made.nets.values()]
    height = rb.FIRST_ROW + made.rows * rb.ROW + 10 * rb.MM
    edge = 1 * rb.MM
    zone = Zone(
        id="zon_00000000-0000-4000-8000-000000000001",
        outline=(
            Point(edge, edge),
            Point(rb.BOARD_WIDTH - edge, edge),
            Point(rb.BOARD_WIDTH - edge, height - edge),
            Point(edge, height - edge),
        ),
        name=POUR,
        layers=("F.Cu",),
        net_id=made.net("GND"),
        settings=ZoneSettings(clearance=ZONE_CLEARANCE),
    )
    made.zones.append(zone)
    made.items["zone"] = (kicad_uuid(zone),)
    made.netclass(CLASS, CLASS_CLEARANCE, *nets, "GND")
    bench = made.build()
    return FreshBench(target, bench, write_triad(bench.design, name=NAME, target=target))


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module's importer

    return probes_runner()


@cache
def refilled_text() -> str:
    """The bench board refilled and saved by ``pcb drc --refill-zones --save-board`` (10.0 only)."""
    bench = fresh_bench(runner().major())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in bench.files.items():
            (folder / name).write_text(text, encoding="utf-8", newline="\n")
        args = ["pcb", "drc", "--refill-zones", "--save-board", "--format", "json", "-o", "drc.json", BOARD]
        run = runner().run(args, files={name: folder / name for name in bench.files})
    assert run.ok, run.stderr
    assert BOARD in run.outputs, "the refill saved no board"
    return run.outputs[BOARD].decode("utf-8")


def findings(text: str, target: int) -> tuple[tuple[CopperFinding, ...], int]:
    """The findings of ``check_copper`` on the board ``text`` judged with the bench's project and rules
    texts, and the number of fill polygons the board holds."""
    bench = fresh_bench(target)
    design = read_board(text, file=BOARD, issues=[])
    rules = design_rules_from_texts(
        design, project_text=bench.files[PROJECT], rules_text=bench.files[RULES], major=target, file_stem=NAME
    )
    assert not rules.unread and not rules.opaque_clearance_rules, (rules.unread, rules.opaque_clearance_rules)
    report = check_copper(
        rules.design,
        pads=KicadBackend().board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    assert not report.summary["unsupported"], report.summary["unsupported"]
    board = rules.design.board
    assert board is not None
    return report.findings, sum(len(zone.fills) for zone in board.zones)


def zone_findings(text: str, target: int) -> list[CopperFinding]:
    return [f for f in findings(text, target)[0] if f.code == "copper.clearance" and f.source == "zone"]


def _fragment(text: str) -> Node:
    wrapped = parse_fragment(f"(x {text})")
    assert isinstance(wrapped, Node)
    return wrapped.nodes()[0]


def stale_text() -> str:
    """The refilled board with its track moved ``STALE_SHIFT`` down, towards the fill, by token edit: the
    fill is kept as KiCad made it."""
    bench = fresh_bench(runner().major())
    (uuid,) = bench.bench.uuids(TRACK)
    root = parse(refilled_text())
    children = list(root.children)
    moved = 0
    for index, child in enumerate(children):
        if not isinstance(child, Node) or child.name != "segment":
            continue
        ident = child.find("uuid")
        if ident is None or ident.atoms()[0].value != uuid:
            continue
        inner: list[Node | object] = []
        for part in child.children:
            if isinstance(part, Node) and part.name in ("start", "end"):
                x, y = (atom.to_nm(exact=False) for atom in part.atoms())
                part = _fragment(f"({part.name} {x / 1e6:.6f} {(y + STALE_SHIFT) / 1e6:.6f})")
            inner.append(part)
        children[index] = child.with_children(inner)  # type: ignore[arg-type]
        moved += 1
    assert moved == 1
    return dumps(root.with_children(children))


def kicad_reports_stale() -> bool:
    """Whether ``pcb drc`` without a refill reports a ``clearance`` violation naming the zone and the moved
    track of ``stale_text``."""
    bench = fresh_bench(runner().major())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in {**bench.files, BOARD: stale_text()}.items():
            (folder / name).write_text(text, encoding="utf-8", newline="\n")
        extra = {name: folder / name for name in bench.files if name != BOARD}
        report = runner().drc(folder / BOARD, files=extra).report
    assert report is not None
    return bool(
        rb.violations_between(report, bench.bench.uuids("zone"), bench.bench.uuids(TRACK), "clearance")
    )


def fresh() -> str:
    """``absent`` when the refilled bench holds fills and no ``copper.clearance`` of source ``zone``."""
    text = refilled_text()
    target = runner().major()
    _, fills = findings(text, target)
    return "absent" if fills and not zone_findings(text, target) else "present"


__all__ = [
    "KINDS",
    "FreshBench",
    "findings",
    "fresh",
    "fresh_bench",
    "kicad_reports_stale",
    "refilled_text",
    "stale_text",
    "zone_findings",
]
