# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``placements.toml`` (capability layout-lens, "Placements file"; change c0069). The positions are round
numbers chosen for these tests."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.lens.placements import (
    FILE_NAME,
    SCHEMA,
    PlacementsFile,
    SourcePlacement,
    decimal_text,
    read_placements,
    write_placements,
)

MM = 1_000_000
ORIGIN = Point(100 * MM, 100 * MM)
HEAD = f'schema = "{SCHEMA}"\n'


def read(body: str) -> PlacementsFile:
    return read_placements(HEAD + body, origin=ORIGIN, file=FILE_NAME)


def test_position_in_millimetres() -> None:
    found = read('[part."power/R1"]\nx = 12.7\ny = 30\nrotation = 90\n')
    assert found.issues == () and list(found.entries) == ["power/R1"]
    entry = found.entries["power/R1"]
    assert entry == SourcePlacement(Point(112_700_000, 130_000_000), 90_000_000, "top", False)


def test_every_key_and_path_order() -> None:
    found = read(
        '[part."U1"]\nx = -1\ny = 0.000001\nrotation = 359.999999\nside = "bottom"\nlocked = true\n'
        '[part."D1"]\nx = 0\ny = 0\n'
    )
    assert list(found.entries) == ["D1", "U1"] and found.issues == ()
    assert found.entries["U1"] == SourcePlacement(Point(99 * MM, 100 * MM + 1), 359_999_999, "bottom", True)
    assert found.entries["D1"] == SourcePlacement(ORIGIN, 0, "top", False)


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ("x = 1.0000005\ny = 0\n", "x"),
        ("x = 1\n", "y"),
        ('x = "1"\ny = 0\n', "x"),
        ("x = true\ny = 0\n", "x"),
        ("x = 1\ny = 0\nrotation = 360\n", "rotation"),
        ("x = 1\ny = 0\nrotation = -90\n", "rotation"),
        ("x = 1\ny = 0\nrotation = 0.0000001\n", "rotation"),
        ('x = 1\ny = 0\nside = "left"\n', "side"),
        ('x = 1\ny = 0\nlocked = "yes"\n', "locked"),
        ("x = 1\ny = 0\nz = 2\n", "z"),
        ("x = inf\ny = 0\n", "x"),
    ],
)
def test_invalid_entry_is_left_out(body: str, key: str) -> None:
    found = read('[part."R1"]\n' + body + '[part."R2"]\nx = 1\ny = 2\n')
    assert list(found.entries) == ["R2"]
    (issue,) = found.issues
    assert (issue.code, issue.severity) == ("layout.source-invalid", "error")
    assert 'part."R1"' in issue.message and key in issue.message and issue.where == f'part."R1".{key}'


def test_invalid_tables() -> None:
    found = read('[part."R 1"]\nx = 1\ny = 2\n[part]\nR2 = 5\n'.replace("[part]\n", ""))
    assert dict(found.entries) == {} and [i.where for i in found.issues] == ['part."R 1"']
    found = read("part = 3\n")
    assert [i.where for i in found.issues] == ["part"]
    found = read('other = 1\n[part."R1"]\nx = 1\ny = 2\n')
    assert list(found.entries) == ["R1"] and [i.where for i in found.issues] == ["other"]
    found = read("[part]\nR2 = 5\n")
    assert dict(found.entries) == {} and [i.where for i in found.issues] == ['part."R2"']


@pytest.mark.parametrize(
    "text",
    ['[part."R1"]\nx = 1\ny = 2\n', 'schema = "fenolite.placements.v1"\n', "schema = \n", "\x00"],
)
def test_missing_schema_or_not_toml(text: str) -> None:
    with pytest.raises(FormatError, match="placements.toml") as raised:
        read_placements(text, origin=ORIGIN, file="placements.toml")
    assert raised.value.file == "placements.toml"


def test_empty_file_with_schema() -> None:
    assert read("") == PlacementsFile({})


def test_printing() -> None:
    entries = {
        "power/R1": SourcePlacement(Point(112_700_000, 130 * MM), 90_000_000, "top", False),
        "D1": SourcePlacement(Point(100 * MM - 1, 100 * MM), 0, "bottom", True),
    }
    assert write_placements(entries, origin=ORIGIN) == (
        "# Written by fenolite sync --to-source.\n"
        'schema = "fenolite.placements.v0"\n'
        "\n"
        '[part."D1"]\nx = -0.000001\ny = 0\nrotation = 0\nside = "bottom"\nlocked = true\n'
        "\n"
        '[part."power/R1"]\nx = 12.7\ny = 30\nrotation = 90\nside = "top"\nlocked = false\n'
    )
    assert write_placements({}, origin=ORIGIN) == (
        '# Written by fenolite sync --to-source.\nschema = "fenolite.placements.v0"\n'
    )
    with pytest.raises(ValueError, match="component path"):
        write_placements({"R 1": entries["D1"]}, origin=ORIGIN)


def test_decimal_text() -> None:
    assert [decimal_text(v, MM) for v in (30 * MM, 12_700_000, -1, 0, 1_000_001, -2_500_000)] == [
        "30",
        "12.7",
        "-0.000001",
        "0",
        "1.000001",
        "-2.5",
    ]


SEGMENT = st.text("abcXYZ019_.+-", min_size=1, max_size=5)
PATHS = st.lists(SEGMENT, min_size=1, max_size=3).map("/".join)
ENTRIES = st.builds(
    SourcePlacement,
    st.builds(Point, st.integers(-(10**9), 10**9), st.integers(-(10**9), 10**9)),
    st.integers(0, 359_999_999),
    st.sampled_from(["top", "bottom"]),
    st.booleans(),
)


@given(
    st.dictionaries(PATHS, ENTRIES, max_size=6),
    st.builds(Point, st.integers(0, 10**9), st.integers(0, 10**9)),
)
def test_round_trip(entries: dict[str, SourcePlacement], origin: Point) -> None:
    text = write_placements(entries, origin=origin)
    found = read_placements(text, origin=origin)
    assert dict(found.entries) == entries and found.issues == ()
    assert list(found.entries) == sorted(entries)
    assert write_placements(found.entries, origin=origin) == text
