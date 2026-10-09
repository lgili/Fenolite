# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracle benches of the pair and length rule kinds and of the pair selector (capability kicad-oracle,
"Differential pair rules are enforced by kicad-cli"; hypotheses H-K-DRU-PAIR and H-K-DRU-PAIRSEL; change
c0104).

Every pair is two 0.2 mm tracks on ``F.Cu``, 0.3 mm apart edge to edge unless a row says otherwise, on two
nets of its own that pair by name. The project is ``{}``, so the ``Default`` class (clearance 0.2 mm) is
below every gap. The rules are model rules lowered by ``lower_rules``, and the canary is scoped to its own
net, because the pairs are closer than the canary's 3 mm. Three benches:

- ``kinds``: one row and one rule per kind row, case and selector case; every rule selects its own row,
  so one ``pcb drc`` run judges them all;
- ``scope``: a rule on every pair (``*``), and a clearance rule with the pair on both sides after a
  board-wide clearance rule, which is written before the canary;
- ``order``: two gap rules and two length rules that match one row, in both orders.

Net names and values are authored for these benches.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from types import MappingProxyType

import _kindcases as kc
import _rulebench as rb
import _rulecases as rc

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

MM = rb.MM
WIDTH = 200_000
GAP = 300_000
PAIR_KINDS: tuple[RuleKind, ...] = (
    "diff_pair_gap",
    "diff_pair_uncoupled",
    "skew",
    "diff_pair_skew",
    "length",
)
VIOLATION_TYPES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "diff_pair_gap": frozenset({"diff_pair_gap_out_of_range"}),
        "diff_pair_uncoupled": frozenset({"diff_pair_uncoupled_length_too_long"}),
        "skew": frozenset({"skew_out_of_range"}),
        "diff_pair_skew": frozenset({"skew_out_of_range"}),
        "length": frozenset({"length_out_of_range"}),
    }
)
"""The DRC violation types of each kind (``docs/formats/kicad/rules.md``)."""
CLEARANCE = frozenset({"clearance"})


@contextmanager
def pair_support(major: int | None = None) -> Iterator[None]:
    """``KIND_SUPPORT`` of the five kinds and ``SELECTOR_SUPPORT["diff_pair"]`` holding ``major`` (the
    running major when ``None``) while a bench lowers its rules: the probes are what puts a major into
    those tables."""
    saved_kinds, saved_keys = rulemap.KIND_SUPPORT, rulemap.SELECTOR_SUPPORT
    running = rc.major() if major is None else major
    kinds = {k: frozenset(v) for k, v in saved_kinds.items()}
    for kind in PAIR_KINDS:
        kinds[kind] = kinds[kind] | {running}
    keys = {k: frozenset(v) for k, v in saved_keys.items()}
    keys["diff_pair"] = keys["diff_pair"] | {running}
    rulemap.KIND_SUPPORT = MappingProxyType(kinds)
    rulemap.SELECTOR_SUPPORT = MappingProxyType(keys)
    try:
        yield
    finally:
        rulemap.KIND_SUPPORT, rulemap.SELECTOR_SUPPORT = saved_kinds, saved_keys


def dp(base: str) -> Selector:
    return Selector("diff_pair", base)


def net(name: str) -> Selector:
    return Selector("net", name)


def either(*names: str) -> Selector:
    return Selector("or", items=tuple(net(name) for name in names))


def rule(name: str, kind: RuleKind, a: Selector, *, priority: int = 0, **fields: object) -> Rule:
    return Rule(
        id=derived_id("rul", "oracle", f"pair:{name}"),
        name=name,
        kind=kind,
        selector_a=a,
        priority=priority,
        **fields,  # type: ignore[arg-type]
    )


def lowered(*rules: Rule) -> str:
    """The rules text of ``rules`` for the running major, without a canary."""
    with pair_support():
        return lower_rules(
            RuleSet(id=derived_id("rst", "oracle", "pair"), rules=rules), target=rc.major()
        ).text


def body(text: str) -> str:
    """A rules text without its version line."""
    return text.partition("(version 1)\n")[2]


