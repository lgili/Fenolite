# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rules oracle cases (c0018 Decision 18): dialect, broken control, order, kinds, conditions and
gating. Each case builds its bench, runs ``pcb drc`` once per session and gives a ``Result``; the
``dru-*`` probes of ``_probes.PROBES`` record their outcomes.

A case that needs a selector key sets ``rulemap.SELECTOR_SUPPORT`` for the running major only while it
lowers its rules; the DRC report still judges the outcome.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType

import _rulebench as rb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.dru import RuleItem, parse_rules, print_rules, read_rules, write_rules
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

MM = rb.MM


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


IGNORED_TYPES = frozenset(
    {"track_dangling", "via_dangling", "lib_footprint_issues", "lib_footprint_mismatch"}
)
"""Warnings every bench gives for its free items; they never judge a rule."""
KINDS: tuple[RuleKind, ...] = (
    "clearance",
    "edge_clearance",
    "track_width",
    "via_diameter",
    "hole_size",
    "via_drill",
)
CONDITION_KEYS = (
    "net",
    "netclass",
    "ref",
    "item_kind",
    "layer_clause",
    "and",
    "or",
    "not",
    "selector_b",
    "glob",
)


@dataclass(frozen=True)
class Result:
    bench: rb.Bench
    report: DrcReport | None

    @property
    def canary(self) -> bool:
        return self.report is not None and rb.canary_fired(self.report, self.bench)

    def between(self, label: str, kind: str | None = "clearance") -> bool:
        assert self.report is not None
        a, b = self.bench.uuids(f"{label}_a"), self.bench.uuids(f"{label}_b")
        return bool(rb.violations_between(self.report, a, b, kind))

    def types_of(self, label: str) -> tuple[str, ...]:
        assert self.report is not None
        found = rb.violations_of(self.report, self.bench.uuids(label))
        return tuple(sorted({v.type for v in found if v.type not in IGNORED_TYPES}))


@contextmanager
def supported(*keys: str) -> Iterator[None]:
    """``SELECTOR_SUPPORT`` with ``keys`` holding the running major, for the duration of a lowering."""
    saved = rulemap.SELECTOR_SUPPORT
    table = {k: frozenset(v) for k, v in saved.items()}
    for key in keys:
        table[key] = table[key] | {major()}
    rulemap.SELECTOR_SUPPORT = MappingProxyType(table)
    try:
        yield
    finally:
        rulemap.SELECTOR_SUPPORT = saved


_N = iter(range(1, 10_000))


def rule(
    kind: RuleKind = "clearance", a: Selector | None = None, *, minimum: int = 5 * MM, **fields: object
) -> Rule:
    n = next(_N)
    return Rule(
        id=derived_id("rul", "oracle", str(n)),
        name=f"case{n}",
        kind=kind,
        selector_a=a or Selector("all"),
        min=minimum,
        **fields,  # type: ignore[arg-type]
    )


def lowered(*rules: Rule, keys: tuple[str, ...] = ()) -> str:
    with supported(*keys):
        text = lower_rules(RuleSet(id=derived_id("rst", "oracle", "x"), rules=rules), target=major()).text
    return rb.with_canary(text)


def run(bench: rb.Bench, rules: str) -> Result:
    return Result(bench, rb.drc(runner(), bench, rules, major()))


def net(value: str) -> Selector:
    return Selector("net", value)


# -- dialect and the broken control


@cache
def dialect(name: str) -> Result:
    made = rb.builder()
    if name == "units":
        made.single("mil", "MIL", width=200_000)
        made.single("inch", "INCH", width=250_000)
    return run(made.build(), rb.with_canary((rb.RULES / f"{name}.kicad_dru").read_text(encoding="utf-8")))


@cache
def broken(name: str = "broken") -> Result:
    """``broken.kicad_dru`` (or the ``ten_only.kicad_dru`` fallback) copied verbatim onto a bench."""
    return run(rb.builder().build(), (rb.RULES / f"{name}.kicad_dru").read_text(encoding="utf-8"))


# -- order


