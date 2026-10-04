# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parity benches of the copper check (change c0029; capability kicad-oracle, "Copper verdict parity
canaries").

Three benches, one per source of the clearance ``c``, each holding one row per pair kind and per gap
(``c − 10 µm``, ``c`` and ``c + 10 µm``), every pair on two probe nets of its own:

- ``rule``: ``_rulebench.Builder`` with a ``{}`` project; ``c`` = 0.2 mm comes from a custom rule on the
  probe nets, written after the unconditional canary rule. It also holds the boundary rows
  (``c − 1 µm``, ``c − 1 nm``) and, for target 10, the zone rows.
- ``class``: written through the triad path; ``c`` = 0.3 mm is the clearance of the class of the probe
  nets, above the template's ``Default`` class. The canary rule is scoped to ``CANARY_A``, and the
  resolution rows bring their own classes and rules, written after it.
- ``floor``: written through the triad path; the probe nets stay in ``Default`` (0.2 mm) and ``c`` =
  0.4 mm is the project's ``min_clearance``. It also holds the row of a rule below the minimum.

No row overlaps or touches: KiCad merges touching copper without pads into one net and does not report the
short of this kind reliably (``docs/formats/kicad/copper.md``, "Via re-net"), so those verdicts cannot be
pinned. The Fenolite half of every row is hermetic (``test_parity_bench.py``).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.backends.kicad.triad import write_triad
from fenolite.checks.copper import CopperReport, check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Zone, ZoneFill
from fenolite.model.rules import Rule, Selector

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
SOURCES = ("rule", "class", "floor")
CLEARANCE = {"rule": 200_000, "class": 300_000, "floor": 400_000}
"""``c`` per source: each is told from the template's ``Default`` class clearance of 0.2 mm, or is it."""
STEP = 10_000
GAPS = {"under": -STEP, "at": 0, "over": STEP}
"""Row gaps relative to ``c``. An arc pair has no ``at`` row: at exactly ``c`` its band may report."""
KINDS = ("track-track", "arc-track", "via-track", "via-via", "pad-track", "pad-pad", "tht-track")
FILL = "fill-track"
BOUNDARY = {"1um": 1_000, "1nm": 1}
RESOLVE = ("rule-below-class", "rule-above-class", "two-classes", "ignore", "arc-kind", "floor-above-rule")
PROBE_CLASS = "PROBE"
HIGH_CLASS = "HV5"
HIGH = 500_000
NAME = "bench"
BOARD, PROJECT, RULES = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro", f"{NAME}.kicad_dru"
ZONE_CLEARANCE = (
    "(connect_pads\n\t\t\t(clearance 0)\n\t\t)\n"
    "\t\t(min_thickness 0.1)\n\t\t(filled_areas_thickness no)\n"
    "\t\t(fill yes\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)"
)
"""Inserted into every zone of the rule bench by token edit: the zone's own clearance is 0, so KiCad's
verdict on a fill rests on the clearance in force alone, and the stored fill is not grown by a stroke.
Without it KiCad applies its default zone clearance of 0.5 mm to the fill."""
SHORT, CLEAR = "shorting_items", "clearance"
VERDICT = {"copper.short": "short", "copper.clearance": "clearance"}


@dataclass(frozen=True)
class Row:
    """One pair of a bench: the labels of its two items are ``<label>_a`` and ``<label>_b``."""

    label: str
    group: str
    """The pair kind, ``boundary-<name>``, ``zone-overlap`` or the resolution case."""
    gap: int


@dataclass(frozen=True)
class ParityBench:
    source: str
    target: int
    bench: rb.Bench
    rows: tuple[Row, ...]
    files: dict[str, str]

    def uuids(self, row: Row) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return self.bench.uuids(f"{row.label}_a"), self.bench.uuids(f"{row.label}_b")


def _rule(n: int, name: str, minimum: int, a: Selector, b: Selector | None = None, *, priority: int = 1,
          severity: str = "error") -> Rule:  # fmt: skip
    return Rule(
        id=f"rul_00000000-0000-4000-8000-{n:012d}",
        name=name,
        kind="clearance",
        selector_a=a,
        selector_b=b,
        min=minimum,
        severity=severity,  # type: ignore[arg-type]
        priority=priority,
    )


def _net(name: str) -> Selector:
    return Selector("net", name)


