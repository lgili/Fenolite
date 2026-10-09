# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas in KiCad: keep-out settings, conditions that name an area, and the parity of the copper
check with them (capability kicad-oracle, "Rule areas and area conditions are probed" and "Keep-outs and
area rules agree with the copper check"; hypotheses ``H-K-AREA-KEEPOUT``, ``H-K-AREA-NAME``,
``H-K-AREA-COND`` and ``H-K-COPPER-AREA``; change c0103).

Every bench is built on ``_rulebench`` with the canary pair, written with ``write_board`` for the running
major, and judged from the JSON report by violation type and item uuid. The canary is the one scoped to
its own net (c0071), so it never takes the place of a violation under test. All values are authored for
these benches: round lengths on a 40 mm board.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from types import MappingProxyType

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pcb import kicad_uuid, read_board, write_board
from fenolite.checks.copper import CopperReport, check_copper
from fenolite.core.ids import derived_id
from fenolite.model.board import ZoneSettings
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

MM = rb.MM
HALF = rb.WIDTH // 2
NOT_ALLOWED = "items_not_allowed"
RULE_MIN = 2 * MM
"""The clearance of the area rule; the pairs it judges are ``PAIR_GAP`` apart."""
PAIR_GAP = 1 * MM
KEEPOUT_KEYS = ("tracks", "cross", "layer", "vias", "pads", "footprints", "pour")
"""The ``area-keepout-<key>`` probes of both majors; ``refill`` is of 10.0 only."""
CONDITIONS: dict[str, bool] = {
    "area": True,
    "two-sided": True,
    "width": True,
    "hole": True,
    "glob": True,
    "touch": True,
    "twin": True,
    "unknown": False,
    "case": False,
    "layer": False,
    "edge": False,
}
"""Condition case → whether its probe items are selected (``present``) or not (``absent``)."""
EMPTY_RULES = "(version 1)\n"


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@contextmanager
def area_supported(target: int) -> Iterator[None]:
    """``SELECTOR_SUPPORT`` with every key holding ``target`` while a bench lowers its rules: the probe
    decides the entry, so the entry cannot gate the probe."""
    saved = rulemap.SELECTOR_SUPPORT
    rulemap.SELECTOR_SUPPORT = MappingProxyType({k: frozenset(v) | {target} for k, v in saved.items()})
    try:
        yield
    finally:
        rulemap.SELECTOR_SUPPORT = saved


def rule(name: str, kind: RuleKind, a: Selector, minimum: int, **fields: object) -> Rule:
    return Rule(
        id=derived_id("rul", "oracle", f"area:{name}"),
        name=name,
        kind=kind,
        selector_a=a,
        min=minimum,
        **fields,  # type: ignore[arg-type]
    )


def lowered(target: int, *rules: Rule) -> str:
    """The rules text of ``rules`` for ``target``, behind the scoped canary."""
    with area_supported(target):
        text = lower_rules(RuleSet(id=derived_id("rst", "oracle", "area"), rules=rules), target=target).text
    return rb.with_scoped_canary(text)


def area(value: str) -> Selector:
    return Selector("area", value)


def next_y(made: rb.Builder) -> int:
    """The y of the row the next ``pair`` or ``single`` call takes."""
    return rb.FIRST_ROW + made.rows * rb.ROW


def around(y: int, *, gap: int = PAIR_GAP) -> tuple[int, int, int, int]:
    """A box around the pair whose first track is at ``y``, 1 mm beyond its copper on every side."""
    return (8 * MM, y - MM, 22 * MM, y + gap + rb.WIDTH + MM)


