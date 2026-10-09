# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracle cases of the six rule kinds of change c0071 (capability kicad-oracle, "New rule kinds are
enforced by kicad-cli"; hypotheses H-K-DRU-KIND-2, H-K-DRU-COURTYARD and H-K-PRO-MIN-RULE-3).

Every bench carries the canary scoped to its own net (``_rulebench.with_scoped_canary``). Each case runs
``pcb drc`` once per session; the ``dru-kind-*``, ``dru-courtyard-*``, ``dru-order-hole-*`` and
``pro-min-rule-*`` probes of ``_probes.PROBES`` record the outcomes.

Geometry, chosen so that only the rule under test can flag the probed item (the board-setup minimums of an
empty project are 0.25 mm for both hole distances and 0.1 mm for the annular ring):

- ``hole_to_hole``: two vias whose holes are 0.7 mm apart, rule 1 mm on the net of one;
- ``hole_clearance``: a via hole 0.45 mm from a track of another net, rule 0.8 mm on the via's net;
- ``annular_width``: a via with a ring of 0.1 mm, rule 0.15 mm on its net; the control ring is 0.12 mm;
- ``courtyard_clearance``: two footprints with courtyards 0.5 mm apart, rule 1 mm on one reference;
- ``silk_clearance``: two footprints whose silkscreen lines are 0.05 mm apart, a board-wide rule of 0.1 mm;
  the control pair is 0.3 mm apart, and a footprint's own silkscreen is 0.157 mm from its own pads;
- ``creepage``: the slot bench of the board analyses (c0047), with a rule 50 µm below and 50 µm above the
  11 mm that Fenolite computes.

Change c0107 adds the kind ``no_tracks`` (capability kicad-oracle, "Plane routing passes the oracle";
hypothesis H-K-DRU-NOTRACKS): a track of the net ``NT`` on ``B.Cu`` under a rule that keeps ``NT`` off
``B.Cu``, with two controls, a track of ``NT`` on ``F.Cu`` and a track of another net on ``B.Cu``. Its rules
are written by ``lower_rules``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType

import _creepbench
import _rulebench as rb
import _rulecases as rc
from _analysis import BRACKET_NM, CreepBench, creep_bench

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import pro
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.core.units import format_length
from fenolite.model.rules import Rule, RuleSet, Selector

MM = rb.MM
NEW_KINDS = (
    "hole_to_hole",
    "hole_clearance",
    "annular_width",
    "courtyard_clearance",
    "silk_clearance",
    "creepage",
)
VIOLATION_TYPES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "hole_to_hole": frozenset({"hole_to_hole"}),
        "hole_clearance": frozenset({"hole_clearance"}),
        "annular_width": frozenset({"annular_width"}),
        "courtyard_clearance": frozenset({"courtyards_overlap"}),
        "silk_clearance": frozenset({"silk_overlap", "silk_over_copper"}),
        "creepage": frozenset({"creepage"}),
    }
)
"""The DRC violation types of each new kind (``docs/formats/kicad/rules.md``)."""
FLOOR_KINDS = ("hole_to_hole", "hole_clearance", "annular_width")
"""The new kinds whose board-setup minimum is above zero in the project template."""
BOARD_RULES: tuple[tuple[str, str | None, int], ...] = (
    ("hole_to_hole", "A.NetName == 'HH_A'", MM),
    ("hole_clearance", "A.NetName == 'HC_V'", 800_000),
    ("annular_width", "A.NetName == 'AW'", 150_000),
    ("courtyard_clearance", "A.Reference == 'CY1'", MM),
    ("silk_clearance", None, 100_000),
)
"""``(kind, condition, min)`` of the five rules of the board bench."""
FLOOR_RULES: Mapping[str, int] = MappingProxyType(
    {"hole_to_hole": 100_000, "hole_clearance": 100_000, "annular_width": 50_000}
)
"""The ``min`` of each board-wide floor rule, below the template minimum of its kind."""


def target() -> int:
    """The board format a bench is written in: the running major."""
    return 10 if rc.major() >= 10 else 9


def rule_text(name: str, constraint: str, minimum: int, condition: str | None = None) -> str:
    """One rule in the form the rules writer gives it: the name, the condition when there is one, the
    constraint with its ``min``, and the severity."""
    lines = [f'(rule "{name}"']
    if condition is not None:
        lines.append(f'\t(condition "{condition}")')
    lines.append(f"\t(constraint {constraint} (min {format_length(minimum, 'mm')}))")
    lines.append("\t(severity error)")
    return "\n".join(lines) + "\n)\n"


def rules_text(*rules: str) -> str:
    return rb.with_scoped_canary("(version 1)\n" + "".join(rules))


