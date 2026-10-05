# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Binary pin records (capability altium-schematic-reader, "Binary pin records")."""

from __future__ import annotations

import pytest
from _altium_sch_build import WORKED_PIN, component_text, pin_payload, schlib

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch.pins import decode_fields, decode_pin, encode_pin
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.core.errors import Issue

L = sch.SchLength.of
SHARED = (
    "owner_part",
    "owner_display_mode",
    "name",
    "designator",
    "electrical",
    "location",
    "length",
    "direction",
    "hidden",
    "name_shown",
    "designator_shown",
    "hot_end",
    "description",
    "formal_type",
    "inner_edge",
    "outer_edge",
    "inside",
    "outside",
    "swap_group",
    "part_and_sequence",
    "default_value",
    "color",
    "tail",
    "unknown_byte",
    "record_id",
)


def _library_pin(payload: bytes, issues: list[Issue] | None = None) -> sch.SchRecord:
    library = read_schlib(schlib([("A", [component_text("A"), (1, payload)])]), issues=issues)
    return library.components[0].records[1]


def test_worked_pin_of_the_format_page() -> None:
    assert len(WORKED_PIN) == 34
    pin = decode_pin(WORKED_PIN)
    assert pin is not None
    assert (pin.designator, pin.name, pin.electrical, pin.direction) == ("1", "IN", 4, 2)
    assert pin.length.value == 2_000_000
    assert pin.location == (sch.SchLength(-3_000_000), sch.SchLength(1_000_000))
    assert pin.hot_end == (sch.SchLength(-5_000_000), sch.SchLength(1_000_000))
    assert pin.strings_read == 5 and pin.tail == b""
    assert pin.binary and pin.props is None
    assert (pin.owner_part, pin.owner_display_mode, pin.formal_type) == (1, 0, 1)
    assert (pin.name_shown, pin.designator_shown, pin.hidden) == (True, True, False)
    assert encode_pin(pin) == WORKED_PIN


def test_pin_without_its_last_strings() -> None:
    cut = pin_payload(strings=())
    assert cut == WORKED_PIN[:-3]
    issues: list[Issue] = []
    pin = _library_pin(cut, issues)
    assert isinstance(pin, sch.Pin)
    assert pin.strings_read == 2 and pin.swap_group == "" and pin.default_value == ""
    assert issues == []
    assert encode_pin(pin) == cut
    for count in (1, 2):
        partial = pin_payload(strings=(b"G", b"1|&|2")[:count])
        decoded = decode_pin(partial)
        assert decoded is not None and decoded.strings_read == 2 + count and encode_pin(decoded) == partial


def test_bytes_after_the_last_string() -> None:
    payload = WORKED_PIN + b"\x01\x02\x03"
    issues: list[Issue] = []
    pin = _library_pin(payload, issues)
    assert isinstance(pin, sch.Pin)
    assert pin.tail == b"\x01\x02\x03"
    assert encode_pin(pin) == payload and len(payload) == 37
    assert [(issue.code, issue.severity) for issue in issues] == [("altium.sch.pin-trailing-bytes", "info")]


def test_a_cut_optional_string_goes_to_the_tail() -> None:
    payload = pin_payload(strings=()) + b"\x05ab"
    pin = decode_pin(payload)
    assert pin is not None and pin.strings_read == 2 and pin.tail == b"\x05ab"
    assert encode_pin(pin) == payload


def test_text_pin_and_binary_pin_agree() -> None:
    payload = pin_payload(
        designator=b"7",
        name=b"CLK",
        part=2,
        mode=1,
        electrical=0,
        conglomerate=0x0D,
        length=30,
        x=40,
        y=-20,
        description=b"clock in",
        formal=1,
        edges=(3, 1, 0, 0),
        color=255,
        strings=(b"G1", b"", b""),
    )
    text = (
        "|RECORD=2|OWNERPARTID=2|OWNERPARTDISPLAYMODE=1|NAME=CLK|DESIGNATOR=7|ELECTRICAL=0|PINCONGLOMERATE=13"
        "|PINLENGTH=30|LOCATION.X=40|LOCATION.Y=-20|DESCRIPTION=clock in|FORMALTYPE=1|SYMBOL_INNEREDGE=3"
        "|SYMBOL_OUTEREDGE=1|COLOR=255|SWAPIDPIN=G1"
    )
    library = read_schlib(schlib([("A", [component_text("A"), (1, payload), text])]))
    binary, textual = library.components[0].records[1:3]
    assert isinstance(binary, sch.Pin) and isinstance(textual, sch.Pin)
    differences = [name for name in SHARED if getattr(binary, name) != getattr(textual, name)]
    assert differences == []
    assert binary.binary and not textual.binary
    assert binary.props is None and textual.props is not None
    assert binary.strings_read == 5 and textual.strings_read == 0


def test_not_a_pin_and_malformed_pins() -> None:
    issues: list[Issue] = []
    library = read_schlib(
        schlib(
            [
                (
                    "A",
                    [
                        component_text("A"),
                        (1, (3).to_bytes(4, "little") + b"rest"),
                        (1, WORKED_PIN[:20]),
                        (1, WORKED_PIN[:29]),
                        (1, b"\x02\x00"),
                    ],
                )
            ]
        ),
        issues=issues,
    )
    records = library.components[0].records
    assert all(isinstance(record, sch.UnknownRecord) for record in records[1:])
    codes = [issue.code for issue in issues]
    assert codes == ["altium.sch.malformed-record"] * 3 + ["altium.sch.unknown-record"]
    assert sch.check_identity(library) == ()


def test_unknown_byte_and_decode_fields() -> None:
    payload = pin_payload(unknown=7)
    pin = decode_pin(payload)
    assert pin is not None and pin.unknown_byte == 7
    assert decode_fields(b"\x01\x00\x00\x00") == "not-pin"
    assert decode_fields(b"\x02\x00\x00\x00\x00") == "malformed"
    assert decode_pin(b"\x09\x00\x00\x00") is None


def test_encode_pin_needs_a_binary_pin() -> None:
    library = read_schlib(schlib([("A", [component_text("A"), "|RECORD=2|NAME=X"])]))
    text_pin = library.components[0].records[1]
    assert isinstance(text_pin, sch.Pin)
    with pytest.raises(ValueError):
        encode_pin(text_pin)


def test_part_and_sequence_of_a_text_pin() -> None:
    library = read_schlib(schlib([("A", [component_text("A"), b"|RECORD=2|SWAPIDPART=2\xa6&\xa61"])]))
    pin = library.components[0].records[1]
    assert isinstance(pin, sch.Pin) and pin.part_and_sequence == "2\u00a6&\u00a61"


def test_trailing_bytes_in_a_schematic_document() -> None:
    from _altium_sch_build import SHEET, schdoc

    issues: list[Issue] = []
    document = sch.read_schematic(
        schdoc([SHEET, (1, WORKED_PIN + b"\x09"), (1, WORKED_PIN + b"\x08")]), issues=issues
    )
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.pin-trailing-bytes", "FileHeader/record 2")
    ]
    assert sch.check_identity(document) == ()
