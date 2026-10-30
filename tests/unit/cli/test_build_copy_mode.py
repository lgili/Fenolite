# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copy mode in ``fenolite build`` (capability design-dsl, "Copy mode in build"; change c0281): an import
record beside the script makes the copper guard warn instead of refusing. Hermetic: the blink example with
a short added to its built board, as the guard's own tests make it."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from _coppercheck import bridge_pads

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
RECORD = {"schema": "fenolite.import-provenance.v0", "design": "blink", "copy": True}


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _build(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, *flags: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    code = cli_main.main(["--kicad-version", "10", "build", str(script), "--out", str(out), *flags, "--json"])
    return code, json.loads(stdout.getvalue() or "{}")


def _shorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "examples" / "blink_2layer", root / "examples" / "blink_2layer")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    script, out = root / "examples" / "blink_2layer" / "design.py", tmp_path / "B"
    assert _build(monkeypatch, script, out, "--confirm")[0] == 0
    board = out / "blink.kicad_pcb"
    board.write_text(bridge_pads(board.read_text(encoding="utf-8"), "R1", "2", "1"), encoding="utf-8")
    return script, out


def test_imported_folder_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Imported folder builds"."""
    script, out = _shorted(tmp_path, monkeypatch)
    provenance = script.parent / "PROVENANCE.json"
    provenance.write_text(json.dumps(RECORD), encoding="utf-8")
    code, env = _build(monkeypatch, script, out, "--dry-run")
    assert code == 0, env["issues"]
    check = env["result"]["copper_check"]
    assert (check["mode"], check["mode_source"], check["shorts"]) == ("warn", "copy", 1)
    (short,) = [i for i in env["issues"] if i["code"] == "copper.short"]
    assert short["severity"] == "warning"
    assert env["result"]["files"]
    code, env = _build(monkeypatch, script, out, "--copper-check", "refuse", "--dry-run")
    assert code == 5 and env["result"]["copper_check"]["mode_source"] == "option"
    provenance.write_text(json.dumps({**RECORD, "copy": False}), encoding="utf-8")
    code, env = _build(monkeypatch, script, out, "--dry-run")
    assert code == 5
    assert env["result"]["copper_check"]["mode"] == "refuse"
    assert env["result"]["copper_check"]["mode_source"] == "default"


def test_no_record_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, out = _shorted(tmp_path, monkeypatch)
    code, env = _build(monkeypatch, script, out, "--dry-run")
    assert code == 5 and env["result"]["copper_check"]["mode_source"] == "default"
