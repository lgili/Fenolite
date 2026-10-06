# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite parity`` (capability cli-contract, "Parity command"; change c0072). Hermetic: the committed
example needs no tool, and the netlist of a schematic that Fenolite does not read itself comes from a fake
``kicad-cli`` that writes an authored export."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import _parityedit as edits
import pytest
from _buildhelp import blink, build
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import tree_snapshot

from fenolite.cli._examples import EXAMPLE_PARITY
from fenolite.cli.cmd_parity import COMMAND, NETLISTS

DATA = Path(__file__).resolve().parents[2] / "data" / "kicad"
AGREE = Path(EXAMPLE_PARITY)
BOARD, SHEET = "blink.kicad_pcb", "blink.kicad_sch"
EXPORT = (DATA / "netlist" / "export_10.net").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_real_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def copy(tmp_path: Path) -> Path:
    return Path(shutil.copytree(AGREE, tmp_path / "agree"))


def edit(root: Path, change: object) -> None:
    board = root / BOARD
    board.write_text(change(board.read_text(encoding="utf-8")), encoding="utf-8")  # type: ignore[operator]


def wired(tmp_path: Path) -> Path:
    """The example board beside an authored schematic that holds wires."""
    root = copy(tmp_path)
    shutil.copyfile(DATA / "schematic" / "flat.kicad_sch", root / SHEET)
    return root


def codes(env: dict[str, object]) -> list[str]:
    return [i["code"] for i in env["issues"]]  # type: ignore[union-attr,index]


def test_command() -> None:
    assert COMMAND.name == "parity" and COMMAND.mutates is False
    assert COMMAND.example_args == (EXAMPLE_PARITY,) and not COMMAND.example_tools
    assert NETLISTS == ("auto", "own", "kicad")


def test_example_is_a_fresh_build() -> None:
    """The committed board and schematic are what ``build`` writes for the blink today."""
    files = build(blink(), 10).files
    assert sorted(p.name for p in AGREE.iterdir()) == [BOARD, SHEET]
    for name in (BOARD, SHEET):
        assert (AGREE / name).read_bytes() == files[name], f"{name}: regenerate tests/data/kicad/parity/agree"


def test_agreeing_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    before = tree_snapshot(AGREE)
    code, env, err, out = run(monkeypatch, tmp_path, "parity", EXAMPLE_PARITY)
    assert code == 0, err
    result = env["result"]
    assert (result["board"], result["schematic"], result["netlist"]) == (BOARD, SHEET, "own")
    assert result["summary"]["refs_one_side"] == 0 and not any(result["summary"].values())
    assert result["findings"] == [] and env["issues"] == []
    assert env["evidence"]["level"] == "INFERRED" and "H-K-PARITY-OWN" in env["evidence"]["hypotheses"]
    assert env["input"]["path"] == BOARD and tree_snapshot(AGREE) == before
    again = run(monkeypatch, tmp_path, "parity", EXAMPLE_PARITY)[3]
    assert without_elapsed(out) == without_elapsed(again)


@pytest.mark.parametrize("given", ["folder", "board"])
def test_edited_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, given: str) -> None:
    root = copy(tmp_path)
    edit(root, lambda text: edits.rename(text, "R1", "R99"))
    before = tree_snapshot(root)
    path = root if given == "folder" else root / BOARD
    code, env, _, _ = run(monkeypatch, tmp_path, "parity", str(path))
    assert code == 5 and codes(env) == ["parity.extra-footprint", "parity.missing-footprint"]
    assert [(i["where"], i["severity"]) for i in env["issues"]] == [("R99", "error"), ("R1", "error")]
    result = env["result"]
    assert result["summary"]["refs_one_side"] == 2
    assert result["findings"] == [
        {"code": "parity.extra-footprint", "severity": "error", "key": "R99", "field": "", "schematic": "",
         "board": ""},
        {"code": "parity.missing-footprint", "severity": "error", "key": "R1", "field": "", "schematic": "",
         "board": ""},
    ]  # fmt: skip
    assert tree_snapshot(root) == before


def test_warnings_do_not_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = copy(tmp_path)
    edit(root, lambda text: edits.revalue(text, "R1"))
    code, env, _, _ = run(monkeypatch, tmp_path, "parity", str(root))
    assert code == 0 and codes(env) == ["parity.footprint-mismatch"]
    assert env["result"]["findings"][0]["field"] == "value"


def test_missing_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = copy(tmp_path)
    (root / SHEET).unlink()
    code, _, error, _ = run(monkeypatch, tmp_path, "parity", str(root))
    assert code == 3 and error["code"] == "FEN-3001" and SHEET in error["message"]


def test_third_party_schematic_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = wired(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "parity", str(root))
    assert code == 6 and error["code"] == "FEN-6001" and "kicad-cli" in json.dumps(error)
    # ``own`` never runs a tool: it refuses the sheet with the reasons
    code, _, error, _ = run(monkeypatch, tmp_path, "parity", str(root), "--netlist", "own")
    assert code == 7 and error["code"] == "FEN-7001" and "wire" in error["message"]


def test_netlist_from_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = wired(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    before = tree_snapshot(root)
    code, env, err, _ = run(monkeypatch, tmp_path, "parity", str(root), "--kicad-cli", str(fake))
    assert code == 5, err
    assert env["result"]["netlist"] == "kicad" and env["result"]["summary"]["refs_one_side"] > 0
    assert env["evidence"]["oracle"].startswith("kicad-cli") and env["evidence"]["level"] == "INFERRED"
    assert any(c["args"][:3] == ["sch", "export", "netlist"] for c in calls(fake))
    assert tree_snapshot(root) == before


def test_kicad_asked_for_a_generated_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = copy(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "parity", str(root), "--netlist", "kicad")
    assert code == 6 and "kicad-cli" in json.dumps(error)
    fake = fake_kicad_cli(tmp_path / "bin", netlist=EXPORT)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "parity", str(root), "--netlist", "kicad", "--kicad-cli", str(fake)
    )
    assert env["result"]["netlist"] == "kicad" and code in (0, 5)


def test_unknown_netlist_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, _, _ = run(monkeypatch, tmp_path, "parity", EXAMPLE_PARITY, "--netlist", "other")
    assert code == 2


def test_check_stage_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``check --stages parity`` (verification-loop, "Parity stage", scenario "Without KiCad")."""
    root = copy(tmp_path)
    edit(root, lambda text: edits.renet(text, "R1", "2", "GND"))
    before = tree_snapshot(root)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", "parity")
    assert code == 5 and [(i["code"], i["where"]) for i in env["issues"]] == [("parity.net-conflict", "R1-2")]
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == ("parity", "errors")
    assert stage["summary"]["netlist"] == "own" and stage["summary"]["compared"] is False
    assert stage["evidence"]["level"] == "INFERRED" and tree_snapshot(root) == before
    # the same finding as the command gives
    code, env, _, _ = run(monkeypatch, tmp_path, "parity", str(root))
    assert code == 5 and codes(env) == ["parity.net-conflict"]


def test_hierarchical_build_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A project with one sheet per module is inside the own netlist: no tool runs (c0070)."""
    from _schbuild import built_nested, write_files

    root = write_files(built_nested(), tmp_path / "nested")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    code, env, err, _ = run(monkeypatch, tmp_path, "parity", str(root))
    assert code == 0, err
    assert env["result"]["netlist"] == "own" and env["result"]["findings"] == [] and env["issues"] == []
