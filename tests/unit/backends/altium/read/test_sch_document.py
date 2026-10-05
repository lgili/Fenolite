# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Entry points and streams of a binary schematic (capability altium-schematic-reader, "Schematic reader entry
points", "Schematic document streams")."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _altium_sch_build import BINARY_HEADER, SHEET, ascii_doc, frame_bytes, prop_frame, schdoc, schlib, stream

from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read import schlib as schlib_reader
from fenolite.backends.altium.read.cfb import CompoundError
from fenolite.core.errors import FormatError, Issue

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"
LIBRARY = ROOT / "tests" / "data" / "altium" / "sample" / "FenoliteSample.SchLib"
FOUR = [SHEET, "|RECORD=27|LOCATIONCOUNT=2|X1=1|Y1=1|X2=2|Y2=1", "|RECORD=25|TEXT=A", "|RECORD=29"]


def test_binary_schematic_by_content() -> None:
    data = BLINK.read_bytes()
    assert sch.detect(data) == "binary"
    document = sch.read_schematic(data, file="x.bin")
    assert document.form == "binary"
    assert isinstance(document.records[0], sch.Sheet)
    assert document.file == "x.bin"


def test_library_given_to_the_schematic_reader() -> None:
    data = LIBRARY.read_bytes()
    assert sch.detect(data) == "library"
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(data, file="a.SchLib")
    assert caught.value.file == "a.SchLib"
    assert "read_schlib" in caught.value.message


def test_schematic_given_to_the_library_reader() -> None:
    with pytest.raises(FormatError) as caught:
        schlib_reader.read_schlib(BLINK.read_bytes(), file="b.SchDoc")
    assert caught.value.file == "b.SchDoc"
    assert "read_schematic" in caught.value.message


def test_neither_form() -> None:
    assert sch.detect(b"hello") is None
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(b"hello")
    assert caught.value.offset == 0


def test_detect_never_looks_at_a_name_and_never_raises() -> None:
    assert sch.detect(ascii_doc([SHEET])) == "ascii"
    assert sch.detect(b"\xef\xbb\xbf" + ascii_doc([SHEET])) == "ascii"
    assert sch.detect(BLINK.read_bytes()[:600]) is None
    assert sch.detect(write_compound([("FileHeader", stream(["|HEADER=Other"]))])) is None
    assert sch.detect(write_compound([("Storage", b"")])) is None


def test_compound_errors_pass_unchanged() -> None:
    data = bytearray(BLINK.read_bytes())
    data[0x1A] = 9  # an unknown major version
    with pytest.raises(CompoundError):
        sch.read_schematic(bytes(data))


def test_three_streams() -> None:
    additional = [
        "|RECORD=215|XSIZE=5",
        "|RECORD=216|OWNERINDEXADDITIONALLIST=T",
        "|RECORD=217|OWNERINDEXADDITIONALLIST=T",
    ]
    storage = stream(["|HEADER=Icon storage"])
    data = schdoc(FOUR, additional=additional, storage=storage)
    document = sch.read_schematic(data)
    assert len(document.records) == 4
    assert len(document.additional) == 3
    assert document.additional[0].ref == sch.RecordRef("additional", 0)
    assert set(document.streams) == {"FileHeader", "Additional", "Storage"}
    for name in ("FileHeader", "Additional", "Storage"):
        assert sch.encode_stream(document, name) == document.streams[name]
    assert sch.check_identity(document) == ()


def test_empty_additional_header() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc(FOUR, additional=[], additional_weight=None), issues=issues)
    assert document.additional == ()
    assert document.additional_header is not None
    assert issues == []


def test_no_additional_stream() -> None:
    document = sch.read_schematic(schdoc(FOUR))
    assert document.additional_header is None and document.additional == ()


def test_wrong_weight() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc(FOUR, weight=9), issues=issues)
    assert len(document.records) == 4
    assert [issue.code for issue in issues] == ["altium.sch.weight-mismatch"]
    assert "9" in issues[0].message and "4" in issues[0].message
    assert issues[0].severity == "warning"


def test_unknown_stream_kept() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc(FOUR, extra=[("Extra", b"12345")]), issues=issues)
    assert document.extra_streams == {"Extra": b"12345"}
    assert [(issue.code, issue.severity) for issue in issues] == [("altium.sch.unknown-stream", "info")]
    assert "Extra" in issues[0].message


