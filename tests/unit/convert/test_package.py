# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The conversion package (capability design-conversion, "Conversion package"; change c0159)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _convert import TWO_LAYER

from fenolite.convert import DIRECTIONS, convert_project

ROOT = Path(__file__).resolve().parents[3]
ALTIUM_BLINK = ROOT / "tests" / "data" / "altium" / "blink"


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def test_hermetic_conversion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Nothing is written": with ``subprocess.run`` patched to raise, the two-layer board is
    converted to Altium in memory, and its folder is unchanged."""
    folder = tmp_path / "source"
    folder.mkdir()
    shutil.copy(TWO_LAYER, folder / TWO_LAYER.name)
    before = _snapshot(folder)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a conversion runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    conversion = convert_project(folder / TWO_LAYER.name, to="altium")
    assert sorted(conversion.files) == [
        f"two_layer.{s}" for s in ("PcbDoc", "PcbLib", "PrjPcb", "SchDoc", "SchLib")
    ]
    assert conversion.read_back == "two_layer.PcbDoc" and conversion.target == "altium"
    assert _snapshot(folder) == before


def test_directions_registered() -> None:
    assert sorted(DIRECTIONS) == [("altium", "kicad"), ("kicad", "altium"), ("kicad", "kicad")]
    assert DIRECTIONS[("kicad", "altium")].experimental and not DIRECTIONS[("kicad", "kicad")].experimental
    assert DIRECTIONS[("kicad", "kicad")].targets == (9, 10)


def test_altium_direction_registered() -> None:
    result = convert_project(ROOT / "tests/data/altium/blink/blink.PrjPcb", to="kicad", allow_lossy=True)
    assert result.source.backend == "altium" and result.target == "kicad"
    assert result.direction.experimental


def test_options_checked() -> None:
    with pytest.raises(ValueError, match="bodies"):
        convert_project(TWO_LAYER, to="altium", bodies="solid")


def test_name_names_the_files() -> None:
    conversion = convert_project(TWO_LAYER, to="altium", name="board")
    assert "board.PcbDoc" in conversion.files and conversion.read_back == "board.PcbDoc"