@dataclass(frozen=True)
class Run:
    """One DRC run of a rule bench, and the uuids of every node of each placed footprint."""

    bench: rb.Bench
    report: DrcReport | None
    inside: Mapping[str, frozenset[str]]

    @property
    def canary(self) -> bool:
        return self.report is not None and rb.canary_fired(self.report, self.bench)

    def between(self, label: str, types: frozenset[str]) -> bool:
        """Whether a violation of ``types`` names an item of ``<label>_a`` and one of ``<label>_b``."""
        assert self.report is not None
        a, b = self.bench.uuids(f"{label}_a"), self.bench.uuids(f"{label}_b")
        return any(v.type in types for v in rb.violations_between(self.report, a, b))

    def of(self, label: str, types: frozenset[str]) -> bool:
        assert self.report is not None
        return any(v.type in types for v in rb.violations_of(self.report, self.bench.uuids(label)))

    def footprints(self, refs: tuple[str, str], types: frozenset[str]) -> bool:
        """Whether a violation of ``types`` names an item inside each of the two footprints ``refs``."""
        assert self.report is not None
        first, second = self.inside[refs[0]], self.inside[refs[1]]
        return any(v.type in types for v in rb.violations_between(self.report, first, second))

    def any_of(self, refs: tuple[str, ...], types: frozenset[str]) -> bool:
        """Whether a violation of ``types`` names an item inside any footprint of ``refs``."""
        assert self.report is not None
        wanted = frozenset().union(*(self.inside[ref] for ref in refs))
        return any(v.type in types for v in rb.violations_of(self.report, wanted))


def _uuids(node: Node) -> set[str]:
    found: set[str] = set()
    for child in node.nodes():
        if child.name == "uuid" and child.atoms():
            found.add(child.atoms()[0].value)
        else:
            found |= _uuids(child)
    return found


def inside_footprints(text: str) -> dict[str, frozenset[str]]:
    """Reference → the uuids of the footprint node and of everything inside it, from a written board."""
    found: dict[str, frozenset[str]] = {}
    for node in parse(text).nodes():
        if node.name != "footprint":
            continue
        for child in node.nodes():
            atoms = child.atoms()
            if child.name == "property" and len(atoms) > 1 and atoms[0].value == "Reference":
                found[atoms[1].value] = frozenset(_uuids(node))
    return found


def run(bench: rb.Bench, rules: str, *, board_target: int | None = None, project: str = rb.PROJECT) -> Run:
    wanted = target() if board_target is None else board_target
    report = rb.drc(rc.runner(), bench, rules, wanted, project=project)
    return Run(bench, report, inside_footprints(write_board(bench.design, target=wanted).text))


# -- the five kinds of the board bench


@cache
def board_bench() -> rb.Bench:
    made = rb.builder()
    made.via_pair("hole_to_hole_probe", "HH_A", "HH_B", gap=400_000)
    made.via_pair("hole_to_hole_control", "HHC_A", "HHC_B", gap=400_000)
    made.via_track("hole_clearance_probe", "HC_V", "HC_T", gap=300_000)
    made.via_track("hole_clearance_control", "HCC_V", "HCC_T", gap=300_000)
    made.lone_via("annular_width_probe", "AW", diameter=600_000, drill=400_000)
    made.lone_via("annular_width_control", "AWC", diameter=640_000, drill=400_000)
    made.courtyard_pair("courtyard_clearance_probe", ("CY1", "CY2"), gap=500_000, target=target())
    made.courtyard_pair("courtyard_clearance_control", ("CC1", "CC2"), gap=500_000, target=target())
    made.silk_pair("silk_clearance_probe", ("SK1", "SK2"), gap=50_000, target=target())
    made.silk_pair("silk_clearance_control", ("SKC1", "SKC2"), gap=300_000, target=target())
    return made.build()


def board_rules() -> str:
    """The rules text of the board bench, as Decisions 1 and 2 of the design write the five rules."""
    return rules_text(
        *(
            rule_text(f"fenolite_0_{kind}", kind, minimum, condition)
            for kind, condition, minimum in BOARD_RULES
        )
    )


@cache
def board_kinds() -> Run:
    return run(board_bench(), board_rules())


def flagged(result: Run, kind: str, which: str) -> bool:
    """Whether the ``probe`` or ``control`` item of ``kind`` has a violation of the kind's types."""
    types = VIOLATION_TYPES[kind]
    label = f"{kind}_{which}"
    if kind == "annular_width":
        return result.of(label, types)
    if kind == "silk_clearance":
        return result.any_of(("SK1", "SK2") if which == "probe" else ("SKC1", "SKC2"), types)
    return result.between(label, types)


# -- creepage, on the slot bench of the board analyses


