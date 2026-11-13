# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite edit PATH.PcbDoc --ops-file FILE [--gate NAME]`` (change c0497, design D1), on the authored
``vias`` board of ``tests/unit/backends/altium/edit/board_ops.py``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.cli.main import main
from tests.unit.backends.altium.edit import board_ops
from tests.unit.backends.altium.test_part_j import build_board

OPS = [
    {
        "op": "set_via_mask",
        "item": {"kind": "vias", "net": "GND"},
        "tented_top": True,
        "tented_bottom": True,
        "expansion": "0.05mm",
        "count": 6,
    }
]


@pytest.fixture(scope="module")
def vias_board(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    folder = tmp_path_factory.mktemp("kit") / "board"
    build_board(folder)
    return board_ops.vias((folder / "edit.PcbDoc").read_bytes())


@pytest.fixture
def folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vias_board: bytes) -> Path:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    (work / "vias.PcbDoc").write_bytes(vias_board)
    return work


def run(capsys: Any, *argv: str) -> tuple[int, Any, Any]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out.strip() else None
    err = json.loads(captured.err.strip().splitlines()[-1]) if captured.err.strip() else None
    return code, out, err


def _ops(folder: Path, entries: list[dict[str, Any]]) -> str:
    (folder / "ops.json").write_text(json.dumps(entries), encoding="utf-8")
    return "ops.json"


def test_plan_and_confirm(capsys: Any, folder: Path) -> None:
    """Scenario "A via mask planned and written"."""
    before = (folder / "vias.PcbDoc").read_bytes()
    name = _ops(folder, OPS)
    code, out, _ = run(capsys, "edit", "vias.PcbDoc", "--ops-file", name, "--gate", "tenting", "--dry-run")
    assert code == 0 and (folder / "vias.PcbDoc").read_bytes() == before
    result = out["result"]
    assert result["operations"] == ["tent 6 vias on top+bottom, expansion 0.05 mm"]
    assert result["records"] == [{"storage": "Vias6", "removed": 6, "added": 6}]
    assert [i["code"] for i in out["issues"]] == ["altium.edit.gate-opened"] and out["evidence"][
        "level"
    ] == "UNVERIFIED"
    code, out, _ = run(capsys, "edit", "vias.PcbDoc", "--ops-file", name, "--gate", "tenting", "--confirm",
                       "--plan", result["plan_id"])  # fmt: skip
    assert code == 0 and [w["path"] for w in out["receipt"]["written"]] == ["vias.PcbDoc"]
    assert [i["code"] for i in out["issues"]] == ["altium.edit.gate-opened"]
    after = State.of((folder / "vias.PcbDoc").read_bytes()).get("Vias6")
    assert sum(rec.split(raw)[1][0][1] & 0x60 == 0x60 for raw in after) >= 6


def test_closed_gate(capsys: Any, folder: Path) -> None:
    """Scenario "A closed gate"."""
    code, out, _ = run(capsys, "edit", "vias.PcbDoc", "--ops-file", _ops(folder, OPS), "--dry-run")
    assert code == 5 and [i["code"] for i in out["issues"]] == ["altium.edit.gate"]
    assert "tenting" in out["issues"][0]["message"] and not out["result"].get("plan_id")


@pytest.mark.parametrize(
    ("entries", "words"),
    [
        ([{"op": "explode"}], "the op 'explode'"),
        ([{"op": "move", "item": {"kind": "blob"}, "dx": 0, "dy": 0}], "the item kind 'blob'"),
        ([{"op": "move", "item": {"kind": "designator", "ref": "D1"}, "dx": "1mm"}], "needs the argument dy"),
        (
            [OPS[0], {"op": "move", "item": {"kind": "comment", "ref": "D1"}, "dx": 0, "dy": 0, "far": 1}],
            "entry 1",
        ),
    ],
)
def test_usage_errors(capsys: Any, folder: Path, entries: list[dict[str, Any]], words: str) -> None:
    code, _, err = run(
        capsys, "edit", "vias.PcbDoc", "--ops-file", _ops(folder, entries), "--gate", "tenting"
    )
    assert code == 2 and err["code"] == "FEN-2001" and words in err["message"]


def test_wrong_source_options(capsys: Any, folder: Path) -> None:
    (folder / "design.py").write_text("x = 1\n", encoding="utf-8")
    code, _, err = run(capsys, "edit", "design.py", "--ops-file", _ops(folder, OPS))
    assert code == 2 and err["code"] == "FEN-2001"
    (folder / "new.txt").write_text("x = 2\n", encoding="utf-8")
    code, _, err = run(capsys, "edit", "vias.PcbDoc", "--content-file", "new.txt")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err = run(capsys, "edit", "vias.PcbDoc", "--ops-file", _ops(folder, OPS), "--gate", "nothing")
    assert code == 2 and "nothing" in err["message"]
