# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The RT2 stage with a fake round-trip oracle (capability verification-loop, "RT2 stage"; change c0020)."""

from __future__ import annotations

import dataclasses

from fakes import VERIFIED, FakeFullOracle, FakeOracle, project, report, rt2_outcome

from fenolite.backends.base import (
    DrcItem,
    DrcReport,
    DrcViolation,
    ErcItem,
    ErcReport,
    ErcRt2Outcome,
    ErcViolation,
)
from fenolite.checks.rt2 import compare_runs, erc_rt2, rt2_stage, violation_key
from fenolite.core.coords import Point
from fenolite.core.evidence import Level


def _v(
    kind: str = "clearance",
    severity: str = "error",
    uid: str = "u1",
    x: int = 0,
    description: str = "item",
    excluded: bool = False,
) -> DrcViolation:
    item = DrcItem(uid, description, Point(x, 0))
    return DrcViolation(kind, kind, severity, (item,), excluded=excluded)


def _stage(before: tuple[DrcReport, ...], after: DrcReport | None, **kwargs: object):  # type: ignore[no-untyped-def]
    oracle = FakeFullOracle(rt2_result=rt2_outcome(before, after, **kwargs))  # type: ignore[arg-type]
    return rt2_stage(oracle, project())


def test_equal_runs_hold() -> None:
    drc = report(_v(), _v("silk_overlap", "warning"), unconnected=(_v("unconnected_items"),))
    result = _stage((drc, drc), drc)
    assert result.status == "ok" and result.issues == ()
    assert result.summary == {
        "holds": True,
        "judged": True,
        "normalised": True,
        "runs": {"original": 2, "redump": 1},
        "before": {"violations": 2, "unconnected": 1},
        "after": {"violations": 2, "unconnected": 1},
        "unstable": 0,
        "differences": 0,
    }
    assert result.evidence.level == Level.KICAD_VERIFIED


def test_unstable_violation_excluded() -> None:
    first = report(_v(), _v("silk_overlap", "warning", x=5))
    second = report(_v())
    result = _stage((first, second), second)
    (info,) = result.issues
    assert (info.code, info.severity) == ("check.rt2-unstable", "info") and info.message.startswith("1 ")
    assert result.summary["holds"] is True and result.summary["unstable"] == 1 and result.status == "ok"


def test_changed_redump_fails() -> None:
    drc = report(_v())
    after = report(_v(), _v(x=2_500_000))
    result = _stage((drc, drc), after)
    (error,) = result.issues
    assert (error.code, error.severity, error.where) == ("check.rt2-failed", "error", "@2.5,0")
    assert "clearance" in error.message and "0 in the original, 1 in the re-dump" in error.message
    assert result.status == "errors" and result.summary["holds"] is False
    assert result.summary["differences"] == 1


def test_item_uuids_masked() -> None:
    drc = report(_v(uid="aaaa"), unconnected=(_v("unconnected_items", uid="bbbb"),))
    after = report(_v(uid="cccc"), unconnected=(_v("unconnected_items", uid="dddd"),))
    assert _stage((drc, drc), after).summary["holds"] is True


def test_keys_tell_groups_severities_and_exclusions_apart() -> None:
    base = _v()
    keys = {
        violation_key("violations", base, source="b.kicad_pcb"),
        violation_key("unconnected_items", base, source="b.kicad_pcb"),
        violation_key("violations", dataclasses.replace(base, severity="warning"), source="b.kicad_pcb"),
        violation_key("violations", dataclasses.replace(base, excluded=True), source="b.kicad_pcb"),
        violation_key("violations", _v(x=1), source="b.kicad_pcb"),
    }
    assert len(keys) == 5
    assert violation_key("violations", _v(uid="x"), source="s") == violation_key(
        "violations", base, source="s"
    )


def test_temporary_folder_left_out_of_keys() -> None:
    one = report(_v(description="/tmp/run-a/lib"))
    two = report(_v(description="/tmp/run-b/lib"))
    one = dataclasses.replace(one, source="/tmp/run-a/board.kicad_pcb")
    two = dataclasses.replace(two, source="/tmp/run-b/board.kicad_pcb")
    assert _stage((one, one), two).summary["holds"] is True


def test_missing_reports_fail_the_oracle() -> None:
    drc = report()
    assert (
        compare_runs(rt2_outcome((drc,), drc)) is None and compare_runs(rt2_outcome((drc, drc), None)) is None
    )
    result = _stage((drc,), None)
    (issue,) = result.issues
    assert (issue.code, issue.retryable) == ("check.oracle-failed", False)
    assert result.evidence.level == Level.UNVERIFIED and result.summary["holds"] is False
    assert result.summary["before"] == {"violations": 0, "unconnected": 0}
    timed = _stage((), None, timeout=True)
    assert timed.issues[0].retryable and "timed out" in timed.issues[0].message


def test_oracle_without_rt2_is_skipped() -> None:
    result = rt2_stage(FakeOracle(), project())
    assert (result.status, result.reason) == ("skipped", "unsupported-oracle")


def test_difference_on_an_unstable_board_is_not_judged() -> None:
    # The two runs of the original disagree, so the tool does not repeat its own report here: another
    # difference from the re-dump cannot be told from that spread.
    first = report(_v(), _v("silk_overlap", "warning", x=5))
    second = report(_v())
    after = report(_v(), _v(x=9))
    result = _stage((first, second), after)
    (info,) = result.issues
    assert (info.code, info.severity) == ("check.rt2-unstable", "info")
    assert "RT2 is not judged" in info.message and "1 more differ" in info.message
    assert result.status == "ok" and result.evidence.level == Level.UNVERIFIED
    assert (result.summary["holds"], result.summary["judged"]) == (False, False)
    assert result.summary["differences"] == 1 and result.summary["unstable"] == 1


