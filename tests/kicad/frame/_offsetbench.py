# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pad shape offset bench (change c0068; capability kicad-oracle, "Pad shape offset passes the oracle";
``H-G-FRAME-OFFSET``).

Each row holds one placed copy of ``Frame_Offset`` (a through-hole ``rect`` pad of 2 mm × 2 mm with a
0.8 mm drill), its ``(offset X Y)`` set by token edit of the footprint text, and one ``F.Cu`` track of
another net above the pad. The track is placed at a known edge gap from the pad's box as it lies WITHOUT
the offset, so the two readings of the offset give different verdicts under the class clearance of 0.2 mm:

- the offset moves the copper (what KiCad does): ``towards`` and ``turned`` are 0.1 mm from the track,
  ``short-of`` 0.25 mm and ``away`` 0.6 mm;
- the offset moves the hole (what Fenolite v0.1 did): the copper stays, so ``towards``, ``short-of`` and
  ``turned`` are 0.5 mm from the track and ``away`` 0.1 mm.

The bench is written through the triad path with the scoped canary, as the class bench of the copper
parity is. The Fenolite half of every row is hermetic.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.backends.kicad.triad import write_triad
from fenolite.checks.copper import check_copper
from fenolite.core.coords import Point
from fenolite.model.circuit import Component, PinRef
from fenolite.model.rules import Rule, Selector

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
FOOTPRINT = rb.LIBS / "Frame.pretty" / "Frame_Offset.kicad_mod"
STORED = "(drill 0.8\n\t\t\t(offset 0 -0.4)\n\t\t)"
CLEARANCE = 200_000
CLASS = "OFFSET"
HALF = 1_000_000
"""Half the side of the pad's 2 mm × 2 mm box."""
NAME = "bench"
BOARD, PROJECT, RULES = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro", f"{NAME}.kicad_dru"


@dataclass(frozen=True)
class Row:
    """One pad and one track: ``offset`` is in the pad's own frame, ``gap`` the edge gap between the track
    and the pad's box without the offset, ``moved`` the gap once the copper has moved."""

    name: str
    offset: tuple[int, int]
    gap: int
    moved: int
    angle: int
    expected: str


ROWS = (
    Row("towards", (0, -400_000), 500_000, 100_000, 0, "clearance"),
    Row("short-of", (0, -250_000), 500_000, 250_000, 0, "clean"),
    Row("away", (0, 500_000), 100_000, 600_000, 0, "clean"),
    # at 90° the placement maps the pad's (x, y) to the board's (y, −x): (0.4, 0) points up, at the track
    Row("turned", (400_000, 0), 500_000, 100_000, 90, "clearance"),
)


@dataclass(frozen=True)
class OffsetBench:
    target: int
    bench: rb.Bench
    files: dict[str, str]


def footprint_text(offset: tuple[int, int]) -> str:
    """The text of ``Frame_Offset`` with its drill offset replaced by ``offset`` (nm)."""
    text = FOOTPRINT.read_text(encoding="utf-8")
    assert STORED in text
    x, y = (f"{value / 1e6:g}" for value in offset)
    return text.replace(STORED, f"(drill 0.8\n\t\t\t(offset {x} {y})\n\t\t)")


def _canary() -> Rule:
    """The scoped canary: 3 mm on ``CANARY_A`` only."""
    return Rule(
        id="rul_00000000-0000-4000-8000-000000000900",
        name="canary",
        kind="clearance",
        selector_a=Selector("net", rb.CANARY_NETS[0]),
        min=3 * rb.MM,
        severity="error",
        priority=99,
    )


