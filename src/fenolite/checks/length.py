# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``length.rules`` stage: the length and skew rules of a board judged on its net lengths, without a
tool (capability verification-loop, "Length rules stage" and "Length stage issue codes"; change c0106).

The rules are the kinds ``length``, ``skew`` and ``diff_pair_skew`` of change c0104; the semantics are
KiCad's (``H-K-NETLEN-RULES``): a length rule judges ``min`` and ``max`` and not ``opt``; every net with a
pad or copper is judged, a net of pads only at length 0; a skew rule groups the nets it governs, a
``diff_pair_skew`` rule each pair among them, and each net's skew is its length less the longest of its
group. ``skew`` and ``diff_pair_skew`` are both KiCad's ``skew`` constraint, so a net's governing skew rule
is the last matching rule of either kind in ``rule_precedence`` order.

The totals come from a ``LengthSource`` (``backends.base``): the length as the tool the board is judged by
counts it, via heights and die lengths included. Without one the routed length alone is judged, with one
``length.input-missing`` warning. No tool runs, and nothing is written.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.base import DesignRulesSource, LengthFacts, LengthSource, NetLength, ProjectSet
from fenolite.checks.clearance import DEFAULT_CLASS, rule_precedence, selector_matches
from fenolite.checks.codes import issue
from fenolite.checks.copper import copper_layers
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import format_length
from fenolite.geometry import arc_length, segment_length
from fenolite.model.design import Design
from fenolite.model.pairs import net_bases
from fenolite.model.rules import Rule, RuleSubject

STAGE = "length.rules"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-RULES",))
"""The stage's verdicts follow KiCad's rules as the canary benches measured them; they cover benches, not
every board, so the level stays ``INFERRED`` when the row is verified."""
LENGTH_KINDS = frozenset({"length"})
SKEW_KINDS = frozenset({"skew", "diff_pair_skew"})


def _mm(value: int) -> str:
    return format_length(value)[:-2]


def _parts(length: NetLength) -> str:
    return f"routed {_mm(length.routed)} mm, vias {_mm(length.vias)} mm, die {_mm(length.die)} mm"


@dataclass(frozen=True, slots=True)
class Governed:
    """The rules that govern the nets of a design: net name → its governing length rule and its governing
    skew rule (each ``None`` when no rule of the kind matches), and the base of each paired net."""

    length: Mapping[str, Rule | None] = field(default_factory=lambda: {})
    skew: Mapping[str, Rule | None] = field(default_factory=lambda: {})
    bases: Mapping[str, str] = field(default_factory=lambda: {})

    def judged(self) -> tuple[str, ...]:
        """The nets that a rule of severity other than ``ignore`` governs, in name order."""
        names = {
            name
            for rules in (self.length, self.skew)
            for name, rule in rules.items()
            if rule is not None and rule.severity != "ignore"
        }
        return tuple(sorted(names))


def present_nets(design: Design) -> tuple[str, ...]:
    """The names of the nets that have a pad, a track, an arc or a via on the board, in name order."""
    board = design.board
    if board is None:
        return ()
    ids = {item.net_id for item in (*board.tracks, *board.arcs, *board.vias)}
    ids |= {pad.net_id for footprint in board.footprints for pad in footprint.pads}
    return tuple(sorted(net.name for net in design.circuit.nets if net.id in ids))


def governing(design: Design) -> Governed:
    """The governing length and skew rule of every net with a pad or copper: the last matching rule in
    ``rule_precedence`` order, whose ``selector_a`` matches the net's ``RuleSubject(item_kind="track", net,
    netclass, diff_pair)``."""
    rules = design.rules.rules if design.rules is not None else ()
    lengths = tuple(reversed(rule_precedence([r for r in rules if r.kind in LENGTH_KINDS])))
    skews = tuple(reversed(rule_precedence([r for r in rules if r.kind in SKEW_KINDS])))
    classes = {netclass.id: netclass.name for netclass in design.circuit.netclasses}
    bases = net_bases(net.name for net in design.circuit.nets)
    present = set(present_nets(design))
    length: dict[str, Rule | None] = {}
    skew: dict[str, Rule | None] = {}
    for net in design.circuit.nets:
        if net.name not in present:
            continue
        netclass = (
            classes.get(net.netclass_id, DEFAULT_CLASS) if net.netclass_id is not None else DEFAULT_CLASS
        )
        subject = RuleSubject(
            item_kind="track",
            net=net.name,
            netclass=netclass,
            diff_pair=bases.get(net.name),
        )
        length[net.name] = next((r for r in lengths if selector_matches(r.selector_a, subject)), None)
        skew[net.name] = next((r for r in skews if selector_matches(r.selector_a, subject)), None)
    return Governed(length, skew, {name: base for name, base in bases.items() if name in present})


def routed_lengths(design: Design, nets: Collection[str]) -> dict[str, NetLength]:
    """Net name → the routed length of its tracks and arcs on copper layers (``geometry-kernel``, "Path
    lengths"), no via height and no die length: the lengths without facts."""
    board = design.board
    found = {name: 0 for name in nets}
    if board is None:
        return {name: NetLength(name, 0, 0, 0, 0, 0) for name in sorted(found)}
    names = {net.id: net.name for net in design.circuit.nets}
    copper = set(copper_layers(board))
    vias: dict[str, int] = {}
    for track in board.tracks:
        name = names.get(track.net_id or "")
        if name in found and track.layer in copper:
            found[name] += segment_length(track.start, track.end)
    for arc in board.arcs:
        name = names.get(arc.net_id or "")
        if name in found and arc.layer in copper:
            found[name] += arc_length(arc.start, arc.mid, arc.end)
    for via in board.vias:
        name = names.get(via.net_id or "")
        if name in found:
            vias[name] = vias.get(name, 0) + 1
    return {
        name: NetLength(name, value, 0, 0, value, vias.get(name, 0)) for name, value in sorted(found.items())
    }


