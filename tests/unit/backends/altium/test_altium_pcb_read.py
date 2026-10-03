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


def document(pads: bytes, components: int = 3, **extra: bytes) -> bytes:
    """A small document; ``extra`` adds or replaces streams, ``/`` written ``__`` in the keyword."""
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
    streams.update({key.replace("__", "/").replace("_", " "): value for key, value in extra.items()})
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


def one(count: int) -> bytes:
    return struct.pack("<I", count)


def test_board_record_of_two_blocks() -> None:
    two = prop(KIND="Protel_Advanced_PCB") * 2
    with pytest.raises(PcbReadError, match="Board6/Data holds more than one record"):
        read_pcbdoc(document(pad(component=0, net=0), Board6__Data=two))
    with pytest.raises(PcbReadError, match="Board6/Data holds 0 records"):
        read_pcbdoc(document(pad(component=0, net=0), Board6__Data=b""))


def test_board_record_of_lines_keeps_the_first_value() -> None:
    text = b"|LAYER=UNKNOWN|KIND=Protel_Advanced_PCB|LAYER=TOP\r|RECORD=Board|VERSION=5.01\0"
    doc = read_pcbdoc(document(pad(component=0, net=0), Board6__Data=one(len(text)) + text))
    assert doc.board["LAYER"] == "UNKNOWN" and doc.board["VERSION"] == "5.01"
    assert [key for key, _ in doc.board_fields] == ["LAYER", "KIND", "LAYER", "RECORD", "VERSION"]


def test_unique_ids_list_every_pad() -> None:
    block = prop(PRIMITIVEINDEX="0", PRIMITIVEOBJECTID="Pad", UNIQUEID="ABCDEFGH")
    good = document(
        pad(component=0, net=0),
        UniqueIDPrimitiveInformation__Header=one(1),
        UniqueIDPrimitiveInformation__Data=block,
    )
    assert read_pcbdoc(good).unique_ids[0]["UNIQUEID"] == "ABCDEFGH"
    for data in (block * 2, block.replace(b"=Pad", b"=Arc"), block.replace(b"INDEX=0", b"INDEX=1")):
        with pytest.raises(PcbReadError, match="does not list every pad once, in order"):
            read_pcbdoc(
                document(
                    pad(component=0, net=0),
                    UniqueIDPrimitiveInformation__Header=one(1),
                    UniqueIDPrimitiveInformation__Data=data,
                )
            )


def test_option_storage_with_another_record() -> None:
    good = prop(RECORD="PinSwapOptions", QUIET="FALSE")
    doc = read_pcbdoc(
        document(pad(component=0, net=0), Pin_Swap_Options6__Header=one(1), Pin_Swap_Options6__Data=good)
    )
    assert doc.options["Pin Swap Options6"]["QUIET"] == "FALSE"
    for data, header in ((prop(RECORD="Other"), 1), (good * 2, 1)):
        with pytest.raises(PcbReadError, match="Pin Swap Options6/Data is not one property block of PinSwap"):
            read_pcbdoc(
                document(
                    pad(component=0, net=0),
                    Pin_Swap_Options6__Header=one(header),
                    Pin_Swap_Options6__Data=data,
                )
            )
    with pytest.raises(PcbReadError, match="Pin Swap Options6/Header says 0, the data holds 1"):
        read_pcbdoc(
            document(pad(component=0, net=0), Pin_Swap_Options6__Header=one(0), Pin_Swap_Options6__Data=good)
        )


