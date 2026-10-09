# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``summary.limits`` and ``check.report-limit`` of the ``drc.kicad`` stage, with fake oracles with and
without limits (capability verification-loop, "DRC report limits in check"; change c0141)."""

from __future__ import annotations

from dataclasses import dataclass

from fakes import FakeLimitedOracle, FakeOracle, outcome, project, report, violation

from fenolite.backends.base import DrcLimits, DrcReport
from fenolite.checks.drc import drc_stage

LIMIT = "check.report-limit"


def _report(silk: int, unconnected: int, dangling: int = 0) -> DrcReport:
    return report(
        *(violation("silk_overlap", "warning", uid=f"s{n}") for n in range(silk)),
        *(violation("track_dangling", "warning", uid=f"t{n}") for n in range(dangling)),
        unconnected=tuple(violation("unconnected_items", "warning", uid=f"n{n}") for n in range(unconnected)),
    )


def _marks(result: object) -> list[tuple[str, str, str]]:
    return [(i.code, i.severity, i.where) for i in result.issues if i.code == LIMIT]  # type: ignore[attr-defined]


def test_two_types_at_their_limits() -> None:
    drc = _report(silk=199, unconnected=499, dangling=150)
    result = drc_stage(FakeLimitedOracle(outcome("fired", drc=drc)), project(), built=True)
    assert result.summary["limits"] == [
        {"type": "silk_overlap", "reported": 199, "limit": 199},
        {"type": "unconnected_items", "reported": 499, "limit": 499},
    ]
    assert [(i.code, i.severity, i.where) for i in result.issues[-2:]] == [
        (LIMIT, "warning", "fake.drc.silk-overlap"),
        (LIMIT, "warning", "fake.drc.unconnected-items"),
    ]
    assert len(_marks(result)) == 2
    assert all(i.code != LIMIT for i in result.issues[:-2])  # the marks follow the findings
    silk, unconnected = result.issues[-2:]
    assert "199 entries of silk_overlap" in silk.message and "at least 199" in silk.message
    assert "499 entries of unconnected_items" in unconnected.message and "at least 499" in unconnected.message
    assert "not in the report" in silk.hint and "check again" in silk.hint
    assert result.summary["by_type"] == {"silk_overlap": 199, "track_dangling": 150}
    assert result.summary["unconnected"] == 499


def test_every_count_under_its_limit() -> None:
    drc = _report(silk=12, unconnected=0)
    result = drc_stage(FakeLimitedOracle(outcome("fired", drc=drc)), project(), built=True)
    assert result.summary["limits"] == []
    assert _marks(result) == []
    assert result.status == "ok"


def test_an_oracle_that_states_no_limits() -> None:
    drc = _report(silk=0, unconnected=499)
    result = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True)
    assert result.summary["limits"] is None
    assert _marks(result) == []


def test_no_report_gives_no_limits() -> None:
    result = drc_stage(
        FakeLimitedOracle(outcome("inconclusive", "no-report", missing=True)), project(), built=True
    )
    assert result.summary["limits"] is None
    assert _marks(result) == []


def test_the_mark_changes_no_verdict() -> None:
    drc = _report(silk=199, unconnected=499, dangling=150)
    plain = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True)
    marked = drc_stage(FakeLimitedOracle(outcome("fired", drc=drc)), project(), built=True)
    assert (marked.status, marked.evidence) == (plain.status, plain.evidence) == ("ok", plain.evidence)
    assert marked.issues[:-2] == plain.issues  # the findings, in their order
    assert {key: value for key, value in marked.summary.items() if key != "limits"} == {
        key: value for key, value in plain.summary.items() if key != "limits"
    }
    assert marked.summary["canary"] == plain.summary["canary"] == "fired"
    assert marked.summary["violations_judged"] is True


def test_a_marked_error_type_keeps_the_status_of_its_findings() -> None:
    drc = report(*(violation("clearance", uid=f"c{n}") for n in range(199)))
    plain = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True)
    marked = drc_stage(FakeLimitedOracle(outcome("fired", drc=drc)), project(), built=True)
    assert plain.status == marked.status == "errors"
    assert marked.summary["limits"] == [{"type": "clearance", "reported": 199, "limit": 199}]


def test_a_count_above_its_limit_is_marked_with_the_count() -> None:
    limits = DrcLimits({"clearance": 499}, others=199)
    drc = report(*(violation("clearance", uid=f"c{n}") for n in range(503)))
    oracle = FakeLimitedOracle(outcome("fired", drc=drc), limits=limits)
    result = drc_stage(oracle, project(), built=True)
    assert result.summary["limits"] == [{"type": "clearance", "reported": 503, "limit": 499}]
    assert "at least 503" in result.issues[-1].message


@dataclass
class _Unmeasured(FakeOracle):
    """A limited oracle whose tool version nobody measured."""

    def report_limits(self) -> DrcLimits:
        raise ValueError("unsupported KiCad 11")


def test_an_unmeasured_tool_version_is_unknown_not_a_failure() -> None:
    drc = _report(silk=0, unconnected=499)
    result = drc_stage(_Unmeasured(outcome("fired", drc=drc)), project(), built=True)
    assert result.summary["limits"] is None
    assert _marks(result) == []
