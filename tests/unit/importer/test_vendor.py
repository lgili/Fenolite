# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The vendored library of an import (capability board-to-code, "Vendored library of an import")."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _importcode import PROJECT, build, edited, imported


def test_build_uses_only_the_vendored_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert imported(tmp_path, PROJECT, "--confirm").exit_code == 0
    out = tmp_path / "out"
    table = (out / "fp-lib-table").read_text(encoding="utf-8")
    assert '(uri "${KIPRJMOD}/lib/Mini.pretty")' in table
    assert '(uri "${KIPRJMOD}/lib/Mini.kicad_sym")' in (out / "sym-lib-table").read_text(encoding="utf-8")
    empty = tmp_path / "config"
    empty.mkdir()
    for name in ("KICAD_CONFIG_HOME", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(empty))
    reply = build(out)
    assert reply.exit_code == 0, reply.error
    assert set(reply.result["libraries"].values()) == {"project"}


def test_edited_instance(tmp_path: Path) -> None:
    reply = imported(tmp_path, edited(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    pretty = tmp_path / "out" / "lib" / "Mini.pretty"
    assert sorted(p.name for p in pretty.iterdir()) == [
        "Mini_LED_THT_3mm.kicad_mod",
        "Mini_R_0603.kicad_mod",
        "Mini_R_0603_2.kicad_mod",
    ]
    text = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert '"R201",\n    "Mini:Mini_R_0603_2",\n    footprint="Mini:Mini_R_0603",' in text
    assert 'footprint_definition="Mini:Mini_R_0603_2"' in text
    codes = [i["code"] for i in (reply.envelope or {})["issues"]]
    assert codes.count("import.footprint-variant") == 1
    assert reply.result["equivalence"]["equivalent"] is True


def _taken_variant_name(tmp: Path) -> Path:
    """The edited board alone (R201 differs from R101) whose second LED is a footprint of its own named
    ``Mini_R_0603_2``, the name R201's variant would take, and whose via at (130, 133) has a drill equal
    to its diameter, a via without a ring (change c0426)."""
    text = edited(tmp).read_text(encoding="utf-8")
    second = text.index(
        '(footprint "Mini:Mini_LED_THT_3mm"', text.index('(footprint "Mini:Mini_LED_THT_3mm"') + 1
    )
    text = (
        text[:second]
        + '(footprint "Mini:Mini_R_0603_2"'
        + text[second + len('(footprint "Mini:Mini_LED_THT_3mm"') :]
    )
    via = text.index("(at 130 133)")
    drill = text.index("(drill 0.4)", via)
    text = text[:drill] + "(drill 0.8)" + text[drill + len("(drill 0.4)") :]
    folder = tmp / "taken"
    folder.mkdir()
    board = folder / "taken.kicad_pcb"
    board.write_text(text, encoding="utf-8")
    return board


def test_a_variant_takes_no_name_of_the_board(tmp_path: Path) -> None:
    """Scenario "A variant name that the board already holds" (change c0426): R201's variant is written as
    ``Mini_R_0603_3``, the board's own ``Mini_R_0603_2`` keeps its file, the via without a ring is written
    as it is, and the emitted code rebuilds the board."""
    reply = imported(tmp_path, _taken_variant_name(tmp_path), "--confirm")
    assert reply.exit_code == 0, reply.error
    issues = (reply.envelope or {})["issues"]
    assert not [i for i in issues if i["code"] == "import.unequal"], issues
    assert reply.result["equivalence"]["equivalent"] is True
    pretty = tmp_path / "out" / "lib" / "Mini.pretty"
    assert sorted(p.name for p in pretty.iterdir()) == [
        "Mini_LED_THT_3mm.kicad_mod",
        "Mini_R_0603.kicad_mod",
        "Mini_R_0603_2.kicad_mod",
        "Mini_R_0603_3.kicad_mod",
    ]
    copper = (tmp_path / "out" / "copper.py").read_text(encoding="utf-8")
    assert re.search(r'diameter=mm\("0\.8"\),\s*drill=mm\("0\.8"\)', copper), copper