def test_wide_string_storages() -> None:
    version = one(8) + "1.0\0".encode("utf-16-le")
    doc = read_pcbdoc(
        document(
            pad(component=0, net=0),
            LayerKindMapping__Header=one(1),
            LayerKindMapping__Data=version + bytes(8),
        )
    )
    assert doc.storages["LayerKindMapping"][0] == 1
    with pytest.raises(PcbReadError, match="LayerKindMapping/Data is not the version 1.0 and an empty table"):
        read_pcbdoc(
            document(
                pad(component=0, net=0),
                LayerKindMapping__Header=one(1),
                LayerKindMapping__Data=version + bytes(4),
            )
        )
    with pytest.raises(PcbReadError, match="ConstraintManager/Data does not start with a wide string"):
        read_pcbdoc(
            document(
                pad(component=0, net=0),
                ConstraintManager__Header=one(1),
                ConstraintManager__Data=one(3) + b"abc",
            )
        )
    with pytest.raises(PcbReadError, match="ConstraintManager/Data holds bytes after its wide string"):
        read_pcbdoc(
            document(
                pad(component=0, net=0),
                ConstraintManager__Header=one(1),
                ConstraintManager__Data=version + b"\0",
            )
        )
    with pytest.raises(PcbReadError, match="a storage Fenolite does not write holds data"):
        read_pcbdoc(document(pad(component=0, net=0), Texts__Header=one(1), Texts__Data=b"x"))


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


# --- copper (change c0038, "Copper records read back") ---------------------------------------------


def via(
    size: int = 321, layer: int = 74, net: int = 0xFFFF, diameter: int = 236220, hole: int = 118110
) -> bytes:
    """A via as ``pcb-copper.md`` ("Via") lays it out: the prefix, x, y, diameter, hole, start 1, end 32."""
    body = head(layer, net=net) + struct.pack("<4i2B", 10, 20, diameter, hole, 1, 32)
    return bytes((3,)) + sub((body + bytes(size))[:size])


def copper_document(**extra: bytes) -> bytes:
    return document(pad(component=2, net=0), **extra)


def test_via_of_the_copper_page_reads() -> None:
    doc = read_pcbdoc(copper_document(Vias6__Header=one(2), Vias6__Data=via(net=0) + via(size=31)))
    first, second = doc.vias
    assert (first.x, first.y, first.diameter, first.hole) == (10, 20, 236220, 118110)
    assert (first.start_layer, first.end_layer, first.prefix.net, first.size) == (1, 32, 0, 321)
    assert second.size == 31 and second.prefix.net == 0xFFFF


def test_via_of_30_bytes() -> None:
    with pytest.raises(PcbReadError, match="a via subrecord of 30 bytes, fewer than 31"):
        read_pcbdoc(copper_document(Vias6__Header=one(1), Vias6__Data=via(size=30)))


def test_via_on_layer_1() -> None:
    with pytest.raises(PcbReadError, match=r"a via on layer 1, not on Multi-Layer \(74\)"):
        read_pcbdoc(copper_document(Vias6__Header=one(1), Vias6__Data=via(layer=1)))


def test_via_hole_not_below_its_diameter() -> None:
    with pytest.raises(PcbReadError, match="a via hole of 300 units is not below its diameter of 300"):
        read_pcbdoc(copper_document(Vias6__Header=one(1), Vias6__Data=via(diameter=300, hole=300)))


def test_via_names_net_9_of_1() -> None:
    with pytest.raises(PcbReadError, match="Vias6 record 0: net 9 of 1"):
        read_pcbdoc(copper_document(Vias6__Header=one(1), Vias6__Data=via(net=9)))


def test_via_header_count() -> None:
    with pytest.raises(PcbReadError, match="Vias6/Header says 2, the data holds 1 records"):
        read_pcbdoc(copper_document(Vias6__Header=one(2), Vias6__Data=via()))


def routed_track(net: int) -> bytes:
    body = head(1, net=net) + struct.pack("<5iHB", 0, 0, 100, 0, 50, 0, 0)
    return bytes((4,)) + sub(body)


def test_routed_track_is_a_free_track() -> None:
    data = track(component=1) + routed_track(0)
    doc = read_pcbdoc(copper_document(Tracks6__Header=one(2), Tracks6__Data=data))
    assert len(doc.tracks) == 2 and [t.prefix.net for t in doc.free_tracks] == [0] and doc.free_arcs == []


def test_routed_track_names_net_9_of_1() -> None:
    with pytest.raises(PcbReadError, match="Tracks6 record 0: net 9 of 1"):
        read_pcbdoc(copper_document(Tracks6__Header=one(1), Tracks6__Data=routed_track(9)))
