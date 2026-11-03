# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 temporary font projects: all-nine controls and planted defects (c0326).

Input geometry is authored by tests/_drawn_fonts.py from registered Fenolite-only mini fixtures.
No native GUI save, external board, accepted difference or regenerated baseline is involved.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _drawn_fonts
import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot

from fenolite.backends.kicad import drawn as writer
from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.model.drawn import DrawnSchematic


def complete(reply) -> None:
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"]), reply.result["levels"]
    assert reply.result["tolerances"] == {
        "length_nm": 0,
        "angle_udeg": 0,
        "length_ppm": 0,
        "pixel_ppm": 1000,
        "render_pitch_um": 50,
        "frame": "absolute",
    }
    copper = next(row for row in reply.result["levels"] if row["level"] == 5)
    assert copper["summary"]["strict"]["tracks"]["matched"] == 1


@pytest.mark.parametrize("target", (9, 10))
def test_styled_authored_hierarchy_proves_all_nine_levels(target: int, tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original", target=target)
    before = snapshot(original)
    assert not (original / ".fenolite").exists()
    complete(roundtrip(original, tmp_path / "roundtrip"))
    assert snapshot(original) == before


def _font(item: Node, height: int, width: int) -> Node:
    effects = item.find("effects")
    assert effects is not None
    old = effects.find("font")
    assert old is not None
    new = node("font", node("size", Atom.from_nm(height), Atom.from_nm(width)))
    changed = effects.with_children(tuple(new if child is old else child for child in effects.children))
    return item.with_children(tuple(changed if child is effects else child for child in item.children))


def test_native_free_text_and_library_pin_fonts_keep_their_existing_slots(tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original")
    path = original / "drawn_full.kicad_sch"
    root = parse(path.read_text(encoding="utf-8"))
    text = root.nodes("text")[0]
    text_new = _font(text, 500_000, 750_000)
    library = root.find("lib_symbols")
    assert library is not None
    definition, body = next(
        (definition, body)
        for definition in library.nodes("symbol")
        if definition.atoms()[0].value == "Mini:Mini_QFP32_IC"
        for body in definition.nodes("symbol")
        if body.nodes("pin")
    )
    pin = body.nodes("pin")[0]
    name, number = pin.find("name"), pin.find("number")
    assert name is not None and number is not None
    changed_name, changed_number = _font(name, 400_000, 600_000), _font(number, 300_000, 500_000)
    pin_new = pin.with_children(
        tuple(
            changed_name if child is name else changed_number if child is number else child
            for child in pin.children
        )
    )
    body_new = body.with_children(tuple(pin_new if child is pin else child for child in body.children))
    definition_new = definition.with_children(
        tuple(body_new if child is body else child for child in definition.children)
    )
    library_new = library.with_children(
        tuple(definition_new if child is definition else child for child in library.children)
    )
    root = root.with_children(
        tuple(
            library_new if child is library else text_new if child is text else child
            for child in root.children
        )
    )
    path.write_text(dumps(root), encoding="utf-8")
    before = snapshot(original)
    complete(roundtrip(original, tmp_path / "roundtrip"))
    assert snapshot(original) == before


def _redundant_junction(original: Path) -> Point:
    path = original / "drawn_full.kicad_sch"
    root = parse(path.read_text(encoding="utf-8"))
    pts = root.nodes("wire")[0].find("pts")
    assert pts is not None
    atoms = pts.nodes("xy")[0].atoms()
    at = Point(atoms[0].to_nm(), atoms[1].to_nm())
    # A visible authored endpoint marker is electrically redundant: the wire already meets its pin.
    junction = node(
        "junction",
        node("at", Atom.from_nm(at.x), Atom.from_nm(at.y)),
        node("diameter", Atom.from_nm(2_540_000)),
        node("uuid", Atom.string("1b45b841-67e3-49f9-8ac0-2b2d124b21aa")),
    )
    path.write_text(dumps(root.with_children((*root.children, junction))), encoding="utf-8")
    return at


def _defect(value: DrawnSchematic, kind: str, junction: Point) -> DrawnSchematic:
    sheets = []
    for sheet in value.sheets:
        if kind == "font":
            refs = tuple(
                dataclasses.replace(
                    ref,
                    fields=tuple(dataclasses.replace(field, font=None) for field in ref.fields),
                    pins=tuple(dataclasses.replace(pin, font=None) for pin in ref.pins),
                )
                for ref in sheet.sheet_refs
            )
            sheet = dataclasses.replace(
                sheet,
                symbols=tuple(
                    dataclasses.replace(
                        symbol, fields=tuple(dataclasses.replace(field, font=None) for field in symbol.fields)
                    )
                    for symbol in sheet.symbols
                ),
                powers=tuple(
                    dataclasses.replace(
                        power, fields=tuple(dataclasses.replace(field, font=None) for field in power.fields)
                    )
                    for power in sheet.powers
                ),
                labels=tuple(dataclasses.replace(label, font=None) for label in sheet.labels),
                sheet_refs=refs,
            )
        elif kind == "text":
            opaques = []
            for opaque in sheet.opaques:
                native = parse(opaque.kicad)
                if native.name == "text":
                    native = native.with_children(
                        (Atom.string("A deliberately different original authored note"), *native.children[1:])
                    )
                    opaque = dataclasses.replace(opaque, kicad=dumps(native, style="compact"))
                opaques.append(opaque)
            sheet = dataclasses.replace(sheet, opaques=tuple(opaques))
        else:
            sheet = dataclasses.replace(
                sheet, junctions=tuple(item for item in sheet.junctions if item.at != junction)
            )
        sheets.append(sheet)
    return dataclasses.replace(value, sheets=tuple(sheets))


@pytest.mark.parametrize("kind", ("font", "text", "junction"))
def test_planted_writer_losses_fail_after_a_passing_all_level_control(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original")
    junction = _redundant_junction(original)
    before = snapshot(original)
    complete(roundtrip(original, tmp_path / "control"))
    lower = writer.lower_drawn

    def broken(value, *args, **kwargs):
        return lower(_defect(value, kind, junction), *args, **kwargs)

    monkeypatch.setattr(writer, "lower_drawn", broken)
    reply = roundtrip(original, tmp_path / "fault")
    assert reply.exit_code == 5 and reply.result["equivalent"] is False, (reply.error, reply.result)
    assert reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    statuses = {row["level"]: row["status"] for row in reply.result["levels"]}
    assert statuses == {**{level: "equal" for level in range(1, 8)}, "S": "differs", 8: "differs"}
    drawn = [item for item in reply.result["differences"] if item["level"] == "S"]
    if kind == "font":
        assert any(".font." in item["field"] for item in drawn)
    elif kind == "text":
        assert drawn and all(item["kind"] == "item-missing" and item["field"] == "opaque" for item in drawn)
    else:
        assert len(drawn) == 1 and (drawn[0]["kind"], drawn[0]["field"]) == ("item-missing", "junction")
        assert drawn[0]["a"] and not drawn[0]["b"]
    assert snapshot(original) == before


@pytest.mark.parametrize("target", (9, 10))
def test_opaque_free_text_color_and_href_survive_strict_full_roundtrip(target: int, tmp_path: Path) -> None:
    from fenolite.lens.drawn import read_drawn

    original = _drawn_fonts.styled_hierarchy(tmp_path / "original", target=target)
    path = original / "drawn_full.kicad_sch"
    root = parse(path.read_text())
    text = root.nodes("text")[0]
    effects = text.find("effects")
    assert effects is not None
    font = effects.find("font")
    assert font is not None
    colored_font = font.with_children((*font.children, parse("(color 194 0 0 0.5)")))
    colored_effects = effects.with_children(
        (
            *[colored_font if child is font else child for child in effects.children],
            parse('(href "https://example.invalid/authored-link")'),
        )
    )
    colored = text.with_children(
        tuple(colored_effects if child is effects else child for child in text.children)
    )
    root = root.with_children(tuple(colored if child is text else child for child in root.children))
    path.write_text(dumps(root))
    before = snapshot(original)
    output = tmp_path / "roundtrip"
    complete(roundtrip(original, output))
    drawing = read_drawn((output / "code/schematic.toml").read_text())
    assert any(parse(opaque.kicad) == colored for sheet in drawing.sheets for opaque in sheet.opaques)
    assert snapshot(original) == before
