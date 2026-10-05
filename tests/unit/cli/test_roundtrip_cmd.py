# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite roundtrip`` (capability cli-contract, "Roundtrip command"; change c0066). Hermetic: RT2 runs
against the fake ``kicad-cli``."""

from __future__ import annotations

from pathlib import Path

import _ipc
import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot

from fenolite.backends import registry
from fenolite.backends.base import ReadResult, RoundTrip, Validation
from fenolite.backends.kicad.pcb import EVIDENCE, opaque_count, read_board
from fenolite.core.errors import Issue

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
SYMBOLS = DATA / "libs" / "Mini.kicad_sym"
SHEET = DATA / "kicad" / "sheets" / "all_items.kicad_wks"
PROJECT = DATA / "kicad" / "project" / "empty_10.kicad_pro"


def test_authored_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER))
    result = env["result"]
    assert code == 0 and env["ok"] is True and env["issues"] == []
    assert result["kind"] == "kicad_pcb" and result["level"] == "rt1"
    assert result["rt0"] == {"passed": True, "difference": ""}
    assert result["rt1"] == {
        "passed": True,
        "difference": "",
        "opaque_count": opaque_count(read_board(TWO_LAYER)),
    }
    assert "rt2" not in result
    assert env["input"]["path"] == "two_layer.kicad_pcb" and env["evidence"]["hypotheses"] == ["H-K-PCB-READ"]


def test_level_rt0_runs_no_rebuild(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER), "--level", "rt0")
    assert code == 0 and env["result"] == {
        "kind": "kicad_pcb",
        "level": "rt0",
        "rt0": {"passed": True, "difference": ""},
    }
    assert env["evidence"]["hypotheses"] == ["H-K-SEXPR-STRICT"]


@pytest.mark.parametrize(("path", "kind"), [(SYMBOLS, "kicad_sym"), (SHEET, "kicad_wks")])
def test_kind_without_a_rebuild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: Path, kind: str
) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(path))
    assert code == 0
    assert (env["result"]["kind"], env["result"]["level"], env["result"]["rt1"]) == (
        kind,
        "rt0",
        "not-applicable",
    )


class _Failing:
    name = "kicad"

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation:
        verdict = RoundTrip("RT1", False, False, True, True, 3, "/kicad_pcb/footprint[0]/pad[1]")
        return Validation(ReadResult(read_board(path), (), EVIDENCE), verdict)


def test_failed_level_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(registry, "for_path", lambda path: _Failing())
    code, env, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER))
    assert code == 5 and err["code"] == "FEN-5001" and env["ok"] is False
    assert env["result"]["level"] == "rt0" and env["result"]["rt1"]["passed"] is False
    failed = [i for i in env["issues"] if i["code"] == "roundtrip.failed"]
    assert len(failed) == 1 and failed[0]["severity"] == "error"
    assert failed[0]["where"] == "/kicad_pcb/footprint[0]/pad[1]"


def test_refused_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
    notes = tmp_path / "notes.txt"
    notes.write_text("x\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(notes))
    assert code == 2 and err["code"] == "FEN-2001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(unbalanced))
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(PROJECT))
    assert code == 3 and err["code"] == "FEN-3001"  # a project file without its board


def test_rt2_needs_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER), "--level", "rt2")
    assert code == 6 and err["code"] == "FEN-6001" and "--level rt1" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(SYMBOLS), "--level", "rt2")
    assert code == 2 and err["code"] == "FEN-2001"


def test_rt2_through_the_fake_tool_is_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10, built=True)
    board = root / "board.kicad_pcb"
    fake = fake_kicad_cli(
        tmp_path / "bin",
        writes=("x.kicad_prl",),
        rewrite_input=True,
        refill_board=board.read_text(encoding="utf-8") + "\n",
        ipcd356=_ipc.for_board(board),
    )
    before = tree_snapshot(root)
    code, env, _, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    assert code == 0, env["issues"]
    rt2 = env["result"]["rt2"]
    assert env["result"]["level"] == "rt2" and rt2["passed"] is True and rt2["judged"] is True
    assert {"normalised", "runs", "before", "after", "unstable", "differences"} <= set(rt2)
    assert any(c["args"][:2] == ["pcb", "drc"] for c in calls(fake))
    assert tree_snapshot(root) == before and not (root / "x.kicad_prl").exists()
