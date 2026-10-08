# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The coupling bench of change c0110 (capability kicad-oracle, "Pair coupling in KiCad's DRC is probed";
hypothesis H-K-DRU-PAIRCOUPLE).

Script copper only: the pair ``CA`` routed 0.15 mm apart edge to edge and the pair ``CB`` 1.07 mm apart,
both 20 mm long, judged with four rules files on every pair: a ``diff_pair_gap`` rule of 0.13 mm to
0.17 mm alone, a ``diff_pair_uncoupled`` rule of 3 mm alone, both, and none. Measurement 2 of c0110 found,
on a routed board, that KiCad counts as uncoupled every segment outside the gap rule's range, and without
a gap rule counts far parallel segments as coupled. Net names and values are authored for this bench.

The outcomes ``dru-pair-couple-<case>`` are ``present`` when the case holds as measurement 2 states.
``couple_probes`` is in ``_probes.PROBES`` for both majors since the four cases passed in the ``kicad-9`` and
``kicad-10`` jobs of CI run 37772583226 (2026-10-08); the outcomes in both probe files are those of that run.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache

import _kindcases as kc
import _pairbench as pb
import _rulebench as rb

from fenolite.model.rules import Rule

MM = rb.MM
LENGTH = 20 * MM
NEAR, FAR = 150_000, 1_070_000
CASES = ("gap", "uncoupled", "both", "none")
GAP_TYPE = frozenset({"diff_pair_gap_out_of_range"})
UNCOUPLED_TYPE = frozenset({"diff_pair_uncoupled_length_too_long"})
_ACTUAL = re.compile(r"actual\s+([0-9.]+)\s*mm")


@cache
def bench() -> rb.Bench:
    made = rb.builder()
    pb.pair(made, "CA", gap=NEAR, long_p=LENGTH, long_n=LENGTH)
    pb.pair(made, "CB", gap=FAR, long_p=LENGTH, long_n=LENGTH)
    return made.build()


def rules(case: str) -> tuple[Rule, ...]:
    gap = pb.rule("couple gap", "diff_pair_gap", pb.dp("*"), min=130_000, max=170_000)
    uncoupled = pb.rule("couple uncoupled", "diff_pair_uncoupled", pb.dp("*"), max=3 * MM)
    return {"gap": (gap,), "uncoupled": (uncoupled,), "both": (gap, uncoupled), "none": ()}[case]


@cache
def judged(case: str) -> kc.Run:
    found = rules(case)
    text = pb.lowered(*found) if found else "(version 1)\n"
    return kc.run(bench(), rb.with_scoped_canary(text))


def uncoupled_length(result: kc.Run, row: str) -> int | None:
    """The uncoupled length in nm that KiCad reports for the row, or ``None`` without a finding."""
    assert result.report is not None
    wanted = [uuid for key in (f"{row}_a", f"{row}_b") for uuid in result.bench.items.get(key, ())]
    for violation in rb.violations_of(result.report, wanted):
        if violation.type in UNCOUPLED_TYPE:
            match = _ACTUAL.search(violation.description)
            return round(float(match.group(1)) * MM) if match else 0
    return None


def holds(case: str) -> bool:
    """Whether the case holds as measurement 2 of c0110 states."""
    result = judged(case)
    gap_ca, gap_cb = pb.hit(result, "CA", GAP_TYPE), pb.hit(result, "CB", GAP_TYPE)
    unc_ca, unc_cb = uncoupled_length(result, "CA"), uncoupled_length(result, "CB")
    if case == "gap":
        return gap_cb and not gap_ca and unc_ca is None and unc_cb is None
    if case == "uncoupled":
        return not (gap_ca or gap_cb) and unc_ca is None and (unc_cb is None or unc_cb < LENGTH)
    if case == "both":
        return (
            gap_cb and not gap_ca and unc_ca is None and unc_cb is not None and abs(unc_cb - LENGTH) <= 10_000
        )
    return not (gap_ca or gap_cb) and unc_ca is None and unc_cb is None


def probe(case: str) -> str:
    result = judged(case)
    if not result.canary:
        return "inconclusive"
    return rb.outcome(holds(case))


def couple_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    return {f"dru-pair-couple-{case}": (lambda case=case: probe(case), (9, 10)) for case in CASES}


__all__ = ["CASES", "bench", "couple_probes", "holds", "judged", "probe", "rules", "uncoupled_length"]