def _reversed_overlap() -> str:
    document = parse_rules((rb.RULES / "overlap.kicad_dru").read_text(encoding="utf-8"))
    rules = [i for i in document.items if isinstance(i, RuleItem)]
    others = [i for i in document.items if not isinstance(i, RuleItem)]
    return print_rules([*others, *reversed(rules)])


@cache
def order(direction: str) -> Result:
    made = rb.builder()
    made.pair("ord", "ORD_A", "ORD_B", gap=2 * MM)
    text = (
        (rb.RULES / "overlap.kicad_dru").read_text(encoding="utf-8")
        if direction == "forward"
        else _reversed_overlap()
    )
    return run(made.build(), rb.with_canary(text))


# -- kinds


@cache
def kinds() -> Result:
    made = rb.builder()
    made.pair("clearance_probe", "K1", "K2")
    made.pair("clearance_control", "K3", "K4")
    made.edge("edge_clearance_probe", "E1")
    made.edge("edge_clearance_control", "E2")
    made.single("track_width_probe", "W1")
    made.single("track_width_control", "W2")
    made.lone_via("via_diameter_probe", "VD1")
    made.lone_via("via_diameter_control", "VD2")
    made.lone_via("hole_size_probe", "H1")
    made.lone_via("hole_size_control", "H2")
    made.lone_via("via_drill_probe", "VR1")
    made.lone_via("via_drill_control", "VR2")
    rules = (
        rule("clearance", net("K1")),
        rule("edge_clearance", net("E1")),
        rule("track_width", net("W1"), minimum=300_000),
        rule("via_diameter", net("VD1"), minimum=MM),
        rule("hole_size", net("H1"), minimum=500_000),
        rule("via_drill", net("VR1"), minimum=500_000),
    )
    return run(made.build(), lowered(*rules, keys=("net",)))


def kind_probe(kind: str) -> str:
    """``present`` when the probed item has a rule violation, the control has none, and the canary fired."""
    result = kinds()
    label = "clearance_probe_a" if kind == "clearance" else f"{kind}_probe"
    control = "clearance_control_a" if kind == "clearance" else f"{kind}_control"
    return judged((result,), bool(result.types_of(label)) and not result.types_of(control))


# -- conditions


@cache
def condition(key: str) -> tuple[Result, ...]:
    """The runs of one condition case: ``(probe run,)``, or ``(probe run, control run)`` for netclass."""
    made = rb.builder()
    if key == "net":
        made.pair("probe", "N1", "N2")
        made.pair("control", "N3", "N4")
        return (run(made.build(), lowered(rule(a=net("N1")), keys=("net",))),)
    if key == "netclass":
        made.pair("probe", "P1", "P2")
        bench = made.build()
        hit = run(bench, lowered(rule(a=Selector("netclass", "Default")), keys=("netclass",)))
        miss = run(bench, lowered(rule(a=Selector("netclass", "NoSuchClass")), keys=("netclass",)))
        return hit, miss
    if key == "ref":
        made.parts("probe", ("R1", "R2"), target=major())
        made.parts("control", ("R3", "R4"), target=major())
        return (run(made.build(), lowered(rule(a=Selector("ref", "R1")), keys=("ref",))),)
    if key == "item_kind":
        made.via_track("probe", "IK1", "IK2")
        made.pair("control", "IK3", "IK4")
        return (run(made.build(), lowered(rule(a=Selector("item_kind", "via")), keys=("item_kind",))),)
    if key == "layer_clause":
        made.pair("probe", "LA1", "LA2", layer="B.Cu")
        made.pair("control", "LA3", "LA4")
        return (run(made.build(), lowered(rule(layers=("B.Cu",)), keys=("layer_clause",))),)
    if key == "and":
        made.pair("probe", "A1", "A2")
        made.via_track("control", "A1", "A3")
        selector = Selector("and", items=(net("A1"), Selector("item_kind", "track")))
        return (run(made.build(), lowered(rule(a=selector), keys=("and", "net", "item_kind"))),)
    if key == "or":
        made.pair("probe", "O2", "O3")
        made.pair("control", "O4", "O5")
        selector = Selector("or", items=(net("O1"), net("O2")))
        return (run(made.build(), lowered(rule(a=selector), keys=("or", "net"))),)
    if key == "not":
        made.pair("probe", "T1", "T2")
        made.via_track("control", "T1", "T3")
        selector = Selector("and", items=(net("T1"), Selector("not", items=(Selector("item_kind", "via"),))))
        return (run(made.build(), lowered(rule(a=selector), keys=("and", "not", "net", "item_kind"))),)
    if key == "selector_b":
        made.pair("probe", "SB1", "SB2")
        made.pair("control", "SB1", "SB3")
        return (
            run(made.build(), lowered(rule(a=net("SB1"), selector_b=net("SB2")), keys=("selector_b", "net"))),
        )
    if key == "glob":
        made.pair("probe", "PWR_A", "PWR_B")
        made.pair("control", "SIG_A", "SIG_B")
        return (run(made.build(), lowered(rule(a=net("PWR_*")), keys=("glob", "net"))),)
    if key == "case":
        made.pair("probe", "LC1", "LC2")
        made.pair("control", "LC3", "LC4")
        return (run(made.build(), lowered(rule(a=net("lc1")), keys=("net",))),)
    raise KeyError(key)


