# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` on a built project with a drawn schematic (capability verification-loop, "Drawn
schematic stage"; change c0276)."""

from __future__ import annotations

from pathlib import Path

import _drawn
import pytest
from _checkcli import hide_kicad, run

from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES
from fenolite.cli.cmd_check import run_stages

ROOT = Path(__file__).resolve().parents[3]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
NO_TOOL = tuple(name for name in DEFAULT_STAGES if name not in ORACLE_STAGES)


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    hide_kicad(monkeypatch, tmp_path)
    out = tmp_path / "B"
    code, _env, err, _ = run(
        monkeypatch, tmp_path, "build", str(_drawn.EXAMPLE / "design.py"), "--out", str(out), "--confirm"
    )
    assert code == 0, err
    return out


def _stage(env: dict[str, object]) -> dict[str, object]:
    stages = env["result"]["stages"]  # type: ignore[index]
    return next(s for s in stages if s["name"] == "schematic.drawn")  # type: ignore[union-attr]


def test_unchanged_project_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, built: Path) -> None:
    """Scenario "Unchanged project passes"."""
    code, env, _err, _ = run(
        monkeypatch, tmp_path, "check", str(built), "--stages", "model.validate,schematic.drawn"
    )
    assert code == 0 and _stage(env)["status"] == "ok"
    assert not [i for i in env["issues"] if i["code"].startswith("drawn.")]
    checked = run_stages(built / "drawn.kicad_pcb", NO_TOOL, kicad_cli=None, timeout=10, default=True)
    assert "schematic.drawn" in [s.name for s in checked.report.stages]


def test_connectivity_edited_in_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, built: Path) -> None:
    """Scenario "Connectivity edited in KiCad": a wire end moved from R1 pin 1 to R1 pin 2 by token edit."""
    sheet = built / "drawn.kicad_sch"
    text = sheet.read_text(encoding="utf-8")
    assert text.count("(xy 123.19 76.2)") == 1
    sheet.write_text(text.replace("(xy 123.19 76.2)", "(xy 130.81 76.2)"), encoding="utf-8")
    code, env, _err, _ = run(monkeypatch, tmp_path, "check", str(built), "--stages", "schematic.drawn")
    assert code == 5 and _stage(env)["status"] == "errors"
    differs = [i for i in env["issues"] if i["code"] == "drawn.netlist-differs"]
    assert len(differs) == 1 and differs[0]["where"] == "R1-1"


def test_warning_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, built: Path) -> None:
    """Scenario "Warning only": the label SDA renamed by token edit."""
    sheet = built / "drawn.kicad_sch"
    text = sheet.read_text(encoding="utf-8")
    sheet.write_text(text.replace('(label "SDA"', '(label "I2C_SDA"'), encoding="utf-8")
    code, env, _err, _ = run(monkeypatch, tmp_path, "check", str(built), "--stages", "schematic.drawn")
    assert code == 0 and _stage(env)["status"] == "ok"
    assert [i["code"] for i in env["issues"]] == ["drawn.net-name-differs"]


def test_not_listed_elsewhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Not listed elsewhere"."""
    hide_kicad(monkeypatch, tmp_path)
    checked = run_stages(TWO_LAYER, NO_TOOL, kicad_cli=None, timeout=10, default=True)
    assert "schematic.drawn" not in [s.name for s in checked.report.stages]
    code, env, _err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "schematic.drawn")
    assert code == 0 and _stage(env)["status"] == "skipped" and _stage(env)["reason"] == "no-drawing"
