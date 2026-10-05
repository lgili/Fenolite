# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``schematic-placements.toml`` (capability design-dsl, "Schematic placements file"; change c0061)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.schlayout import SymbolPlacement
from fenolite.core.errors import FormatError, Issue
from fenolite.lens import schplacements
from fenolite.lens.schplacements import read_placements


def read(text: str) -> tuple[dict[str, SymbolPlacement], list[Issue]]:
    issues: list[Issue] = []
    return dict(read_placements(text, file="schematic-placements.toml", issues=issues)), issues


def test_position_in_millimetres() -> None:
    found, issues = read('["R1"]\nx = 25.4\ny = 50.8\n')
    assert found == {"R1": SymbolPlacement(25_400_000, 50_800_000, 0, "")} and not issues


def test_rotation_mirror_units_and_module_paths() -> None:
    text = '["bank1/R3"]\nx = 127\ny = 63.5\nrotation = 90\nmirror = "y"\n\n["U2#2"]\nx = 1.27\ny = 2.54\n'
    found, issues = read(text)
    assert not issues
    assert found["bank1/R3"] == SymbolPlacement(127_000_000, 63_500_000, 90, "y")
    assert found["U2#2"] == SymbolPlacement(1_270_000, 2_540_000)


def test_off_the_grid() -> None:
    found, issues = read('["R1"]\nx = 25.5\ny = 50.8\n')
    assert found == {}
    (issue,) = issues
    assert (issue.code, issue.severity, issue.where) == ("build.symbol-placement-invalid", "error", "R1")
    assert "[R1] x" in issue.message and "25.5" in issue.message


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ("x = 25.4\ny = 50.8\nsize = 1\n", "size"),
        ("x = 25.4\n", "y"),
        ("rotation = 90\n", "x"),
        ("x = 25.4\ny = 50.8\nrotation = 45\n", "rotation"),
        ('x = 25.4\ny = 50.8\nmirror = "z"\n', "mirror"),
        ('x = "25.4"\ny = 50.8\n', "x"),
        ("x = 25.4\ny = 50.8\nrotation = true\n", "rotation"),
    ],
)
def test_invalid_tables(body: str, key: str) -> None:
    found, issues = read(f'["R1"]\n{body}')
    assert found == {} and [i.code for i in issues] == ["build.symbol-placement-invalid"]
    assert f"[R1] {key}" in issues[0].message


def test_an_unproved_frame_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schplacements, "PROVED_FRAMES", frozenset({(0, "")}))
    found, issues = read('["R1"]\nx = 25.4\ny = 50.8\nrotation = 90\n')
    assert found == {} and "not checked against KiCad" in issues[0].message
    assert read('["R1"]\nx = 25.4\ny = 50.8\n')[0]


def test_not_toml() -> None:
    with pytest.raises(FormatError, match="schematic-placements.toml") as error:
        read_placements("[R1\nx = 1", file="schematic-placements.toml")
    assert error.value.file == "schematic-placements.toml"


def test_a_value_that_is_not_a_table() -> None:
    found, issues = read("R1 = 3\n")
    assert found == {} and issues[0].where == "R1"


def test_placements_reach_the_sheet() -> None:
    found, _ = read('["R1"]\nx = 25.4\ny = 50.8\nrotation = 90\n\n["R9"]\nx = 25.4\ny = 25.4\n')
    output = build(blink(), symbol_placements=found)
    assert output.schematic is not None and output.files
    r1 = next(s for s in output.schematic.sheet.symbols if s.ref == "R1")
    assert (r1.position.x, r1.position.y, r1.rotation) == (25_400_000, 50_800_000, 90_000_000)
    unknown = [i for i in output.issues if i.code == "build.symbol-placement-unknown"]
    assert [(i.severity, i.where) for i in unknown] == [("warning", "R9")]


def test_no_float_is_created() -> None:
    tree = ast.parse(Path(schplacements.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert "parse_float=Decimal" in Path(schplacements.__file__).read_text(encoding="utf-8")