def test_empty_additional_stream() -> None:
    entries = [("FileHeader", stream([f"|HEADER={BINARY_HEADER}|WEIGHT=1", SHEET])), ("Additional", b"")]
    issues: list[Issue] = []
    document = sch.read_schematic(write_compound(entries), issues=issues)
    assert document.additional == () and document.additional_header is None
    assert [issue.code for issue in issues] == ["altium.sch.empty-stream"]
    assert document.storage_header is None and document.embedded == ()
    assert sch.check_identity(document) == ()


def test_property_list_without_its_nul() -> None:
    file_header = stream([f"|HEADER={BINARY_HEADER}|WEIGHT=3", SHEET])
    file_header += frame_bytes(0, b"|RECORD=27")
    file_header += stream(["|RECORD=25|TEXT=B"])
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc([], file_header=file_header), issues=issues)
    record = document.records[1]
    assert isinstance(record, sch.UnknownRecord)
    assert record.payload == b"|RECORD=27" and len(record.payload) == 10
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.malformed-record", "FileHeader/record 2")
    ]
    assert isinstance(document.records[2], sch.NetLabel)
    assert sch.check_identity(document) == ()


def test_missing_file_header() -> None:
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(write_compound([("Storage", stream(["|HEADER=Icon storage"]))]), file="a.SchDoc")
    assert (caught.value.file, caught.value.locator) == ("a.SchDoc", "FileHeader")


def test_wrong_header_text() -> None:
    data = schdoc([], file_header=stream(["|HEADER=Protel for Windows - Something Else"]))
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(data)
    assert caught.value.locator == "FileHeader/record 0"


def test_header_text_without_letter_case() -> None:
    data = schdoc([], file_header=stream([f"|HEADER={BINARY_HEADER.upper()}|WEIGHT=1", SHEET]))
    assert sch.read_schematic(data).header.header == BINARY_HEADER.upper()


def test_cut_frame_is_fatal() -> None:
    data = schdoc([], file_header=stream([f"|HEADER={BINARY_HEADER}|WEIGHT=1"]) + b"\x10\x00")
    with pytest.raises(FormatError) as caught:
        sch.read_schematic(data, file="c.SchDoc")
    assert (caught.value.locator, caught.value.file) == ("FileHeader/record 1", "c.SchDoc")


def test_compound_notes_reach_the_issues() -> None:
    data = bytearray(schdoc(FOUR))
    data[0x18] = 0x3F  # minor version other than 0x3E
    issues: list[Issue] = []
    sch.read_schematic(bytes(data), issues=issues)
    assert [issue.code for issue in issues] == ["cfb.note.minor-version"]


def test_no_issue_list_gives_the_same_result() -> None:
    data = schdoc(FOUR, weight=9)
    issues: list[Issue] = []
    assert sch.read_schematic(data) == sch.read_schematic(data, issues=issues)
    assert len(issues) == 1


def test_results_are_frozen_tuples() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    assert isinstance(document.records, tuple) and isinstance(document.roots, tuple)
    with pytest.raises(AttributeError):
        document.form = "ascii"  # type: ignore[misc]
    assert hash(document.records[0]) == hash(sch.read_schematic(BLINK.read_bytes()).records[0])


SCRIPT = """
import hashlib, sys
from pathlib import Path
from fenolite.backends.altium.read import sch, schlib
issues = []
doc = sch.read_schematic(Path(sys.argv[1]).read_bytes(), issues=issues)
lib = schlib.read_schlib(Path(sys.argv[2]).read_bytes(), issues=issues)
text = repr((doc.records, doc.roots, issues, lib.components, sorted(doc.census().items())))
print(hashlib.sha256(text.encode()).hexdigest())
"""


@pytest.mark.parametrize("seeds", [("0", "12345")])
def test_equal_results_whatever_the_hash_seed(seeds: tuple[str, str]) -> None:
    digests = []
    for seed in seeds:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, str(BLINK), str(LIBRARY)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        digests.append(result.stdout.strip())
    assert digests[0] == digests[1]


def test_library_detect_and_schlib_builder() -> None:
    data = schlib([("A", ["|RECORD=1|LIBREFERENCE=A"])])
    assert sch.detect(data) == "library"
    assert prop_frame("x") == (0, b"x\0")