def pair_row(made: rb.Builder, label: str, positive: str, negative: str, *, gap: int = GAP,
             long_p: int = 10 * MM, long_n: int = 10 * MM, layer: str = "F.Cu") -> None:  # fmt: skip
    """Two parallel 0.2 mm tracks from the left margin, ``gap`` apart edge to edge, ``long_p`` and
    ``long_n`` long: items ``<label>_a`` (the positive net) and ``<label>_b``."""
    y = made.row()
    made.track(f"{label}_a", positive, y, layer=layer, width=WIDTH, x0=rb.LEFT, x1=rb.LEFT + long_p)
    made.track(
        f"{label}_b", negative, y + gap + WIDTH, layer=layer, width=WIDTH, x0=rb.LEFT, x1=rb.LEFT + long_n
    )


def pair(made: rb.Builder, base: str, **fields: int) -> None:
    """The pair ``<base>_P``/``<base>_N`` under the label ``base``."""
    pair_row(made, base, f"{base}_P", f"{base}_N", **fields)


def single(made: rb.Builder, name: str, *, length: int = 20 * MM) -> None:
    """One 0.2 mm track of ``length`` on the net ``name``: item ``<name>_a``."""
    made.track(f"{name}_a", name, made.row(), width=WIDTH, x0=rb.LEFT, x1=rb.LEFT + length)


def hit(result: kc.Run, label: str, types: frozenset[str]) -> bool:
    """Whether a violation of ``types`` names an item of the row ``label``."""
    assert result.report is not None
    wanted = [
        uuid
        for key, uuids in result.bench.items.items()
        if key in (f"{label}_a", f"{label}_b")
        for uuid in uuids
    ]
    return any(v.type in types for v in rb.violations_of(result.report, wanted))


# -- the kinds bench ---------------------------------------------------------------------------------

GAPPED = ("GA", "GB", "GC", "GD", "GE", "GF", "GH", "GI", "GJ", "XA", "XB", "XC")
"""Pairs 0.3 mm apart, except ``GB`` (0.4 mm), under a gap rule each."""
LENGTHS = ("LA", "LB", "LC", "LD", "LE", "LF", "LG")
"""Single nets of 20 mm tracks under a length rule each."""


@cache
def kinds_bench() -> rb.Bench:
    made = rb.builder()
    for base in GAPPED:
        pair(made, base, gap=400_000 if base == "GB" else GAP)
    pair_row(made, "GG", "GG_A", "GG_B")  # 0.3 mm apart, and no pair by name
    pair(made, "UA", long_p=13 * MM)  # the positive track 3 mm longer
    pair(made, "UB", long_p=11 * MM)
    pair(made, "UC", gap=3 * MM)  # equal tracks 3 mm apart
    pair(made, "SA", long_p=20 * MM, long_n=21 * MM)
    pair(made, "SB", long_p=20 * MM, long_n=20_200_000)
    pair(made, "SM", long_p=20 * MM, long_n=21 * MM)
    for base, length in (("SC", 20), ("SD", 23), ("SE", 20), ("SF", 23)):
        pair(made, base, long_p=length * MM, long_n=length * MM)
    for name in LENGTHS:
        single(made, name)
    return made.build()


