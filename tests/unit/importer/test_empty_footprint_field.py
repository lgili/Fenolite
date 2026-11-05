# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An empty schematic Footprint field beside a board footprint (c0414), on authored CC0 projects."""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

import _drawn_fonts
import _schema
import pytest
from _fidelity import ALL_LEVELS, snapshot

from fenolite import api
from fenolite.backends.kicad import drawn, sch
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import read_drawn
from fenolite.model._drawn_text import write_drawn
from fenolite.model.drawn import DrawnSymbol

FLAT = Path(__file__).parents[2] / "data/drawn/flat/schematic.toml"
FOOTPRINT = "Footprints:Mini_R_0603"


def _flagged() -> str:
    value = read_drawn(FLAT.read_text(encoding="utf-8"))
    sheet = value.sheets[0]
    symbols = (dataclasses.replace(sheet.symbols[0], empty_footprint=True), *sheet.symbols[1:])
    changed = dataclasses.replace(
        value, sheets=(dataclasses.replace(sheet, symbols=symbols), *value.sheets[1:])
    )
    return write_drawn(changed)


def test_flag_is_written_read_and_in_the_schema() -> None:
    text = _flagged()
    assert text.count("empty_footprint = true") == 1
    value = read_drawn(text)
    assert value.sheets[0].symbols[0].empty_footprint
    assert not any(s.empty_footprint for s in value.sheets[0].symbols[1:])
    assert write_drawn(value) == text
    assert "empty_footprint" not in FLAT.read_text(encoding="utf-8")
    assert _schema.validate(tomllib.loads(text), _schema.load("fenolite.drawn-schematic.v0.json")) == []


def test_a_non_boolean_flag_refuses() -> None:
    text = _flagged().replace("empty_footprint = true", 'empty_footprint = "yes"')
    with pytest.raises(FormatError) as caught:
        read_drawn(text)
    assert caught.value.locator == "sheet[0].symbol[0].empty_footprint"
    with pytest.raises(TypeError, match="empty_footprint"):
        DrawnSymbol("R1", 1, Point(0, 0), empty_footprint=1)  # type: ignore[arg-type]


def _emptied(folder: Path) -> Path:
    """The authored one-resistor project with its visible schematic Footprint field emptied."""
    original = _drawn_fonts.original(folder)
    path = original / "font_probe.kicad_sch"
    root = parse(path.read_text(encoding="utf-8"))
    symbol = root.nodes("symbol")[0]
    prop = next(p for p in symbol.nodes("property") if p.atoms()[0].value == "Footprint")
    assert prop.atoms()[1].value == FOOTPRINT
    changed = prop.with_children((prop.children[0], Atom.string(""), *prop.children[2:]))
    changed_symbol = symbol.with_children(tuple(changed if c is prop else c for c in symbol.children))
    path.write_text(
        dumps(root.with_children(tuple(changed_symbol if c is symbol else c for c in root.children))),
        encoding="utf-8",
    )
    return original


@pytest.mark.parametrize(
    ("footprints", "flagged"),
    (({"R1": FOOTPRINT}, True), ({"R1": ""}, False), ({}, False)),
)
def test_extract_flags_only_a_part_that_builds_with_a_footprint(
    tmp_path: Path, footprints: dict[str, str], flagged: bool
) -> None:
    original = _emptied(tmp_path / "original")
    root = sch.read_schematic(original / "font_probe.kicad_sch", file="font_probe.kicad_sch")
    value, _ = drawn.extract(root, {}, components={"R1": "R1"}, footprints=footprints)
    [symbol] = value.sheets[0].symbols
    assert symbol.empty_footprint is flagged


def _import(original: Path, tmp_path: Path) -> Path:
    output = tmp_path / "code"
    reply = api.run(
        "import", str(original / "font_probe.kicad_pro"), "--to", "python", "--out", str(output),
        "--licence", "CC0-1.0", "--copyright", "2026 Fenolite contributors",
        "--source", "https://example.invalid/fenolite-authored-font-probe", "--revision", "authored-c0414",
        "--confirm", cwd=tmp_path, seed=0,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    return output


def test_empty_source_field_stays_empty_and_the_part_keeps_its_footprint(tmp_path: Path) -> None:
    original = _emptied(tmp_path / "original")
    before = snapshot(original)
    output = _import(original, tmp_path)
    assert "empty_footprint = true" in (output / "schematic.toml").read_text(encoding="utf-8")
    assert f'footprint="{FOOTPRINT}"' in (output / "design.py").read_text(encoding="utf-8")
    built = api.run("build", str(output / "design.py"), "--out", "built", "--confirm", cwd=tmp_path, seed=0)
    assert built.exit_code == 0, built.error
    sheet = sch.read_schematic(tmp_path / "built/font_probe.kicad_sch", file="font_probe.kicad_sch")
    [symbol] = [s for s in sheet.symbols if s.ref == "R1"]
    assert symbol.footprint == "" and symbol.properties["Footprint"] == ""
    board = parse((tmp_path / "built/font_probe.kicad_pcb").read_text(encoding="utf-8"))
    [footprint] = board.nodes("footprint")
    assert footprint.atoms()[0].value == FOOTPRINT
    reply = api.run(
        "verify-source", str(output / "design.py"), "--against", str(original), cwd=tmp_path, seed=0
    )
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"]), reply.result["levels"]
    assert snapshot(original) == before
