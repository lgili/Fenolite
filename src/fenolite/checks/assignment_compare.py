# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``netlist.assignment_compare`` stage (capability verification-loop, "Assignment compare stage").

The net-to-pad assignments of the model, of the re-read board and of the tool's netlist export are
compared as partitions of ``REF-PIN`` elements, never by net name: an export may shorten names, and a
model and a board may name a net differently. The board is the hub, so a reassigned pad is reported once:
(``model``, ``board``) on built input and (``board``, ``export``) on every input. Elements that only one
side covers are coverage, never differences.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from fenolite.backends.base import (
    NetlistOracle,
    Oracle,
    PadAssignment,
    PadNetList,
    ProjectSet,
    Uncovered,
    Validation,
)
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

NO_NET = ""
"""The label of a pad on no net; one class of the partition, like any other label."""
MODEL_EVIDENCE = Evidence(Level.INFERRED)
"""Fenolite's own model rules on built input: checked by its tests, not by an oracle."""
SHOWN = 5


@dataclass(frozen=True, slots=True)
class Difference:
    """An element whose net block differs between sources ``a`` and ``b``, with its label on each side."""

    element: str
    a: str
    b: str
    net_a: str
    net_b: str


@dataclass(frozen=True, slots=True)
class PairResult:
    """One compared pair: the elements both sides cover, those each side does not cover (with the reason),
    and the located differences. ``only_a`` holds what ``b`` does not cover, and ``only_b`` what ``a`` does
    not."""

    a: str
    b: str
    common: int
    only_a: tuple[Uncovered, ...]
    only_b: tuple[Uncovered, ...]
    differences: tuple[Difference, ...]


def _refs(design: Design) -> dict[str, str]:
    return {c.id: c.ref for c in design.circuit.components}


def board_netlist(design: Design) -> tuple[PadNetList, int]:
    """The numbered pads of the board with their ``net_id`` as label (``NO_NET`` for none), and the count
    of pads without a number, which are not compared."""
    refs = _refs(design)
    assignments: list[PadAssignment] = []
    unnumbered = 0
    for fp in design.board.footprints if design.board is not None else ():
        ref = refs.get(fp.component_id, "")
        for pad in fp.pads:
            if not pad.number:
                unnumbered += 1
                continue
            assignments.append(PadAssignment(f"{ref}-{pad.number}", pad.net_id or NO_NET))
    return PadNetList("board", tuple(assignments)), unnumbered


def model_netlist(model: Design) -> PadNetList:
    """Each ``PinRef`` of a net with the net's id as label, and every other pin of a component on
    ``NO_NET``."""
    refs = _refs(model)
    assignments: list[PadAssignment] = []
    seen: set[str] = set()
    for net in model.circuit.nets:
        for member in net.members:
            element = f"{refs.get(member.component_id, '')}-{member.pin}"
            assignments.append(PadAssignment(element, net.id))
            seen.add(element)
    for component in model.circuit.components:
        for pin in component.pins:
            element = f"{component.ref}-{pin.number}"
            if pin.number and element not in seen:
                assignments.append(PadAssignment(element, NO_NET))
                seen.add(element)
    return PadNetList("model", tuple(assignments))


def _labels(listed: PadNetList) -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for assignment in listed.assignments:
        found[assignment.element].add(assignment.net)
    return found


def _covered(listed: PadNetList, min_pins: int) -> tuple[dict[str, set[str]], set[str]]:
    """The labels of each element a side covers, and the elements it leaves out for ``min_pins``."""
    labels = _labels(listed)
    sizes = Counter(label for found in labels.values() for label in found)
    small = {e for e, found in labels.items() if all(sizes[label] < min_pins for label in found)}
    return {e: found for e, found in labels.items() if e not in small}, small


