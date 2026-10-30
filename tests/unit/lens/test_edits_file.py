# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``edits.toml`` (capability edit-merge, "Edits file schema" to "Edits file round trip"; change c0250)."""

from __future__ import annotations

from types import MappingProxyType

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.lens.edits import EDITS_SCHEMA, PartEdits, Value, read_edits, write_edits
from fenolite.lens.placements import SourcePlacement, read_placements, write_placements

MM = 1_000_000
ORIGIN = Point(100 * MM, 100 * MM)


def test_value_and_position_edits() -> None:
    text = (
        f'schema = "{EDITS_SCHEMA}"\n\n[part."buck1/L"]\nx = 12.7\ny = 30\nvalue = "6u8"\n\n'
        '[part."buck1/L".over]\nunplaced = true\nvalue = "4u7"\n'
    )
    found = read_edits(text, origin=ORIGIN)
    assert found.issues == ()
    edits = found.parts["buck1/L"]
    assert edits.values["position"] == (112_700_000, 130 * MM)
    assert edits.values["value"] == "6u8" and edits.over is not None
    assert edits.over == {"position": None, "value": "4u7"}
    assert "rotation" not in edits.values


def test_a_placements_table_is_an_edits_table() -> None:
    entries = {
        "R1": SourcePlacement(Point(112_700_000, 130 * MM), 90_000_000, "bottom", True),
        "power/D1": SourcePlacement(Point(101 * MM, 102 * MM), 0, "top", False),
    }
    original = write_placements(entries, origin=ORIGIN)
    tables = original.replace('schema = "fenolite.placements.v0"', f'schema = "{EDITS_SCHEMA}"')
    blocks = tables.split("\n\n")
    text = "\n\n".join(
        [blocks[0], *(b + f"\n\n[{b.splitlines()[0][1:-1]}.over]\nunplaced = true\n" for b in blocks[1:])]
    )
    found = read_edits(text, origin=ORIGIN)
    assert found.issues == ()
    placed = read_placements(original, origin=ORIGIN).entries
    for path, entry in placed.items():
        edits = found.parts[path]
        assert edits.values["position"] == (entry.at.x, entry.at.y)
        assert edits.values["rotation"] == (entry.rotation, entry.side)
        assert edits.locked == entry.locked


def test_edit_without_its_script_value() -> None:
    found = read_edits(
        f'schema = "{EDITS_SCHEMA}"\n[part."R1"]\nvalue = "4k7"\n', origin=ORIGIN, file="edits.toml"
    )
    (problem,) = found.issues
    assert problem.code == "layout.source-invalid" and problem.severity == "error"
    assert "R1" in problem.where and "over.value" in problem.where
    assert "R1" not in found.parts


@pytest.mark.parametrize(
    "body",
    [
        'value = "4k7"\n[part."R1".over]\nvalue = "330"\nfootprint = "X"\n',  # over key without its edit
        'x = 1\ny = 2\n[part."R1".over]\nunplaced = true\nx = 1\ny = 2\n',  # unplaced with a position
        'x = 1\n[part."R1".over]\nunplaced = true\n',  # x without y
        'rotation = 90\nside = "top"\nlocked = true\n[part."R1".over]\nunplaced = true\n',  # locked without x
        'colour = "red"\n',  # unknown key
    ],
)
def test_invalid_tables_are_left_out(body: str) -> None:
    found = read_edits(f'schema = "{EDITS_SCHEMA}"\n[part."R1"]\n{body}', origin=ORIGIN)
    assert found.parts == {} and found.issues
    assert all(i.code == "layout.source-invalid" for i in found.issues)


def test_value_off_the_nanometre() -> None:
    text = (
        f'schema = "{EDITS_SCHEMA}"\n[part."R1"]\nx = 1.0000005\ny = 0\n[part."R1".over]\nunplaced = true\n'
    )
    found = read_edits(text, origin=ORIGIN)
    assert [i.where for i in found.issues] == ['part."R1".x'] and found.parts == {}


