# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proof gate of board items (capability fenolite-library, "Board proof gate"; c0281's "Skipped levels";
change c0279). Reports have the shape of ``fenolite verify-source --json`` ``result``."""

from __future__ import annotations

from typing import Any

from fenolite.library.proof import FAIL, PASS, PASS_ACCEPTED, derive, gate, recorded_result

DIFF = {
    "level": 7,
    "kind": "graphic-missing",
    "where": "board:Edge.Cuts:1,2-3,4",
    "field": "graphic",
    "a": "0.127",
    "b": "0.1",
}
FIDELITY: dict[str, Any] = {
    "accepted": [
        {
            "id": "A001",
            "level": 7,
            "kind": "graphic-missing",
            "where": "board:Edge.Cuts:*",
            "field": "graphic",
            "reason": "stroke width",
            "attribution": "fenolite",
            "decided": "2026-10-30",
        }
    ],
    "proof": {"levels": {"1": "equal", "2": "equal", "7": "accepted"}},
}


def _report(seven: str, differences: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "levels": [
            {"level": 1, "status": "equal", "reason": ""},
            {"level": 2, "status": "equal", "reason": ""},
            {"level": 7, "status": seven, "reason": ""},
        ],
        "differences": differences or [],
        "accepted": [{**DIFF, "rule": "A001"}],
    }


def test_accepted_difference_passes() -> None:
    """Scenario "Accepted difference passes"."""
    found = gate(_report("accepted"), FIDELITY, item="boards/x")
    assert found.result == PASS_ACCEPTED and found.issues == ()


def test_new_difference_fails() -> None:
    """Scenario "New difference fails"."""
    second = {**DIFF, "where": "board:F.SilkS:9,9-8,8"}
    found = gate(_report("differs", [second]), FIDELITY, item="boards/x")
    assert found.result == FAIL
    messages = [i.message for i in found.issues if i.code == "library.proof-failed"]
    assert any("board:F.SilkS:9,9-8,8" in m for m in messages)


def test_statuses_must_equal_the_record() -> None:
    record = {**FIDELITY, "proof": {"levels": {"1": "equal", "2": "equal", "7": "equal"}}}
    found = gate(_report("accepted"), record)
    assert found.result == FAIL and any("fidelity.proof records equal" in i.message for i in found.issues)


def test_level_skipped_with_a_reason() -> None:
    """c0281 scenario "Level S skipped with a reason"."""
    levels = {"1": "equal", "2": "equal", "S": "skipped"}
    found = derive(levels, {"S": "drawn-unavailable"})
    assert found.result == PASS and dict(found.skipped) == {"S": "drawn-unavailable"}
    assert derive(levels, {}).result == FAIL
    refused = derive(levels, {"S": "build-failed"})
    assert refused.result == FAIL and "build-failed" in refused.issues[0].message
    report = {
        "levels": [
            {"level": 1, "status": "equal", "reason": ""},
            {"level": "S", "status": "skipped", "reason": "drawn-unavailable"},
        ]
    }
    record = {
        "accepted": [],
        "proof": {"levels": {"1": "equal", "S": "skipped"}, "skipped": {"S": "drawn-unavailable"}},
    }
    assert gate(report, record).result == PASS


def test_skipped_level_without_a_reason_in_the_record() -> None:
    assert (
        recorded_result(
            {"proof": {"levels": {"1": "equal", "S": "skipped"}, "skipped": {"S": "drawn-unavailable"}}}
        )
        == PASS
    )
    assert recorded_result({"proof": {"levels": {"1": "equal", "S": "skipped"}}}) == FAIL
    assert recorded_result(None) is None


def test_audit_gates_a_verify_source_reply(monkeypatch, tmp_path, demo) -> None:  # type: ignore[no-untyped-def]
    """The library's proof job: ``library audit ROOT --item BOARD --proof REPLY`` gates a verify-source
    reply."""
    import io
    import json
    from contextlib import redirect_stderr, redirect_stdout

    from fenolite.cli import main as cli_main

    board = "boards/cern-ohl-s/demo-src/blink"
    reply = {
        "result": {
            "levels": [
                {"level": 1, "status": "equal", "reason": ""},
                {"level": 2, "status": "equal", "reason": ""},
                {"level": 7, "status": "accepted", "reason": ""},
                {"level": "S", "status": "skipped", "reason": ""},
            ],
            "differences": [],
        }
    }
    (tmp_path / "reply.json").write_text(json.dumps(reply), encoding="utf-8")
    monkeypatch.chdir(demo)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = cli_main.main(
            ["library", "audit", ".", "--item", board, "--proof", str(tmp_path / "reply.json"), "--json"]
        )
    envelope = json.loads(out.getvalue())
    assert code == 0, envelope["issues"]
    assert envelope["result"]["proof"] == {
        "item": board,
        "result": "pass-with-accepted",
        "skipped": {"S": "drawn-unavailable"},
    }