def _blocks(elements: Iterable[str], label: Mapping[str, str]) -> dict[str, frozenset[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for element in elements:
        found[label[element]].add(element)
    return {name: frozenset(members) for name, members in found.items()}


def _outliers(blocks: Mapping[str, frozenset[str]], other: Mapping[str, str]) -> set[str]:
    """For each block, the elements outside the one block of the other side that holds most of it (ties
    flag nothing)."""
    flagged: set[str] = set()
    for members in blocks.values():
        counts = Counter(other[e] for e in members).most_common(2)
        if len(counts) > 1 and counts[0][1] > counts[1][1]:
            flagged |= {e for e in members if other[e] != counts[0][0]}
    return flagged


def _missing(element: str, listed: PadNetList, small: set[str], reasons: Mapping[str, str]) -> Uncovered:
    if element in small:
        return Uncovered(element, "below-min-pins")
    return Uncovered(element, reasons.get(element, f"not-in-{listed.source}"))


def compare(a: PadNetList, b: PadNetList, *, min_pins: int = 1) -> PairResult:
    """Compare two sources as partitions of the elements both cover; see the module docstring."""
    cover_a, small_a = _covered(a, min_pins)
    cover_b, small_b = _covered(b, min_pins)
    reasons_a = {u.element: u.reason for u in a.uncovered}
    reasons_b = {u.element: u.reason for u in b.uncovered}
    named = set(cover_a) | set(cover_b) | small_a | small_b | set(reasons_a) | set(reasons_b)
    only_a = tuple(_missing(e, b, small_b, reasons_b) for e in sorted(named - set(cover_b)))
    only_b = tuple(_missing(e, a, small_a, reasons_a) for e in sorted(named - set(cover_a)))
    common = sorted(set(cover_a) & set(cover_b))
    double = {e for e in common if len(cover_a[e]) > 1 or len(cover_b[e]) > 1}
    single = [e for e in common if e not in double]
    label_a = {e: next(iter(cover_a[e])) for e in single}
    label_b = {e: next(iter(cover_b[e])) for e in single}
    blocks_a, blocks_b = _blocks(single, label_a), _blocks(single, label_b)
    flagged = _outliers(blocks_a, label_b) | _outliers(blocks_b, label_a)
    sets_a, sets_b = set(blocks_a.values()), set(blocks_b.values())
    if not flagged and sets_a != sets_b:
        flagged = {e for block in sets_a ^ sets_b for e in block}
    differences = tuple(
        Difference(e, a.source, b.source, "|".join(sorted(cover_a[e])), "|".join(sorted(cover_b[e])))
        for e in sorted(flagged | double)
    )
    return PairResult(a.source, b.source, len(common), only_a, only_b, differences)


def net_names(design: Design | None) -> dict[str, str]:
    """The name of each net of ``design`` by its id; empty for no design."""
    return {} if design is None else {n.id: n.name for n in design.circuit.nets}


def net_text(label: str, names: Mapping[str, str]) -> str:
    """A partition label as text: ``no net``, or the names of the nets it stands for."""
    if label == NO_NET:
        return "no net"
    return " and ".join(names.get(part, part) for part in label.split("|"))


def _pair_issues(pair: PairResult, names: Mapping[str, Mapping[str, str]]) -> list[Issue]:
    issues = [
        issue(
            "netlist.assignment-differs",
            f"{d.element} is on {net_text(d.net_a, names.get(d.a, {}))} in the {d.a} "
            f"and on {net_text(d.net_b, names.get(d.b, {}))} in the {d.b}",
            where=d.element,
        )
        for d in pair.differences
    ]
    for missing_in, found in ((pair.b, pair.only_a), (pair.a, pair.only_b)):
        by_reason: dict[str, list[str]] = defaultdict(list)
        for uncovered in found:
            by_reason[uncovered.reason].append(uncovered.element)
        for reason, elements in sorted(by_reason.items()):
            shown = ", ".join(sorted(elements)[:SHOWN]) + (", …" if len(elements) > SHOWN else "")
            issues.append(
                issue(
                    "netlist.uncovered",
                    f"{pair.a}/{pair.b}: {len(elements)} element(s) not covered by the {missing_in} "
                    f"({reason}): {shown}",
                    where=sorted(elements)[0],
                )
            )
    return issues


def _pair_summary(pair: PairResult) -> dict[str, object]:
    return {
        "a": pair.a,
        "b": pair.b,
        "common": pair.common,
        "only_a": len(pair.only_a),
        "only_b": len(pair.only_b),
        "differences": len(pair.differences),
    }


def assignment_stage(
    oracle: Oracle | None,
    project: ProjectSet,
    *,
    validation: Validation | None,
    model: Design | None,
    built: bool,
    min_pins: int = 1,
) -> StageResult:
    """Compare (``model``, ``board``) on built input and (``board``, ``export``) on every input."""
    name = "netlist.assignment_compare"
    if validation is None:
        return skipped(name, "read-refused")
    if not isinstance(oracle, NetlistOracle):
        return skipped(name, "unsupported-oracle")
    design = validation.read.design
    board, unnumbered = board_netlist(design)
    names: dict[str, Mapping[str, str]] = {"board": net_names(design), "model": net_names(model)}
    pairs: list[PairResult] = []
    issues: list[Issue] = []
    if built and model is not None:
        pairs.append(compare(model_netlist(model), board, min_pins=min_pins))
    outcome = oracle.netlist(project, board=design)
    if outcome.netlist is None:
        what = "timed out" if outcome.outcome == "timeout" else "wrote no netlist export"
        detail = f": {outcome.message}" if outcome.message else ""
        issues.append(issue("check.oracle-failed", f"{oracle.name} {what}{detail}", where=project.board,
                            retryable=outcome.outcome == "timeout"))  # fmt: skip
    else:
        pairs.append(compare(board, outcome.netlist, min_pins=min_pins))
    for pair in pairs:
        issues += _pair_issues(pair, names)
    summary = {"pairs": [_pair_summary(p) for p in pairs], "min_pins": min_pins, "unnumbered": unnumbered}
    if outcome.netlist is None:
        evidence = Evidence()
    else:
        parts = [validation.read.evidence, outcome.evidence, *([MODEL_EVIDENCE] if built else [])]
        evidence = Evidence.combine(*parts)
        evidence = Evidence(evidence.level, outcome.evidence.oracle, evidence.hypotheses)
    return ran(name, issues, evidence, summary)


__all__ = [
    "MODEL_EVIDENCE",
    "NO_NET",
    "Difference",
    "PairResult",
    "assignment_stage",
    "board_netlist",
    "compare",
    "model_netlist",
    "net_names",
    "net_text",
]
