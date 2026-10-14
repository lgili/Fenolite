# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored acceptance coverage and truthful quick reports (c0092); no external tool is run."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def tool():
    return runpy.run_path(str(ROOT / "tools/acceptance_v03.py"))


def test_authored_build_covers_scope(tmp_path: Path) -> None:
    from fenolite.backends.altium import rulemap
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.kicad.pcb import read_board

    model, _, altium = tool()["build"](tmp_path)
    board = model.board
    assert board is not None
    assert len([layer for layer in board.layers if layer.kind == "copper"]) == 6
    assert {via.via_type for via in board.vias} >= {"through", "blind", "buried"}
    assert board.holes and board.keepouts and board.texts and board.zones and board.stackup
    assert sum(len(fp.bodies) for fp in board.footprints) == 3
    assert {module.path for module in model.circuit.modules} == {"io", "io/outputs"}
    assert model.circuit.buses
    assert model.rules is not None
    assert {row.neutral for row in rulemap.TABLE if row.exact} <= {rule.kind for rule in model.rules.rules}
    assert "acceptance_v03.PcbDoc" in altium.files and "acceptance_v03.OutJob" in altium.files
    assert "acceptance_v03_io.outputs.SchDoc" in altium.files
    # These are own read-backs, not a claim that Altium opened the project.
    read_pcbdoc(altium.files["acceptance_v03.PcbDoc"], file="acceptance_v03.PcbDoc")
    read_board((tmp_path / "kicad/acceptance_v03.kicad_pcb").read_text())


def test_build_only_never_claims_acceptance_or_a_tool_run(tmp_path: Path) -> None:
    report = tool()["run"](tmp_path, build_only=True)
    assert report["passed"] is False and report["build_only"] is True
    assert report["altium_version"] is report["kit_run_id"] is report["kicad_version"] is None
    assert set(report["steps"]) == {"build-kicad", "build-altium"}
    assert json.loads((tmp_path / "acceptance.json").read_text()) == report


def test_full_run_requires_an_explicit_oracle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --kicad-cli"):
        tool()["run"](tmp_path)
