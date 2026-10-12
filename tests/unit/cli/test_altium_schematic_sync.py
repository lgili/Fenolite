# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build, native edits, reviewed capture and byte-exact replay through the CLI."""

from __future__ import annotations

import io
import json
import runpy
from pathlib import Path
from typing import Any

import pytest
from _altium import SAMPLE

from fenolite.backends.altium.project import write_project
from fenolite.cli.main import main
from fenolite.dsl import to_model
from fenolite.lens.altium import generic_pins
from fenolite.lens.altium_schematic import BASELINE_DIR, FILE_NAME


def cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as m:
        m.setattr("sys.stdout", stdout)
        m.setattr("sys.stderr", stderr)
        code = main([*args, "--json"])
    return code, json.loads(stdout.getvalue()), json.loads(stderr.getvalue()) if stderr.getvalue() else {}


def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, tuple[str, ...]]:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    script = tmp_path / "design.py"
    script.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "build"
    args = (str(script), "--out", str(out), "--target", "altium", "--altium-format", "ascii")
    code, env, err = cli(monkeypatch, "build", *args, "--confirm")
    assert code == 0, (env, err)
    return script, out, args


def edit(out: Path) -> bytes:
    path = out / "altium_sample.SchDoc"
    before = path.read_bytes()
    after = before.replace(b"FONTNAME1=Times New Roman", b"FONTNAME1=Courier New")
    assert before != after
    path.write_bytes(after)
    return after


def test_sync_and_regenerate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, args = project(tmp_path, monkeypatch)
    edited = edit(out)
    sync = ("sync", str(script), "--out", str(out), "--target", "altium", "--to-source")
    code, env, err = cli(monkeypatch, *sync, "--dry-run")
    assert code == 0, (env, err)
    assert not (script.parent / FILE_NAME).exists()
    plan = env["result"]["plan_id"]
    assert cli(monkeypatch, *sync, "--confirm", "--plan", plan)[0] == 0
    assert (script.parent / FILE_NAME).is_file()
    assert cli(monkeypatch, *sync, "--check")[0] == 0
    assert cli(monkeypatch, "build", *args, "--confirm")[0] == 0
    assert (out / "altium_sample.SchDoc").read_bytes() == edited
    assert (out / BASELINE_DIR / "altium_sample.SchDoc").read_bytes() != edited
    # The source snapshot also works in an empty output folder.
    second = tmp_path / "second"
    other = tuple(str(second) if arg == str(out) else arg for arg in args)
    assert cli(monkeypatch, "build", *other, "--confirm")[0] == 0
    assert (second / "altium_sample.SchDoc").read_bytes() == edited
    assert cli(monkeypatch, *sync)[1]["result"]["files"] == []


def test_source_conflict_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, args = project(tmp_path, monkeypatch)
    edit(out)
    assert (
        cli(
            monkeypatch,
            "sync",
            str(script),
            "--out",
            str(out),
            "--target",
            "altium",
            "--to-source",
            "--confirm",
        )[0]
        == 0
    )
    script.write_text(
        script.read_text(encoding="utf-8").replace('value="330"', 'value="470"'), encoding="utf-8"
    )
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    for extra in ((), ("--discard-layout",)):
        code, env, _ = cli(monkeypatch, "build", *args, *extra, "--confirm")
        assert code == 5
        assert "build.altium-layout-conflict" in {i["code"] for i in env["issues"]}
        assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("problem", ["changed-net", "missing-sheet", "tampered-baseline", "project-list"])
def test_bad_capture_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str) -> None:
    script, out, _ = project(tmp_path, monkeypatch)
    native = out / "altium_sample.SchDoc"
    if problem == "changed-net":
        native.write_bytes(native.read_bytes().replace(b"LED_DRV", b"BROKEN"))
    elif problem == "missing-sheet":
        native.unlink()
    elif problem == "tampered-baseline":
        baseline = out / BASELINE_DIR / native.name
        baseline.write_bytes(baseline.read_bytes() + b"\r\n")
    else:
        project_file = out / "altium_sample.PrjPcb"
        project_file.write_bytes(
            project_file.read_bytes() + b"\r\n[Document99]\r\nDocumentPath=Extra.SchDoc\r\n"
        )
    code, _, _ = cli(
        monkeypatch, "sync", str(script), "--out", str(out), "--target", "altium", "--to-source", "--confirm"
    )
    assert code == 5
    assert not (script.parent / FILE_NAME).exists()


def test_reviewed_sync_binds_edited_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out, _ = project(tmp_path, monkeypatch)
    edit(out)
    args = ("sync", str(script), "--out", str(out), "--target", "altium", "--to-source")
    _, env, _ = cli(monkeypatch, *args, "--dry-run")
    path = out / "altium_sample.SchDoc"
    path.write_bytes(path.read_bytes() + b"\r\n")
    code, _, err = cli(monkeypatch, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4 and err["code"] == "FEN-4002"
    assert not (script.parent / FILE_NAME).exists()


def test_reviewed_build_binds_absent_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, _, args = project(tmp_path, monkeypatch)
    _, env, _ = cli(monkeypatch, "build", *args, "--dry-run")
    (script.parent / FILE_NAME).write_text("{}", encoding="utf-8")
    code, _, err = cli(monkeypatch, "build", *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4 and err["code"] == "FEN-4002"


def test_saved_binary_form_has_the_correct_write_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script, out, args = project(tmp_path, monkeypatch)
    model = generic_pins(to_model(runpy.run_path(str(script))["design"]))
    name = "altium_sample.SchDoc"
    saved = write_project(model, name="altium_sample", form="binary")[name]
    (out / name).write_bytes(saved)
    assert (
        cli(
            monkeypatch,
            "sync",
            str(script),
            "--out",
            str(out),
            "--target",
            "altium",
            "--to-source",
            "--confirm",
        )[0]
        == 0
    )
    code, env, _ = cli(monkeypatch, "build", *args, "--dry-run")
    assert code == 0
    planned = next(p for p in env["result"]["plan"] if p["path"] == str(out / name))
    assert planned["kind"] == "altium_schdoc_binary"
    assert env["result"]["schematic_layout"]["formats"] == {name: "binary"}
    assert cli(monkeypatch, "build", *args, "--confirm", "--plan", env["result"]["plan_id"])[0] == 0
    assert (out / name).read_bytes() == saved
