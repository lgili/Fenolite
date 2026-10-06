# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ASCII form (capability altium-schematic-reader, "ASCII schematic form")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_sch_build import ASCII_HEADER, BINARY_HEADER, SHEET, ascii_doc

from fenolite.backends.altium.read import sch
from fenolite.core.errors import FormatError, Issue

ROOT = Path(__file__).resolve().parents[5]
SAMPLE = ROOT / "tests" / "data" / "altium" / "sample"
ASCII_FILES = [
    SAMPLE / "altium_sample.SchDoc",
    SAMPLE / "variants" / "altium_sample_lf.SchDoc",
    SAMPLE / "variants" / "altium_sample_nouid.SchDoc",
    ROOT / "tests" / "data" / "altium" / "no_connect" / "ascii" / "altium_no_connect.SchDoc",
]


def _view(document: sch.SchDocument) -> list[tuple[str, tuple[tuple[str, bytes | None], ...]]]:
    return [
        (type(record).__name__, tuple((p.key, p.raw) for p in record.props.items) if record.props else ())
        for record in document.records
    ]


def test_fenolites_own_ascii_sample() -> None:
    data = (SAMPLE / "altium_sample.SchDoc").read_bytes()
    issues: list[Issue] = []
    document = sch.read_schematic(data, issues=issues)
    assert document.form == "ascii"
    assert issues == []
    binary = sch.read_schematic((SAMPLE / "binary" / "altium_sample.SchDoc").read_bytes())
    assert _view(document) == _view(binary)
    assert sch.encode_stream(document, "ascii") == data
    assert sch.check_identity(document) == ()


@pytest.mark.parametrize("path", ASCII_FILES, ids=lambda path: path.name)
def test_committed_ascii_files_and_their_lf_variant(path: Path) -> None:
    data = path.read_bytes()
    for variant in (data, data.replace(b"\r\n", b"\n")):
        issues: list[Issue] = []
        document = sch.read_schematic(variant, issues=issues)
        assert issues == []
        assert sch.encode_stream(document, "ascii") == variant


def test_line_ends_and_continuation() -> None:
    lines = [SHEET, "|RECORD=27|LOCATIONCOUNT=2|X1=10|Y1=20|>", "|X2=30|Y2=20", "|RECORD=25|TEXT=A"]
    data = ascii_doc(lines, eol=b"\n", weight=3)
    document = sch.read_schematic(data)
    assert len(document.records) == 3
    wire = document.records[1]
    assert isinstance(wire, sch.Wire)
    assert wire.props is not None
    assert wire.props.keys() == ("RECORD", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2")
    assert len(wire.points) == 2
    assert wire.payload == b"|RECORD=27|LOCATIONCOUNT=2|X1=10|Y1=20|>\n|X2=30|Y2=20\n"
    assert sch.encode_stream(document, "ascii") == data


def test_second_header_starts_the_additional_section() -> None:
    lines = [
        SHEET,
        "|RECORD=25|TEXT=A",
        f"|HEADER={ASCII_HEADER}|WEIGHT=2",
        "|RECORD=215|XSIZE=5",
        "|RECORD=216",
    ]
    data = ascii_doc(lines, weight=2)
    issues: list[Issue] = []
    document = sch.read_schematic(data, issues=issues)
    assert [record.ref for record in document.additional] == [
        sch.RecordRef("additional", 0),
        sch.RecordRef("additional", 1),
    ]
    assert len(document.records) == 2
    assert document.additional_header is not None
    assert issues == []
    assert sch.encode_stream(document, "ascii") == data


def test_binary_header_text_also_starts_the_additional_section() -> None:
    lines = [SHEET, f"|HEADER={BINARY_HEADER}", "|RECORD=218|LOCATIONCOUNT=0"]
    document = sch.read_schematic(ascii_doc(lines, weight=1))
    assert len(document.additional) == 1


def test_byte_order_mark() -> None:
    data = (SAMPLE / "altium_sample.SchDoc").read_bytes()
    marked = b"\xef\xbb\xbf" + data
    assert sch.detect(marked) == "ascii"
    document = sch.read_schematic(marked)
    assert document.preamble == b"\xef\xbb\xbf"
    assert _view(document) == _view(sch.read_schematic(data))
    assert sch.encode_stream(document, "ascii") == marked


def test_empty_line_is_kept_and_not_counted() -> None:
    data = ascii_doc([SHEET, "", "|RECORD=25|OWNERINDEX=0|TEXT=A"], weight=2)
    issues: list[Issue] = []
    document = sch.read_schematic(data, issues=issues)
    assert len(document.records) == 2
    assert document.records[1].owner == sch.RecordRef("main", 0)
    (blank,) = document.blank_lines
    assert isinstance(blank, sch.UnknownRecord) and blank.payload == b"\r\n"
    assert issues == []
    assert sch.encode_stream(document, "ascii") == data


def test_last_line_without_a_line_end() -> None:
    data = ascii_doc([SHEET, "|RECORD=25|TEXT=A"]).removesuffix(b"\r\n")
    document = sch.read_schematic(data)
    assert len(document.records) == 2
    assert sch.encode_stream(document, "ascii") == data


def test_storage_and_unknown_sections() -> None:
    lines = [SHEET, "|HEADER=Icon storage", "|NAME=a.bmp|DATA_LEN=1|DATA=00", "|HEADER=Something", "|X=1"]
    data = ascii_doc(lines, weight=1)
    issues: list[Issue] = []
    document = sch.read_schematic(data, issues=issues)
    assert document.storage_header is not None and len(document.embedded) == 1
    assert len(document.extra_sections) == 1 and len(document.extra_sections[0].records) == 1
    assert [issue.code for issue in issues] == ["altium.sch.storage-opaque", "altium.sch.unknown-stream"]
    assert [issue.where for issue in issues] == ["line 4", "line 5"]
    assert sch.encode_stream(document, "ascii") == data


def test_wrong_first_line() -> None:
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(b"|HEADER=Protel for Windows - Other\r\n", file="x.SchDoc")
    assert (caught.value.locator, caught.value.file) == ("line 1", "x.SchDoc")
    with pytest.raises(FormatError, match="binary header"):
        sch.read_schematic(f"|HEADER={BINARY_HEADER}\r\n".encode())


def test_ascii_locators_and_owner_rules() -> None:
    issues: list[Issue] = []
    data = ascii_doc([SHEET, "|RECORD=25|OWNERINDEX=5", "|RECORD=2|OWNERINDEX=0"], weight=2)
    document = sch.read_schematic(data, issues=issues)
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.weight-mismatch", "line 1"),
        ("altium.sch.orphan-record", "line 3"),
    ]
    assert document.records[2].owner == sch.RecordRef("main", 0)


def test_encode_stream_names() -> None:
    document = sch.read_schematic(ascii_doc([SHEET]))
    with pytest.raises(KeyError):
        sch.encode_stream(document, "FileHeader")