class _Maker:
    """Adds rows to a builder and remembers them."""

    def __init__(self, target: int, prefix: str) -> None:
        self.made = rb.builder()
        self.target = target
        self.prefix = prefix
        self.rows: list[Row] = []
        self.count = 0
        self.probe_nets: list[str] = []
        self.last_nets = ("", "")

    def nets(self) -> tuple[str, str]:
        self.count += 1
        return f"{self.prefix}{self.count}A", f"{self.prefix}{self.count}B"

    def add(self, kind: str, group: str, gap: int, nets: tuple[str, str] | None = None) -> Row:
        a, b = nets if nets is not None else self.nets()
        label = f"r{len(self.rows)}"
        made = self.made
        if kind == "track-track":
            made.pair(label, a, b, gap=gap)
        elif kind == "arc-track":
            made.arc_pair(label, a, b, gap=gap)
        elif kind == "via-track":
            made.via_track(label, a, b, gap=gap)
        elif kind == "via-via":
            made.via_pair(label, a, b, gap=gap)
        elif kind == "pad-track":
            made.pad_track(label, f"R{len(self.rows)}", a, b, gap=gap, target=self.target)
        elif kind == "tht-track":
            made.tht_track(label, f"D{len(self.rows)}", a, b, gap=gap, target=self.target)
        elif kind == "pad-pad":
            refs = (f"{a}X", f"{b}X")  # ``parts`` puts the pads of each copy on the net ``<ref>_NET``
            made.parts(label, refs, gap=gap, target=self.target)
            a, b = f"{refs[0]}_NET", f"{refs[1]}_NET"
        elif kind == FILL:
            made.fill_track(label, a, b, gap=gap)
        else:
            raise KeyError(kind)
        row = Row(label, group, gap)
        self.rows.append(row)
        self.last_nets = (a, b)
        return row

    def kinds(self, c: int) -> None:
        for kind in KINDS:
            for name, delta in GAPS.items():
                if kind == "arc-track" and name == "at":
                    continue
                self.add(kind, kind, c + delta)
                self.probe_nets.extend(self.last_nets)


def _zone_edit(text: str) -> str:
    """Every zone of a written board with a zone clearance of 0 and a fill that is not grown by a stroke."""
    marker = "\t\t(polygon\n"
    assert marker in text
    return text.replace(marker, f"\t\t{ZONE_CLEARANCE}\n{marker}")


def _rule_bench(target: int) -> ParityBench:
    c = CLEARANCE["rule"]
    maker = _Maker(target, "P")
    maker.kinds(c)
    for name, delta in BOUNDARY.items():
        maker.add("track-track", f"boundary-{name}", c - delta)
    if target >= 10:
        for delta in GAPS.values():
            maker.add(FILL, FILL, c + delta)
        _overlapping_zones(maker)
    bench = maker.made.build()
    rules = (
        "(version 1)\n"
        + rb.canary_rule()
        + "(rule probe\n\t(condition \"A.NetName == 'P*'\")\n"
        + f"\t(constraint clearance (min {c / 1e6:g}mm))\n)\n"
    )
    board = write_board(bench.design, target=target).text
    if target >= 10:
        board = _zone_edit(board)
    return ParityBench(
        "rule", target, bench, tuple(maker.rows), {BOARD: board, PROJECT: rb.PROJECT, RULES: rules}
    )


def _overlapping_zones(maker: _Maker) -> None:
    """Two filled zones of different nets and equal priority whose outlines overlap: the row's items are
    the two zones."""
    made = maker.made
    y = made.row()
    label = f"r{len(maker.rows)}"
    for side, (x0, x1, net) in zip(
        "ab", ((rb.LEFT, rb.LEFT + 6 * rb.MM, "PZA"), (rb.LEFT + 4 * rb.MM, rb.RIGHT, "PZB")), strict=True
    ):
        ring = (Point(x0, y), Point(x1, y), Point(x1, y + 3 * rb.MM), Point(x0, y + 3 * rb.MM))
        zone = Zone(
            id=f"zon_00000000-0000-4000-8000-{900 + len(made.zones):012d}",
            outline=ring,
            name=f"{label}_{side}",
            layers=("F.Cu",),
            net_id=made.net(net),
            fills=(ZoneFill("F.Cu", ring),),
        )
        made.zones.append(zone)
        made.items[f"{label}_{side}"] = (kicad_uuid(zone),)
    maker.rows.append(Row(label, "zone-overlap", -2 * rb.MM))


def _canary(n: int = 900) -> Rule:
    """c0010's scoped canary: 3 mm on ``CANARY_A`` only, written before every other rule."""
    return _rule(n, "canary", 3 * rb.MM, _net(rb.CANARY_NETS[0]), priority=99)


