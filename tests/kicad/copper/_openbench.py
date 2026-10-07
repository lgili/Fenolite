# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bench of the open connections (change c0108; capability kicad-oracle, "Open connections agree with
unconnected items").

One net per case, on a row of its own: two ``Mini_R_0603`` copies 10 mm apart, the first turned 180°, whose
pads ``1`` are on the net, and the copper of the case (0.25 mm tracks). ``expected`` is the number of open
connections of the case: what ``kicad-cli pcb drc`` reported as unconnected items on 9.0.9 and 10.0.6 when
the change was proposed (2026-10-05), and what ``analysis.connectivity`` must give.

Built with ``_rulebench.Builder`` and written with ``write_board`` for the running major. Every value is
authored for Fenolite; nothing is committed besides this module.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.analysis.connectivity import ConnectivityReport, connectivity
from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.core.coords import Point
from fenolite.model.board import Arc
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = rb.MM
HALF_TURN = 180_000_000
UNCONNECTED = "unconnected_items"
FOOTPRINT = "Mini_R_0603"
DISC_FOOTPRINT = "Mini_LED_THT_3mm"
"""A square and a round through-hole pad: the pad copper of the frame is the shape of the model."""

EXPECTED: dict[str, int] = {
    "none": 1,
    "joined": 0,
    "stub": 1,
    "crossing": 0,
    "across": 0,
    "beside": 0,
    "tee-0": 0,
    "tee-100": 0,
    "tee-200": 0,
    "floating": 1,
    "two-vias": 0,
    "one-via": 1,
    "arc": 0,
    "fill-over": 0,
    "fill-between": 1,
    "three-pads": 1,
    "fill-track": 1,
    "lone-via": 1,
    "fill-one-pad": 1,
}
"""Case → open connections of its net: the 19 cases of the design's measurement 3."""
FILL_CASES = ("fill-over", "fill-between", "fill-track", "fill-one-pad")


def net_name(case: str) -> str:
    return f"N_{case.upper().replace('-', '_')}"


@dataclass(frozen=True)
class OpenBench:
    """The bench and, per case, the KiCad uuids of every item of its net."""

    bench: rb.Bench
    uuids: dict[str, frozenset[str]]

    @property
    def design(self) -> Design:
        return self.bench.design


@dataclass
class _Row:
    """One case being built: its net, its row and the centres of the two pads on the net."""

    builder: rb.Builder
    case: str
    y: int
    a: Point
    b: Point
    labels: list[str]

    @property
    def net(self) -> str:
        return net_name(self.case)

    def label(self) -> str:
        name = f"{self.case}:{len(self.labels)}"
        self.labels.append(name)
        return name

    def track(self, start: Point, end: Point, *, layer: str = "F.Cu") -> None:
        label = self.label()
        self.builder.track(label, self.net, start.y, layer=layer, x0=start.x, x1=start.x + MM)
        made = dataclasses.replace(self.builder.tracks[-1], start=start, end=end)
        self.builder.tracks[-1] = made

    def via(self, at: Point) -> None:
        self.builder.via(self.label(), self.net, at)

    def arc(self, start: Point, mid: Point, end: Point) -> None:
        builder = self.builder
        arc = Arc(
            id=f"arc_00000000-0000-4000-8000-{len(builder.arcs) + 1:012d}",
            start=start,
            mid=mid,
            end=end,
            width=rb.WIDTH,
            layer="F.Cu",
            net_id=builder.net(self.net),
        )
        builder.arcs.append(arc)
        label = self.label()
        builder.items[label] = (kicad_uuid(arc),)

    def fill(self, x0: int, x1: int, top: int) -> None:
        self.builder.filled_zone(self.label(), self.net, top, x0=x0, x1=x1)

    def join(self) -> None:
        self.track(self.a, self.b)


