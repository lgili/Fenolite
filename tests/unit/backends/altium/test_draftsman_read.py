# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Draftsman reader (capability altium-draftsman, "Draftsman document read", scenario "Not a document";
change c0172, task 2.1; ``H-A-DWF-CONTAINER``).

The documents here are authored for Fenolite: element names from ``docs/formats/altium/draftsman.md``,
values of this test. They are encoded by the small encoder below (stored chunks and LZ4 blocks of
literals) and by one LZ4 block written by hand. The public documents are read by
``tests/corpus/test_altium_draftsman_census.py``; the maintainer's F0 files by ``test_f0_files_decode``
with ``FENOLITE_DWF_F0=<folder>``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fenolite.backends.altium.read.draftsman import (
    NAMESPACE,
    DraftsmanError,
    chunks,
    decode,
    lz4_block,
    read_draftsman,
    summary,
)

ROOT = Path(__file__).resolve().parents[4]
F0 = os.environ.get("FENOLITE_DWF_F0")

DOCUMENT = f"""<Document xmlns="{NAMESPACE}" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">\
<Id>0</Id><FormatVersion>22</FormatVersion><Pages><Page><Id>1</Id><Items>\
<Item i:type="Text"><Id>2</Id><Anchor>Top Left</Anchor><OriginatedFromTemplate>true</OriginatedFromTemplate>\
<Text>=Title</Text></Item>\
<Item i:type="BoardAssemblyViewData"><Id>3</Id><Anchor>Top Left</Anchor>\
<OriginatedFromTemplate>false</OriginatedFromTemplate><Location><X>100</X><Y>200</Y></Location>\
<Scale><Denominator>1</Denominator><Numenator>1</Numenator></Scale><Title>TOP</Title>\
<ViewSide>Top</ViewSide></Item>\
<Item i:type="BillOfMaterialsView"><Id>4</Id><Anchor>Top Left</Anchor>\
<OriginatedFromTemplate>false</OriginatedFromTemplate><Title>PARTS</Title><ViewSide>Top</ViewSide></Item>\
<Item i:type="Note"><Id>5</Id><Anchor>Top Left</Anchor><OriginatedFromTemplate>false</OriginatedFromTemplate>\
<Elements><NoteElement><Id>6</Id><Text>FENOLITE ONE</Text></NoteElement>\
<NoteElement><Id>7</Id><Text>FENOLITE TWO</Text></NoteElement></Elements><Title>NOTES</Title></Item>\
<Item i:type="Line"><Id>8</Id><Anchor>Top Left</Anchor><OriginatedFromTemplate>true</OriginatedFromTemplate>\
</Item></Items><SheetSizingMode>StandardSize</SheetSizingMode>\
<Size><Height>793.7</Height><Width>1122.5</Width></Size><StandardSizeName>A4</StandardSizeName></Page>\
<Page><Id>9</Id><Items/><Size><Height>816</Height><Width>1056</Width></Size>\
<StandardSizeName>Letter</StandardSizeName></Page></Pages>\
<Parameters><DrawingDocumentParameterData><Name>Revision</Name><Value>A</Value></DrawingDocumentParameterData>\
</Parameters></Document>""".encode()


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        out.append((value & 0x7F) | (0x80 if value > 0x7F else 0))
        value >>= 7
        if not value:
            return bytes(out)


