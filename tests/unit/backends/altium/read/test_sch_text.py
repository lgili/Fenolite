# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Text decoding (capability altium-schematic-reader, "Text decoding")."""

from __future__ import annotations

import pytest
from _altium_sch_build import SHEET, ascii_doc, schdoc

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch.props import check_codepage, parse
from fenolite.core.errors import Issue


def test_utf8_twin_wins() -> None:
    payload = b"|RECORD=4|TEXT=\xb5F|%UTF8%TEXT=\xc2\xb5F"
    props = parse(payload)
    assert props.text("TEXT") == "µF"
    assert props.to_bytes() == payload
    assert props.keys() == ("RECORD", "TEXT")
    data = schdoc([SHEET, payload])
    label = sch.read_schematic(data).records[1]
    assert isinstance(label, sch.Label)
    assert label.text == "µF"
    assert label.unknown_keys == ()


def test_code_page_fallback() -> None:
    data = schdoc([SHEET, b"|RECORD=4|TEXT=caf\xe9"])
    first = sch.read_schematic(data)
    second = sch.read_schematic(data, codepage="cp1251")
    label_1, label_2 = first.records[1], second.records[1]
    assert isinstance(label_1, sch.Label) and isinstance(label_2, sch.Label)
    assert label_1.text == "café"
    assert label_2.text == "cafй"
    assert label_1.payload == label_2.payload
    assert label_1.props is not None and label_1.props.raw("TEXT") == b"caf\xe9"


def test_undefined_byte() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc([SHEET, b"|RECORD=4|TEXT=a\x81b"]), issues=issues)
    label = document.records[1]
    assert isinstance(label, sch.Label)
    assert label.text == "a�b"
    assert [issue.code for issue in issues] == ["altium.sch.text-undecodable"]
    assert issues[0].where == "FileHeader/record 2"
    assert label.props is not None and label.props.raw("TEXT") == b"a\x81b"


def test_one_warning_per_record() -> None:
    issues: list[Issue] = []
    sch.read_schematic(schdoc([SHEET, b"|RECORD=4|TEXT=\x81|NAME=\x8d"]), issues=issues)
    assert [issue.code for issue in issues] == ["altium.sch.text-undecodable"]


def test_unknown_code_page() -> None:
    with pytest.raises(ValueError, match="klingon"):
        sch.read_schematic(b"hello", codepage="klingon")
    with pytest.raises(ValueError, match="utf-8"):
        check_codepage("utf-8")
    with pytest.raises(ValueError, match="cp932"):
        check_codepage("cp932")
    assert check_codepage("latin-1") == "iso8859-1"


def test_utf8_ascii_file() -> None:
    data = ascii_doc([SHEET, "|RECORD=4|TEXT=café"], eol=b"\n")
    data = data.replace(b"caf\xe9", "café".encode())
    label = sch.read_schematic(data).records[1]
    assert isinstance(label, sch.Label)
    assert label.text == "café"


def test_latin_ascii_file_uses_the_code_page() -> None:
    data = ascii_doc([SHEET, b"|RECORD=4|TEXT=caf\xe9"])
    issues: list[Issue] = []
    label = sch.read_schematic(data, issues=issues).records[1]
    assert isinstance(label, sch.Label)
    assert label.text == "café"
    assert issues == []