@cache
def creepage_runs() -> tuple[tuple[DrcReport | None, CreepBench], ...]:
    """The slot bench with a creepage rule on its two nets, 50 µm below and above Fenolite's value."""
    bench = creep_bench("slot")
    found = []
    for minimum in (bench.creepage - BRACKET_NM, bench.creepage + BRACKET_NM):
        rule = rule_text("fenolite_0_creepage", "creepage", minimum, "A.NetName == 'A' && B.NetName == 'B'")
        found.append((_creepbench.drc(rc.runner(), bench, minimum, target(), rules=rules_text(rule)), bench))
    return tuple(found)


def creepage_probe() -> str:
    (below, bench), (above, _) = creepage_runs()
    if below is None or above is None:
        return "inconclusive"
    if not (_creepbench.canary_fired(below, bench) and _creepbench.canary_fired(above, bench)):
        return "inconclusive"
    return rb.outcome(
        _creepbench.creepage_found(above, bench) and not _creepbench.creepage_found(below, bench)
    )


def kind_probe(kind: str) -> str:
    """``present`` when the probed item has a violation of the kind's types and the control has none, with
    the canary in every run."""
    if kind == "creepage":
        return creepage_probe()
    result = board_kinds()
    if not result.canary:
        return "inconclusive"
    return rb.outcome(flagged(result, kind, "probe") and not flagged(result, kind, "control"))


# -- track layer rules (change c0107)

NO_TRACKS_TYPES = frozenset({"items_not_allowed"})
"""The DRC violation type of a ``disallow track`` rule (``docs/formats/kicad/rules.md``)."""
NO_TRACKS_LABELS = ("no_tracks_probe", "no_tracks_other_layer", "no_tracks_other_net")


def no_tracks_rule() -> Rule:
    """The model rule of the bench: the net ``NT`` takes no track on ``B.Cu``."""
    return Rule(
        id=derived_id("rul", "oracle", "no_tracks"),
        name="no_tracks",
        kind="no_tracks",
        selector_a=Selector("net", "NT"),
        layers=("B.Cu",),
    )


def no_tracks_rules() -> str:
    """The rules text of the bench, written by ``lower_rules``, with the scoped canary."""
    ruleset = RuleSet(id=derived_id("rst", "oracle", "no_tracks"), rules=(no_tracks_rule(),))
    return rb.with_scoped_canary(lower_rules(ruleset, target=10).text)


@cache
def no_tracks_bench() -> rb.Bench:
    made = rb.builder()
    made.track("no_tracks_probe", "NT", made.row(), layer="B.Cu")
    made.track("no_tracks_other_layer", "NT", made.row(), layer="F.Cu")
    made.track("no_tracks_other_net", "NTC", made.row(), layer="B.Cu")
    return made.build()


@cache
def no_tracks() -> Run:
    return run(no_tracks_bench(), no_tracks_rules())


def no_tracks_probe() -> str:
    """``present`` when the track of the net on the rule's layer is the one item reported as not allowed:
    neither its track on the other layer nor the other net's track on the rule's layer is."""
    result = no_tracks()
    if not result.canary:
        return "inconclusive"
    probe, *controls = (result.of(label, NO_TRACKS_TYPES) for label in NO_TRACKS_LABELS)
    return rb.outcome(probe and not any(controls))


# -- how a courtyard rule selects a footprint


@cache
def courtyard_bench() -> rb.Bench:
    made = rb.builder()
    made.courtyard_pair("cy", ("CY1", "CY2"), gap=500_000, target=target())
    return made.build()


@cache
def courtyard(form: str) -> Run:
    """The pair ``CY1``/``CY2`` with a 1 mm courtyard rule on ``CY1``, selected by ``reference`` or as a
    ``member`` of the footprint."""
    condition = {"reference": "A.Reference == 'CY1'", "member": "A.memberOfFootprint('CY1')"}[form]
    return run(
        courtyard_bench(), rules_text(rule_text("fenolite_0_cy", "courtyard_clearance", MM, condition))
    )


def courtyard_probe(form: str) -> str:
    result = courtyard(form)
    if not result.canary:
        return "inconclusive"
    return rb.outcome(result.between("cy", VIOLATION_TYPES["courtyard_clearance"]))


# -- two overlapping rules of a new kind


@cache
def hole_order_bench() -> rb.Bench:
    made = rb.builder()
    made.via_pair("ord", "OH_A", "OH_B", gap=400_000)
    return made.build()


