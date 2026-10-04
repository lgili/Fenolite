# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check``, ``inspect``, ``doctor``, ``export`` and ``render`` leave the project folder untouched, even
with a ``kicad-cli`` that writes next to its input and rewrites it (capability verification-loop, "Check is
read-only", scenario "Fake kicad-cli that writes", and "New stages stay read-only"; changes c0013, c0020
and c0029; cli-contract, "Export command", scenario "Source is untouched"; change c0024)."""

from __future__ import annotations

from pathlib import Path

import _ipc
import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot


@pytest.fixture
def project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10, built=True)
    board = root / "board.kicad_pcb"
    fake = fake_kicad_cli(
        tmp_path / "bin",
        writes=("x.kicad_prl",),
        rewrite_input=True,
        refill_board=board.read_text(encoding="utf-8") + "\n",
        ipcd356=_ipc.for_board(board),
    )
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


def test_new_stages_are_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, fake = project
    before = tree_snapshot(root)
    code, env, _, _ = run(
        monkeypatch, root, "check", str(root), "--kicad-cli", str(fake),
        "--stages", "copper.clearance,netlist.assignment_compare,roundtrip.rt2",
    )  # fmt: skip
    assert code == 0, env["issues"]
    assert [s["name"] for s in env["result"]["stages"]] == [
        "copper.clearance",
        "netlist.assignment_compare",
        "roundtrip.rt2",
    ]
    words = [tuple(c["args"][:3]) for c in calls(fake)]
    assert ("pcb", "export", "ipcd356") in words and ("pcb", "upgrade", "--force") in words
    assert not (root / ".fenolite" / "native").exists()
    _untouched(root, before)


def test_inspect_is_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, _ = project
    before = tree_snapshot(root)
    code, _, _, _ = run(monkeypatch, root, "inspect", str(root / "board.kicad_pcb"))
    assert code == 0
    _untouched(root, before)


def test_fill_dry_run_leaves_source_untouched(
    monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]
) -> None:
    root, _ = project
    before = tree_snapshot(root)
    refilled = Path(__file__).resolve().parents[2] / "data" / "kicad" / "fill" / "triad_t9_refilled.kicad_pcb"
    code, env, _, _ = run(monkeypatch, root, "fill", str(root), "--from", str(refilled), "--dry-run")
    assert code == 0 and env["result"]["plan"]
    _untouched(root, before)


def test_doctor_is_read_only(monkeypatch: pytest.MonkeyPatch, project: tuple[Path, Path]) -> None:
    root, fake = project
    before = tree_snapshot(root)
    code, _, _, _ = run(monkeypatch, root, "doctor", "--kicad-cli", str(fake))
    assert code == 0
    _untouched(root, before)


@pytest.mark.parametrize(
    "command", [("export", "--all", "--manifest"), ("render", "--svg", "--png")], ids=["export", "render"]
)
@pytest.mark.parametrize("protocol", ["--dry-run", "--confirm"])
def test_export_and_render_leave_the_source_untouched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project: tuple[Path, Path],
    command: tuple[str, ...],
    protocol: str,
) -> None:
    root, fake = project
    before = tree_snapshot(root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    name, *flags = command
    code, env, _, _ = run(
        monkeypatch, elsewhere, name, str(root), "--out", "out", *flags, "--kicad-cli", str(fake), protocol
    )
    assert code == 0, env["issues"]
    assert any(c["args"][:2] in (["pcb", "export"], ["pcb", "render"]) for c in calls(fake))
    assert (elsewhere / "out").is_dir() is (protocol == "--confirm")
    _untouched(root, before)
