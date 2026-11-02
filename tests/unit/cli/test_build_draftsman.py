# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build's Draftsman request and drawing-spec guards, with the native gate off by default."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from _altium import blink_tree

import fenolite.cli.main as cli
from fenolite.backends.altium import draftsman


def run(monkeypatch: pytest.MonkeyPatch, script: Path, folder: Path, *flags: str) -> tuple[int, dict, dict]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(folder.parent / "kicad-config"))
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", out)
        patch.setattr("sys.stderr", err)
        code = cli.main(["build", str(script), "--out", str(folder), "--json", *flags])
    return (
        code,
        json.loads(out.getvalue()) if out.getvalue() else {},
        json.loads(err.getvalue()) if err.getvalue() else {},
    )


@pytest.fixture
def script(tmp_path: Path) -> Path:
    target = blink_tree(tmp_path / "source")
    return target / "design.py"


@pytest.mark.parametrize(
    "flags",
    [
        ("--altium-draftsman", "on"),
        ("--drawing-spec", "absent.toml"),
        ("--target", "altium", "--drawing-spec", "absent.toml"),
    ],
)
def test_option_combinations_refuse_before_writes(
    monkeypatch: pytest.MonkeyPatch, script: Path, tmp_path: Path, flags: tuple[str, ...]
) -> None:
    code, _, error = run(monkeypatch, script, tmp_path / "B", *flags, "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001" and not (tmp_path / "B").exists()


def test_gate_off_request(monkeypatch: pytest.MonkeyPatch, script: Path, tmp_path: Path) -> None:
    code, reply, _ = run(
        monkeypatch, script, tmp_path / "B", "--target", "altium", "--altium-draftsman", "on", "--dry-run"
    )
    assert code == 0 and reply["result"]["draftsman"] is None
    assert not any(row["path"].endswith(".PCBDwf") for row in reply["result"]["plan"])
    assert any(row["code"] == "altium.draftsman-not-written" for row in reply["issues"])


def test_drawing_spec_is_bound_and_native_file_is_planned(
    monkeypatch: pytest.MonkeyPatch, script: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(draftsman, "NATIVE_WRITE", True)
    path = tmp_path / "drawing.toml"
    path.write_text('schema = "fenolite.drawing-spec.v0"\n[fab]\nnotes = ["One", "Two"]\n')
    flags = ("--target", "altium", "--altium-draftsman", "on", "--drawing-spec", str(path))
    code, reply, error = run(monkeypatch, script, tmp_path / "B", *flags, "--dry-run")
    assert code == 0, error
    result = reply["result"]
    assert result["draftsman"]["spec"] == {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    assert any(row["kind"] == "altium_draftsman" for row in result["plan"])
    path.write_text(path.read_text().replace('"Two"', '"Changed"'))
    code, _, error = run(
        monkeypatch, script, tmp_path / "B", *flags, "--confirm", "--plan", result["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002" and not (tmp_path / "B").exists()


def test_invalid_drawing_spec(monkeypatch: pytest.MonkeyPatch, script: Path, tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text('schema = "wrong"')
    code, _, error = run(
        monkeypatch,
        script,
        tmp_path / "B",
        "--target",
        "altium",
        "--altium-draftsman",
        "on",
        "--drawing-spec",
        str(path),
        "--dry-run",
    )
    assert code == 3 and error["code"] == "FEN-3004" and not (tmp_path / "B").exists()


def test_cad_edited_drawing_is_preserved_until_reviewed_replacement(
    monkeypatch: pytest.MonkeyPatch,
    script: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(draftsman, "NATIVE_WRITE", True)
    flags = ("--target", "altium", "--altium-draftsman", "on")
    code, _, error = run(monkeypatch, script, tmp_path / "B", *flags, "--confirm")
    assert code == 0, error
    path = tmp_path / "B/blink.PCBDwf"
    changed = path.read_bytes() + b"authored CAD edit"
    path.write_bytes(changed)
    code, _, error = run(monkeypatch, script, tmp_path / "B", *flags, "--dry-run")
    assert code == 7 and error["code"] == "FEN-7001" and path.read_bytes() == changed
    code, reply, error = run(monkeypatch, script, tmp_path / "B", *flags, "--discard-layout", "--dry-run")
    assert code == 0, error
    code, _, error = run(
        monkeypatch,
        script,
        tmp_path / "B",
        *flags,
        "--discard-layout",
        "--confirm",
        "--plan",
        reply["result"]["plan_id"],
    )
    assert code == 0, error
    assert path.with_suffix(path.suffix + ".bak").read_bytes() == changed