@cache
def hole_order(direction: str) -> Run:
    """Two ``hole_to_hole`` rules on the net of one via of a pair whose holes are 0.7 mm apart: 0.5 mm then
    1 mm (``forward``), or 1 mm then 0.5 mm (``reverse``)."""
    values = (500_000, MM) if direction == "forward" else (MM, 500_000)
    rules = [
        rule_text(f"fenolite_{n}_order", "hole_to_hole", value, "A.NetName == 'OH_A'")
        for n, value in enumerate(values)
    ]
    return run(hole_order_bench(), rules_text(*rules))


def hole_order_probe(direction: str) -> str:
    result = hole_order(direction)
    if not result.canary:
        return "inconclusive"
    return rb.outcome(result.between("ord", VIOLATION_TYPES["hole_to_hole"]))


# -- board-wide rules below the template's board-setup minimums


@cache
def floor_bench() -> rb.Bench:
    """Items between each floor rule and the template minimum of its kind: via holes 0.2 mm apart, a via
    hole 0.2 mm from a track, and a via ring of 0.075 mm."""
    made = rb.builder()
    x = (rb.LEFT + rb.RIGHT) // 2
    y = made.row()
    made.via("hole_to_hole_a", "FH_A", Point(x, y), diameter=450_000, drill=300_000)
    made.via("hole_to_hole_b", "FH_B", Point(x, y + 500_000), diameter=450_000, drill=300_000)
    y = made.row()
    made.via("hole_clearance_a", "FC_V", Point(x, y), diameter=450_000, drill=300_000)
    made.track("hole_clearance_b", "FC_T", y + 150_000 + 200_000 + rb.WIDTH // 2)
    made.lone_via("annular_width", "FA", diameter=450_000, drill=300_000)
    return made.build()


@cache
def floor(board_target: int, with_rules: bool) -> Run:
    """The floor bench for ``board_target`` on the template project, with the three board-wide rules or
    without them.

    Both runs start with a board-wide clearance rule of 0.05 mm, before the canary: KiCad gives a pair whose
    copper clearance fails a ``clearance`` entry and no ``hole_clearance`` entry (measured on this bench with
    the template's 0.2 mm class clearance), and the copper of a hole 0.2 mm from a track is always closer
    than that. The canary comes after it, so the canary still governs its own pair."""
    rules = [rule_text(f"fenolite_0_{kind}", kind, FLOOR_RULES[kind]) for kind in FLOOR_KINDS]
    project = pro.write_project_text(pro.template(board_target))
    clearance = rule_text("fenolite_0_clearance", "clearance", 50_000)
    text = "(version 1)\n" + clearance + rb.scoped_canary_rule() + "".join(rules if with_rules else ())
    return run(floor_bench(), text, board_target=board_target, project=project)


def _floor_flagged(result: Run, kind: str) -> bool:
    types = VIOLATION_TYPES[kind]
    return result.of(kind, types) if kind == "annular_width" else result.between(kind, types)


def floor_probe(kind: str, board_target: int) -> str:
    """``present`` when the rule governs below the template minimum: the item is reported without the rule
    and not reported with it, with the canary in both runs."""
    ruled, plain = floor(board_target, True), floor(board_target, False)
    if not (ruled.canary and plain.canary):
        return "inconclusive"
    if not _floor_flagged(plain, kind):
        return "inconclusive"
    return rb.outcome(not _floor_flagged(ruled, kind))


def kind_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {}
    for kind in NEW_KINDS:
        probes[f"dru-kind-{kind}"] = (lambda kind=kind: kind_probe(kind), both)
    probes["dru-kind-no_tracks"] = (no_tracks_probe, both)  # change c0107
    for form in ("reference", "member"):
        probes[f"dru-courtyard-{form}"] = (lambda form=form: courtyard_probe(form), both)
    for direction in ("forward", "reverse"):
        probes[f"dru-order-hole-{direction}"] = (
            lambda direction=direction: hole_order_probe(direction),
            both,
        )
    for board_target, majors in ((10, (10,)), (9, both)):
        for kind in FLOOR_KINDS:
            probes[f"pro-min-rule-{kind}-t{board_target}"] = (
                lambda kind=kind, board_target=board_target: floor_probe(kind, board_target),
                majors,
            )
    return probes


__all__ = [
    "BOARD_RULES",
    "FLOOR_KINDS",
    "FLOOR_RULES",
    "NEW_KINDS",
    "VIOLATION_TYPES",
    "Run",
    "board_kinds",
    "board_rules",
    "courtyard",
    "courtyard_probe",
    "creepage_probe",
    "creepage_runs",
    "flagged",
    "floor",
    "floor_probe",
    "hole_order",
    "hole_order_probe",
    "kind_probe",
    "kind_probes",
    "no_tracks",
    "no_tracks_bench",
    "no_tracks_probe",
    "no_tracks_rule",
    "no_tracks_rules",
    "rule_text",
    "rules_text",
]