def test_repeats_of_the_redump_count_as_instability() -> None:
    drc = report(_v())
    varying = (report(_v(), _v(x=3)), report(_v()), report(_v()))
    result = _stage((drc, drc, drc, drc, drc), report(_v(), _v(x=2)), repeats=varying)
    # x=2 and x=3 each appear in some re-dump runs only: both keys are unstable, nothing else differs.
    assert result.summary["unstable"] == 2 and result.summary["holds"] is True
    assert result.summary["runs"] == {"original": 5, "redump": 4}
    assert [i.code for i in result.issues] == ["check.rt2-unstable"]


def test_repeated_difference_fails() -> None:
    drc = report(_v())
    after = report(_v(), _v(x=2_500_000))
    result = _stage((drc,) * 5, after, repeats=(after,) * 3)
    assert [i.code for i in result.issues] == ["check.rt2-failed"]
    assert result.status == "errors" and result.summary["judged"] is True
    assert result.evidence.level == Level.KICAD_VERIFIED


# --- RT2 of a schematic through ERC (c0066 task 2.4b) -----------------------------------------------


def _erc(*kinds: str) -> ErcReport:
    return ErcReport(
        "top.kicad_sch",
        "",
        "10.0.6",
        "mm",
        tuple(ErcViolation(kind, kind, "error", sheet="/") for kind in kinds),
    )


class _ErcOracle:
    """Gives the scripted outcomes in order, the last one from then on, and counts the calls."""

    def __init__(self, *outcomes: ErcRt2Outcome) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def rt2_erc(self, project: object) -> ErcRt2Outcome:
        self.calls += 1
        return self.outcomes[min(self.calls, len(self.outcomes)) - 1]


def _outcome(first: ErcReport, second: ErcReport, after: ErcReport | None) -> ErcRt2Outcome:
    return ErcRt2Outcome((first, second), after, "10.0.6", evidence=VERIFIED, redumped=2, kept=1)


def _named(kind: str, at: int) -> ErcReport:
    """One violation of ``kind`` whose item lies at ``(at, 0)``: the pin the tool chose to name."""
    item = ErcItem(uuid="u", description="pin", position=Point(at, 0))
    return ErcReport(
        "top.kicad_sch", "", "10.0.6", "mm", (ErcViolation(kind, kind, "error", (item,), sheet="/"),)
    )


def test_erc_rt2_holds() -> None:
    same = _erc("pin_not_connected")
    oracle = _ErcOracle(_outcome(same, same, same))
    verdict = erc_rt2(oracle, project(schematic=True))
    assert (verdict.reported, verdict.judged, verdict.holds, verdict.exact) == (True, True, True, True)
    assert (verdict.violations, verdict.violations_redump, verdict.redumped, verdict.kept) == (1, 1, 2, 1)
    assert verdict.difference == "" and verdict.evidence == VERIFIED and oracle.calls == 1


def test_erc_rt2_holds_when_the_tool_names_another_item() -> None:
    """The tool names another pin of one violation in each run: the kinds agree, so RT2 is judged and
    holds, and ``exact`` says that the items did not."""
    here, there = _named("power_pin_not_driven", 1), _named("power_pin_not_driven", 2)
    assert here.entries() != there.entries() and here.kinds() == there.kinds()
    for outcome in (_outcome(here, there, here), _outcome(here, here, there)):
        oracle = _ErcOracle(outcome)
        verdict = erc_rt2(oracle, project(schematic=True))
        assert (verdict.judged, verdict.holds, verdict.exact) == (True, True, False)
        assert verdict.difference == "" and verdict.evidence == VERIFIED and oracle.calls == 1


def test_erc_rt2_is_not_judged_when_the_kinds_of_two_runs_differ() -> None:
    oracle = _ErcOracle(_outcome(_erc("a"), _erc("a", "b"), _erc("a")))
    verdict = erc_rt2(oracle, project(schematic=True))
    assert (verdict.judged, verdict.holds, verdict.exact) == (False, False, False)
    assert verdict.difference == "" and verdict.evidence.level == Level.UNVERIFIED and oracle.calls == 1


def test_erc_rt2_difference_of_kinds_fails_at_once() -> None:
    same, more = _erc("a"), _erc("a", "extra")
    oracle = _ErcOracle(_outcome(same, same, more), _outcome(same, same, same))
    verdict = erc_rt2(oracle, project(schematic=True))
    assert (verdict.judged, verdict.holds, verdict.exact) == (True, False, False)
    assert oracle.calls == 1, "no further attempt: the kinds are what the tool repeats"
    assert verdict.difference == "extra (error) on sheet /: 0 in the original, 1 in the re-dump"
    assert verdict.evidence.level == Level.UNVERIFIED
    # the same kind in another number is a difference too
    twice = erc_rt2(_ErcOracle(_outcome(same, same, _erc("a", "a"))), project(schematic=True))
    assert twice.holds is False
    assert twice.difference == "a (error) on sheet /: 1 in the original, 2 in the re-dump"


def test_erc_rt2_without_a_report() -> None:
    timeout = ErcRt2Outcome((), None, "10.0.6", outcome="timeout", returncode=None, message="timed out")
    verdict = erc_rt2(_ErcOracle(timeout), project(schematic=True))
    assert (verdict.reported, verdict.judged, verdict.holds) == (False, False, False)
    assert verdict.message == "timed out" and verdict.retryable is True
    silent = erc_rt2(_ErcOracle(ErcRt2Outcome((), None, "10.0.6")), project(schematic=True))
    assert silent.message == "no ERC report" and silent.retryable is False
