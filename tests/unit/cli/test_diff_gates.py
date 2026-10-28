# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite diff --allow`` and ``--three-way`` (capability file-safety, "Gated differences" and "Three-way
difference of KiCad boards"; change c0207). Hermetic: authored boards with round invented edits."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run
from _merge_boards import TRACK_END, replaced, three_boards

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"


def _edited(tmp_path: Path) -> Path:
    """The two-layer board with a track moved and the footprint R1 moved."""
    text = TWO_LAYER.read_text(encoding="utf-8")
    text = replaced(text, "\t\t(end 25 15.8)\n", "\t\t(end 26 15.8)\n")
    text = replaced(text, "\t\t(at 20 15 90)\n", "\t\t(at 21 15 90)\n")
    path = tmp_path / "edited.kicad_pcb"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def test_a_change_outside_the_allowed_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    edited = _edited(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(edited), "--allow", "track")
    assert code == 5 and err["code"] == "FEN-5001" and env["ok"] is False
    found = [(i["code"], i["where"]) for i in env["issues"]]
    assert found == [("diff.not-allowed", "/footprint/R1/position")]
    assert env["result"]["allow"] == ["track"] and env["result"]["total"] == 3
    assert "plan" not in env["result"]  # a gate plans no write
    code, env, _, _ = run(
        monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(edited), "--allow", "track,footprint"
    )
    assert code == 0 and env["issues"] == []


@pytest.mark.parametrize(
    "extra",
    [
        ("--allow", "tracks"),
        ("--allow", "track", "--view", "tree"),
        ("--three-way", "x.kicad_pcb", "--view", "records"),
        ("--out", "merged.kicad_pcb"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra: tuple[str, ...]) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(TWO_LAYER), *extra)
    assert code == 2 and err["code"] == "FEN-2001"


def test_three_way_needs_boards_and_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = str(TWO_LAYER)
    code, _, err, _ = run(monkeypatch, tmp_path, "diff", board, board, "--three-way", board)
    assert code == 2 and err["code"] == "FEN-2001" and "--out" in err["message"]
    code, _, err, _ = run(
        monkeypatch,
        tmp_path,
        "diff",
        str(FOOTPRINT),
        str(FOOTPRINT),
        "--three-way",
        str(FOOTPRINT),
        "--out",
        "x",
    )
    assert code == 2 and err["code"] == "FEN-2001" and "kicad_pcb" in err["hint"]


def test_three_way_merge_under_the_protocol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    args = (
        "diff",
        str(boards.base),
        str(boards.ours),
        "--three-way",
        str(boards.theirs),
        "--out",
        "merged.kicad_pcb",
    )
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 4 and err["code"] == "FEN-4001" and not (tmp_path / "merged.kicad_pcb").exists()
    merge = env["result"]["merge"]
    assert (merge["applied"], merge["already"], merge["conflicts"], merge["refused"]) == (2, 0, 0, None)
    assert merge["out"] == "merged.kicad_pcb" and merge["theirs"] == "theirs.kicad_pcb"
    assert [row["path"] for row in env["result"]["plan"]] == ["merged.kicad_pcb"]
    assert env["result"]["summary"] == {"track": {"added": 2, "removed": 1, "changed": 0}}
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0 and [w["path"] for w in env["receipt"]["written"]] == ["merged.kicad_pcb"]
    merged = (tmp_path / "merged.kicad_pcb").read_text(encoding="utf-8")
    assert "(at 11 10)" in merged and "(end 24 9)" in merged and "000000000207" in merged
    # merged with --allow: the merge only moves tracks
    code, _, _, _ = run(monkeypatch, tmp_path, *args, "--allow", "track", "--dry-run")
    assert code == 0


def test_three_way_conflict_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    theirs = boards.write("other.kicad_pcb", replaced(boards.base_text, TRACK_END, "\t\t(end 25 9)\n"))
    args = (
        "diff",
        str(boards.base),
        str(boards.ours),
        "--three-way",
        str(theirs),
        "--out",
        "merged.kicad_pcb",
    )
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 5 and err["code"] == "FEN-5001" and env["receipt"] is None
    assert [(i["code"], i["where"]) for i in env["issues"]] == [
        ("diff.conflict", "segment 07af368b-89d1-537e-bd8c-1eba13e6bf03")
    ]
    assert env["result"]["merge"]["conflicts"] == 1 and not (tmp_path / "merged.kicad_pcb").exists()


def test_three_way_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boards = three_boards(tmp_path)
    newer = boards.write(
        "newer.kicad_pcb", replaced(boards.base_text, "(version 20260206)", "(version 20260207)")
    )
    args = (
        "diff",
        str(boards.base),
        str(boards.ours),
        "--three-way",
        str(newer),
        "--out",
        "merged.kicad_pcb",
    )
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["diff.unmergeable"]
    assert not (tmp_path / "merged.kicad_pcb").exists()