def _length_issues(name: str, rule: Rule, length: NetLength) -> list[Issue]:
    if rule.severity == "ignore":
        return []
    total = length.total
    if rule.min is not None and total < rule.min:
        side, limit = "below the minimum", rule.min
    elif rule.max is not None and total > rule.max:
        side, limit = "above the maximum", rule.max
    else:
        return []
    return [
        issue(
            "length.out-of-range",
            f"net {name}: length {_mm(total)} mm is {side} {_mm(limit)} mm of rule {rule.name} "
            f"({_parts(length)})",
            severity=rule.severity,
            where=name,
            hint="change the routing of the net, or the limits of the rule",
        )
    ]


def _skew_issues(rule: Rule, group: Sequence[str], lengths: Mapping[str, NetLength]) -> list[Issue]:
    if rule.severity == "ignore" or rule.max is None or len(group) < 2:
        return []
    ordered = sorted(group)
    longest = ordered[0]
    for name in ordered[1:]:
        if lengths[name].total > lengths[longest].total:
            longest = name
    target = lengths[longest].total
    found: list[Issue] = []
    for name in ordered:
        if name == longest:
            continue
        total = lengths[name].total
        skew = total - target
        if abs(skew) > rule.max:
            found.append(
                issue(
                    "length.skew-out-of-range",
                    f"net {name}: length {_mm(total)} mm against {longest} at {_mm(target)} mm, "
                    f"a skew of {_mm(skew)} mm beyond the maximum {_mm(rule.max)} mm of rule {rule.name}",
                    severity=rule.severity,
                    where=name,
                    hint="lengthen the shorter net (a meander, Design.meander), or change the rule",
                )
            )
    return found


def judge_lengths(lengths: Mapping[str, NetLength], governed: Governed) -> list[Issue]:
    """The ``length.out-of-range`` and ``length.skew-out-of-range`` issues of the nets of ``governed``
    whose lengths ``lengths`` gives (a net missing there is judged at length 0)."""
    found: list[Issue] = []

    def length_of(name: str) -> NetLength:
        return lengths.get(name) or NetLength(name, 0, 0, 0, 0, 0)

    every = {name: length_of(name) for name in (*governed.length, *governed.skew)}
    for name, rule in sorted(governed.length.items()):
        if rule is not None:
            found += _length_issues(name, rule, every[name])
    groups: dict[tuple[str, str, str], list[str]] = {}
    rules: dict[tuple[str, str, str], Rule] = {}
    for name, rule in sorted(governed.skew.items()):
        if rule is None:
            continue
        if rule.kind == "diff_pair_skew":
            base = governed.bases.get(name)
            key = (rule.id, rule.name, base if base is not None else "\0" + name)
        else:
            key = (rule.id, rule.name, "")
        groups.setdefault(key, []).append(name)
        rules[key] = rule
    for key in sorted(groups):
        found += _skew_issues(rules[key], groups[key], every)
    return found


def length_stage(
    design: Design | None,
    *,
    project: ProjectSet,
    rules_source: DesignRulesSource | None,
    facts_source: LengthSource | None,
    evidence: Evidence,
) -> StageResult:
    """The ``length.rules`` stage on the board model that ``run_checks`` read (``design``; ``None`` when
    that read was refused): the rules of the project's own files from ``rules_source``, the totals from
    ``facts_source`` for the nets those rules govern. ``evidence`` is the evidence of the board read."""
    if design is None:
        return skipped(STAGE, "read-refused")
    issues: list[Issue] = []
    rules = rules_source.design_rules(design, project) if rules_source is not None else None
    if rules is None:
        issues.append(
            issue(
                "length.input-missing",
                "rules source: none was given, so only the length and skew rules of the board model are "
                "judged",
                where="rules",
            )
        )
    checked = rules.design if rules is not None else design
    governed = governing(checked)
    nets = governed.judged()
    facts: LengthFacts | None = None
    if nets and facts_source is not None:
        facts = facts_source.length_facts(checked, project=project, nets=nets)
        lengths: Mapping[str, NetLength] = facts.nets
    else:
        lengths = routed_lengths(checked, nets)
        if nets:
            issues.append(
                issue(
                    "length.input-missing",
                    "length facts: the backend gives none, so the routed lengths are judged without via "
                    "heights and die lengths",
                    where="lengths",
                )
            )
    issues += judge_lengths(lengths, governed)
    all_rules = checked.rules.rules if checked.rules is not None else ()
    summary: dict[str, object] = {
        "rules": {
            "length": sum(1 for r in all_rules if r.kind in LENGTH_KINDS),
            "skew": sum(1 for r in all_rules if r.kind in SKEW_KINDS),
        },
        "nets": len(nets),
        "major": facts.major if facts is not None else None,
        "stackup": facts.stackup if facts is not None else None,
    }
    inputs = [evidence]
    if facts is not None:
        inputs.append(facts.evidence)
    if rules is not None:
        inputs.append(rules.evidence)
    level = Evidence.combine(EVIDENCE, *inputs)
    if any(found.code == "length.input-missing" for found in issues):
        level = Evidence(Level.UNVERIFIED, hypotheses=level.hypotheses)
    return ran(STAGE, issues, level, summary)


__all__ = [
    "EVIDENCE",
    "LENGTH_KINDS",
    "SKEW_KINDS",
    "STAGE",
    "Governed",
    "governing",
    "judge_lengths",
    "length_stage",
    "present_nets",
    "routed_lengths",
]