def _class_bench(target: int) -> ParityBench:
    c = CLEARANCE["class"]
    maker = _Maker(target, "P")
    maker.kinds(c)
    made = maker.made
    made.netclass(PROBE_CLASS, c, *maker.probe_nets)
    made.netclass(HIGH_CLASS, HIGH)
    made.rule(_canary())
    # a rule below the class value: both nets in the 0.5 mm class, a 0.1 mm rule on the pair
    for gap in (300_000, 50_000):
        maker.add("track-track", "rule-below-class", gap, ("RB_A", "RB_B"))
    made.assign(HIGH_CLASS, "RB_A", "RB_B")
    made.rule(_rule(1, "below", 100_000, _net("RB_A"), _net("RB_B")))
    # a rule above the class value: Default (0.2 mm) nets, a 0.5 mm rule
    for gap in (300_000, 600_000):
        maker.add("track-track", "rule-above-class", gap, ("RA_A", "RA_B"))
    made.rule(_rule(2, "above", HIGH, _net("RA_A"), _net("RA_B")))
    # two classes: Default against the 0.5 mm class, and Default against Default as the control
    for gap in (300_000, 600_000):
        maker.add("track-track", "two-classes", gap, ("TC_A", "TC_B"))
    made.assign(HIGH_CLASS, "TC_B")
    maker.add("track-track", "two-classes", 300_000, ("TC_C", "TC_D"))
    # an ignore rule on a pair far below its class value
    maker.add("track-track", "ignore", 50_000, ("IG_A", "IG_B"))
    made.rule(_rule(3, "quiet", HIGH, _net("IG_A"), _net("IG_B"), severity="ignore"))
    maker.add("track-track", "ignore", 50_000, ("IG_C", "IG_D"))  # the control: no rule, flagged
    # a rule on item kind ``track`` governs an arc track
    for gap in (300_000, 600_000):
        maker.add("arc-track", "arc-kind", gap, ("AK_A", "AK_B"))
    kind = Selector("and", items=(Selector("item_kind", "track"), _net("AK_A")))
    made.rule(_rule(4, "arcs", HIGH, kind, _net("AK_B")))
    bench = made.build()
    return ParityBench(
        "class", target, bench, tuple(maker.rows), write_triad(bench.design, name=NAME, target=target)
    )


def _floor_bench(target: int) -> ParityBench:
    c = CLEARANCE["floor"]
    maker = _Maker(target, "P")
    maker.kinds(c)
    made = maker.made
    made.rule(_canary())
    for gap in (300_000, 50_000):
        maker.add("track-track", "floor-above-rule", gap, ("FR_A", "FR_B"))
    made.rule(_rule(1, "under_floor", 100_000, _net("FR_A"), _net("FR_B")))
    bench = made.build()
    files = write_triad(bench.design, name=NAME, target=target)
    data = _json.loads(files[PROJECT])
    data["board"]["design_settings"]["rules"]["min_clearance"] = JsonNumber(f"{c / 1e6:g}")  # type: ignore[index]
    files[PROJECT] = _json.dumps(data)
    return ParityBench("floor", target, bench, tuple(maker.rows), files)


@cache
def parity_bench(source: str, target: int) -> ParityBench:
    return {"rule": _rule_bench, "class": _class_bench, "floor": _floor_bench}[source](target)


# --- verdicts -------------------------------------------------------------------------------------