@cache
def offset_bench(target: int) -> OffsetBench:
    made = rb.builder()
    x = (rb.LEFT + rb.RIGHT) // 2
    nets: list[str] = []
    for n, row in enumerate(ROWS, start=1):
        y = made.row() + 4 * rb.MM
        ref, pad_net, track_net = f"J{n}", f"OFF{n}A", f"OFF{n}B"
        defn = read_footprint(footprint_text(row.offset), library="Frame")
        component = Component(
            id=f"cmp_00000000-0000-4000-8000-{n:012d}", ref=ref, value="offset", lib_footprint_ref=defn.lib_id
        )
        placed = place_footprint(
            defn, component=component, at=Point(x, y), rotation=row.angle * 1_000_000, key=ref
        )
        net_id = made.net(pad_net)
        placed = dataclasses.replace(
            placed, pads=tuple(dataclasses.replace(pad, net_id=net_id) for pad in placed.pads)
        )
        made.members[net_id] = [PinRef(component.id, pad.number) for pad in placed.pads]
        made.components.append(component)
        made.footprints.append(placed)
        made.items[f"{row.name}_a"] = tuple(kicad_uuid(pad) for pad in placed.pads)
        made.track(f"{row.name}_b", track_net, y - HALF - row.gap - rb.WIDTH // 2)
        nets += [pad_net, track_net]
    made.netclass(CLASS, CLEARANCE, *nets)
    made.rule(_canary())
    bench = made.build()
    return OffsetBench(target, bench, write_triad(bench.design, name=NAME, target=target))


def fenolite_verdict(target: int, row: Row) -> str:
    """``clearance`` when ``check_copper`` reports the row's pad against its track, ``short`` for a short,
    ``clean`` otherwise, on the bench read back from its written texts."""
    bench = offset_bench(target)
    design = read_board(bench.files[BOARD], file=BOARD)
    rules = design_rules_from_texts(
        design,
        project_text=bench.files[PROJECT],
        rules_text=bench.files[RULES],
        major=target,
        file_stem=NAME,
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
    entities = [*board.tracks, *(pad for footprint in board.footprints for pad in footprint.pads)]
    uuid_of = {e.id: e.native_ids["kicad"] for e in entities if "kicad" in e.native_ids}
    a, b = set(bench.bench.uuids(f"{row.name}_a")), set(bench.bench.uuids(f"{row.name}_b"))
    for finding in report.findings:
        first, second = (uuid_of.get(item.entity_id) for item in finding.items)
        if (first in a and second in b) or (first in b and second in a):
            return {"copper.short": "short", "copper.clearance": "clearance"}.get(finding.code, finding.code)
    return "clean"


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@cache
def kicad_report() -> DrcReport | None:
    bench = offset_bench(runner().major())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in bench.files.items():
            (folder / name).write_text(text, encoding="utf-8", newline="\n")
        extra = {name: folder / name for name in bench.files if name != BOARD}
        return runner().drc(folder / BOARD, files=extra).report


def kicad_verdict(row: Row) -> str:
    """``clearance`` when a ``clearance`` violation names the row's pad and its track. A report without the
    canary violation fails the test with "rules file not loaded"."""
    bench = offset_bench(runner().major())
    report = rb.require_canary(kicad_report(), bench.bench)
    a, b = bench.bench.uuids(f"{row.name}_a"), bench.bench.uuids(f"{row.name}_b")
    if rb.violations_between(report, a, b, "shorting_items"):
        return "short"
    return "clearance" if rb.violations_between(report, a, b, "clearance") else "clean"


def compared() -> list[tuple[Row, str, str]]:
    """``(row, KiCad's verdict, Fenolite's verdict)`` on the running major."""
    target = runner().major()
    return [(row, kicad_verdict(row), fenolite_verdict(target, row)) for row in ROWS]


def pad_offset() -> str:
    """``equal`` when KiCad's verdict is the expected one on every row and ``check_copper`` gives the same."""
    return (
        "equal"
        if all(kicad == row.expected and ours == kicad for row, kicad, ours in compared())
        else "different"
    )


def offset_probes() -> Probes:
    return {"pcb-frame-pad-offset": (pad_offset, (9, 10))}


__all__ = [
    "ROWS",
    "OffsetBench",
    "Row",
    "compared",
    "fenolite_verdict",
    "footprint_text",
    "kicad_verdict",
    "offset_bench",
    "offset_probes",
    "pad_offset",
]
