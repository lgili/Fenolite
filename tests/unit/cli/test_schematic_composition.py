# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Composition artifacts, reviewed writes and exact native replay share one transaction."""

import json
from pathlib import Path

import pytest
from _altium import SAMPLE

from fenolite.schematic.report import REPORT_FILE
from tests.unit.cli.test_altium_schematic_sync import cli, edit


def script(tmp_path: Path, *, declared: bool = False) -> Path:
    path = tmp_path / "design.py"
    extra = '\ndesign.schematic_layout(mode="blocks")\n' if declared else ""
    path.write_text(SAMPLE.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return path


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_reviewed_composition_writes_all_artifacts(tmp_path, monkeypatch, form):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    path = script(tmp_path)
    out = tmp_path / "build"
    args = (
        "build",
        str(path),
        "--out",
        str(out),
        "--target",
        "altium",
        "--altium-layout",
        "blocks",
        "--altium-format",
        form,
    )
    code, env, error = cli(monkeypatch, *args, "--dry-run")
    assert code == 0, (env, error)
    assert not out.exists()
    report = env["result"]["schematic_composition"]
    assert report["origin"] == "generated-baseline"
    assert report["sheets"][0]["placements"]
    planned = {Path(p["path"]).relative_to(out).as_posix() for p in env["result"]["plan"]}
    assert REPORT_FILE in planned and report["sheets"][0]["preview"] in planned
    assert cli(monkeypatch, *args, "--confirm", "--plan", env["result"]["plan_id"])[0] == 0
    assert json.loads((out / REPORT_FILE).read_bytes()) == report


def test_dsl_enables_composition_and_grid_contradiction_is_usage_error(tmp_path, monkeypatch):
    path = script(tmp_path, declared=True)
    args = ("build", str(path), "--out", str(tmp_path / "out"), "--target", "altium", "--dry-run")
    code, env, error = cli(monkeypatch, *args)
    assert code == 0, (env, error)
    assert "schematic_composition" in env["result"]
    code, _, error = cli(monkeypatch, *args, "--altium-layout", "grid")
    assert code == 2 and error["code"] == "FEN-2001"
    code, _, _ = cli(monkeypatch, "build", str(path), "--out", str(tmp_path / "other"), "--dry-run")
    assert code == 3


def test_native_replay_and_changed_intent_conflict(tmp_path, monkeypatch):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    path = script(tmp_path, declared=True)
    out = tmp_path / "out"
    args = ("build", str(path), "--out", str(out), "--target", "altium", "--altium-format", "ascii")
    assert cli(monkeypatch, *args, "--confirm")[0] == 0
    saved = edit(out)
    assert (
        cli(
            monkeypatch,
            "sync",
            str(path),
            "--out",
            str(out),
            "--target",
            "altium",
            "--to-source",
            "--confirm",
        )[0]
        == 0
    )
    code, env, error = cli(monkeypatch, *args, "--confirm")
    assert code == 0, (env, error)
    assert (out / "altium_sample.SchDoc").read_bytes() == saved
    assert env["result"]["schematic_composition"]["replayed_sheets"] == ["altium_sample.SchDoc"]
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    path.write_text(
        path.read_text(encoding="utf-8").replace('mode="blocks"', 'mode="blocks", flow="top-to-bottom"'),
        encoding="utf-8",
    )
    code, env, _ = cli(monkeypatch, *args, "--discard-layout", "--confirm")
    assert code == 5 and "build.altium-layout-conflict" in {i["code"] for i in env["issues"]}
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before
