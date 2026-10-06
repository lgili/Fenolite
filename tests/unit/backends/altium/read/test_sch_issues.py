# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Located errors and the closed set of issue codes (capability altium-schematic-reader, "Located errors and
issue codes")."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from _altium_sch_build import (
    BINARY_HEADER,
    SHEET,
    WORKED_PIN,
    component_text,
    frame_bytes,
    pin_frac_stream,
    schdoc,
    schlib,
    stream,
)

from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.core.errors import FormatError, Issue


def _doc(data: bytes) -> Callable[[list[Issue]], object]:
    return lambda issues: sch.read_schematic(data, issues=issues)


def _lib(data: bytes) -> Callable[[list[Issue]], object]:
    return lambda issues: read_schlib(data, issues=issues)


NEGATIVE: dict[str, Callable[[list[Issue]], object]] = {
    "altium.sch.malformed-record": _doc(
        schdoc(
            [],
            file_header=stream([f"|HEADER={BINARY_HEADER}|WEIGHT=2", SHEET]) + frame_bytes(0, b"|RECORD=27"),
        )
    ),
    "altium.sch.bad-value": _doc(schdoc([SHEET, "|RECORD=27|LOCATIONCOUNT=two"])),
    "altium.sch.unknown-record": _doc(schdoc([SHEET, "|RECORD=209"])),
    "altium.sch.unknown-stream": _doc(schdoc([SHEET], extra=[("Extra", b"12345")])),
    "altium.sch.empty-stream": _doc(
        write_compound(
            [("FileHeader", stream([f"|HEADER={BINARY_HEADER}|WEIGHT=1", SHEET])), ("Additional", b"")]
        )
    ),
    "altium.sch.weight-mismatch": _doc(schdoc([SHEET], weight=9)),
    "altium.sch.orphan-record": _doc(schdoc([SHEET, "|RECORD=25|OWNERINDEX=5"])),
    "altium.sch.no-sheet": _doc(schdoc(["|RECORD=25"])),
    "altium.sch.part-out-of-range": _doc(
        schdoc([SHEET, "|RECORD=1|PARTCOUNT=2", "|RECORD=2|OWNERINDEX=1|OWNERPARTID=4"])
    ),
    "altium.sch.text-undecodable": _doc(schdoc([SHEET, b"|RECORD=4|TEXT=\x81"])),
    "altium.sch.pin-trailing-bytes": _lib(schlib([("Q", [component_text("Q"), (1, WORKED_PIN + b"\x00")])])),
    "altium.sch.storage-opaque": _doc(schdoc([SHEET], storage=stream(["|HEADER=Icon storage", (1, b"abc")]))),
    "altium.schlib.unlisted-component": _lib(
        schlib(
            [("A", [component_text("A")]), ("B", [component_text("B")])],
            header_fields="|WEIGHT=3|COMPCOUNT=2|LIBREF0=A",
        )
    ),
    "altium.schlib.missing-component": _lib(
        schlib([("A", [component_text("A")])], header_fields="|WEIGHT=2|COMPCOUNT=1|LIBREF0=A|LIBREF1=B")
    ),
    "altium.schlib.no-component": _lib(schlib([("A", ["|RECORD=14"])])),
    "altium.schlib.side-stream-opaque": _lib(schlib([("A", [component_text("A")], [("PinWideText", b"x")])])),
    "altium.schlib.side-stream-orphan": _lib(
        schlib([("A", [component_text("A")], [("PinFrac", pin_frac_stream([(3, 1, 1, 1)]))])])
    ),
}


@pytest.mark.parametrize("code", sorted(NEGATIVE))
def test_each_negative_fixture(code: str) -> None:
    issues: list[Issue] = []
    NEGATIVE[code](issues)
    assert [issue.code for issue in issues] == [code]
    assert issues[0].severity == sch.ISSUE_CODES[code]
    assert issues[0].where


def test_closed_set() -> None:
    assert set(NEGATIVE) == set(sch.ISSUE_CODES)
    severities = {code: severity for code, severity in sch.ISSUE_CODES.items()}
    infos = {code for code, severity in severities.items() if severity == "info"}
    assert infos == {
        "altium.sch.unknown-record",
        "altium.sch.unknown-stream",
        "altium.sch.pin-trailing-bytes",
        "altium.sch.storage-opaque",
        "altium.schlib.unlisted-component",
        "altium.schlib.side-stream-opaque",
    }


def test_issues_come_in_stream_order() -> None:
    data = schdoc(
        [SHEET, b"|RECORD=4|TEXT=\x81", "|RECORD=27|LOCATIONCOUNT=x", "|RECORD=25|OWNERINDEX=9"], weight=9
    )
    first: list[Issue] = []
    second: list[Issue] = []
    sch.read_schematic(data, issues=first)
    sch.read_schematic(data, issues=second)
    assert first == second
    assert [issue.where for issue in first] == [
        "FileHeader/record 2",
        "FileHeader/record 3",
        "FileHeader/record 0",
        "FileHeader/record 4",
    ]


def test_missing_file_header() -> None:
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(write_compound([("Storage", stream(["|HEADER=Icon storage"]))]), file="a.SchDoc")
    assert (caught.value.file, caught.value.locator) == ("a.SchDoc", "FileHeader")


def test_fatal_errors_carry_file_and_locator() -> None:
    cases = [
        (b"nothing", ""),
        (schdoc([], file_header=b""), "FileHeader/record 0"),
        (schdoc([], file_header=stream(["|HEADER=x"])), "FileHeader/record 0"),
        (schdoc([], file_header=stream([(1, b"abc")])), "FileHeader/record 0"),
    ]
    for data, locator in cases:
        with pytest.raises(FormatError) as caught:
            sch.read_schematic(data, file="f.SchDoc")
        assert (caught.value.file, caught.value.locator) == ("f.SchDoc", locator)