def kinds_rules() -> tuple[Rule, ...]:
    gap, skew = "diff_pair_gap", "diff_pair_skew"
    return (
        rule("gap ga", gap, dp("GA_"), min=350_000),
        rule("gap gb", gap, dp("GB_"), min=350_000),
        rule("gap gc", gap, dp("GC_"), max=250_000),
        rule("gap gd opt", gap, dp("GD_"), opt=500_000),
        rule("gap ge inside", gap, dp("GE_"), min=250_000, opt=300_000, max=350_000),
        rule("gap gf below", gap, dp("GF_"), min=350_000, opt=350_000, max=350_000),
        rule("gap gh layer", gap, dp("GH_"), min=350_000, layers=("F.Cu",)),
        rule("gap gi layer", gap, dp("GI_"), min=350_000, layers=("B.Cu",)),
        rule("gap gj net", gap, net("GJ_P"), min=350_000),
        rule("gap gg nets", gap, either("GG_A", "GG_B"), min=350_000),
        rule("gap xa", gap, dp("XA_"), min=350_000),
        rule("gap xb", gap, dp("XB"), min=350_000),
        rule("gap xc", gap, dp("xc_"), min=350_000),
        rule("unc ua", "diff_pair_uncoupled", dp("UA_"), max=2 * MM),
        rule("unc ub", "diff_pair_uncoupled", dp("UB_"), max=2 * MM),
        rule("unc uc", "diff_pair_uncoupled", dp("UC_"), max=2 * MM),
        rule("skew sa", skew, dp("SA_"), max=500_000),
        rule("skew sb", skew, dp("SB_"), max=500_000),
        rule("skew sm opt", skew, dp("SM_"), opt=100_000),
        rule("skew group", "skew", either("SC_P", "SC_N", "SD_P", "SD_N"), max=500_000),
        rule("skew within", skew, either("SE_P", "SE_N", "SF_P", "SF_N"), max=500_000),
        rule("len la", "length", net("LA"), min=25 * MM),
        rule("len lb", "length", net("LB"), max=15 * MM),
        rule("len lc", "length", net("LC"), min=25 * MM, max=30 * MM),
        rule("len ld", "length", net("LD"), min=15 * MM, max=25 * MM),
        rule("len le opt", "length", net("LE"), opt=30 * MM),
        rule("len lf inside", "length", net("LF"), min=15 * MM, opt=20 * MM, max=25 * MM),
        rule("len lg below", "length", net("LG"), min=25 * MM, opt=27 * MM, max=30 * MM),
    )


@cache
def kinds() -> kc.Run:
    return kc.run(kinds_bench(), rb.with_scoped_canary(lowered(*kinds_rules())))


KIND_ROWS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = MappingProxyType(
    {
        "diff_pair_gap": (("GA", "GC"), ("GB",)),
        "diff_pair_uncoupled": (("UA",), ("UB",)),
        "diff_pair_skew": (("SA",), ("SB",)),
        "skew": (("SC",), ("SD",)),
        "length": (("LA", "LB", "LC"), ("LD",)),
    }
)
"""Kind → the rows that must be reported and the control rows that must not."""
CASES: Mapping[str, tuple[str, str, bool]] = MappingProxyType(
    {
        "opt-gap": ("GD", "diff_pair_gap", False),
        "opt-skew": ("SM", "diff_pair_skew", False),
        "opt-length": ("LE", "length", False),
        "opt-gap-inside": ("GE", "diff_pair_gap", False),
        "opt-gap-below": ("GF", "diff_pair_gap", True),
        "opt-length-inside": ("LF", "length", False),
        "opt-length-below": ("LG", "length", True),
        "layer-same": ("GH", "diff_pair_gap", True),
        "layer-other": ("GI", "diff_pair_gap", False),
        "gap-not-a-pair": ("GG", "diff_pair_gap", False),
        "gap-positive-net": ("GJ", "diff_pair_gap", True),
        "uncoupled-far": ("UC", "diff_pair_uncoupled", False),
        "skew-within-equal": ("SE", "diff_pair_skew", False),
    }
)
"""Case → its row, the kind whose DRC type is looked for, and whether the row is reported."""
SELECTED: Mapping[str, tuple[str, bool]] = MappingProxyType(
    {"underscore": ("XA", True), "bare": ("XB", True), "lower": ("XC", False)}
)
"""Selector case of the kinds bench → its row and whether the gap rule on its base reports it."""


def reported(result: kc.Run, row: str, kind: str) -> bool:
    return hit(result, row, VIOLATION_TYPES[kind])


def kind_probe(kind: str) -> str:
    result = kinds()
    if not result.canary:
        return "inconclusive"
    probed, controls = KIND_ROWS[kind]
    found = all(reported(result, row, kind) for row in probed)
    return rb.outcome(found and not any(reported(result, row, kind) for row in controls))


def case_probe(case: str) -> str:
    result = kinds()
    if not result.canary:
        return "inconclusive"
    row, kind, _ = CASES[case]
    found = reported(result, row, kind)
    if case == "skew-within-equal":  # neither pair of the rule is reported
        found = found or reported(result, "SF", kind)
    return rb.outcome(found)


def selected_probe(case: str) -> str:
    result = kinds()
    if not result.canary:
        return "inconclusive"
    return rb.outcome(reported(result, SELECTED[case][0], "diff_pair_gap"))


# -- the scope bench: every pair, and the clearance inside a pair ------------------------------------


