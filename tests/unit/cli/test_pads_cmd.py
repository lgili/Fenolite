# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pads`` (capability cli-contract, "Pads command"; change c0068). Hermetic: no tool runs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import ELAPSED, run
from _placed import LIBS

from fenolite.backends.kicad import frame
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import cmd_pads
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.core.evidence import Evidence

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
KEYS = [
    "where", "ref", "number", "index", "kind", "position", "rotation", "side", "layers", "net", "box",
    "drill",
]  # fmt: skip


def pads(monkeypatch: pytest.MonkeyPatch, *args: str, board: Path = BOARD) -> tuple[int, dict[str, Any], Any]:
    code, env, err, _ = run(monkeypatch, ROOT, "pads", str(board), *args)
    return code, env, err


def test_pads_of_one_part(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Pads of one part"."""
    code, env, _ = pads(monkeypatch, "R1")
    assert code == 0 and env["command"] == "pads" and env["schema"] == "fenolite.pads.v0"
    result = env["result"]
    assert result["count"] == 2 and result["origin"] == [0, 0]
    first, second = result["pads"]
    assert list(first) == KEYS
    assert (first["where"], first["net"], first["position"]) == ("R1-1", "VCC", [20_000_000, 15_800_000])
    assert (second["where"], second["net"], second["position"]) == ("R1-2", "LED_A", [20_000_000, 14_200_000])
    for pad in (first, second):
        assert (pad["kind"], pad["side"], pad["index"], pad["drill"], pad["ref"]) == (
            "smd",
            "top",
            0,
            None,
            "R1",
        )
        x0, y0, x1, y1 = pad["box"]
        assert x0 < pad["position"][0] < x1 and y0 < pad["position"][1] < y1
        assert all(isinstance(v, int) for v in (*pad["position"], *pad["box"], pad["rotation"]))


def test_one_pad_of_a_through_hole_part(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "One pad of a through-hole part"."""
    code, env, _ = pads(monkeypatch, "D1", "1")
    assert code == 0 and env["result"]["count"] == 1
    (pad,) = env["result"]["pads"]
    assert (pad["where"], pad["net"], pad["kind"], pad["side"], pad["drill"]) == (
        "D1-1", "GND", "thru_hole", "bottom", 800_000,
    )  # fmt: skip
    design = read_board(BOARD)
    (record,) = frame.find_pads(design, "D1", 1)
    assert {entry.layer for entry in record.copper} == {"F.Cu", "B.Cu"}
    assert pad["layers"] == list(record.layers) and pad["rotation"] == record.rotation


def test_positions_relative_to_an_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Positions relative to an origin"."""
    _, plain, _ = pads(monkeypatch, "R1")
    code, env, _ = pads(monkeypatch, "R1", "--origin", "10mm,10mm")
    assert code == 0 and env["result"]["origin"] == [10_000_000, 10_000_000]
    moved, before = env["result"]["pads"][0], plain["result"]["pads"][0]
    assert moved["position"] == [10_000_000, 5_800_000]
    assert moved["box"] == [value - 10_000_000 for value in before["box"]]
    code, env, _ = pads(monkeypatch, "R1", "--origin", "1in, 500mil")
    assert code == 0 and env["result"]["origin"] == [25_400_000, 12_700_000]


def test_whole_board(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Whole board"."""
    code, env, _ = pads(monkeypatch)
    assert code == 0 and env["result"]["count"] == 4
    assert [pad["where"] for pad in env["result"]["pads"]] == ["R1-1", "R1-2", "D1-1", "D1-2"]


def test_unknown_reference_and_unknown_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Unknown reference and unknown number"."""
    code, _, err = pads(monkeypatch, "R9")
    assert code == 2 and err["code"] == "FEN-2001" and "R1" in err["hint"]
    code, _, err = pads(monkeypatch, "R1", "7")
    assert code == 2 and err["code"] == "FEN-2001" and "1, 2" in err["hint"]


@pytest.mark.parametrize("origin", ["10,10", "10mm", "10mm,10mm,1mm", "abc,1mm", "10mm,"])
def test_bad_origin(monkeypatch: pytest.MonkeyPatch, origin: str) -> None:
    code, _, err = pads(monkeypatch, "R1", "--origin", origin)
    assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--origin"


def test_project_folder_and_missing_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    shutil.copy(BOARD, folder / "board.kicad_pcb")
    code, env, _ = pads(monkeypatch, board=folder)
    assert code == 0 and env["result"]["count"] == 4 and env["input"]["path"] == "board.kicad_pcb"
    code, _, err = pads(monkeypatch, board=tmp_path / "none.kicad_pcb")
    assert code != 0 and err["code"].startswith("FEN-")


def test_index_counts_the_pads_that_share_a_number(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``index`` is the value that ``Part.pad(number, index=…)`` takes; a pad without copper has no box."""
    from _placed import Part, design_of

    from fenolite.backends.kicad.pcb import write_board

    design = design_of(Part("J1", "Mini_Edge_Cases", 10, 10, nets={"1": "GND"}))
    board = tmp_path / "edge.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    assert (LIBS / "Mini.pretty").is_dir()
    code, env, _ = pads(monkeypatch, "J1", board=board)
    assert code == 0
    ones = [pad for pad in env["result"]["pads"] if pad["number"] == "1"]
    assert [pad["index"] for pad in ones] == [0, 1] and len({tuple(pad["position"]) for pad in ones}) == 2
    hole = next(pad for pad in env["result"]["pads"] if pad["kind"] == "np_thru_hole")
    assert (hole["box"], hole["where"], hole["number"]) == (None, "J1", "") and hole["drill"] == 1_200_000
    code, env, _ = pads(monkeypatch, "J1", "1", board=board)
    assert code == 0 and [pad["index"] for pad in env["result"]["pads"]] == [0, 1]


def test_deterministic_and_without_absolute_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    first = run(monkeypatch, ROOT, "pads", str(BOARD))[3]
    second = run(monkeypatch, ROOT, "pads", str(BOARD))[3]
    assert ELAPSED.sub("", first) == ELAPSED.sub("", second)
    assert str(ROOT) not in first and str(Path.home()) not in first


def test_evidence_and_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    command = cmd_pads.COMMAND
    assert (command.name, command.mutates, command.example_args) == ("pads", False, (EXAMPLE_BOARD, "R1"))
    code, env, _ = pads(monkeypatch, "R1")
    assert code == 0 and env["receipt"] is None
    assert set(frame.EVIDENCE.hypotheses) <= set(env["evidence"]["hypotheses"])
    assert "H-K-PCB-READ" in env["evidence"]["hypotheses"]
    assert env["evidence"]["level"] == Evidence.combine(frame.EVIDENCE).level.value


def test_runs_no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The command is hermetic and read-only", the hermetic half."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("pads ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    code, env, _ = pads(monkeypatch, *cmd_pads.COMMAND.example_args[1:], board=Path(EXAMPLE_BOARD))
    assert code == 0 and env["result"]["count"] >= 1