def condition_probe(key: str) -> str:
    """``present`` when the probe pair's violation is present and the control pair's absent, with the
    canary in every run (for ``case``: whether ``'lc1'`` matched net ``LC1``)."""
    runs = condition(key)
    if key == "netclass":
        hit, miss = runs
        return judged(runs, hit.between("probe") and not miss.between("probe"))
    (only,) = runs
    return judged(runs, only.between("probe", None) and not only.between("control", None))


# -- gating


@cache
def gating(target: int) -> Result:
    """``ten_only.kicad_dru`` read and written for ``target`` (with ``allow_lossy`` for 9)."""
    ruleset = read_rules((rb.RULES / "ten_only.kicad_dru").read_text(encoding="utf-8"))
    text = write_rules(ruleset, target=target, allow_lossy=target < 10)
    return run(rb.builder().build(), text)


def loaded(result: Result) -> str:
    return "load" if result.canary else "reject"


def judged(runs: tuple[Result, ...], found: bool) -> str:
    """``inconclusive`` when a run lacks the canary (the rules file was not loaded), else the outcome."""
    return rb.outcome(found) if all(r.canary for r in runs) else "inconclusive"


def dru_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    forward, reverse = (lambda: order("forward")), (lambda: order("reverse"))
    units = lambda: dialect("units")  # noqa: E731
    probes: dict[str, tuple[object, tuple[int, ...]]] = {
        "dru-broken-silent": (lambda: rb.outcome(broken().canary), both),
        "dru-order-forward": (lambda: judged((forward(),), forward().between("ord")), both),
        "dru-order-reverse": (lambda: judged((reverse(),), reverse().between("ord")), both),
        "dru-gating-lossy-9": (lambda: loaded(gating(9)), both),
        "dru-gating-ten": (lambda: loaded(gating(10)), (10,)),
        "dru-dialect-units-mil": (lambda: judged((units(),), bool(units().types_of("mil"))), both),
        "dru-dialect-units-in": (lambda: judged((units(),), bool(units().types_of("inch"))), both),
    }
    for name in ("comments", "units", "selectors"):
        probes[f"dru-dialect-{name}"] = (lambda name=name: loaded(dialect(name)), both)
    for kind in KINDS:
        probes[f"dru-kind-{kind}"] = (lambda kind=kind: kind_probe(kind), both)
    for key in (*CONDITION_KEYS, "case"):
        probes[f"dru-cond-{key}"] = (lambda key=key: condition_probe(key), both)
    return probes


__all__ = [
    "CONDITION_KEYS",
    "IGNORED_TYPES",
    "KINDS",
    "Result",
    "broken",
    "condition",
    "condition_probe",
    "dialect",
    "dru_probes",
    "gating",
    "judged",
    "kind_probe",
    "kinds",
    "order",
    "supported",
]
