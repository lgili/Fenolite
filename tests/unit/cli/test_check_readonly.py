# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check``, ``inspect`` and ``doctor`` leave the project folder untouched, even with a ``kicad-cli`` that
writes next to its input and rewrites it (capability verification-loop, "Check is read-only", scenario
"Fake kicad-cli that writes"; change c0013)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10, built=True)
    fake = fake_kicad_cli(tmp_path / "bin", writes=("x.kicad_prl",), rewrite_input=True)
    return root, fake


def _untouched(root: Path, before: dict[str, tuple[str, str, int]]) -> None:
    assert tree_snapshot(root) == before
    assert not (root / "native").exists()
    assert not (root / "x.kicad_prl").exists()


def test_check_is_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, fake = project
    before = tree_snapshot(root)
    code, env, _, _ = run(monkeypatch, root, "check", str(root), "--kicad-cli", str(fake))
    assert code == 0, env["issues"]
    assert any(c["args"][:2] == ["pcb", "drc"] for c in calls(fake))  # the fake ran on a copy
    drc = next(s for s in env["result"]["stages"] if s["name"] == "drc.kicad")
    assert "x.kicad_prl" in drc["summary"]["tool_writes"]
    _untouched(root, before)


def test_inspect_is_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, _ = project
    before = tree_snapshot(root)
    code, _, _, _ = run(monkeypatch, root, "inspect", str(root / "board.kicad_pcb"))
    assert code == 0
    _untouched(root, before)


def test_doctor_is_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, fake = project
    before = tree_snapshot(root)
    code, _, _, _ = run(monkeypatch, root, "doctor", "--kicad-cli", str(fake))
    assert code == 0
    _untouched(root, before)