def literal_block(text: bytes) -> bytes:
    """One LZ4 block that holds ``text`` as its only, last literal run."""
    if len(text) < 15:
        return bytes([len(text) << 4]) + text
    rest = len(text) - 15
    return bytes([0xF0]) + b"\xff" * (rest // 255) + bytes([rest % 255]) + text


def stored_chunk(text: bytes) -> bytes:
    return b"\x00" + varint(len(text)) + text


def lz4_chunk(text: bytes, block: bytes | None = None) -> bytes:
    block = literal_block(text) if block is None else block
    return b"\x01" + varint(len(text)) + varint(len(block)) + block


def encode(text: bytes, cut: int = 1000) -> bytes:
    """``text`` in chunks of ``cut`` bytes, alternately stored and LZ4."""
    pieces = [text[at : at + cut] for at in range(0, len(text), cut)]
    return b"".join(stored_chunk(p) if n % 2 else lz4_chunk(p) for n, p in enumerate(pieces))


def test_authored_document_reads() -> None:
    data = encode(DOCUMENT, cut=300)
    file = read_draftsman(data)
    assert [c.flag for c in file.chunks] == [n % 2 == 0 for n in range(len(file.chunks))]
    assert sum(c.size for c in file.chunks) == len(DOCUMENT)
    assert file.root.tag == f"{{{NAMESPACE}}}Document"
    assert decode(data)[1] == DOCUMENT


def test_summary_lists_sheets_items_and_parameters() -> None:
    result = summary(read_draftsman(encode(DOCUMENT)))
    assert result.format_version == "22"
    assert [(s.id, s.paper, s.size) for s in result.sheets] == [
        ("1", "A4", ("1122.5", "793.7")),
        ("9", "Letter", ("1056", "816")),
    ]
    assert result.sheets[0].sizing == "StandardSize" and result.sheets[1].sizing == ""
    first = result.sheets[0].items
    assert [(i.role, i.name) for i in first] == [
        ("text", "Text"),
        ("view", "board-assembly"),
        ("table", "bill-of-materials"),
        ("note", "Note"),
        ("other", "Line"),
    ]
    view = result.items("view")[0]
    assert (view.side, view.title, view.scale, view.place) == ("Top", "TOP", ("1", "1"), ("100", "200"))
    assert result.items("note")[0].texts == ("FENOLITE ONE", "FENOLITE TWO")
    assert result.items("text")[0].texts == ("=Title",) and result.items("text")[0].from_template
    assert result.parameters == ("Revision",)


def test_lz4_block_with_an_overlapping_match() -> None:
    """Literals ``ab``, a match of 10 at offset 2, then the last literals ``cdefg``."""
    block = bytes([0x26]) + b"ab" + bytes([2, 0]) + bytes([0x50]) + b"cdefg"
    assert lz4_block(block, 17) == b"abababababab" + b"cdefg"
    text = b"abababababab" + b"cdefg"
    assert decode(lz4_chunk(text, block))[1] == text


def test_lz4_block_with_long_runs() -> None:
    """A literal run and a match of more than 15 + 255 bytes each, then the last literals."""
    literals = bytes(range(256)) + b"x" * 44
    rest = len(literals) - 15
    match = 300
    block = (
        bytes([0xFF])
        + bytes([255] * (rest // 255) + [rest % 255])
        + literals
        + bytes([1, 0])
        + bytes([255, match - 4 - 15 - 255])
        + bytes([0x50])
        + b"tail!"
    )
    assert lz4_block(block, len(literals) + match + 5) == literals + b"x" * match + b"tail!"


def test_not_a_document() -> None:
    """Scenario "Not a document": the bytes of a ``.PcbDoc`` (a compound file) raise ``DraftsmanError``."""
    pcbdoc = (ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc").read_bytes()
    with pytest.raises(DraftsmanError) as error:
        read_draftsman(pcbdoc)
    assert error.value.offset == 0 and "flag 208" in str(error.value)


@pytest.mark.parametrize(
    ("data", "offset", "words"),
    [
        (b"", 0, "no chunk"),
        (b"\x02\x01a", 0, "flag 2"),
        (b"\x00\x05abc", 0, "runs past the end"),
        (b"\x01\x80", 1, "length runs past"),
        (b"\x01\x04\x04" + bytes([0x10]) + b"a" + bytes([5, 0]), 5, "offset 5"),
        (b"\x01\x04\x02" + bytes([0x30]) + b"a", 4, "literals run past"),
        (b"\x01\x05\x04" + bytes([0x30]) + b"abc", 3, "decodes to 3 bytes, not 5"),
    ],
)
def test_container_errors_name_the_offset(data: bytes, offset: int, words: str) -> None:
    with pytest.raises(DraftsmanError) as error:
        read_draftsman(data)
    assert error.value.offset == offset and words in str(error.value)


def test_text_errors() -> None:
    with pytest.raises(DraftsmanError) as error:
        read_draftsman(lz4_chunk(b"<Document>\n<Pages></Page>"))
    assert error.value.locator == "text" and error.value.offset == 20
    with pytest.raises(DraftsmanError) as error:
        read_draftsman(lz4_chunk(b"<Document/>"))
    assert "not a Draftsman Document" in str(error.value)


def test_chunks_of_a_large_stored_length() -> None:
    """A length of three 7-bit groups (``80 80 40`` is 1048576, as in every public document)."""
    assert varint(1 << 20) == b"\x80\x80\x40"
    text = b"y" * (1 << 20)
    assert [(c.flag, c.size, c.stored) for c in chunks(stored_chunk(text))] == [(0, 1 << 20, 1 << 20)]


@pytest.mark.skipif(F0 is None, reason="set FENOLITE_DWF_F0 to the maintainer's F0 folder")
def test_f0_files_decode() -> None:
    """Gate G1, the F0 half: every ``.PCBDwf`` and ``.DwfDot`` that the maintainer saved decodes into one
    Draftsman document with at least one sheet."""
    folder = Path(str(F0)).expanduser()
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".pcbdwf", ".dwfdot"))
    assert files, folder
    for path in files:
        assert summary(read_draftsman(path.read_bytes())).sheets, path.name
