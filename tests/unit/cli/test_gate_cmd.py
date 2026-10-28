# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``--gate drc`` of ``route`` and ``tidy`` (change c0225; capability kicad-oracle, "DRC gate on writing
commands", "DRC gate report" and "DRC gate units"), hermetic: the trial is a fake that drops the items a
test names. ``tests/kicad/check/test_gate_cli.py`` runs the gate on ``kicad-cli``."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Collection, Iterable
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _tidybench import bench

from fenolite.api.trials import DroppedItem, TrialFinding, TrialResult, revert
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import _gate
from fenolite.core.evidence import Evidence, Level

ROOT = Path(__file__).resolve().parents[3]
GATED = ("--router", "direct", "--gate", "drc")
TWO_PADS = ROOT / "tests" / "data" / "kicad" / "routing" / "two_pads.kicad_pcb"


def _two_pads(tmp_path: Path) -> Path:
    board = tmp_path / "two_pads.kicad_pcb"
    shutil.copyfile(TWO_PADS, board)
    return board


def _fake(monkeypatch: pytest.MonkeyPatch, drop: Callable[[tuple[str, ...]], set[str]]) -> list[Any]:
    """Replace the pre-flight and ``trial``: the fake drops ``drop(ids)``, with ``together`` applied, and
    records each call's ``together``."""
    calls: list[Any] = []

    def trial(board: Path, edit: Any, *, together: Iterable[Collection[str]] = (), **_: Any) -> TrialResult:
        fresh = read_board(board.read_text(encoding="utf-8"), file=board.name)
        edited, ids = edit(fresh)
        units = [set(unit) for unit in together]
        calls.append(units)
        named = drop(tuple(ids))
        gone = set(named)
        for unit in units:
            if unit & named:
                gone |= unit & set(ids)
        finding = TrialFinding("clearance", "error", "Clearance violation", ("u1",), tuple(sorted(named)))
        dropped = tuple(DroppedItem(item, (finding,)) for item in ids if item in gone)
        kept = revert(edited, fresh, gone)
        return TrialResult(
            board_text=write_board(kept, target=10).text,
            findings=(),
            kept=tuple(item for item in ids if item not in gone),
            dropped=dropped,
            baseline=2,
            edited=2,
            runs=2 if not gone else 3,
            refilled=False,
            tool_version="10.0.7",
            evidence=Evidence(Level.KICAD_VERIFIED, oracle="kicad-cli 10.0.7", hypotheses=("H-K-DRC-TRIAL",)),
        )

    monkeypatch.setattr(_gate, "tool_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_gate, "trial", trial)
    return calls


def test_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "No tool": exit 6 before routing, the board unchanged."""
    hide_kicad(monkeypatch, tmp_path)
    board = _two_pads(tmp_path)
    before = board.read_bytes()
    code, _, error, _ = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--gate", "drc",
                            "--confirm")  # fmt: skip
    assert code == 6 and error["code"] == "FEN-6001"
    assert board.read_bytes() == before


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _two_pads(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--kicad-cli",
                            "kicad-cli", "--dry-run")  # fmt: skip
    assert code == 2 and error["code"] == "FEN-2001" and "--gate" in error["message"]
    for extra in (("--drc",), ("--report",)):
        code, _, error, _ = run(monkeypatch, tmp_path, "tidy", board.name, "--gate=drc", *extra, "--dry-run")
        assert code == 2 and error["code"] == "FEN-2001", extra


def test_verdict_of_a_gated_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Verdict of a gated route", against the fake: the one routed track dropped leaves its net
    unrouted, counts no track and plans no write."""
    _fake(monkeypatch, lambda ids: set(ids))
    board = _two_pads(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "route", board.name, *GATED, "--dry-run")
    assert code == 0, error
    result = env["result"]
    assert result["unrouted"] == ["ROUTE_ME"] and result["routed"] == [] and result["tracks"] == 0
    assert not result.get("plan")
    gate = result["gate"]
    assert gate["items"] == 1 and gate["kept"] == 0 and gate["runs"] == 3
    assert gate["dropped"][0]["findings"][0]["type"] == "clearance"
    assert [found["code"] for found in env["issues"] if found["code"].startswith("gate.")] == ["gate.dropped"]
    assert env["evidence"]["level"] == "KICAD-VERIFIED"


def test_a_clean_gated_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake(monkeypatch, lambda ids: set())
    board = _two_pads(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "route", board.name, *GATED, "--dry-run")
    assert code == 0, error
    result = env["result"]
    assert result["routed"] == ["ROUTE_ME"] and result["tracks"] == 1 and len(result["plan"]) == 1
    assert result["gate"]["dropped"] == [] and env["evidence"]["level"] == "KICAD-VERIFIED"
    plain = run(monkeypatch, tmp_path, "route", board.name, "--router", "direct", "--dry-run")[1]
    assert plain["result"]["gate"] is None and plain["evidence"]["level"] == "UNVERIFIED"


def _tidy_board(tmp_path: Path) -> Path:
    board = tmp_path / "tidy.kicad_pcb"
    board.write_text(write_board(bench(), target=10).text, encoding="utf-8", newline="\n")
    project = synthesize_project(bench(), target=10, board_name="tidy")
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    return board


def test_tidy_drops_an_edit_whole(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A chamfer undone whole", through the command: the track the T-joint entry adds is named,
    and the track it shortened goes back too; the other edits stay."""
    board = _tidy_board(tmp_path)
    plain = run(monkeypatch, tmp_path, "tidy", board.name, "--dry-run")[1]["result"]
    chamfer = next(edit for edit in plain["edits"] if edit["step"] == "chamfer")
    named = chamfer["added"][0]
    calls = _fake(monkeypatch, lambda ids: {named} & set(ids))
    code, env, error, _ = run(monkeypatch, tmp_path, "tidy", board.name, "--gate", "drc", "--dry-run")
    assert code == 0, error
    result = env["result"]
    assert [edit for edit in result["edits"] if edit["step"] == "chamfer"] == []
    assert len(result["edits"]) == len(plain["edits"]) - 1 and len(result["plan"]) == 1
    unit = {*chamfer["removed"], *chamfer["replaced"], *chamfer["added"]}
    assert any(unit <= group for group in calls[0])
    dropped = {item["id"] for item in result["gate"]["dropped"]}
    assert dropped == unit
    assert env["evidence"]["level"] == "KICAD-VERIFIED"


def test_joined_and_edit_ids() -> None:
    assert sorted(map(sorted, _gate.joined([("a", "b"), ("c",), ("b", "d")]))) == [["a", "b", "d"], ["c"]]
    design = bench()
    assert _gate.edit_ids(design, design) == ()
