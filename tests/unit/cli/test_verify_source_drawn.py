# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S of ``fenolite verify-source`` on drawn schematics (changes c0276 and c0278; capability
design-equivalence, "Level S compares drawn schematics"). Hermetic: the original is the build of an authored
drawn fixture, made in ``tmp_path``."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import _drawn
import pytest
from _checkcli import hide_kicad, run

LIBS = _drawn.ROOT / "tests" / "data" / "libs"


def fixture(name: str, folder: Path) -> Path:
    """A copy of drawn fixture ``name`` under ``folder``, with library tables naming the mini library by
    its absolute path."""
    shutil.copytree(_drawn.folder(name), folder)
    for table in ("fp-lib-table", "sym-lib-table"):
        text = (folder / table).read_text(encoding="utf-8")
        (folder / table).write_text(text.replace("${KIPRJMOD}/../../libs/", LIBS.as_posix() + "/"), "utf-8")
    return folder / "design.py"


def original(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> tuple[Path, Path]:
    """The script of fixture ``name`` and its build, the original that verify-source proves against."""
    script = fixture(name, tmp_path / "code")
    hide_kicad(monkeypatch, tmp_path)
    out = tmp_path / "original"
    code, _, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, err
    return script, out


def level_s(envelope: dict[str, Any]) -> dict[str, Any]:
    return next(level for level in envelope["result"]["levels"] if level["level"] == "S")


@pytest.mark.parametrize("name", ["flat", "hier", "repeat"])
def test_drawn_original_proves_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    script, out = original(monkeypatch, tmp_path, name)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "verify-source", str(script), "--against", str(out), "--levels", "S"
    )
    assert code == 0, err
    found = level_s(env)
    assert found["status"] == "equal" and found["reason"] == "", found
    assert found["summary"]["symbols"] >= 2 and found["summary"]["pins"] > 0


def test_junction_removed_in_the_original(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script, out = original(monkeypatch, tmp_path, "flat")
    root = out / "drawn_flat.kicad_sch"
    text = root.read_text(encoding="utf-8")
    stripped, count = re.subn(r"\n\t\(junction\n.*?\n\t\)", "", text, flags=re.DOTALL)
    assert count == 1
    root.write_text(stripped, encoding="utf-8")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "verify-source", str(script), "--against", str(out), "--levels", "S"
    )
    assert code == 5 and level_s(env)["status"] == "differs"
    rows = [(d["kind"], d["field"], bool(d["a"]), bool(d["b"])) for d in env["result"]["differences"]]
    assert ("item-missing", "junction", False, True) in rows
    assert any(i["code"] == "equiv.item-missing" for i in env["issues"])


def test_accepted_junction(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A level-S difference is accepted as any other: ``--accept`` with the key of the difference."""
    script, out = original(monkeypatch, tmp_path, "flat")
    root = out / "drawn_flat.kicad_sch"
    stripped = re.sub(r"\n\t\(junction\n.*?\n\t\)", "", root.read_text(encoding="utf-8"), flags=re.DOTALL)
    root.write_text(stripped, encoding="utf-8")
    args = ("verify-source", str(script), "--against", str(out), "--levels", "S")
    _, env, _, _ = run(monkeypatch, tmp_path, *args)
    keys = [f"{d['level']}:{d['kind']}:{d['where']}" for d in env["result"]["differences"]]
    accept = [part for key in keys for part in ("--accept", key)]
    code, env, err, _ = run(monkeypatch, tmp_path, *args, *accept, "--reason", "planted by the test")
    assert code == 0, err
    assert level_s(env)["status"] == "accepted"
