# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` without a real ``kicad-cli`` (capability verification-loop: "Check command input",
"Check exit codes", "Inputs Fenolite cannot read" and the hermetic stage scenarios; change c0013)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import STEM, authored_project

from fenolite.backends.kicad.pcb import opaque_count, read_board

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
HERMETIC = ("--stages", "model.validate,erc.lite,roundtrip")


@pytest.fixture(autouse=True)
def _no_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def _stages(envelope: dict[str, object]) -> dict[str, dict[str, object]]:
    return {s["name"]: s for s in envelope["result"]["stages"]}  # type: ignore[index]


def _copy(tmp_path: Path, name: str = "board.kicad_pcb", data: bytes | None = None) -> Path:
    folder = tmp_path / "proj"
    folder.mkdir(exist_ok=True)
    target = folder / name
    target.write_bytes(TWO_LAYER.read_bytes() if data is None else data)
    return target


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_project_folder_resolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, "a.kicad_pcb")
    _copy(tmp_path, "b.kicad_pcb")
    (board.parent / "a.kicad_pro").write_text("{}\n", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--stages", "roundtrip")
    assert code == 0 and env["result"]["project"]["board"] == "a.kicad_pcb"
    assert env["input"]["path"] == "a.kicad_pcb"


def test_ambiguous_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, "a.kicad_pcb")
    _copy(tmp_path, "b.kicad_pcb")
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board.parent))
    assert code == 2 and err["code"] == "FEN-2001"
    assert "a.kicad_pcb" in err["hint"] and "b.kicad_pcb" in err["hint"]


def test_unknown_stage_or_missing_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "drc")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "roundtrip,")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "check", "missing.kicad_pcb")
    assert code == 3 and err["code"] == "FEN-3001"


def test_skipped_by_design(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)
    stages = _stages(env)
    assert code == 0
    assert (stages["erc.lite"]["status"], stages["erc.lite"]["reason"]) == ("skipped", "native-input")
    assert stages["model.validate"]["status"] == stages["roundtrip"]["status"] == "ok"
    assert not any(i["code"].startswith("erc.") for i in env["issues"])


def test_built_input_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), *HERMETIC)
    assert code == 0 and env["result"]["project"]["built"] is True
    assert _stages(env)["erc.lite"]["status"] == "ok"


def test_clean_built_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", "model.validate")
    stage = _stages(env)["model.validate"]
    assert code == 0 and stage["status"] == "ok" and stage["evidence"]["level"] == "INFERRED"


def test_unreadable_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    (root / ".fenolite" / "board.json").write_text("{", encoding="utf-8")
    code, env, _, stdout = run(monkeypatch, tmp_path, "check", str(root), *HERMETIC)
    stages = _stages(env)
    assert [i["code"] for i in env["issues"]].count("check.cache-unreadable") == 1
    assert stages["model.validate"]["reason"] == stages["erc.lite"]["reason"] == "cache-unreadable"
    assert stages["roundtrip"]["status"] == "ok" and code == 0
    assert str(tmp_path) not in stdout


def test_native_board_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "roundtrip")
    text = TWO_LAYER.read_text(encoding="utf-8")
    assert code == 0 and _stages(env)["roundtrip"]["summary"]["opaque_count"] == opaque_count(
        read_board(text)
    )


def test_hermetic_stages_are_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)[3]
    second = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)[3]
    assert without_elapsed(first) == without_elapsed(second)
    assert str(DATA) not in first


def test_missing_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER))
    assert code == 6 and err["code"] == "FEN-6001" and "--stages" in err["hint"]


@pytest.mark.parametrize(
    ("version", "header"),
    [("8.0.7", None), ("9.0.9", b"20260206"), ("10.0.6", b"20990101")],
)
def test_unsupported_or_older_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str,
                                    header: bytes | None) -> None:  # fmt: skip
    data = TWO_LAYER.read_bytes()
    if header is not None:
        data = data.replace(b"(version 20241229)", b"(version " + header + b")", 1)
    board = _copy(tmp_path, data=data)
    fake = fake_kicad_cli(tmp_path / "bin", version=version)
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--kicad-cli", str(fake))
    assert code == 6 and err["code"] == "FEN-6002"
    assert [c["args"] for c in calls(fake)] == [["version"]]


def test_oracle_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    fake = fake_kicad_cli(tmp_path / "bin", sleep=30.0)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--timeout", "2"
    )
    failed = [i for i in env["issues"] if i["code"] == "check.oracle-failed"]
    assert code == 5 and len(failed) == 1 and failed[0]["retryable"] is True


def test_rules_without_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    shutil.copyfile(DATA / "kicad" / "rules" / "units.kicad_dru", board.with_suffix(".kicad_dru"))
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--kicad-cli", str(fake))
    assert "kicad.drc.rules-not-loaded" in [i["code"] for i in env["issues"]]
    assert _stages(env)["drc.kicad"]["summary"]["canary"] == "not-applicable"
    assert code == 0  # native input: an info


def test_unreadable_board_without_drc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, data=TWO_LAYER.read_bytes() + b"\n(trailing)\n")
    _no_subprocess(monkeypatch)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "check", str(board), "--stages", "model.validate,roundtrip"
    )
    assert code == 3 and err["code"] == "FEN-3004"
    assert env["ok"] is False
    assert [i["code"] for i in env["issues"]] == ["check.read-refused"]
    assert env["issues"][0]["message"].startswith("FEN-3004: ")
    assert env["issues"][0]["where"].startswith("board.kicad_pcb:") and "@" in env["issues"][0]["where"]


def test_board_older_than_the_read_floor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(
        tmp_path, data=TWO_LAYER.read_bytes().replace(b"(version 20241229)", b"(version 20221018)", 1)
    )
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--stages", "roundtrip")
    assert code == 3 and err["code"] == "FEN-3003"
    assert [i["code"] for i in env["issues"]] == ["check.read-refused"]
    assert env["issues"][0]["message"].startswith("FEN-3003: ")


def test_unreadable_board_with_a_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n(trailing)\n")
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake))
    stages = _stages(env)
    assert code == 5 and stages["roundtrip"]["reason"] == "read-refused"
    assert stages["model.validate"]["reason"] == "read-refused"
    assert stages["drc.kicad"]["summary"]["canary_reason"] == "board-unparsed"
    assert env["issues"][0]["code"] == "check.read-refused"