@dataclasses.dataclass(frozen=True)
class Run:
    bench: rb.Bench
    report: DrcReport | None

    @property
    def canary(self) -> bool:
        return self.report is not None and rb.canary_fired(self.report, self.bench)

    def named(self, label: str, kind: str = NOT_ALLOWED) -> bool:
        """Whether a violation of ``kind`` names every item of ``label`` (each pad, for a footprint)."""
        assert self.report is not None
        found = {
            item.uuid for v in self.report.violations if v.type == kind for item in v.items
        }  # fmt: skip
        return set(self.bench.uuids(label)) <= found

    def any_named(self, label: str, kind: str = NOT_ALLOWED) -> bool:
        assert self.report is not None
        found = {item.uuid for v in self.report.violations if v.type == kind for item in v.items}
        return bool(set(self.bench.uuids(label)) & found)

    def between(self, label: str, kind: str | None = "clearance") -> bool:
        assert self.report is not None
        a, b = self.bench.uuids(f"{label}_a"), self.bench.uuids(f"{label}_b")
        return bool(rb.violations_between(self.report, a, b, kind))

    def types_of(self, label: str) -> set[str]:
        assert self.report is not None
        return {v.type for v in rb.violations_of(self.report, self.bench.uuids(label))}


def drc(bench: rb.Bench, rules: str) -> Run:
    return Run(bench, rb.drc(runner(), bench, rules, major()))


def judged(run: Run, found: bool) -> str:
    """``inconclusive`` when the run lacks the canary (the rules file was not loaded)."""
    return rb.outcome(found) if run.canary else "inconclusive"


# --- keep-out settings ----------------------------------------------------------------------------


def keepout_bench(setting: str, target: int) -> rb.Bench:
    """The bench of one keep-out setting: an item inside an area that forbids it and a control outside."""
    made = rb.builder()
    y = next_y(made)
    if setting == "tracks":
        made.area("area", "KT", (8 * MM, y - MM, 22 * MM, y + 3 * MM), layers=("F.Cu",), no_tracks=True)
        made.single("in", "T1")
        made.track("cross", "T2", y + MM, x0=4 * MM, x1=14 * MM)
        made.track("under", "T3", y + 2 * MM, layer="B.Cu")
        made.single("out", "T4")
    elif setting == "vias":
        made.area("area", "KV", (8 * MM, y - 2 * MM, 22 * MM, y + 3 * MM), no_vias=True)
        made.lone_via("in", "V1")
        made.track("track", "V2", y + 2 * MM)
        made.lone_via("out", "V3")
    elif setting in ("pads", "footprints"):
        flag = "no_pads" if setting == "pads" else "no_footprints"
        made.area("area", "KP", (8 * MM, y - 3 * MM, 22 * MM, y + 3 * MM), **{flag: True})
        made.part("in", "R1", rb.Point(15 * MM, made.row()), target=target, nets={})
        made.part("out", "R2", rb.Point(15 * MM, made.row()), target=target, nets={})
    elif setting == "pour":
        top = made.row()
        zone = made.filled_zone("zone", "Z1", top, x0=6 * MM, x1=24 * MM)
        # islands are kept, so the refill of 10.0 leaves copper although no pad is on the net
        made.zones[-1] = dataclasses.replace(zone, settings=ZoneSettings(island_removal="never"))
        made.area(
            "area", "KC", (12 * MM, top - MM, 18 * MM, top + 4 * MM), layers=("F.Cu",), no_copper_pour=True
        )
    else:
        raise KeyError(setting)
    return made.build()


@cache
def keepout(setting: str) -> Run:
    return drc(keepout_bench(setting, major()), rb.with_scoped_canary(EMPTY_RULES))


def keepout_probe(key: str) -> str:
    if key in ("tracks", "cross", "layer"):
        run = keepout("tracks")
        if key == "tracks":
            return judged(run, run.named("in") and not run.any_named("out"))
        return judged(run, run.named("cross" if key == "cross" else "under"))
    run = keepout(key)
    if key == "vias":
        return judged(run, run.named("in") and not run.any_named("track") and not run.any_named("out"))
    if key == "pads":
        return judged(run, run.named("in") and not run.any_named("out"))
    if key == "footprints":
        found = run.named("in:footprint") and not run.any_named("in") and not run.any_named("out:footprint")
        return judged(run, found)
    return judged(run, run.any_named("zone"))