def test_missing_schema() -> None:
    with pytest.raises(FormatError) as raised:
        read_edits('[part."R1"]\nvalue = "1"\n', origin=ORIGIN, file="edits.toml")
    assert "edits.toml" in str(raised.value) or raised.value.file == "edits.toml"


def test_not_toml() -> None:
    with pytest.raises(FormatError):
        read_edits("schema = ", origin=ORIGIN, file="edits.toml")


def test_printed_order() -> None:
    edits = PartEdits(
        MappingProxyType({"value": "4k7", "position": (101 * MM, 102 * MM), "property:PN": "B"}),
        MappingProxyType({"value": "330", "position": (100 * MM, 100 * MM), "property:PN": "A"}),
    )
    text = write_edits({"R1": edits}, origin=ORIGIN)
    assert text == (
        "# Written by fenolite sync --to-source.\n"
        f'schema = "{EDITS_SCHEMA}"\n\n'
        '[part."R1"]\nx = 1\ny = 2\nvalue = "4k7"\nproperties = { "PN" = "B" }\n\n'
        '[part."R1".over]\nx = 0\ny = 0\nvalue = "330"\nproperties = { "PN" = "A" }\n'
    )
    assert read_edits(text, origin=ORIGIN).parts == {"R1": edits}


def test_texts_are_escaped() -> None:
    edits = PartEdits(MappingProxyType({"value": 'a "b" \\ \n\t\x01'}), MappingProxyType({"value": ""}))
    text = write_edits({"R1": edits}, origin=ORIGIN)
    assert read_edits(text, origin=ORIGIN).parts["R1"] == edits


def test_write_refuses_an_edit_without_its_script_value() -> None:
    with pytest.raises(ValueError, match="over"):
        write_edits({"R1": PartEdits(MappingProxyType({"value": "1"}), MappingProxyType({}))}, origin=ORIGIN)
    with pytest.raises(ValueError, match="over"):
        write_edits({"R1": PartEdits(MappingProxyType({"value": "1"}), None)}, origin=ORIGIN)


# --- round trip -----------------------------------------------------------------------------------

_texts = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=8)
_position = st.tuples(st.integers(-(10**12), 10**12), st.integers(-(10**12), 10**12))
_rotation = st.tuples(st.integers(0, 359_999_999), st.sampled_from(["top", "bottom"]))


@st.composite
def _part_edits(draw: st.DrawFn) -> PartEdits:
    values: dict[str, Value] = {}
    over: dict[str, Value | None] = {}
    unplaced = draw(st.booleans())
    for prop, strategy in (("position", _position), ("rotation", _rotation)):
        if draw(st.booleans()):
            values[prop] = draw(strategy)
            over[prop] = None if unplaced else draw(strategy)
    for prop in ("value", "footprint", "reference"):
        if draw(st.booleans()):
            values[prop] = draw(_texts)
            over[prop] = draw(_texts)
    for name in draw(st.lists(_texts.filter(bool), max_size=2, unique=True)):
        values[f"property:{name}"] = draw(_texts)
        over[f"property:{name}"] = draw(_texts)
    locked = "position" in values and draw(st.booleans())
    return PartEdits(MappingProxyType(values), MappingProxyType(over), locked)


_paths = st.lists(
    st.from_regex(r"[A-Za-z0-9_]{1,4}(/[A-Za-z0-9_.+-]{1,4})?", fullmatch=True), max_size=3, unique=True
)


@settings(max_examples=150, deadline=None)
@given(_paths.flatmap(lambda paths: st.fixed_dictionaries({p: _part_edits() for p in paths})))
def test_round_trip(parts: dict[str, PartEdits]) -> None:
    text = write_edits(parts, origin=ORIGIN)
    found = read_edits(text, origin=ORIGIN)
    assert found.issues == ()
    assert dict(found.parts) == parts
    assert write_edits(found.parts, origin=ORIGIN) == text
