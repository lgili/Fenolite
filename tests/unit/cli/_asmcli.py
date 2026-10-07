# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the tests of ``bom`` and ``pnp`` share (change c0064): a confirmed build of the blink, and the
authored templates. Every property and value added to the blink here is made up."""

from __future__ import annotations

from pathlib import Path

import pytest
from _asmfeatures import FEATURES, LAST_LINE
from _buildhelp import blink_variant
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
TEMPLATES = ROOT / "tests" / "data" / "assembly"
COLUMNS = str(TEMPLATES / "columns.toml")
ROTATED = str(TEMPLATES / "rotated.toml")
INVALID = str(TEMPLATES / "invalid.toml")
R1 = 'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")'


def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No KiCad configuration of this machine is read by a build."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *edits: tuple[str, str], name: str = "p") -> Path:
    """A confirmed build of the blink, or of a variant with ``edits`` applied to its script."""
    script = blink_variant(tmp_path / f"{name}-src")
    text = script.read_text(encoding="utf-8")
    for old, new in edits:
        assert old in text, old
        text = text.replace(old, new)
    script.write_text(text, encoding="utf-8", newline="\n")
    out = tmp_path / name
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, (env.get("issues"), err)
    return out


__all__ = ["COLUMNS", "FEATURES", "FIXTURE", "INVALID", "LAST_LINE", "R1", "ROTATED", "built", "isolate"]
