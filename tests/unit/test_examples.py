# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The second example board (capability release-gate, "Second example board"; change c0025)."""

from __future__ import annotations

import io
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.cli._script import run_design_script
from fenolite.dsl import to_model

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "board_40parts"
SCRIPT = EXAMPLE / "design.py"
MINIMUMS = {"clearance": 150_000, "track_width": 150_000, "via_diameter": 450_000, "via_drill": 200_000}


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_board_40parts_header_and_listing() -> None:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# SPDX-License-Identifier: CC0-1.0"
    assert lines[1].startswith("# Authored for Fenolite")
    assert (EXAMPLE / "fp-lib-table").is_file() and (EXAMPLE / "sym-lib-table").is_file()
    assert "`board_40parts/`" in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_board_40parts_holds_forty_parts() -> None:
    """Scenario "Forty parts": 40 parts, two of them placed and locked, two modules, the script's minimums."""
    design = run_design_script(SCRIPT).design
    parts = list(design.parts.values())
    assert len(parts) == 40
    kinds = Counter(part.lib_id for part in parts)
    assert kinds == {"Mini:Mini_QFP32_IC": 2, "Mini:Mini_R": 20, "Mini:Mini_LED": 18}
    placed = {part.ref: part.request for part in parts if part.request is not None}
    assert sorted(placed) == ["U1", "U2"] and all(request.locked for request in placed.values())
    assert len(design.modules) >= 2
    assert design.size == (100_000_000, 80_000_000)

    model = to_model(design)
    assert [netclass.name for netclass in model.circuit.netclasses if netclass.name != "Default"] == ["PWR"]
    assert len(model.board.zones) == 1 and "B.Cu" in model.board.zones[0].layers
    board_wide = {rule.kind: rule.min for rule in model.rules.rules if rule.priority == 0}
    assert {kind: board_wide[kind] for kind in MINIMUMS} == MINIMUMS


@pytest.mark.parametrize("target", [9, 10])
def test_board_40parts_builds_without_a_subprocess(
    target: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Builds for both targets without a subprocess"."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a build started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    folder = tmp_path / "bar"
    code = cli_main.main(
        ["build", str(SCRIPT), "--out", str(folder), "--kicad-version", str(target), "--confirm", "--json"]
    )
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert not [issue for issue in envelope["issues"] if issue["severity"] == "error"]
    assert envelope["result"]["components"] == 40
    for suffix in (".kicad_pro", ".kicad_pcb", ".kicad_dru"):
        assert (folder / f"board_40parts{suffix}").is_file()
    board = (folder / "board_40parts.kicad_pcb").read_text(encoding="utf-8")
    assert '"F.Cu"' in board and '"B.Cu"' in board and '"In1.Cu"' not in board
