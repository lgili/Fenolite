# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An explicit import target reaches both emission and self-check without default drift (c0356)."""

from __future__ import annotations

from pathlib import Path

import _minimum_bench as mb
import pytest

from fenolite.api import run
from fenolite.backends.kicad import _json, pro
from fenolite.backends.kicad.triad import write_triad
from fenolite.cli.main import invoke

STAMP = "2026-11-03T00:00:00Z"


def source(tmp_path: Path, *, future: bool) -> Path:
    files = write_triad(mb.bench_design(target=9, board_wide=False), name="bench", target=9)
    if future:
        project = _json.loads(files["bench.kicad_pro"])
        project["component_class_settings"] = pro.template(10)["component_class_settings"]
        files["bench.kicad_pro"] = _json.dumps(project)
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return tmp_path / "bench.kicad_pro"


def args(path: Path) -> tuple[str, ...]:
    return "import", str(path), "--to", "python", "--out", "out", "--timestamp", STAMP


@pytest.mark.parametrize("prefix", (False, True))
def test_explicit_10_overrides_native_9_for_emission_and_selfcheck(tmp_path: Path, prefix: bool) -> None:
    path = source(tmp_path, future=True)
    argv = ("--kicad-version", "10", *args(path)) if prefix else (*args(path), "--kicad-version", "10")
    code, envelope, error = invoke([*argv, "--dry-run", "--seed", "0"], cwd=tmp_path)
    assert code == 0, (error, envelope)
    assert envelope is not None and envelope["result"]["plan"]
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("flags", ((), ("--kicad-version", "9"), ("--kicad-version", "9", "--allow-lossy")))
def test_native_default_and_explicit_9_keep_project_refusal(tmp_path: Path, flags: tuple[str, ...]) -> None:
    path = source(tmp_path, future=True)
    reply = run(*args(path), *flags, "--dry-run", cwd=tmp_path, seed=0)
    assert reply.exit_code == 5
    assert any("too-new-key" in issue["message"] for issue in reply.envelope["issues"])
    assert not (tmp_path / "out").exists()


def test_explicit_9_keeps_default_payload_bytes(tmp_path: Path) -> None:
    path = source(tmp_path, future=False)
    default = run(*args(path), "--dry-run", cwd=tmp_path, seed=0)
    explicit = run(*args(path), "--kicad-version", "9", "--dry-run", cwd=tmp_path, seed=0)
    assert default.exit_code == explicit.exit_code == 0
    assert default.result["plan"] == explicit.result["plan"]


def test_reviewed_plan_cannot_confirm_with_changed_target(tmp_path: Path) -> None:
    path = source(tmp_path, future=False)
    dry = run(*args(path), "--kicad-version", "10", "--dry-run", cwd=tmp_path, seed=0)
    assert dry.exit_code == 0, dry.error
    reply = run(
        *args(path),
        "--kicad-version",
        "9",
        "--confirm",
        "--plan",
        dry.result["plan_id"],
        cwd=tmp_path,
        seed=0,
    )
    assert reply.exit_code == 4 and reply.error and reply.error["code"] == "FEN-4002"
    assert not (tmp_path / "out").exists()
