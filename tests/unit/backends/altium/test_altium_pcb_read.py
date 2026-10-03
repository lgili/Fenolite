# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test decoder of Altium PCB files on hand-written bytes (change c0035, capability altium-pcb-writer,
"PCB files read back", "Negative controls"). The bytes here follow the fact pages, not the product's PCB
writers, which this file never imports; only the compound-file container comes from ``cfb``."""

from __future__ import annotations

import struct

import pytest
from _altium_pcb_read import PcbReadError, decode_primitives, read_pcbdoc, read_pcblib

from fenolite.backends.altium.cfb import storage_from_paths, write_compound


def prop(**fields: str) -> bytes:
    text = "".join(f"|{k}={v}" for k, v in fields.items()).encode("ascii") + b"\0"
    return struct.pack("<I", len(text)) + text


def sblock(text: str) -> bytes:
    return struct.pack("<IB", len(text) + 1, len(text)) + text.encode("ascii")


def sub(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def head(layer: int, net: int = 0xFFFF, component: int = 0xFFFF) -> bytes:
    return struct.pack("<BBBHHH", layer, 0x0C, 0, net, 0xFFFF, component) + b"\xff" * 4


def track(size: int = 36, component: int = 0xFFFF) -> bytes:
    body = head(33, component=component) + struct.pack("<5iHB", 0, 0, 1000, 0, 100, 0, 0)
    return bytes((4,)) + sub(body[:size] + bytes(max(0, size - len(body))))


def arc(size: int = 47) -> bytes:
    body = head(33) + struct.pack("<3iddiH", 0, 0, 500, 0.0, 360.0, 100, 0)
    return bytes((1,)) + sub(body[:size])


def pad(geometry: int = 114, component: int = 0xFFFF, net: int = 0xFFFF) -> bytes:
    body = head(1, net=net, component=component) + struct.pack("<8i", 0, 0, 100, 100, 100, 100, 100, 100)
    body += struct.pack("<i3BdBBB", 0, 2, 2, 2, 0.0, 0, 0, 0)
    body += bytes(geometry - len(body))
    return bytes((2,)) + sub(b"\x011") + sub(b"\0") + sub(b"\x04|&|0") + sub(b"\0") + sub(body) + sub(b"")


FILE_HEADER = struct.pack("<IB", 27, 27) + b"PCB 6.0 Binary Library File" + struct.pack("<d", 5.01)
FILE_HEADER += struct.pack("<IB", 8, 8) + b"ABCDEFGH"
BOARD = {"FILENAME": "FP.PcbLib", "KIND": "Protel_Advanced_PCB_Library", "VERSION": "3.00"}
BOARD["V9_MASTERSTACK_STYLE"] = "0"


def library(
    data: bytes,
    *,
    parameters: bool = True,
    file_header: bytes = FILE_HEADER,
    board: dict[str, str] | None = None,
    without: str | None = None,
    unique: str = "UniqueIDPrimitiveInformation",
) -> bytes:
    primitives = decode_primitives(data)
    pads = sum(type(p).__name__ == "PadRecord" for p in primitives)
    toc = f"Name=FP|Pad Count={pads}|Height=0|Description=\r\n".encode("ascii") + b"\0"
    zero = struct.pack("<I", 0)
    streams = {
        "FileHeader": file_header,
        "Library/Header": struct.pack("<I", 1),
        "Library/Data": prop(**(BOARD if board is None else board)) + struct.pack("<I", 1) + sblock("FP"),
        "Library/EmbeddedFonts": zero,
        "Library/Models/Header": zero,
        "Library/Models/Data": b"",
        "Library/ModelsNoEmbed/Header": zero,
        "Library/ModelsNoEmbed/Data": b"",
        "Library/Textures/Header": zero,
        "Library/Textures/Data": b"",
        "Library/ComponentParamsTOC/Header": struct.pack("<I", 1),
        "Library/ComponentParamsTOC/Data": struct.pack("<I", len(toc)) + toc,
        "Library/PadViaLibrary/Header": zero,
        "Library/PadViaLibrary/Data": prop(
            **{
                "PADVIALIBRARY.LIBRARYID": "{00000000-0000-0000-0000-000000000000}",
                "PADVIALIBRARY.LIBRARYNAME": "<Local>",
                "PADVIALIBRARY.DISPLAYUNITS": "1",
            }
        ),
        "FP/Header": struct.pack("<I", len(primitives)),
        "FP/WideStrings": struct.pack("<I", 1) + b"\0",
        "FP/Data": sblock("FP") + data,
        f"FP/{unique}/Header": zero,
        f"FP/{unique}/Data": b"",
    }
    if parameters:
        streams["FP/Parameters"] = prop(
            PATTERN="FP", HEIGHT="0mil", DESCRIPTION="", ITEMGUID="", REVISIONGUID=""
        )
    if without is not None:
        del streams[without]
    return write_compound(storage_from_paths(streams))


HEADER_SIX = struct.pack("<IB", 19, 19) + b"PCB 6.0 Binary File" + struct.pack("<d", 5.01)
HEADER_SIX += struct.pack("<IB", 38, 38) + b"{01234567-89AB-CDEF-0123-456789ABCDEF}"


def document(pads: bytes, components: int = 3) -> bytes:
    streams = {
        "FileHeader": struct.pack("<I", 19) + "PCB 5.0 Bi".encode("utf-16-le"),
        "FileHeaderSix": HEADER_SIX,
        "Board6/Header": struct.pack("<I", 1),
        "Board6/Data": prop(KIND="Protel_Advanced_PCB", LAYER1NAME="Top Layer"),
        "Nets6/Header": struct.pack("<I", 1),
        "Nets6/Data": prop(NAME="GND"),
        "Components6/Header": struct.pack("<I", components),
        "Components6/Data": b"".join(prop(PATTERN="FP", SOURCEDESIGNATOR=f"R{i}") for i in range(components)),
        "Pads6/Header": struct.pack("<I", len(decode_primitives(pads))),
        "Pads6/Data": pads,
        "Vias6/Header": struct.pack("<I", 0),
        "Vias6/Data": b"",
    }
    return write_compound(storage_from_paths(streams))


def test_positive_library() -> None:
    lib = read_pcblib(library(pad() + track() + arc()))
    footprint = lib.footprints["FP"]
    assert lib.names == ["FP"] and footprint.header_count == 3
    first = footprint.primitives[0]
    assert getattr(first, "name", None) == "1" and getattr(first, "geometry_size", None) == 114


def test_file_header_of_32_bytes() -> None:
    """The header that AltiumSharp version 1 writes, which Altium refuses (``pcb-library.md``)."""
    with pytest.raises(PcbReadError, match="FileHeader holds 32 bytes, not 53"):
        read_pcblib(library(pad(), file_header=FILE_HEADER[:32]))


def test_file_header_with_another_version() -> None:
    header = FILE_HEADER[:32] + struct.pack("<d", 6.0) + FILE_HEADER[40:]
    with pytest.raises(PcbReadError, match="the version is 6.0, not 5.01"):
        read_pcblib(library(pad(), file_header=header))


def test_board_record_of_header_and_weight() -> None:
    """The two-key block of version 1, which Altium refuses."""
    with pytest.raises(PcbReadError, match="does not hold KIND=Protel_Advanced_PCB_Library"):
        read_pcblib(library(pad(), board={"HEADER": "PCB 6.0 Binary Library File", "WEIGHT": "1"}))
    with pytest.raises(PcbReadError, match="holds HEADER or WEIGHT"):
        read_pcblib(library(pad(), board={**BOARD, "WEIGHT": "1"}))


@pytest.mark.parametrize(
    "stream",
    [
        "Library/EmbeddedFonts",
        "Library/Textures/Header",
        "Library/ModelsNoEmbed/Data",
        "Library/PadViaLibrary/Data",
    ],
)
def test_library_without_a_side_stream(stream: str) -> None:
    with pytest.raises(PcbReadError, match=f"the library has no stream {stream}"):
        read_pcblib(library(pad(), without=stream))


def test_board_record_with_a_stray_cr() -> None:
    from _altium_pcb_read import field_block_at

    good = b"|KIND=X\r|RECORD=Board|A=1\0"
    fields, end = field_block_at(struct.pack("<I", len(good)) + good, 0, "t")
    assert fields == [("KIND", "X"), ("RECORD", "Board"), ("A", "1")] and end == 4 + len(good)
    bad = b"|KIND=X\r|A=1\0"
    with pytest.raises(PcbReadError, match="line 1 does not start with"):
        field_block_at(struct.pack("<I", len(bad)) + bad, 0, "t")
    with pytest.raises(PcbReadError, match="is not printable KEY=VALUE"):
        field_block_at(struct.pack("<I", 9) + b"|KIND=X\n\0", 0, "t")


def test_unique_id_storage_spelling() -> None:
    with pytest.raises(PcbReadError, match="no storage spelled UniqueIDPrimitiveInformation"):
        read_pcblib(library(pad(), unique="UniqueIdPrimitiveInformation"))


def test_positive_document() -> None:
    doc = read_pcbdoc(document(pad(component=2, net=0)))
    assert len(doc.components) == 3 and doc.pads[0].prefix.component == 2 and doc.nets[0]["NAME"] == "GND"
    assert doc.storages["Vias6"] == (0, b"")


def test_file_header_six_without_its_id() -> None:
    cut = document(pad(component=2, net=0)).replace(HEADER_SIX[33:], bytes(len(HEADER_SIX) - 33))
    with pytest.raises(PcbReadError, match="FileHeaderSix is not the header text"):
        read_pcbdoc(cut)


def test_pad_subrecord_5_of_100_bytes() -> None:
    with pytest.raises(PcbReadError, match="subrecord 5 has 100 bytes, fewer than 110"):
        read_pcblib(library(pad(geometry=100)))


def test_arc_of_45_bytes() -> None:
    with pytest.raises(PcbReadError, match="an arc subrecord of 45 bytes, fewer than 47"):
        read_pcblib(library(arc(size=45)))


def test_track_of_35_bytes() -> None:
    with pytest.raises(PcbReadError, match="a track subrecord of 35 bytes, fewer than 36"):
        decode_primitives(track(size=35))


def test_footprint_without_parameters() -> None:
    with pytest.raises(PcbReadError, match="names 'FP', which no Parameters stream holds as PATTERN"):
        read_pcblib(library(pad(), parameters=False))


def test_pad_names_component_9_of_3() -> None:
    with pytest.raises(PcbReadError, match="component 9 of 3"):
        read_pcbdoc(document(pad(component=9)))


def test_pad_names_net_4_of_1() -> None:
    with pytest.raises(PcbReadError, match="net 4 of 1"):
        read_pcbdoc(document(pad(net=4)))


def test_pad_name_length() -> None:
    broken = pad().replace(sub(b"\x011"), sub(b"\x021"), 1)
    with pytest.raises(PcbReadError, match="pad name subrecord"):
        decode_primitives(broken)


def test_unknown_record_type() -> None:
    with pytest.raises(PcbReadError, match="unknown record type 7"):
        decode_primitives(bytes((7,)) + sub(b"\0" * 36))


def test_header_count_differs() -> None:
    with pytest.raises(PcbReadError, match="Pads6/Header says 2, the data holds 1"):
        read_pcbdoc(_with_pads_header(2))


def _with_pads_header(count: int) -> bytes:
    pads = pad()
    streams = {
        "FileHeader": struct.pack("<I", 19) + "PCB 5.0 Bi".encode("utf-16-le"),
        "FileHeaderSix": HEADER_SIX,
        "Board6/Header": struct.pack("<I", 1),
        "Board6/Data": prop(KIND="Protel_Advanced_PCB"),
        "Pads6/Header": struct.pack("<I", count),
        "Pads6/Data": pads,
    }
    return write_compound(storage_from_paths(streams))
