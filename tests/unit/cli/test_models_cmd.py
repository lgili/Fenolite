# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite models`` (capability cli-contract, "Models command"; change c0116). Hermetic: the command
runs no tool, and the model is the authored box of ``tests/data/models/``."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _models import BOX, BOX_REL, MODELS, official, two_layer_with_models
from _projects import tree_snapshot

from fenolite.backends.kicad import libs
from fenolite.backends.kicad import models as kicad_models
from fenolite.cli.cmd_models import COMMAND

ABSENT = official("Fenolite.3dshapes/Absent.step")
SHA = hashlib.sha256(BOX.read_bytes()).hexdigest()


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The two-layer board whose ``R1`` names the authored box and whose ``D1`` names a model no source
    holds, with ``KICAD10_3DMODEL_DIR`` on the authored folder, no install and no KiCad configuration."""
    hide_kicad(monkeypatch, tmp_path)
    empty = tmp_path / "config-home"
    empty.mkdir()
    monkeypatch.setenv("KICAD10_3DMODEL_DIR", str(MODELS))
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(empty))
    monkeypatch.delenv("FENOLITE_LIBS_CACHE", raising=False)
    monkeypatch.setattr(libs, "MACOS_INSTALL", tmp_path / "no-install")
    monkeypatch.setattr(libs, "LINUX_INSTALL", tmp_path / "no-install")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("fenolite models ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    return two_layer_with_models(tmp_path / "proj", {"R1": official(), "D1": ABSENT})


def test_list_located_and_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    before = tree_snapshot(board.parent)
    code, env, _, out = run(monkeypatch, tmp_path, "models", str(board))
    assert code == 0, env
    result = env["result"]
    assert result["counts"] == {"paths": 2, "located": 1, "missing": 1}
    assert result["board"] == "two_layer.kicad_pcb"
    assert result["models"] == [
        {"path": ABSENT, "source": "missing", "sha256": None, "bytes": None, "refs": ["D1"]},
        {"path": official(), "source": "env", "sha256": SHA, "bytes": BOX.stat().st_size, "refs": ["R1"]},
    ]
    (warning,) = env["issues"]
    assert (warning["code"], warning["severity"]) == ("kicad.lib.missing-3d-model", "warning")
    assert "D1" in warning["message"] and "Absent.step" in warning["message"]
    assert env["evidence"]["level"] == kicad_models.EVIDENCE.level.value == "INFERRED"
    assert env["evidence"]["hypotheses"] == ["H-K-EXPORT-MODELS"]
    assert "plan" not in result and tree_snapshot(board.parent) == before
    for needle in (str(tmp_path), str(Path.home()), str(MODELS)):
        assert needle not in out
    # two runs on unchanged inputs give the same output
    _, _, _, again = run(monkeypatch, tmp_path, "models", str(board))
    assert without_elapsed(again) == without_elapsed(out)


def test_vendored_then_read_from_the_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    text = board.read_bytes()
    code, env, err, _ = run(monkeypatch, tmp_path, "models", str(board), "--vendor")
    assert code == 4 and err["code"] == "FEN-4001"  # a plan, and nothing written without --confirm
    assert [p["path"] for p in env["result"]["plan"]] == [f"proj/3dmodels/{BOX_REL}"]
    assert not (board.parent / "3dmodels").exists()

    code, env, _, _ = run(monkeypatch, tmp_path, "models", str(board), "--vendor", "--confirm")
    assert code == 0, env
    assert [w["path"] for w in env["receipt"]["written"]] == [f"proj/3dmodels/{BOX_REL}"]
    assert env["receipt"]["written"][0]["sha256"] == SHA
    copy = board.parent / "3dmodels" / BOX_REL
    assert copy.read_bytes() == BOX.read_bytes()
    assert sorted(p.relative_to(board.parent).as_posix() for p in board.parent.rglob("*") if p.is_file()) == [
        f"3dmodels/{BOX_REL}",
        "two_layer.kicad_pcb",
    ]
    assert board.read_bytes() == text  # the board and its model paths never change

    code, env, _, _ = run(monkeypatch, tmp_path, "models", str(board))
    by_path = {m["path"]: m for m in env["result"]["models"]}
    assert code == 0 and by_path[official()]["source"] == "project" and by_path[official()]["sha256"] == SHA
    # nothing is left to vendor: the copy is the project's own
    code, env, _, _ = run(monkeypatch, tmp_path, "models", str(board), "--vendor", "--dry-run")
    assert code == 0 and env["result"].get("plan", []) == []


def test_vendor_from_inside_the_project(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    code, env, _, _ = run(monkeypatch, board.parent, "models", ".", "--vendor", "--dry-run")
    assert code == 0 and [p["path"] for p in env["result"]["plan"]] == [f"3dmodels/{BOX_REL}"]
    assert env["result"]["plan"][0]["kind"] == "3d-model"


def test_models_are_paged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    assert COMMAND.paged == "models" and COMMAND.mutates
    code, env, _, _ = run(monkeypatch, tmp_path, "models", str(board), "--limit", "1")
    assert code == 0 and len(env["result"]["models"]) == 1
    assert env["result"]["counts"]["paths"] == 2


def test_a_board_without_models(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path) -> None:
    plain = two_layer_with_models(tmp_path / "plain", {})
    code, env, _, _ = run(monkeypatch, tmp_path, "models", str(plain), "--vendor", "--confirm")
    assert code == 0 and env["issues"] == []
    assert env["result"]["models"] == [] and env["result"]["counts"] == {
        "paths": 0,
        "located": 0,
        "missing": 0,
    }


def test_examples_run_no_tool() -> None:
    assert COMMAND.example_args and COMMAND.mutation_example_args == (*COMMAND.example_args, "--vendor")
    assert COMMAND.example_tools == ()


def test_an_altium_document_is_refused_as_export_refuses_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, board: Path
) -> None:
    """``models`` and ``export --step`` take a KiCad board: a ``.PcbDoc`` is a usage error before any tool
    is looked for (change c0116, design Decision 17)."""
    document = tmp_path / "board.PcbDoc"
    document.write_bytes(b"not a KiCad board")
    monkeypatch.undo()  # the export below needs a real subprocess for nothing: it must stop before one
    hide_kicad(monkeypatch, tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin")
    code, _, err, _ = run(monkeypatch, tmp_path, "models", str(document))
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(
        monkeypatch, tmp_path, "export", str(document), "--out", "fab", "--step", "--kicad-cli", str(fake),
        "--dry-run",
    )  # fmt: skip
    assert code == 2 and err["code"] == "FEN-2001"
    assert calls(fake) == []
