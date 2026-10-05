# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Storage`` stream and embedded files (capability altium-schematic-reader, "Storage stream and embedded
files")."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest
from _altium_sch_build import SHEET, schdoc, short, stream

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch import document as document_module
from fenolite.core.errors import FormatError, Issue

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"


def embedded(name: bytes, content: bytes) -> bytes:
    packed = zlib.compress(content)
    return bytes([0xD0]) + short(name) + struct.pack("<I", len(packed)) + packed


def test_icon_storage_only() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    assert document.storage_header is not None
    assert document.storage_header.props is not None
    assert document.storage_header.props.text("HEADER") == "Icon storage"
    assert document.embedded == ()
    assert sch.encode_stream(document, "Storage") == document.streams["Storage"]


def test_unknown_storage_payload() -> None:
    issues: list[Issue] = []
    storage = stream(["|HEADER=Icon storage", (1, b"1234567")])
    document = sch.read_schematic(schdoc([SHEET], storage=storage), issues=issues)
    (item,) = document.embedded
    assert item.payload == b"1234567"
    assert item.packed is None and item.name == ""
    assert [(issue.code, issue.severity, issue.where) for issue in issues] == [
        ("altium.sch.storage-opaque", "info", "Storage/record 1")
    ]
    assert sch.check_identity(document) == ()
    with pytest.raises(FormatError):
        item.data()


def test_embedded_file_and_image_data() -> None:
    storage = stream(["|HEADER=Icon storage|WEIGHT=1", (1, embedded(b"logo.bmp", b"BM" + bytes(40)))])
    document = sch.read_schematic(
        schdoc([SHEET, "|RECORD=30|EMBEDIMAGE=T|FILENAME=logo.bmp"], storage=storage)
    )
    (item,) = document.embedded
    assert item.name == "logo.bmp" and not item.opaque
    image = document.records[1]
    assert isinstance(image, sch.Image) and image.embedded
    assert document.image_data(image) is item
    assert item.data() == b"BM" + bytes(40)
    assert sch.check_identity(document) == ()
    other = sch.read_schematic(schdoc([SHEET, "|RECORD=30|FILENAME=other.bmp"], storage=storage))
    other_image = other.records[1]
    assert isinstance(other_image, sch.Image) and other.image_data(other_image) is None


def test_decompression_limit() -> None:
    content = bytes(2 * 1024 * 1024)
    storage = stream(["|HEADER=Icon storage", (1, embedded(b"big.bmp", content))])
    (item,) = sch.read_schematic(schdoc([SHEET], storage=storage), file="d.SchDoc").embedded
    with pytest.raises(FormatError) as caught:
        item.data(limit=1_048_576)
    assert "1048576" in caught.value.message and caught.value.file == "d.SchDoc"
    assert item.data() == content
    assert sch.MAX_EMBEDDED == 64 * 1024 * 1024


def test_cut_or_broken_zlib() -> None:
    packed = zlib.compress(b"x" * 1000)[:-3]
    payload = bytes([0xD0]) + short(b"a") + struct.pack("<I", len(packed)) + packed
    (item,) = sch.read_schematic(
        schdoc([SHEET], storage=stream(["|HEADER=Icon storage", (1, payload)]))
    ).embedded
    with pytest.raises(FormatError, match="cut"):
        item.data()
    junk = bytes([0xD0]) + short(b"a") + struct.pack("<I", 3) + b"xyz"
    (bad,) = sch.read_schematic(schdoc([SHEET], storage=stream(["|HEADER=Icon storage", (1, junk)]))).embedded
    with pytest.raises(FormatError, match="zlib"):
        bad.data()


def test_reading_never_decompresses(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> None:
        raise AssertionError("decompressed while reading")

    monkeypatch.setattr(document_module.zlib, "decompressobj", refuse)
    storage = stream(["|HEADER=Icon storage", (1, embedded(b"a.bmp", b"data"))])
    document = sch.read_schematic(schdoc([SHEET], storage=storage))
    assert document.embedded[0].name == "a.bmp"


def test_storage_without_its_header_and_missing_storage() -> None:
    entries = stream([(1, b"abc")])
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc([SHEET], storage=entries), issues=issues)
    assert document.storage_header is None and len(document.embedded) == 1
    assert sch.check_identity(document) == ()
    assert [issue.where for issue in issues] == ["Storage/record 0"]
