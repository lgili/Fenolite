# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing specification file (capability manufacturing-exports, "Drawing specification files";
change c0117)."""

from __future__ import annotations

import pytest

from fenolite.core.errors import FormatError
from fenolite.exports.drawing_spec import (
    DEFAULT,
    SCHEMA,
    TABLES,
    AssemblySpec,
    DrawingSpec,
    FabSpec,
    PageSpec,
    SpecError,
    read_spec,
)

HEAD = f'schema = "{SCHEMA}"\n'
GOOD = {
    "page": {
        "paper": '"A3"',
        "portrait": "true",
        "drawing_sheet": '"frames/a3.kicad_wks"',
        "text_size": '"2mm"',
        "gap": '"4mm"',
        "notes_width": '"90mm"',
    },
    "fab": {
        "title": '"Fabrication"',
        "tables": '["notes", "drill"]',
        "dimensions": "false",
        "dimension_offset": '"6mm"',
        "dimension_precision": "3",
        "notes": '["One.", "Two\\nlines."]',
        "at": '{ drill = ["20mm", "30mm"] }',
    },
    "assembly": {
        "title_top": '"Top"',
        "title_bottom": '"Bottom"',
        "sides": '["bottom"]',
        "dnp": '"hide"',
        "values": "true",
        "pads": "true",
        "designators": "false",
        "designator_size": '"0.8mm"',
        "notes": '["Glue."]',
        "at": '{ notes = ["20mm", "30mm"] }',
    },
}
BAD = {
    "page": {
        "paper": '"B9"',
        "portrait": '"yes"',
        "drawing_sheet": '"frame.txt"',
        "text_size": "1.5",
        "gap": "5",
        "notes_width": '"120"',
    },
    "fab": {
        "title": "3",
        "tables": '["drill", "bom"]',
        "dimensions": '"no"',
        "dimension_offset": '"0mm"',
        "dimension_precision": "5",
        "notes": '"one"',
        "at": '{ title = ["1mm", "1mm"] }',
    },
    "assembly": {
        "title_top": "1",
        "title_bottom": "false",
        "sides": '["left"]',
        "dnp": '"maybe"',
        "values": "1",
        "pads": '"x"',
        "designators": "0",
        "designator_size": '"1"',
        "notes": "[1]",
        "at": '{ drill = ["1mm", "1mm"] }',
    },
}


def _file(tables: dict[str, dict[str, str]]) -> str:
    lines = [HEAD]
    for table, keys in tables.items():
        lines.append(f"[{table}]")
        lines += [f"{key} = {value}" for key, value in keys.items()]
    return "\n".join(lines) + "\n"


def test_defaults() -> None:
    spec = read_spec(HEAD)
    assert spec == DEFAULT == DrawingSpec(PageSpec(), FabSpec(), AssemblySpec())
    assert spec.fab.notes == () and spec.assembly.notes == ()
    assert spec.page.text_size == 1_500_000 and spec.page.gap == 5_000_000
    assert spec.page.notes_width == 120_000_000 and spec.page.paper == "auto" and not spec.page.portrait
    assert spec.fab.tables == ("board", "stackup", "drill", "impedance", "notes")
    assert (spec.fab.dimensions, spec.fab.dimension_offset, spec.fab.dimension_precision) == (
        True,
        8_000_000,
        2,
    )
    assert spec.fab.title == "Fabrication drawing"
    assert spec.assembly.title_top == "Assembly drawing, top side"
    assert spec.assembly.title_bottom == "Assembly drawing, bottom side"
    assert spec.assembly.sides == ("top", "bottom") and spec.assembly.dnp == "crossout"
    assert (spec.assembly.values, spec.assembly.pads, spec.assembly.designators) == (False, False, True)
    assert spec.assembly.designator_size == 1_000_000
    hash(spec)  # the specification is a value


def test_every_key_is_read() -> None:
    assert {name: set(keys) for name, keys in GOOD.items()} == {n: set(k) for n, k in TABLES.items()}
    spec = read_spec(_file(GOOD))
    assert spec.page == PageSpec("A3", True, "frames/a3.kicad_wks", 2_000_000, 4_000_000, 90_000_000)
    assert spec.fab == FabSpec(
        "Fabrication",
        ("drill", "notes"),
        False,
        6_000_000,
        3,
        ("One.", "Two\nlines."),
        (("drill", (20_000_000, 30_000_000)),),
    )
    assert spec.assembly.sides == ("bottom",) and spec.assembly.dnp == "hide"
    assert spec.assembly.designator_size == 800_000 and spec.assembly.notes == ("Glue.",)
    assert spec.assembly.at == (("notes", (20_000_000, 30_000_000)),)


def test_every_problem_in_file_order() -> None:
    text = HEAD + '[page]\npaper = "B9"\n[fab]\ncolour = "red"\n[assembly]\ndnp = "maybe"\n'
    with pytest.raises(SpecError) as caught:
        read_spec(text, file="d.toml")
    assert [key for key, _ in caught.value.problems] == ["page.paper", "fab.colour", "assembly.dnp"]
    assert caught.value.file == "d.toml" and "page.paper" in str(caught.value)
    assert isinstance(caught.value, FormatError)


@pytest.mark.parametrize(("table", "key"), [(t, k) for t, keys in BAD.items() for k in keys])
def test_closed_keys_one_by_one(table: str, key: str) -> None:
    assert set(BAD[table]) == set(TABLES[table])
    with pytest.raises(SpecError) as caught:
        read_spec(_file({table: {key: BAD[table][key]}}))
    assert [found for found, _ in caught.value.problems] == [f"{table}.{key}"]
    read_spec(_file({table: {key: GOOD[table][key]}} if key != "portrait" else {table: GOOD[table]}))


def test_lengths_carry_units_and_no_float_is_made() -> None:
    with pytest.raises(SpecError) as caught:
        read_spec(HEAD + "[page]\ngap = 5\n")
    assert [key for key, _ in caught.value.problems] == ["page.gap"]
    with pytest.raises(SpecError) as caught:
        read_spec(HEAD + "[page]\ngap = 5.5\n")
    assert [key for key, _ in caught.value.problems] == ["page.gap"]
    assert read_spec(HEAD + '[page]\ngap = "0.1in"\n').page.gap == 2_540_000


def test_schema_tables_and_toml() -> None:
    for text in ("", 'schema = "fenolite.drawing-spec.v1"\n'):
        with pytest.raises(SpecError) as caught:
            read_spec(text)
        assert caught.value.problems[0][0] == "schema"
    with pytest.raises(SpecError) as caught:
        read_spec(HEAD + "[gerbers]\nx = 1\n")
    assert caught.value.problems[0][0] == "gerbers"
    with pytest.raises(FormatError):
        read_spec("schema = ")


def test_portrait_needs_a_named_paper() -> None:
    with pytest.raises(SpecError) as caught:
        read_spec(HEAD + "[page]\nportrait = true\n")
    assert [key for key, _ in caught.value.problems] == ["page.portrait"]
    assert read_spec(HEAD + '[page]\nportrait = true\npaper = "A4"\n').page.portrait


def test_a_note_with_a_control_character() -> None:
    with pytest.raises(SpecError) as caught:
        read_spec(HEAD + '[fab]\nnotes = ["ok", "tab\\there"]\n')
    assert caught.value.problems == (
        ("fab.notes", "note 2 holds a control character other than a line feed"),
    )
    assert read_spec(HEAD + '[fab]\nnotes = ["a\\nb ${TITLE}"]\n').fab.notes == ("a\nb ${TITLE}",)


def test_no_note_and_no_tolerance_is_shipped() -> None:
    assert DEFAULT.fab.notes == () and DEFAULT.assembly.notes == ()
    assert not any(
        "tolerance" in key or "class" in key or "finish" in key for t in TABLES.values() for key in t
    )