def refill_probe() -> str:
    """``equal`` when the refill of 10.0 leaves copper of the zone and none of it inside the copper-pour
    keep-out (x from 12 mm to 18 mm)."""
    bench = keepout_bench("pour", major())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=major()).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
        args = ["pcb", "drc", "--refill-zones", "--save-board", "--format", "json", "-o", "drc.json"]
        run = runner().run(
            [*args, board.name], files={board.name: board, "bench.kicad_pro": folder / "bench.kicad_pro"}
        )
    if not run.ok or board.name not in run.outputs:
        return "inconclusive"
    saved = read_board(run.outputs[board.name].decode("utf-8"), file=board.name, issues=[])
    assert saved.board is not None
    fills = [fill for zone in saved.board.zones for fill in zone.fills]
    inside = [
        fill
        for fill in fills
        if min(p.x for p in fill.polygon) < 18 * MM and max(p.x for p in fill.polygon) > 12 * MM
    ]
    return "equal" if fills and not inside else "different"


def name_probe() -> str:
    """``equal`` when ``pcb upgrade --force`` keeps the name of a created rule area."""
    bench = keepout_bench("tracks", major())
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=major()).text, encoding="utf-8")
        saved = read_board(runner().upgrade_board(board).decode("utf-8"), file=board.name, issues=[])
    assert saved.board is not None
    return "equal" if [k.name for k in saved.board.keepouts] == ["KT"] else "different"


# --- conditions that name an area -----------------------------------------------------------------


def _hv_rule(value: str = "HV") -> Rule:
    return rule("hv", "clearance", area(value), RULE_MIN)


@cache
def condition(key: str) -> Run:
    """The run of one condition case: a probe (pair or item) and a control outside every area."""
    target = major()
    made = rb.builder()
    y = next_y(made)
    if key in ("area", "glob", "case", "unknown"):
        made.area("hv", "HV", around(y))
        made.pair("probe", "A1", "A2", gap=PAIR_GAP)
        made.pair("control", "A3", "A4", gap=PAIR_GAP)
        value = {"area": "HV", "glob": "H*", "case": "hv", "unknown": "NOPE"}[key]
        return drc(made.build(), lowered(target, _hv_rule(value)))
    if key == "layer":
        made.area("hv", "HV", around(y), layers=("F.Cu",))
        made.pair("probe", "A1", "A2", gap=PAIR_GAP, layer="B.Cu")
        made.pair("control", "A3", "A4", gap=PAIR_GAP)
        return drc(made.build(), lowered(target, _hv_rule()))
    if key == "twin":
        made.area("first", "HV", (26 * MM, y - MM, 34 * MM, y + MM))
        made.area("second", "HV", around(y))
        made.pair("probe", "A1", "A2", gap=PAIR_GAP)
        made.pair("control", "A3", "A4", gap=PAIR_GAP)
        return drc(made.build(), lowered(target, _hv_rule()))
    if key in ("touch", "edge"):
        # the area ends 50 µm inside (touch) or 50 µm outside (edge) the copper of the first track
        reach = 50_000 if key == "touch" else -50_000
        made.area("hv", "HV", (8 * MM, y - 3 * MM, 22 * MM, y - HALF + reach))
        made.pair("probe", "A1", "A2", gap=PAIR_GAP)
        made.pair("control", "A3", "A4", gap=PAIR_GAP)
        return drc(made.build(), lowered(target, _hv_rule()))
    if key == "two-sided":
        second = y + PAIR_GAP + rb.WIDTH
        made.area("p", "P", (8 * MM, y - MM, 22 * MM, y + HALF + 100_000))
        made.area("q", "Q", (8 * MM, second - HALF - 100_000, 22 * MM, second + MM))
        made.pair("probe", "A1", "A2", gap=PAIR_GAP)
        made.pair("control", "A3", "A4", gap=PAIR_GAP)
        both = rule("pq", "clearance", area("P"), RULE_MIN, selector_b=area("Q"))
        return drc(made.build(), lowered(target, both))
    if key == "width":
        made.area("bga", "BGA", (8 * MM, y - MM, 22 * MM, y + MM))
        made.single("probe", "W1", width=200_000)
        made.single("control", "W2", width=200_000)
        wide = rule("w", "track_width", Selector("all"), 300_000)
        neck = rule("neck", "track_width", area("BGA"), 100_000, priority=1)
        return drc(made.build(), lowered(target, wide, neck))
    if key == "hole":
        made.area("hv", "HV", (8 * MM, y - MM, 22 * MM, y + 2 * MM))
        made.via_pair("probe", "H1", "H2", gap=400_000)
        made.via_pair("control", "H3", "H4", gap=400_000)
        holes = rule("holes", "hole_to_hole", area("HV"), 1 * MM)
        return drc(made.build(), lowered(target, holes))
    raise KeyError(key)


