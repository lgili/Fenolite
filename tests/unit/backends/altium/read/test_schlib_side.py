# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pin side streams (capability altium-schematic-reader, "Pin side streams")."""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

from _altium_sch_build import component_text, pin_frac_stream, pin_payload, schlib, short, stream

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import SIDE_STREAMS_DECODED, decode_pin_frac, read_schlib
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
LIBRARY_PAGE = ROOT / "docs" / "formats" / "altium" / "schematic-library.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
DATA = [
    component_text("Q"),
    (1, pin_payload(designator=b"1")),
    "|RECORD=2|DESIGNATOR=2|LOCATION.X=7",
    (1, pin_payload()),
]
L = sch.SchLength.of


def _pins(extra: list[tuple[str, bytes]], issues: list[Issue] | None = None) -> tuple[sch.Pin, ...]:
    return read_schlib(schlib([("Q", DATA, extra)]), issues=issues).components[0].pins


def test_opaque_side_stream() -> None:
    issues: list[Issue] = []
    content = bytes(range(12))
    library = read_schlib(schlib([("Q", DATA, [("PinSymbolLineWidth", content)])]), issues=issues)
    component = library.components[0]
    assert component.side_streams == {"PinSymbolLineWidth": content}
    assert component.pins == _pins([])
    assert [(issue.code, issue.severity) for issue in issues] == [
        ("altium.schlib.side-stream-opaque", "info")
    ]
    assert "Q" in issues[0].message and "PinSymbolLineWidth" in issues[0].message


def test_unknown_stream_of_a_component() -> None:
    issues: list[Issue] = []
    component = read_schlib(schlib([("Q", DATA, [("Whatever", b"abc")])]), issues=issues).components[0]
    assert component.extra_streams == {"Whatever": b"abc"}
    assert component.side_streams == {}
    assert [issue.code for issue in issues] == ["altium.sch.unknown-stream"]


def test_spelling_with_pins() -> None:
    component = read_schlib(schlib([("Q", DATA, [("PinsWideText", b"x"), ("PinsFrac", b"")])])).components[0]
    assert set(component.side_streams) == {"PinsWideText", "PinsFrac"}


def test_pin_frac_changes_the_pin_it_names() -> None:
    issues: list[Issue] = []
    pins = _pins([("PinFrac", pin_frac_stream([(0, 50_000, -25_000, 1), (2, 3, 0, 0)]))], issues)
    assert issues == []
    plain = _pins([])
    assert pins[0].location == (L(-30, 50_000), L(10, -25_000))
    assert pins[0].length == L(20, 1)
    assert pins[0].fraction_source == "PinFrac" and plain[0].fraction_source == ""
    assert pins[1] == plain[1]  # the text pin (index 1) has no entry
    assert pins[2].location == (L(-30, 3), L(10))
    assert pins[0].payload == plain[0].payload


def test_pin_frac_entry_without_a_pin() -> None:
    issues: list[Issue] = []
    pins = _pins([("PinFrac", pin_frac_stream([(0, 1, 1, 1), (9, 1, 1, 1)]))], issues)
    assert pins[0].fraction_source == "PinFrac"
    assert [(issue.code, issue.severity) for issue in issues] == [
        ("altium.schlib.side-stream-orphan", "warning")
    ]


def test_pin_frac_that_does_not_match_stays_opaque() -> None:
    packed = zlib.compress(struct.pack("<4i", 1, 2, 3, 4))
    sixteen = bytes([0xD0]) + short(b"0") + struct.pack("<I", len(packed)) + packed
    cases = [
        stream([(1, b"\x01" + sixteen[1:])]),
        stream([(1, sixteen)]),
        stream([(1, bytes([0xD0]) + short(b"x") + struct.pack("<I", 0))]),
        stream([(1, bytes([0xD0]) + short(b"0") + struct.pack("<I", 5) + b"abc")]),
        stream([(1, bytes([0xD0]) + short(b"0") + struct.pack("<I", 3) + b"abc")]),
        pin_frac_stream([(0, 1, 1, 1), (0, 2, 2, 2)]),
        b"\x05\x00",
        stream([(0, b"|HEADER=PinFrac")]),
    ]
    for content in cases[:-1]:
        assert decode_pin_frac(content) is None
        issues: list[Issue] = []
        pins = _pins([("PinFrac", content)], issues)
        assert pins == _pins([])
        assert [issue.code for issue in issues] == ["altium.schlib.side-stream-opaque"]
    assert decode_pin_frac(cases[-1]) is None
    assert decode_pin_frac(stream(["|HEADER=PinFrac|Weight=0"])) == {}


def test_side_streams_documented() -> None:
    page = LIBRARY_PAGE.read_text(encoding="utf-8")
    registered = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), flags=re.M))
    assert SIDE_STREAMS_DECODED == ("PinFrac",)
    for name in SIDE_STREAMS_DECODED:
        rows = [
            line
            for line in page.splitlines()
            if line.startswith(f"| `{name}` is a sequence of framed records")
        ]
        assert len(rows) == 1, name
        sources = set(re.findall(r"\bS-\d{4}\b", rows[0].split("|")[2]))
        assert sources and sources <= registered and "S-0142" not in sources
    # every decoded stream has an authored fixture that changes a pin
    assert _pins([("PinFrac", pin_frac_stream([(0, 1, 0, 0)]))]) != _pins([])