def _copper(row: _Row, fills: bool) -> None:  # noqa: PLR0912, PLR0915 (one branch per case of the table)
    case, a, b, y = row.case, row.a, row.b, row.y
    mid = (a.x + b.x) // 2
    if case == "joined":
        row.join()
    elif case == "stub":
        row.track(a, Point(a.x + 3 * MM, y))
    elif case == "crossing":  # the two tracks cross at 70 % of their length
        row.track(a, Point(a.x + 6 * MM, y + 3 * MM))
        row.track(b, Point(b.x - 6 * MM, y + 3 * MM))
    elif case == "across":
        row.track(a, Point(b.x + 2 * MM, y))
    elif case == "beside":  # centre lines 0.2 mm apart: the copper overlaps by 0.05 mm, no end inside
        row.track(a, Point(mid + MM, y))
        row.track(Point(mid - MM, y + 200_000), Point(b.x, y + 200_000))
    elif case.startswith("tee-"):  # a track that ends on, or beside, the centre line of another
        off = int(case.split("-")[1]) * 1_000
        row.track(a, Point(mid - off, y))
        row.track(Point(mid, y - 2 * MM), Point(mid, y + 2 * MM))
        row.track(Point(mid, y + 2 * MM), Point(b.x, y + 2 * MM))
        row.track(Point(b.x, y + 2 * MM), b)
    elif case == "floating":
        row.join()
        row.track(Point(a.x + MM, y + 3 * MM), Point(b.x - MM, y + 3 * MM))
    elif case in ("two-vias", "one-via"):
        first, second = Point(a.x + 2 * MM, y), Point(b.x - 2 * MM, y)
        row.track(a, first)
        row.via(first)
        row.track(first, second, layer="B.Cu")
        if case == "two-vias":
            row.via(second)
        row.track(second, b)
    elif case == "arc":  # a half circle whose three points lie exactly on it
        row.arc(a, Point(mid, y + (b.x - a.x) // 2), b)
    elif case == "three-pads":
        row.join()
    elif case == "lone-via":
        row.join()
        row.via(Point(mid, y + 3 * MM))
    elif case == "fill-track":
        row.join()
        row.track(Point(a.x + MM, y + 3_500_000), Point(b.x - MM, y + 3_500_000))
        if fills:
            row.fill(a.x - MM, b.x + MM, y + 2 * MM)
    elif fills and case == "fill-over":
        row.fill(a.x - 2 * MM, b.x + 2 * MM, y - 1_500_000)
    elif fills and case == "fill-between":
        row.fill(a.x + 2 * MM, b.x - 2 * MM, y - 1_500_000)
    elif fills and case == "fill-one-pad":
        row.fill(a.x - 2 * MM, a.x + 2 * MM, y - 1_500_000)


@cache
def open_bench(target: int, *, fills: bool = True, footprint: str = FOOTPRINT) -> OpenBench:
    """The bench for ``target``. Without ``fills`` the four fill cases hold no zone (their counts are then
    not those of ``EXPECTED``); ``footprint`` names the ``Mini`` footprint of the parts."""
    builder = rb.Builder()
    uuids: dict[str, frozenset[str]] = {}
    for index, case in enumerate(EXPECTED):
        y = builder.row()
        net = net_name(case)
        refs = (f"RA{index}", f"RB{index}")
        builder.part(f"{case}:a", refs[0], Point(rb.LEFT, y), target=target, nets={"1": net},
                     footprint=footprint, rotation=HALF_TURN)  # fmt: skip
        builder.part(f"{case}:b", refs[1], Point(rb.RIGHT, y), target=target, nets={"1": net},
                     footprint=footprint)  # fmt: skip
        labels = [f"{case}:a:1", f"{case}:b:1"]
        if case == "three-pads":
            builder.part(f"{case}:c", f"RC{index}", Point((rb.LEFT + rb.RIGHT) // 2, y + 4 * MM),
                         target=target, nets={"1": net}, footprint=footprint)  # fmt: skip
            labels.append(f"{case}:c:1")
        centres = {
            pad.ref: pad.position
            for pad in board_pads(builder.build().design)
            if pad.ref in refs and pad.number == "1"
        }
        row = _Row(builder, case, y, centres[refs[0]], centres[refs[1]], labels)
        _copper(row, fills)
        uuids[case] = frozenset(u for label in row.labels for u in builder.items[label])
    return OpenBench(builder.build(), uuids)


def reversed_design(design: Design) -> Design:
    """``design`` with its tracks, arcs, vias, zones and footprints in reverse order."""
    board = design.board
    assert board is not None
    turned = dataclasses.replace(
        board,
        tracks=board.tracks[::-1],
        arcs=board.arcs[::-1],
        vias=board.vias[::-1],
        zones=board.zones[::-1],
        footprints=board.footprints[::-1],
    )
    return dataclasses.replace(design, board=turned)


def query(design: Design) -> ConnectivityReport:
    return connectivity(design, pads=board_pads(design))


def query_counts(bench: OpenBench) -> dict[str, int]:
    """Case → the open connections that ``analysis.connectivity`` finds for its net."""
    report = query(bench.design)
    by_name = {net.name: len(net.open) for net in report.nets}
    return {case: by_name.get(net_name(case), 0) for case in EXPECTED}


def kicad_counts(report: DrcReport, bench: OpenBench) -> dict[str, int]:
    """Case → the unconnected items of the report whose items all belong to the case's net, by uuid."""
    counts = dict.fromkeys(EXPECTED, 0)
    for found in report.unconnected_items:
        named = {item.uuid for item in found.items}
        for case, uuids in bench.uuids.items():
            if named and named <= uuids:
                counts[case] += 1
    return counts


def drc(runner: KicadCli, bench: OpenBench, target: int) -> DrcReport | None:
    """``pcb drc`` on the bench written for ``target`` with a ``{}`` project beside it."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "open.kicad_pcb"
        board.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        (folder / "open.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
        return runner.drc(board, files={"open.kicad_pro": folder / "open.kicad_pro"}).report


def _runner() -> KicadCli:
    from _probes import runner  # _probes imports this module

    return runner()


@cache
def kicad_case_counts() -> dict[str, int] | None:
    """KiCad's count per case on the running ``kicad-cli`` (``None`` without a report)."""
    runner = _runner()
    target = runner.major()
    bench = open_bench(target)
    report = drc(runner, bench, target)
    return None if report is None else kicad_counts(report, bench)


def kicad_outcome() -> str:
    """Probe ``copper-open-kicad``: KiCad's counts per case against ``EXPECTED``."""
    found = kicad_case_counts()
    if found is None:
        return "reject"
    return "equal" if found == EXPECTED else "different"


def parity_outcome() -> str:
    """Probe ``copper-open-parity``: KiCad's count of every case against the query's."""
    found = kicad_case_counts()
    if found is None:
        return "reject"
    return "equal" if found == query_counts(open_bench(_runner().major())) else "different"


def open_probes() -> Probes:
    """The probes of the open connections: the bench is written for the running major, and both are
    pinned on both majors."""
    both = (9, 10)
    return {"copper-open-kicad": (kicad_outcome, both), "copper-open-parity": (parity_outcome, both)}


__all__ = [
    "EXPECTED",
    "FILL_CASES",
    "OpenBench",
    "kicad_case_counts",
    "kicad_counts",
    "kicad_outcome",
    "net_name",
    "open_bench",
    "open_probes",
    "parity_outcome",
    "query",
    "query_counts",
    "reversed_design",
]