def condition_selected(key: str) -> bool:
    """Whether the probe of the case is selected by the area rule and the control is not."""
    run = condition(key)
    if key == "width":
        # the neck-down rule lets the 0.2 mm track pass inside the area; outside, the 0.3 mm rule holds
        return "track_width" in run.types_of("control") and "track_width" not in run.types_of("probe")
    kind = "hole_to_hole" if key == "hole" else "clearance"
    return run.between("probe", kind) and not run.between("control", kind)


def condition_probe(key: str) -> str:
    return judged(condition(key), condition_selected(key))


# --- parity with the copper check -----------------------------------------------------------------


@cache
def keepout_parity_bench(target: int) -> rb.Bench:
    """Tracks, vias and pads inside, across and outside keep-outs of each copper setting, on two layers."""
    made = rb.builder()
    y = next_y(made)
    made.area("kt", "KT", (8 * MM, y - MM, 22 * MM, y + 4 * MM), no_tracks=True)
    made.single("track_in", "T1")
    made.track("track_cross", "T2", y + MM, x0=4 * MM, x1=14 * MM)
    made.track("track_back", "T3", y + 2 * MM, layer="B.Cu")
    made.single("track_out", "T4")
    y = next_y(made)
    made.area("kv", "KV", (8 * MM, y - 2 * MM, 22 * MM, y + 3 * MM), layers=("B.Cu",), no_vias=True)
    made.lone_via("via_in", "V1")
    made.track("via_track", "V2", y + 2 * MM, layer="B.Cu")
    made.lone_via("via_out", "V3")
    y = next_y(made)
    made.area("kp", "KP", (8 * MM, y - 3 * MM, 22 * MM, y + 3 * MM), layers=("F.Cu",), no_pads=True)
    made.part("pads_in", "R1", rb.Point(15 * MM, made.row()), target=target, nets={})
    made.part("pads_out", "R2", rb.Point(15 * MM, made.row()), target=target, nets={})
    return made.build()


AREA_RULE = "hv"


@cache
def area_parity_bench(target: int) -> rb.Bench:
    """Track pairs 1 mm apart inside, across and outside a rule area ``HV`` on two layers, with the 2 mm
    clearance rule scoped to it in the model."""
    made = rb.builder()
    y = next_y(made)
    made.area("hv", "HV", (8 * MM, y - MM, 22 * MM, y + 2 * rb.ROW + 3 * MM))
    made.pair("in", "P1", "P2", gap=PAIR_GAP)
    made.pair("back", "P3", "P4", gap=PAIR_GAP, layer="B.Cu")
    y = next_y(made)
    made.track("cross_a", "P5", y, x0=18 * MM, x1=30 * MM)
    made.track("cross_b", "P6", y + PAIR_GAP + rb.WIDTH, x0=18 * MM, x1=30 * MM)
    made.rows += 1
    made.pair("out", "P7", "P8", gap=PAIR_GAP)
    made.rule(_hv_rule())
    return made.build()


def _uuids(bench: rb.Bench) -> dict[str, str]:
    """Entity id → KiCad uuid for the copper items of the bench."""
    board = bench.design.board
    assert board is not None
    entities = [*board.tracks, *board.arcs, *board.vias]
    entities += [pad for footprint in board.footprints for pad in footprint.pads]
    return {entity.id: kicad_uuid(entity) for entity in entities}