@cache
def fenolite_report(
    source: str, target: int, major: int | None = None
) -> tuple[CopperReport, dict[str, str]]:
    """``check_copper`` on the bench read back from its written texts, with the switches of ``major`` (the
    target when ``None``), and the map from entity id to KiCad uuid."""
    bench = parity_bench(source, target)
    design = read_board(bench.files[BOARD], file=BOARD)
    rules = design_rules_from_texts(
        design,
        project_text=bench.files[PROJECT],
        rules_text=bench.files[RULES],
        major=target if major is None else major,
        file_stem=NAME,
    )
    assert not rules.unread and not rules.opaque_clearance_rules, (rules.unread, rules.opaque_clearance_rules)
    pads = KicadBackend().board_pads(rules.design)
    report = check_copper(
        rules.design,
        pads=pads,
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    assert not report.summary["unsupported"], report.summary["unsupported"]
    board = rules.design.board
    assert board is not None
    entities = [*board.tracks, *board.arcs, *board.vias, *board.zones]
    entities += [pad for footprint in board.footprints for pad in footprint.pads]
    return report, {e.id: e.native_ids["kicad"] for e in entities if "kicad" in e.native_ids}


def fenolite_verdict(source: str, target: int, row: Row, major: int | None = None) -> str:
    """``short``, ``clearance``, ``overlap`` (zone outlines) or ``clean`` for the row's pair."""
    bench = parity_bench(source, target)
    report, uuid_of = fenolite_report(source, target, major)
    a, b = (set(uuids) for uuids in bench.uuids(row))
    for finding in report.findings:
        first, second = (uuid_of.get(item.entity_id) for item in finding.items)
        if (first in a and second in b) or (first in b and second in a):
            return VERDICT.get(finding.code, "overlap")
    return "clean"


def kicad_verdict(report: DrcReport | None, bench: ParityBench, row: Row) -> str:
    """``short`` when a ``shorting_items`` violation names an item of each side of the row, ``clearance``
    when a ``clearance`` violation does, ``clean`` otherwise. A report without the canary violation fails
    the test with "rules file not loaded"."""
    loaded = rb.require_canary(report, bench.bench)
    a, b = bench.uuids(row)
    for kind, verdict in ((SHORT, "short"), (CLEAR, "clearance")):
        if rb.violations_between(loaded, a, b, kind):
            return verdict
    return "clean"


def types_between(report: DrcReport, a: Collection[str], b: Collection[str]) -> tuple[str, ...]:
    return tuple(sorted({v.type for v in rb.violations_between(report, a, b)}))


# --- running --------------------------------------------------------------------------------------


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def running_target() -> int:
    return runner().major()


@cache
def kicad_report(source: str) -> DrcReport | None:
    bench = parity_bench(source, running_target())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in bench.files.items():
            (folder / name).write_text(text, encoding="utf-8")
        extra = {name: folder / name for name in bench.files if name != BOARD}
        return runner().drc(folder / BOARD, files=extra).report


def compared(source: str, groups: Iterable[str]) -> list[tuple[Row, str, str]]:
    """``(row, KiCad's verdict, Fenolite's verdict)`` for the rows of ``groups`` on the running major."""
    target = running_target()
    bench = parity_bench(source, target)
    report = kicad_report(source)
    wanted = set(groups)
    return [
        (row, kicad_verdict(report, bench, row), fenolite_verdict(source, target, row))
        for row in bench.rows
        if row.group in wanted
    ]


def _equal(rows: list[tuple[Row, str, str]]) -> str:
    if not rows:
        return "inconclusive"
    return "equal" if all(kicad == ours for _, kicad, ours in rows) else "different"


def parity(kind: str) -> str:
    """``equal`` when every row of the pair kind agrees, under each of the three clearance sources."""
    sources = ("rule",) if kind == FILL else SOURCES
    return _equal([entry for source in sources for entry in compared(source, (kind,))])


def resolve(case: str) -> str:
    return _equal(compared("floor" if case == "floor-above-rule" else "class", (case,)))


def boundary(name: str) -> str:
    ((_, kicad, _),) = compared("rule", (f"boundary-{name}",))
    return rb.outcome(kicad == "clearance")


def zone_overlap() -> str:
    """``present`` when a violation of any type names both overlapping zones."""
    bench = parity_bench("rule", running_target())
    report = rb.require_canary(kicad_report("rule"), bench.bench)
    (row,) = [row for row in bench.rows if row.group == "zone-overlap"]
    return rb.outcome(bool(rb.violations_between(report, *bench.uuids(row))))


def parity_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {f"copper-parity-{kind}": (lambda kind=kind: parity(kind), both) for kind in KINDS}
    probes[f"copper-parity-{FILL}"] = (lambda: parity(FILL), (10,))
    probes["copper-zone-overlap"] = (zone_overlap, (10,))
    for case in RESOLVE:
        probes[f"copper-resolve-{case}"] = (lambda case=case: resolve(case), both)
    for name in BOUNDARY:
        probes[f"copper-boundary-{name}"] = (lambda name=name: boundary(name), both)
    return probes


__all__ = [
    "BOUNDARY",
    "CLEARANCE",
    "FILL",
    "GAPS",
    "KINDS",
    "RESOLVE",
    "SOURCES",
    "ParityBench",
    "Row",
    "boundary",
    "compared",
    "fenolite_report",
    "fenolite_verdict",
    "kicad_report",
    "kicad_verdict",
    "parity",
    "parity_bench",
    "parity_probes",
    "resolve",
    "types_between",
    "zone_overlap",
]
