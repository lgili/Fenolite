# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 build scenarios: offline resolution, precedence, conflicts, output bytes and hints."""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import pytest
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/data/library/project"
SCRIPT = """from fenolite.dsl import Design, mm
design = Design("device_demo")
design.board(mm(20), mm(12))
r = design.part("R1", device="Demo266:Demo900")
r.place(mm(10), mm(6))
r.unused_no_connect()
"""


def project(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    (tmp_path / "design.py").write_text(SCRIPT)
    return tmp_path


def test_vendored_offline_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    project(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, (error, env.get("issues"))
    result = env["result"]
    assert result["devices"][0]["origin"] == "library"
    assert result["devices"][0]["item"] == {"kind": "device", "id": "Demo266:Demo900", "version": "1.0.0"}
    assert result["libraries"]["Demo266:TwoPad"] == "library"
    assert result["library_items"]["footprint/Demo266:TwoPad"]["version"] == "1.0.0"


def test_vendored_authored_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    (tmp_path / "devices").mkdir()
    shutil.copy(
        tmp_path / "fenolite_library/devices/Demo266/Demo900/record.toml", tmp_path / "devices/own.toml"
    )
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, error
    assert env["result"]["devices"][0]["origin"] == "authored"
    assert "library.overrides-item" in {i["code"] for i in env["issues"]}


def test_vendored_conflict_plans_no_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    folder = tmp_path / "fenolite_library/devices/Demo266/Demo900"
    shutil.copytree(folder, folder.with_name("Copy"))
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 5, error
    assert "library.item-conflict" in {i["code"] for i in env["issues"]}
    assert not (tmp_path / "out").exists()


def test_vendored_unused_changes_no_output_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "design.py").write_text(SCRIPT.replace("Demo266:Demo900", "Fenolite:R_0603"))
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, (error, env.get("issues"))
    before = {
        p.relative_to(tmp_path / "out"): p.read_bytes() for p in (tmp_path / "out").rglob("*") if p.is_file()
    }
    shutil.rmtree(tmp_path / "out")
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, (error, env.get("issues"))
    after = {
        p.relative_to(tmp_path / "out"): p.read_bytes() for p in (tmp_path / "out").rglob("*") if p.is_file()
    }
    assert before == after


def test_vendored_matches_library_tree_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, (error, env.get("issues"))
    before = {
        p.relative_to(tmp_path / "out"): p.read_bytes() for p in (tmp_path / "out").rglob("*") if p.is_file()
    }
    shutil.rmtree(tmp_path / "out")
    (tmp_path / "devices").mkdir()
    for marker in (tmp_path / "fenolite_library").rglob("record.toml"):
        shutil.copy(marker, tmp_path / "devices" / f"{marker.parent.name}.toml")
    shutil.rmtree(tmp_path / "fenolite_library")
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, (error, env.get("issues"))
    after = {
        p.relative_to(tmp_path / "out"): p.read_bytes() for p in (tmp_path / "out").rglob("*") if p.is_file()
    }
    assert before == after


def test_vendored_unknown_id_hint_from_newest_cached_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = tmp_path / "cache/1.0.0"
    cache.mkdir(parents=True)
    (cache / "index.json").write_text(json.dumps({"items": [{"kind": "device", "id": "Demo266:Other"}]}))
    monkeypatch.setenv("FENOLITE_LIBRARY_DIR", str(cache.parent))
    (tmp_path / "design.py").write_text(SCRIPT.replace("Demo266:Demo900", "Demo266:Other"))
    code, env, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 3 and "fenolite get device Demo266:Other --dry-run" in error["message"]
    assert not (tmp_path / "out").exists()