def copper_report(bench: rb.Bench) -> CopperReport:
    """``check_copper`` on the bench as built: its rules are those of its model."""
    return check_copper(bench.design, pads=board_pads(bench.design))


def fenolite_keepouts(bench: rb.Bench) -> set[str]:
    """The KiCad uuids of the items of the ``copper.keepout`` findings."""
    uuid_of = _uuids(bench)
    report = copper_report(bench)
    return {uuid_of[f.items[0].entity_id] for f in report.findings if f.code == "copper.keepout"}


def fenolite_area_pairs(bench: rb.Bench) -> set[frozenset[str]]:
    """The pairs of the ``copper.clearance`` findings whose source is the area rule."""
    uuid_of = _uuids(bench)
    report = copper_report(bench)
    return {
        frozenset(uuid_of[item.entity_id] for item in f.items)
        for f in report.findings
        if f.code == "copper.clearance" and f.source == f"rule:{AREA_RULE}"
    }


@cache
def keepout_parity_run() -> Run:
    return drc(keepout_parity_bench(major()), rb.with_scoped_canary(EMPTY_RULES))


@cache
def area_parity_run() -> Run:
    bench = area_parity_bench(major())
    assert bench.design.rules is not None
    return drc(bench, lowered(major(), *bench.design.rules.rules))


def kicad_keepouts(run: Run) -> set[str]:
    """The copper items that ``items_not_allowed`` names (footprints and areas left out)."""
    assert run.report is not None
    copper = set(_uuids(run.bench).values())
    named = {item.uuid for v in run.report.violations if v.type == NOT_ALLOWED for item in v.items}
    return named & copper


def kicad_area_pairs(run: Run) -> set[frozenset[str]]:
    """The pairs of bench items that KiCad reports as ``clearance``, the canary pair left out."""
    assert run.report is not None
    copper = set(_uuids(run.bench).values())
    canary = {*run.bench.uuids("canary_a"), *run.bench.uuids("canary_b")}
    found: set[frozenset[str]] = set()
    for violation in run.report.violations:
        uuids = frozenset(item.uuid for item in violation.items) & copper
        if violation.type == "clearance" and len(uuids) == 2 and not uuids & canary:
            found.add(frozenset(uuids))
    return found


def keepout_parity() -> str:
    run = keepout_parity_run()
    if not run.canary:
        return "inconclusive"
    return "equal" if kicad_keepouts(run) == fenolite_keepouts(run.bench) else "different"


def area_parity() -> str:
    run = area_parity_run()
    if not run.canary:
        return "inconclusive"
    return "equal" if kicad_area_pairs(run) == fenolite_area_pairs(run.bench) else "different"


Probes = dict[str, tuple[object, tuple[int, ...]]]


def area_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: Probes = {
        f"area-keepout-{key}": (lambda key=key: keepout_probe(key), both) for key in KEEPOUT_KEYS
    }
    probes["area-keepout-refill"] = (refill_probe, (10,))
    probes["area-name-keep"] = (name_probe, (10,))
    for key in CONDITIONS:
        pid = "dru-cond-area" if key == "area" else f"area-cond-{key}"
        probes[pid] = (lambda key=key: condition_probe(key), both)
    probes["copper-keepout-parity"] = (keepout_parity, both)
    probes["copper-area-parity"] = (area_parity, both)
    return probes


__all__ = [
    "AREA_RULE",
    "CONDITIONS",
    "KEEPOUT_KEYS",
    "Run",
    "area_parity",
    "area_parity_bench",
    "area_probes",
    "condition",
    "condition_probe",
    "condition_selected",
    "fenolite_area_pairs",
    "fenolite_keepouts",
    "keepout",
    "keepout_parity",
    "keepout_parity_bench",
    "keepout_probe",
    "name_probe",
    "refill_probe",
]