@cache
def scope_bench() -> rb.Bench:
    made = rb.builder()
    pair(made, "SP")
    pair_row(made, "SQ", "SQ_A", "SQ_B")  # no pair by name
    pair(made, "YA")
    pair(made, "YB")
    return made.build()


def scope_rules() -> str:
    """A board-wide clearance rule of 0.5 mm before the canary, then the gap rule on every pair and a
    clearance rule of 0.1 mm with the pair ``YA_`` on both sides."""
    wide = lowered(rule("wide", "clearance", Selector("all"), min=500_000))
    later = lowered(
        rule("every pair", "diff_pair_gap", dp("*"), min=350_000),
        rule("inside ya", "clearance", dp("YA_"), selector_b=dp("YA_"), min=100_000),
    )
    return "(version 1)\n" + body(wide) + rb.scoped_canary_rule() + body(later)


@cache
def scope() -> kc.Run:
    return kc.run(scope_bench(), scope_rules())


def star_probe() -> str:
    """``present`` when the rule on ``*`` reports the pair and not the two nets that do not pair."""
    result = scope()
    if not result.canary:
        return "inconclusive"
    return rb.outcome(reported(result, "SP", "diff_pair_gap") and not reported(result, "SQ", "diff_pair_gap"))


def both_sides_probe() -> str:
    """``present`` when the pair of the two-sided clearance rule is not reported and the pair without one
    is, under the board-wide rule."""
    result = scope()
    if not result.canary:
        return "inconclusive"
    return rb.outcome(not result.between("YA", CLEARANCE) and result.between("YB", CLEARANCE))


# -- the order bench ---------------------------------------------------------------------------------


@cache
def order_bench() -> rb.Bench:
    made = rb.builder()
    pair(made, "OG")
    single(made, "OL1")
    return made.build()


@cache
def order(direction: str) -> kc.Run:
    """``forward``: the rule that fails the row first and the rule that passes it later; ``reverse``: the
    two swapped. The later rule has priority 1 (``rulemap.rule_order``)."""
    passing, failing = (1, 0) if direction == "forward" else (0, 1)
    rules = (
        rule("gap every", "diff_pair_gap", dp("*"), min=350_000, priority=failing),
        rule("gap og", "diff_pair_gap", dp("OG_"), min=250_000, priority=passing),
        rule("len every", "length", net("OL*"), max=15 * MM, priority=failing),
        rule("len ol", "length", net("OL1"), max=25 * MM, priority=passing),
    )
    return kc.run(order_bench(), rb.with_scoped_canary(lowered(*rules)))


def order_probe(kind: str) -> str:
    """``present`` when the later rule governs: the row is clean with the passing rule last and reported
    with the two swapped."""
    forward, reverse = order("forward"), order("reverse")
    if not (forward.canary and reverse.canary):
        return "inconclusive"
    row = "OG" if kind == "diff_pair_gap" else "OL1"
    return rb.outcome(not reported(forward, row, kind) and reported(reverse, row, kind))


def pair_rule_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {}
    for kind in PAIR_KINDS:
        probes[f"dru-kind-{kind}"] = (lambda kind=kind: kind_probe(kind), both)
    for case in CASES:
        probes[f"dru-pair-{case}"] = (lambda case=case: case_probe(case), both)
    probes["dru-pair-order-gap"] = (lambda: order_probe("diff_pair_gap"), both)
    probes["dru-pair-order-length"] = (lambda: order_probe("length"), both)
    for case in SELECTED:
        probes[f"dru-pair-sel-{case}"] = (lambda case=case: selected_probe(case), both)
    probes["dru-pair-sel-star"] = (star_probe, both)
    probes["dru-pair-sel-both-sides"] = (both_sides_probe, both)
    return probes


__all__ = [
    "CASES",
    "KIND_ROWS",
    "PAIR_KINDS",
    "SELECTED",
    "VIOLATION_TYPES",
    "both_sides_probe",
    "case_probe",
    "kind_probe",
    "kinds",
    "kinds_bench",
    "kinds_rules",
    "order",
    "order_probe",
    "pair_rule_probes",
    "pair_support",
    "scope",
    "scope_rules",
    "selected_probe",
    "star_probe",
]
