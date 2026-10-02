# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ASCII record form (capability altium-schematic-writer, "ASCII schematic form" and "Text the ASCII
form cannot carry"; change c0032)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.ascii import (
    HEADER_TEXT,
    LINE_END,
    coord_fields,
    encode_records,
    format_record,
    header_record,
    text_problem,
    to_units,
)


def test_header_record() -> None:
    assert HEADER_TEXT == "Protel for Windows - Schematic Capture Ascii File Version 5.0"
    assert format_record(header_record(122)) == (
        "|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=122"
    )
    with pytest.raises(ValueError):
        header_record(-1)


def test_format_record() -> None:
    assert format_record([("RECORD", "31"), ("BORDERON", "T")]) == "|RECORD=31|BORDERON=T"
    assert format_record([("TEXT", "=x=y")]) == "|TEXT==x=y"  # a value may hold '='


@pytest.mark.parametrize(
    "fields",
    [
        [],
        [("", "1")],
        [("A|B", "1")],
        [("A=B", "1")],
        [("TEXT", "a|b")],
        [("TEXT", "10µF")],
        [("TEXT", "a\r\nb")],
    ],
)
def test_format_record_refuses(fields: list[tuple[str, str]]) -> None:
    with pytest.raises(ValueError):
        format_record(fields)


def test_encode_records() -> None:
    data = encode_records([[("RECORD", "31")], [("RECORD", "1"), ("UNIQUEID", "ABCDEFGH")]])
    assert data == (
        b"|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=2\r\n"
        b"|RECORD=31\r\n"
        b"|RECORD=1|UNIQUEID=ABCDEFGH\r\n"
    )
    assert LINE_END == b"\r\n" and data.endswith(LINE_END)
    lines = data.split(b"\r\n")
    assert lines[-1] == b"" and all(not line.endswith(b"|>") for line in lines)
    assert all(0x20 <= b <= 0x7E for b in data.replace(b"\r\n", b""))


def test_encode_records_counts_the_records() -> None:
    records = [[("RECORD", "27")]] * 5
    first = encode_records(records).split(b"\r\n", 1)[0]
    assert first.endswith(b"|WEIGHT=5")


# --- scenario "Units" -------------------------------------------------------------------------------


def test_units() -> None:
    assert coord_fields("LOCATION", 1000, 500) == (("LOCATION.X", "100"), ("LOCATION.Y", "50"))
    assert coord_fields("CORNER", 0, 11500) == (("CORNER.X", "0"), ("CORNER.Y", "1150"))
    assert to_units(200) == 20
    assert coord_fields("LOCATION", 1050, 500) == (("LOCATION.X", "105"), ("LOCATION.Y", "50"))
    assert coord_fields("LOCATION", 1000, 510) == (("LOCATION.X", "100"), ("LOCATION.Y", "51"))


@pytest.mark.parametrize(("x", "y"), [(1055, 500), (1000, 515), (1000, 5), (-100, 0)])
def test_units_off_the_grid(x: int, y: int) -> None:
    with pytest.raises(ValueError):
        coord_fields("LOCATION", x, y)


# --- requirement "Text the ASCII form cannot carry" -------------------------------------------------


def test_pipe_in_a_net_name() -> None:
    reason = text_problem("A|B")
    assert reason is not None and "|" in reason


def test_non_ascii_value() -> None:
    reason = text_problem("10µF", parameter=True)
    assert reason is not None and "µ" in reason


def test_comment_starting_with_an_equals_sign() -> None:
    assert text_problem("=Value", parameter=True) is not None
    assert text_problem("=Value") is None


@pytest.mark.parametrize("text", ["R1", "+5V", "10k", "LED_DRV", "FenoliteSample.SchLib", "My Parts.PcbLib"])
def test_ordinary_texts(text: str) -> None:
    assert text_problem(text) is None


@pytest.mark.parametrize("text", ["", " R1", "R1 ", "a\tb", "a\nb", "a\x7fb", "Ω"])
def test_other_refused_texts(text: str) -> None:
    assert text_problem(text) is not None
