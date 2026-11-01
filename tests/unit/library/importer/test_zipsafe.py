# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hostile archives authored in memory for c0264's zip scenarios."""

from __future__ import annotations

import io
import stat
import zipfile

import pytest

from fenolite.core.errors import FormatError
from fenolite.library.importer import zipsafe


def archive(*names: str | zipfile.ZipInfo, body: bytes = b"authored for Fenolite") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name in names:
            output.writestr(name, body)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name", ["../evil.kicad_mod", "/abs.kicad_mod", "C:/x.kicad_mod", "./C:/x.kicad_mod", "a\\..\\x"]
)
def test_path_traversal_refused(name: str) -> None:
    with pytest.raises(FormatError, match="forbidden"):
        zipsafe.read_zip(archive(name), file="authored.zip")


def test_duplicate_normalised_names_and_links() -> None:
    for names in [("A.kicad_mod", "a.kicad_mod"), ("a\\x.kicad_mod", "a/x.kicad_mod")]:
        with pytest.raises(FormatError, match="duplicate"):
            zipsafe.read_zip(archive(*names), file="authored.zip")
    link = zipfile.ZipInfo("link.kicad_mod")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(FormatError, match="symbolic link"):
        zipsafe.read_zip(archive(link), file="authored.zip")


def test_nul_and_encryption_headers() -> None:
    info = zipfile.ZipInfo("a.kicad_mod")
    info.orig_filename = "a\x00.kicad_mod"
    with pytest.raises(FormatError, match="NUL"):
        zipsafe._name(info, "authored.zip")
    info.orig_filename = info.filename
    info.flag_bits = 1
    with pytest.raises(FormatError, match="encrypted"):
        zipsafe._name(info, "authored.zip")


def test_legacy_library_skipped_without_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*args: object, **kwargs: object) -> None:
        raise AssertionError("unsupported members must never inflate")

    data = archive("part.lib", "inner.zip", "notes.txt")
    monkeypatch.setattr(zipfile.ZipFile, "open", refused)
    got = zipsafe.read_zip(data, file="authored.zip")
    assert not got.members
    assert [(s.name, s.reason) for s in got.skipped] == [
        ("inner.zip", "nested archive"),
        ("notes.txt", "unsupported format"),
        ("part.lib", "legacy KiCad 5 library"),
    ]


def test_compression_bomb_stops_while_counting(monkeypatch: pytest.MonkeyPatch) -> None:
    data = archive("bomb.kicad_mod", body=b"0" * (65 * 1024 * 1024))
    counted = 0
    original = zipfile.ZipExtFile.read

    def read(stream: zipfile.ZipExtFile, n: int = -1) -> bytes:
        nonlocal counted
        block = original(stream, n)
        counted += len(block)
        return block

    monkeypatch.setattr(zipfile.ZipExtFile, "read", read)
    with pytest.raises(FormatError, match="bomb.kicad_mod.*ratio limit"):
        zipsafe.read_zip(data, file="authored.zip")
    assert counted < 65 * 1024 * 1024


@pytest.mark.parametrize(
    ("constant", "limit", "names", "body"),
    [
        ("MAX_ENTRIES", 1, ("a.kicad_mod", "b.kicad_mod"), b"x"),
        ("MAX_MEMBER", 4, ("a.kicad_mod",), b"12345"),
        ("MAX_TOTAL", 7, ("a.kicad_mod", "b.kicad_mod"), b"1234"),
    ],
)
def test_each_size_limit(
    constant: str, limit: int, names: tuple[str, ...], body: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(zipsafe, constant, limit)
    with pytest.raises(FormatError, match="limit"):
        zipsafe.read_zip(archive(*names, body=body), file="authored.zip")


def test_valid_zip_and_unreadable_zip() -> None:
    got = zipsafe.read_zip(archive("KiCad\\part.kicad_mod"), file="authored.zip")
    assert got.members[0].name == "KiCad/part.kicad_mod"
    with pytest.raises(FormatError, match="unreadable zip"):
        zipsafe.read_zip(b"authored invalid archive", file="authored.zip")
