# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``parity`` stage (capability verification-loop, "Parity stage"; change c0072).

The board is compared with its schematic by ``checks.parity.compare``. The schematic side comes from the
backend (``ParityInputs``): with its own reading of the nets when that covers the schematic, so that a
project that ``build`` wrote needs no tool, else with the schematic netlist of the injected oracle.

When the DRC stage of the same check judged parity with the tool, the tool stays the authority: the
findings that the tool also reports are not reported again. They are compared with the tool's entries by
type and key, and each difference is one ``parity.oracle-differs``, so Fenolite's comparison is checked
against the tool on every such run. The findings that only Fenolite makes (a pin without a pad, a pad
without a pin) are always reported.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import cast

from fenolite.backends.base import ParityInputs, ProjectSet, SchematicNetlistOracle
from fenolite.checks import parity
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, read_refused, skipped
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

STAGE = "parity"
DRC_STAGE = "drc.kicad"
SCHEMATIC_SUFFIX = ".kicad_sch"
OWN_CODES: frozenset[str] = frozenset({parity.PIN_WITHOUT_PAD, parity.PAD_WITHOUT_PIN})
"""The findings of the symbol and footprint comparison: reported whether or not the tool judged parity."""
ORACLE_TYPES: frozenset[str] = frozenset(parity.KICAD_TYPES.values())
KEYLESS = "missing_footprint"
"""The tool's entry for a missing footprint names no board item; its reference is read from the text."""
_MISSING = re.compile(r"Missing footprint (\S+)")
Entry = tuple[str, str]


def _oracle_entries(drc: StageResult) -> Counter[Entry] | None:
    """``(type, key)`` of every parity entry among the issues of the DRC stage, or ``None`` when that
    stage did not judge parity. The key is the first board item the entry names (a reference or
    ``REF-PAD``), or the reference in the text of a missing footprint; ``""`` when neither is known."""
    if drc.status == "skipped" or drc.summary.get("parity_judged") is not True:
        return None
    types = drc.summary.get("types")
    kinds: dict[str, str] = (
        {str(code): str(kind) for code, kind in cast(Mapping[object, object], types).items()}
        if isinstance(types, Mapping)
        else {}
    )
    found: Counter[Entry] = Counter()
    for item in drc.issues:
        kind = kinds.get(item.code)
        if kind not in ORACLE_TYPES:
            continue
        key = item.where.split(", ")[0]
        if kind == KEYLESS:
            match = _MISSING.search(item.message)
            key = match.group(1) if match else ""
        found[(kind, "" if key.startswith("@") else key)] += 1
    return found


def differences(own: Counter[Entry], oracle: Counter[Entry]) -> list[tuple[str, str, str]]:
    """``(type, key, side)`` for every entry that one side holds more often than the other, ``side`` being
    the one that holds it (``fenolite`` or the oracle's ``kicad``). When the tool's text gave no reference
    for a missing footprint, missing footprints are compared by their number alone."""
    if any(kind == KEYLESS and not key for kind, key in oracle):
        own = Counter({(k, "" if k == KEYLESS else key): 0 for k, key in own}) + Counter(
            (k, "" if k == KEYLESS else key) for k, key in own.elements()
        )
    found: list[tuple[str, str, str]] = []
    for entry in sorted(set(own) | set(oracle)):
        ours, theirs = own.get(entry, 0), oracle.get(entry, 0)
        side = "fenolite" if ours > theirs else "kicad"
        found += [(entry[0], entry[1], side)] * abs(ours - theirs)
    return found


def parity_stage(
    inputs: ParityInputs | None,
    oracle: object | None,
    project: ProjectSet,
    design: Design,
    *,
    drc: StageResult | None = None,
) -> StageResult:
    """Compare the board ``design`` of ``project`` with the schematic of its stem. ``oracle`` gives the
    schematic netlist when the backend's own reading does not cover the schematic; ``drc`` is the result of
    the DRC stage of the same check, when it ran."""
    schematic = f"{PurePosixPath(project.board).stem}{SCHEMATIC_SUFFIX}"
    if schematic not in project.files:
        return skipped(STAGE, "no-schematic")
    if inputs is None:
        return skipped(STAGE, "netlist-unavailable")
    source = "own"
    evidence = parity.EVIDENCE
    try:
        outcome = inputs.schematic_side(project)
        if outcome.side is None:
            if not isinstance(oracle, SchematicNetlistOracle):
                return skipped(STAGE, "netlist-unavailable")
            export = oracle.schematic_netlist(project)
            if export.netlist is None:
                what = "timed out" if export.outcome == "timeout" else "wrote no netlist"
                detail = f": {export.message}" if export.message else ""
                failed = issue("check.oracle-failed", f"{oracle.name} {what}{detail}", where=schematic,
                               retryable=export.outcome == "timeout")  # fmt: skip
                return ran(STAGE, [failed], Evidence(), {"netlist": "oracle", "compared": False})
            outcome = inputs.schematic_side(project, nodes=export.netlist)
            source = "oracle"
            evidence = Evidence.combine(evidence, export.evidence)
    except FormatError as error:
        return ran(
            STAGE, [read_refused(error, project.root)], Evidence(), {"netlist": source, "compared": False}
        )
    side = outcome.side
    if side is None:
        return skipped(STAGE, "netlist-unavailable")
    evidence = Evidence.combine(evidence, outcome.evidence) if source == "own" else evidence
    report = parity.compare(side, design)
    judged = _oracle_entries(drc) if drc is not None else None
    issues: list[Issue] = []
    differing: list[tuple[str, str, str]] = []
    if judged is None:
        issues += [parity.finding_issue(f) for f in report.findings]
    else:
        issues += [parity.finding_issue(f) for f in report.findings if f.code in OWN_CODES]
        own = Counter(entry for f in report.findings if (entry := parity.oracle_entry(f)) is not None)
        differing = differences(own, judged)
        for kind, key, side_name in differing:
            other = "kicad" if side_name == "fenolite" else "fenolite"
            issues.append(
                issue(
                    parity.ORACLE_DIFFERS,
                    f"{kind} at {key or '(no reference)'}: {side_name} reports it and {other} does not",
                    where=key,
                    hint="KiCad's parity test is the authority; report the difference to Fenolite",
                )
            )
    summary: dict[str, object] = {
        "netlist": source,
        "compared": judged is not None,
        "differences": len(differing),
        **report.summary,
    }
    return ran(STAGE, issues, evidence, summary)


__all__ = ["OWN_CODES", "STAGE", "differences", "parity_stage"]
