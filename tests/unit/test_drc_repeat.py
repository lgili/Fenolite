# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The comparison of two DRC outcomes can fail (``tests/_drcrepeat.py``; capability kicad-oracle, "DRC
repeatability on the demo boards"; change c0051), and its named sets match the record. Hermetic: the
outcomes are authored here."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from _drcrepeat import UNREPEATABLE_BOARDS, UNREPEATABLE_TYPES, canonical, repeat_problems

from fenolite.backends.base import DrcItem, DrcOutcome, DrcReport, DrcViolation
from fenolite.backends.kicad.canary import CANARY_UUIDS, CLEARANCE_REPORT_LIMIT
from fenolite.core.coords import Point
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[2]
NAMED = "kicad-demo-10-0-6-pcb-07"
STABLE = "kicad-demo-10-0-6-pcb-17"


def _violation(kind: str, n: int, uid: str = "") -> DrcViolation:
    item = DrcItem(uid or f"u{n}", f"Track {n}", Point(n * 1000, 2000))
    return DrcViolation(kind, f"{kind} {n}", "error", (item,))


def _outcome(
    *violations: DrcViolation, source: str = "/tmp/run-a/board.kicad_pcb", **fields: object
) -> DrcOutcome:
    report = DrcReport(source, "", "10.0.6", "mm", violations=violations)
    return dataclasses.replace(
        DrcOutcome(report, "10.0.6", "fired", tool_writes=("board.kicad_prl",)), **fields
    )  # type: ignore[arg-type]


CLEARANCE = [_violation("clearance", n) for n in range(3)]
DANGLING = [_violation("track_dangling", n) for n in range(3)]
SATURATED = [_violation("clearance", n) for n in range(CLEARANCE_REPORT_LIMIT)]


def test_problems_none_for_equal_outcomes_in_another_order_and_folder() -> None:
    first = _outcome(*CLEARANCE, *DANGLING)
    second = _outcome(*reversed(DANGLING), *reversed(CLEARANCE), source="/tmp/run-b/board.kicad_pcb")
    assert repeat_problems(STABLE, first, second) == []
    assert repeat_problems(NAMED, first, second) == []


def test_problems_canonical_leaves_out_the_run_folder() -> None:
    item = DrcItem("u", "Footprint of /tmp/run-a/lib", Point(0, 0))
    report = DrcReport(
        "/tmp/run-a/board.kicad_pcb",
        "",
        "10.0.6",
        "mm",
        violations=(DrcViolation("x", "d", "error", (item,)),),
    )
    assert canonical(report)[0][4][0][0] == "Footprint of <tmp>/lib"


def test_problems_named_type_on_a_named_board_is_accepted() -> None:
    first, second = _outcome(*CLEARANCE, *DANGLING), _outcome(*CLEARANCE[:2], *DANGLING)
    assert repeat_problems(NAMED, first, second) == []


def test_problems_named_type_on_a_stable_board_fails() -> None:
    first, second = _outcome(*CLEARANCE, *DANGLING), _outcome(*CLEARANCE[:2], *DANGLING)
    (problem,) = repeat_problems(STABLE, first, second)
    assert STABLE in problem and "clearance: 3 and 2 entries" in problem


def test_problems_other_type_on_a_named_board_fails() -> None:
    first, second = _outcome(*CLEARANCE, *DANGLING), _outcome(*CLEARANCE, *DANGLING[:2])
    (problem,) = repeat_problems(NAMED, first, second)
    assert NAMED in problem and "track_dangling: 3 and 2 entries, 1 not in both runs" in problem


def test_problems_same_count_but_another_item_fails() -> None:
    first = _outcome(*DANGLING)
    second = _outcome(*DANGLING[:2], _violation("track_dangling", 9))
    (problem,) = repeat_problems(NAMED, first, second)
    assert "track_dangling: 3 and 3 entries, 2 not in both runs" in problem


def test_problems_canary_state_must_be_fired_and_equal() -> None:
    fired, absent = _outcome(*DANGLING), _outcome(*DANGLING, canary="absent")
    problems = repeat_problems(NAMED, fired, absent)
    assert any("second run: canary is 'absent'" in p for p in problems)
    assert any("canary differs" in p for p in problems)


def test_problems_clearance_limit_needs_a_saturated_report() -> None:
    limit = {"canary": "inconclusive", "canary_reason": "clearance-limit"}
    below = repeat_problems(NAMED, _outcome(*CLEARANCE), _outcome(*CLEARANCE, **limit))
    assert any("second run: canary is 'inconclusive' ('clearance-limit')" in p for p in below)
    assert repeat_problems(NAMED, _outcome(*SATURATED), _outcome(*SATURATED, **limit)) == []
    other = {"canary": "inconclusive", "canary_reason": "no-front-copper"}
    assert repeat_problems(NAMED, _outcome(*SATURATED), _outcome(*SATURATED, **other)) != []


def test_problems_run_facts_must_be_equal() -> None:
    first = _outcome(*DANGLING)
    assert any(
        "returncode differs" in p for p in repeat_problems(NAMED, first, _outcome(*DANGLING, returncode=5))
    )
    assert any(
        "tool_writes differs" in p for p in repeat_problems(NAMED, first, _outcome(*DANGLING, tool_writes=()))
    )
    assert any(
        "canary_removed is 3" in p
        for p in repeat_problems(NAMED, first, _outcome(*DANGLING, canary_removed=3))
    )


def test_problems_missing_report_and_canary_item() -> None:
    first = _outcome(*DANGLING)
    none = dataclasses.replace(first, report=None, outcome="timeout", returncode=None)
    assert any("second run has no report" in p for p in repeat_problems(NAMED, first, none))
    named = _outcome(*DANGLING, _violation("track_dangling", 7, CANARY_UUIDS[0]))
    assert any("names a canary item" in p for p in repeat_problems(NAMED, named, named))


def test_record_names_the_sets() -> None:
    evidence = (ROOT / "docs" / "evidence" / "kicad-check.md").read_text(encoding="utf-8")
    section = evidence[evidence.index("## DRC repeatability on the demo boards (change c0051)") :]
    (row,) = [r for r in load_register(ROOT / "docs" / "hypotheses.md") if r.id == "H-K-DRC-REPEAT"]
    assert len(UNREPEATABLE_BOARDS) == 6 and len(UNREPEATABLE_TYPES) == 3
    for kind in UNREPEATABLE_TYPES:
        assert f"`{kind}`" in section and f"`{kind}`" in row.statement, kind
    for board in UNREPEATABLE_BOARDS:
        assert f"`{board}`" in section, board
        # the register row spells the first id whole and the others by their number ("`-07`")
        assert f"`{board}`" in row.statement or f"`{board[-3:]}`" in row.statement, board


def test_contract_names_what_does_not_repeat() -> None:
    """``docs/cli-contract.md`` tells the user which part of ``check`` repeats (capability verification-loop,
    "Check output is deterministic")."""
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    check = contract[contract.index("\n## check\n") : contract.index("\n## export\n")]
    paragraph = check[check.index("**Repeatability.**") :]
    paragraph = paragraph[: paragraph.index("\n| code |")]
    for kind in UNREPEATABLE_TYPES:
        assert f"`kicad.drc.{kind.replace('_', '-')}`" in paragraph, kind
    assert (
        "`clearance-limit`" in paragraph and "`clearance-limit`" in check[: check.index("**Repeatability.**")]
    )
    assert str(CLEARANCE_REPORT_LIMIT) in paragraph
