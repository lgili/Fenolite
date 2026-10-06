# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``erc.kicad`` stage with a fake oracle (capability verification-loop, "ERC stage"; change c0062)."""

from __future__ import annotations

from fakes import (
    VERIFIED,
    FakeErcOracle,
    FakeFullOracle,
    FakeOracle,
    erc_outcome,
    erc_report,
    erc_violation,
    project,
)

from fenolite.checks.erc import STAGE, erc_stage, schematic_of
from fenolite.core.evidence import Level

SUMMARY_KEYS = {
    "tool_version",
    "sheets",
    "violations",
    "by_type",
    "by_severity",
    "excluded",
    "ignored_checks",
    "types",
    "tool_writes",
}


def _oracle(*violations: object, **report: object) -> FakeErcOracle:
    found = erc_report(*violations, **report)  # type: ignore[arg-type]
    return FakeErcOracle(erc_result=erc_outcome(found))


def test_clean_report() -> None:
    oracle = _oracle()
    result = erc_stage(oracle, project(schematic=True))
    assert (result.name, result.status, result.issues, result.reason) == ("erc.kicad", "ok", (), "")
    assert STAGE == "erc.kicad" and len(oracle.erc_calls) == 1 and oracle.calls == []  # no DRC run
    assert set(result.summary) == SUMMARY_KEYS
    assert result.summary["violations"] == 0 and result.summary["sheets"] == 1
    assert result.evidence == VERIFIED


def test_findings_counts_and_summary() -> None:
    oracle = _oracle(
        erc_violation("pin_not_connected", where="R1-1"),
        erc_violation("lib_symbol_issues", "warning", where="U1", sheet="/Child/"),
        erc_violation("pin_not_connected", where="U1-2", excluded=True, uid="e2"),
        sheets=("/", "/Child/"),
        ignored=("single_global_label", "footprint_filter"),
    )
    result = erc_stage(oracle, project(schematic=True))
    assert result.status == "errors"
    assert [(i.code, i.severity, i.where) for i in result.issues] == [
        ("fake.erc.lib-symbol-issues", "warning", "U1"),
        ("fake.erc.pin-not-connected", "error", "R1-1"),
        ("fake.erc.pin-not-connected", "info", "U1-2"),
    ]  # sorted by code, then where
    assert result.summary == {
        "tool_version": "1.0",
        "sheets": 2,
        "violations": 3,
        "by_type": {"lib_symbol_issues": 1, "pin_not_connected": 2},
        "by_severity": {"error": 2, "warning": 1},
        "excluded": 1,
        "ignored_checks": ["footprint_filter", "single_global_label"],
        "types": {
            "fake.erc.lib-symbol-issues": "lib_symbol_issues",
            "fake.erc.pin-not-connected": "pin_not_connected",
        },
        "tool_writes": ["a.kicad_prl", "z.kicad_prl"],
    }


def test_warnings_only_is_ok() -> None:
    result = erc_stage(_oracle(erc_violation("lib_symbol_issues", "warning")), project(schematic=True))
    assert result.status == "ok" and len(result.issues) == 1


def test_no_schematic_is_a_skip_and_runs_nothing() -> None:
    oracle = _oracle(erc_violation("pin_not_connected"))
    result = erc_stage(oracle, project())
    assert (result.status, result.reason, result.issues) == ("skipped", "no-schematic", ())
    assert result.evidence.level == Level.UNVERIFIED and oracle.erc_calls == []
    assert schematic_of(project()) is None and schematic_of(project(schematic=True)) == "board.kicad_sch"


def test_oracle_without_erc_is_a_skip() -> None:
    for oracle in (FakeOracle(), FakeFullOracle()):
        result = erc_stage(oracle, project(schematic=True))
        assert (result.status, result.reason, result.issues) == ("skipped", "unsupported-oracle", ())
    # without a schematic the reason is the missing schematic, whatever the oracle can do
    assert erc_stage(FakeOracle(), project()).reason == "no-schematic"


def test_no_report_is_an_error_of_the_stage() -> None:
    oracle = FakeErcOracle(erc_result=erc_outcome(missing=True))
    result = erc_stage(oracle, project(schematic=True))
    (failed,) = result.issues
    assert (failed.code, failed.severity, failed.retryable) == ("check.oracle-failed", "error", False)
    assert failed.message == "fake wrote no ERC report: Failed to load schematic"
    assert failed.where == "board.kicad_sch"
    assert result.status == "errors" and result.evidence.level == Level.UNVERIFIED
    assert result.summary["violations"] == 0 and result.summary["sheets"] == 0
    assert set(result.summary) == SUMMARY_KEYS


def test_timeout_is_retryable() -> None:
    oracle = FakeErcOracle(erc_result=erc_outcome(timeout=True))
    (failed,) = erc_stage(oracle, project(schematic=True)).issues
    assert failed.code == "check.oracle-failed" and failed.retryable is True
    assert failed.message == "fake timed out"


def test_codes_carry_the_oracle_name() -> None:
    oracle = _oracle(erc_violation("pin_not_driven"))
    oracle.name = "other"
    (found,) = erc_stage(oracle, project(schematic=True)).issues
    assert found.code == "other.erc.pin-not-driven"


def test_item_without_a_location_falls_back_to_sheet_and_position() -> None:
    oracle = _oracle(erc_violation("endpoint_off_grid", "warning", at=(76_190_000, 55_080_000)))
    (found,) = erc_stage(oracle, project(schematic=True)).issues
    assert found.where == "/@76.19,55.08"
