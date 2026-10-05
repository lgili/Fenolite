# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The lossless INI layer (capability altium-project-reader, "Text forms are kept byte for byte")."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium.read.ini import IniEntry, parse_ini
from fenolite.backends.altium.read.textfile import BOM


def test_bom_and_lf() -> None:
    """Scenario "Byte-order mark and LF are kept"."""
    data = BOM + b"[Design]\nVersion=1.0\n\n[Document1]\nDocumentPath=a.SchDoc\n"
    doc = parse_ini(data)
    assert doc.to_bytes() == data
    assert doc.form.bom == BOM and {line.end for line in doc.form.lines} == {b"\n"}
    assert [s.name for s in doc.sections] == ["Design", "Document1"]
    design = doc.section("Design")
    assert design is not None and design.get("Version") == "1.0" and design.line == 1
    assert doc.issues == ()


def test_unknown_section_and_key_order() -> None:
    """Scenario "Unknown section and key order survive"."""
    data = (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Zeta Options]\r\nB=2\r\nA=1\r\nB=3\r\n\r\n"
        b"[Document1]\r\nDocumentPath=x\r\n"
    )
    doc = parse_ini(data, file="z.PrjPcb")
    assert doc.to_bytes() == data
    zeta = doc.section("Zeta Options")
    assert zeta is not None
    assert [(e.key, e.value) for e in zeta.entries] == [("B", "2"), ("A", "1"), ("B", "3")]
    assert zeta.get("B") == "2" and zeta.keys() == ("B", "A", "B")
    assert [(i.code, i.severity, i.where) for i in doc.issues] == [
        ("altium.text.duplicate-key", "info", "z.PrjPcb:7")
    ]


def test_value_keeps_spaces_and_further_equals() -> None:
    doc = parse_ini(b"[S]\nKey = a=b \nEmpty=\n=lone\n")
    section = doc.sections[0]
    assert section.entries == (
        IniEntry("Key ", " a=b ", 2),
        IniEntry("Empty", "", 3),
        IniEntry("", "lone", 4),
    )


def test_duplicate_sections_kept_in_order() -> None:
    doc = parse_ini(b"[A]\nx=1\n[B]\n[A]\nx=2\n")
    assert [(s.name, s.line) for s in doc.sections] == [("A", 1), ("B", 3), ("A", 4)]
    first = doc.section("A")
    assert first is not None and first.get("x") == "1"
    assert doc.issues == ()


def test_lines_before_the_first_section_and_stray_lines() -> None:
    data = b"lead=1\nnot a key\n[Design]\n  \nVersion=1.0\n[broken\n"
    doc = parse_ini(data, file="s.PrjPcb")
    assert doc.to_bytes() == data
    assert [(s.name, s.line, s.keys()) for s in doc.sections] == [
        ("", 0, ("lead",)),
        ("Design", 3, ("Version",)),
    ]
    assert [(i.code, i.where) for i in doc.issues] == [
        ("altium.text.stray-line", "s.PrjPcb:2"),
        ("altium.text.stray-line", "s.PrjPcb:4"),
        ("altium.text.stray-line", "s.PrjPcb:6"),
    ]


def test_names_are_matched_as_written() -> None:
    doc = parse_ini(b"[design]\nversion=1.0\n")
    assert doc.section("Design") is None
    section = doc.section("design")
    assert section is not None and section.get("Version") is None and section.get("version") == "1.0"


def test_numbered_sections_by_name() -> None:
    names = ("Document7", "Document2", "Document", "Document02", "DocumentX", "GeneratedDocument1")
    doc = parse_ini("".join(f"[{name}]\n" for name in names).encode())
    assert [(n, s.name) for n, s in doc.numbered("Document")] == [(7, "Document7"), (2, "Document2")]
    assert [n for n, _ in doc.numbered("GeneratedDocument")] == [1]


# --- property test --------------------------------------------------------------------------------

_PRINTABLE = st.characters(min_codepoint=32, max_codepoint=126, exclude_characters="[]")
_NAME = st.text(alphabet=_PRINTABLE, max_size=12)
_TEXT = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0x2FF, exclude_characters="\r\n"), max_size=16
)
_LINE = st.one_of(
    _NAME.map(lambda name: f"[{name}]"),
    st.tuples(_NAME.filter(lambda k: "=" not in k), _TEXT).map(lambda kv: f"{kv[0]}={kv[1]}"),
    st.just(""),
    _TEXT,
)
_END = st.sampled_from(["\r\n", "\n", "\r"])


@st.composite
def _ini_bytes(draw: st.DrawFn) -> bytes:
    lines = draw(st.lists(st.tuples(_LINE, _END), max_size=20))
    text = "".join(line + end for line, end in lines)
    if draw(st.booleans()) and lines:
        text = text[: -len(lines[-1][1])]
    encoding = draw(st.sampled_from(["utf-8", "latin-1"]))
    data = text.encode(encoding, errors="replace")
    return (BOM + data) if draw(st.booleans()) else data


@given(_ini_bytes())
def test_parse_ini_gives_the_bytes_back(data: bytes) -> None:
    doc = parse_ini(data)
    assert doc.to_bytes() == data
    keys = sum(len(section.entries) for section in doc.sections)
    sections = sum(1 for text in doc.form.texts() if text.startswith("[") and text.endswith("]"))
    assert keys == sum(1 for text in doc.form.texts() if "=" in text) - sum(
        1 for text in doc.form.texts() if "=" in text and text.startswith("[") and text.endswith("]")
    )
    assert len([s for s in doc.sections if s.line]) == sections
