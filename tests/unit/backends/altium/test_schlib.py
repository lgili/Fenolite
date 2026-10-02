# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic library writer (capability altium-schematic-writer, "Binary pin record", "Schematic
library file", "Library component records", "Generic library symbols", "Library and storage names" and
"Schematic libraries read back"; change c0034).

Libraries are read back with ``tests/_altium_read.py`` (``read_schlib``), written from
``docs/formats/altium/schematic-library.md``; each check of the reader has a negative control here.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from functools import cache

import pytest
from _altium import dual_symbol, sample_model
from _altium_read import LibRecord, ReadError, read_schlib
from _cfb_read import parse_compound, read_compound

from fenolite.backends.altium.altsym import AltiumPin, AltiumRect, AltiumSymbol, from_symbol_def
from fenolite.backends.altium.binary import frame_record, storage_stream
from fenolite.backends.altium.cfb import Entry, Storage, storage_from_paths, write_compound
from fenolite.backends.altium.project import generic_symbols, schlib_name, storage_name, unique_id
from fenolite.backends.altium.schlib import HEADER_TEXT, data_stream, pin_record, write_schlib

LIBRARY = "FenoliteSample.SchLib"


@cache
def sample_symbols() -> dict[str, AltiumSymbol]:
    return generic_symbols(sample_model())


@cache
def sample_library() -> bytes:
    return write_schlib(list(sample_symbols().values()), library=LIBRARY)


# --- binary pins ------------------------------------------------------------------------------------


def worked_pin() -> AltiumPin:
    return AltiumPin("1", "IN", part=1, x=-300, y=100, direction=2, length=200, electrical=4)


def test_worked_pin() -> None:
    expected = (
        "22000001 02000000 00 0100 00 00000000 00 01 04 1a 1400 e2ff 0a00 00000000 02494e 0131 00 00 00"
    )
    assert pin_record(worked_pin()).hex() == expected.replace(" ", "")


@pytest.mark.parametrize(
    "change",
    [
        {"name": "x" * 256},
        {"designator": "1" * 256},
        {"x": 400_000},
        {"length": -400_000},
        {"x": 5},
        {"inner_edge": 256},
        {"electrical": -1},
        {"part": 40_000},
        {"name": "é"},
    ],
)
def test_pin_refusals(change: dict[str, object]) -> None:
    fields = {**worked_pin().__dict__, **change}
    with pytest.raises(ValueError):
        pin_record(AltiumPin(**fields))  # type: ignore[arg-type]


# --- names ------------------------------------------------------------------------------------------


def test_names() -> None:
    assert schlib_name("Device:R", design="board") == "board.SchLib"
    assert schlib_name("My.schlib:R", design="board") == "My.schlib"
    assert storage_name("A" * 40) == "A" * 31
    assert storage_name("RES") == "RES"
    assert storage_name("A/B") == "A_B"
    with pytest.raises(ValueError):
        storage_name("A:B")
    with pytest.raises(ValueError):
        storage_name("")
    with pytest.raises(ValueError):
        schlib_name("NOCOLON", design="board")


def test_storage_name_collision() -> None:
    symbol = sample_symbols()["FenoliteSample.SchLib:RES"]
    other = AltiumSymbol("res", 1, symbol.pins, symbol.rectangles, "R", "res")
    with pytest.raises(ValueError, match="one storage name"):
        write_schlib([symbol, other], library=LIBRARY)


# --- the sample's library ---------------------------------------------------------------------------


def test_generic_resistor_of_the_sample() -> None:
    res = sample_symbols()["FenoliteSample.SchLib:RES"]
    pins = {p.designator: p for p in res.pins}
    assert (pins["1"].x, pins["1"].y, pins["1"].direction) == (0, -100, 2)
    assert (pins["2"].x, pins["2"].y, pins["2"].direction) == (600, -100, 0)
    assert all(p.length == 200 and p.electrical == 4 and p.part == 1 for p in res.pins)
    assert res.rectangles == (AltiumRect(1, 0, -200, 600, 0),)
    assert res.prefix == "R"
    assert res.footprint == ("FenoliteSample.PcbLib", "R0603")


def test_library_of_the_sample() -> None:
    found = parse_compound(sample_library())
    names = ["CAP", "DRV4", "HDR2", "LDO3", "LED", "RES"]
    assert sorted(found.streams) == sorted(["FileHeader", "Storage", *(f"{n}/Data" for n in names)])
    assert sorted(found.storages) == names
    assert "SectionKeys" not in found.streams
    library = read_schlib(sample_library())
    assert list(library) == ["CAP", "LED", "RES", "DRV4", "HDR2", "LDO3"]  # MS-CFB order


def _header(data: bytes) -> dict[str, str]:
    stream = read_compound(data)["FileHeader"]
    (length,) = struct.unpack_from("<I", stream, 0)
    assert len(stream) == 4 + length, "nothing follows the header record"
    text = stream[4:-1].decode("ascii")
    return dict(f.split("=", 1) for f in text[1:].split("|"))


def test_header_keys() -> None:
    data = sample_library()
    stream = read_compound(data)["FileHeader"]
    assert stream[4:].startswith(f"|HEADER={HEADER_TEXT}|WEIGHT=".encode("ascii"))
    header = _header(data)
    assert header["COMPCOUNT"] == "6"
    refs = [header[f"LIBREF{i}"] for i in range(6)]
    assert refs == list(read_schlib(data))
    assert all(header[f"PARTCOUNT{i}"] == "2" for i in range(6))
    assert (header["FONTIDCOUNT"], header["SIZE1"], header["FONTNAME1"]) == ("1", "10", "Times New Roman")
    records = sum(len(r) for r in read_schlib(data).values())
    assert header["WEIGHT"] == str(records + 1)
    assert read_compound(data)["Storage"] == storage_stream()


def test_records_of_res() -> None:
    records = read_schlib(sample_library())["RES"]
    kinds = [str(r["RECORD"]) for r in records]
    assert kinds == ["1", "2", "2", "14", "34", "41", "44", "45", "46", "48"]
    component = records[0]
    assert component["LIBREFERENCE"] == "RES" and component["PARTCOUNT"] == "2"
    assert component["UNIQUEID"] == unique_id(f"schlib:{LIBRARY}:RES")
    assert component["DESIGNITEMID"] == "RES" and "COMPONENTDESCRIPTION" not in component
    assert [r["DESIGNATOR"] for r in records[1:3]] == ["1", "2"]
    assert all(r.get("BINARY") for r in records[1:3])
    assert records[3]["OWNERPARTID"] == "1"
    assert (records[3]["LOCATION.X"], records[3]["LOCATION.Y"]) == ("0", "-20")
    assert (records[3]["CORNER.X"], records[3]["CORNER.Y"]) == ("60", "0")
    assert records[4]["TEXT"] == "R?" and records[4]["LOCATION.Y"] == "10"
    assert records[5]["NAME"] == "Comment" and records[5]["LOCATION.Y"] == "-40"
    assert records[7]["MODELNAME"] == "R0603" and records[7]["MODELDATAFILE0"] == "FenoliteSample.PcbLib"
    assert all("OWNERINDEX" not in r for r in records)


def test_pins_decode_field_by_field() -> None:
    pin = read_schlib(sample_library())["RES"][1]
    expected = {
        "OWNERPARTID": 1,
        "OWNERPARTDISPLAYMODE": 0,
        "SYMBOL_INNEREDGE": 0,
        "SYMBOL_OUTEREDGE": 0,
        "DESCRIPTION": "",
        "FORMALTYPE": 1,
        "ELECTRICAL": 4,
        "PINCONGLOMERATE": 2 | 0x10,
        "PINLENGTH": 20,
        "LOCATION.X": 0,
        "LOCATION.Y": -10,
        "COLOR": 0,
        "NAME": "1",
        "DESIGNATOR": "1",
        "SWAPIDGROUP": "",
        "PARTANDSEQUENCE": "",
        "DEFAULTVALUE": "",
    }
    assert {k: pin[k] for k in expected} == expected


def test_bytes_depend_only_on_symbols_and_library() -> None:
    symbols = list(sample_symbols().values())
    assert write_schlib(list(reversed(symbols)), library=LIBRARY) == sample_library()
    assert write_schlib(symbols, library="Other.SchLib") != sample_library()


# --- section keys -----------------------------------------------------------------------------------


def test_section_key() -> None:
    res = sample_symbols()["FenoliteSample.SchLib:RES"]
    long = AltiumSymbol("L" * 40, 1, res.pins, res.rectangles, "R", "long")
    data = write_schlib([res, long], library=LIBRARY)
    streams = read_compound(data)
    assert "SectionKeys" in streams and f"{'L' * 31}/Data" in streams
    library = read_schlib(data)
    assert library["L" * 31][0]["LIBREFERENCE"] == "L" * 40


# --- a mapped dual-unit symbol ----------------------------------------------------------------------


def test_round_trip_of_a_mapped_symbol() -> None:
    symbol = from_symbol_def(dual_symbol(), lib_ref="DUAL", footprint=None)
    records = read_schlib(write_schlib([symbol], library="board.SchLib"))["DUAL"]
    kinds = [str(r["RECORD"]) for r in records]
    assert kinds == ["1", *["2"] * 8, "14", "14", "34", "41"]
    assert records[0]["PARTCOUNT"] == "3"
    for pin, record in zip(symbol.pins, records[1:9], strict=True):
        assert record["DESIGNATOR"] == pin.designator and record["NAME"] == pin.name
        assert record["OWNERPARTID"] == pin.part and record["ELECTRICAL"] == pin.electrical
        assert record["PINCONGLOMERATE"] == pin.conglomerate
        assert (record["LOCATION.X"], record["LOCATION.Y"]) == (pin.x // 10, pin.y // 10)
        assert record["PINLENGTH"] == pin.length // 10
        assert (record["SYMBOL_INNEREDGE"], record["SYMBOL_OUTEREDGE"]) == (pin.inner_edge, pin.outer_edge)
    assert [r["OWNERPARTID"] for r in records[9:11]] == ["1", "2"]


# --- reader negative controls -----------------------------------------------------------------------


def _rebuild(change: Callable[[dict[str, bytes]], None]) -> bytes:
    """The sample's library with its streams changed by ``change``, rebuilt with ``write_compound``."""
    streams = dict(read_compound(sample_library()))
    change(streams)
    entries: list[Entry] = list(storage_from_paths(streams))
    return write_compound(entries)


def _replace_record(stream: bytes, index: int, new: bytes) -> bytes:
    out: list[bytes] = []
    offset = 0
    while offset < len(stream):
        (word,) = struct.unpack_from("<I", stream, offset)
        end = offset + 4 + (word & 0xFFFFFF)
        out.append(new if len(out) == index else stream[offset:end])
        offset = end
    return b"".join(out)


def _fields(stream: bytes) -> dict[str, str]:
    text = stream[4:-1].decode("ascii")
    return dict(f.split("=", 1) for f in text[1:].split("|"))


def _header_with(**changes: str) -> Callable[[dict[str, bytes]], None]:
    def change(streams: dict[str, bytes]) -> None:
        fields = {**_fields(streams["FileHeader"]), **changes}
        streams["FileHeader"] = frame_record(list(fields.items()))

    return change


def _set(path: str, value: bytes) -> Callable[[dict[str, bytes]], None]:
    def change(streams: dict[str, bytes]) -> None:
        streams[path] = value

    return change


def _drop_strings(streams: dict[str, bytes]) -> None:
    pin = pin_record(sample_symbols()["FenoliteSample.SchLib:RES"].pins[0])
    payload = pin[4:-2]
    streams["RES/Data"] = _replace_record(
        streams["RES/Data"], 1, struct.pack("<I", 1 << 24 | len(payload)) + payload
    )


def _pin_id(streams: dict[str, bytes]) -> None:
    pin = bytearray(pin_record(sample_symbols()["FenoliteSample.SchLib:RES"].pins[0]))
    pin[4] = 3
    streams["RES/Data"] = _replace_record(streams["RES/Data"], 1, bytes(pin))


def _first_not_component(streams: dict[str, bytes]) -> None:
    data = streams["RES/Data"]
    (word,) = struct.unpack_from("<I", data, 0)
    first = data[: 4 + (word & 0xFFFFFF)]
    streams["RES/Data"] = data[len(first) :] + first


def _two_header_records(streams: dict[str, bytes]) -> None:
    streams["FileHeader"] += frame_record([("X", "1")])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_header_with(HEADER="Protel for Windows - Schematic Capture Binary File Version 5.0"), "header"),
        (_header_with(COMPCOUNT="5"), "COMPCOUNT=5"),
        (_header_with(LIBREF0="NOPE"), "LIBREF"),
        (_header_with(WEIGHT="7"), "WEIGHT=7"),
        (_set("RES/PinFrac", b"x"), "not exactly Data"),
        (_first_not_component, "first record"),
        (_drop_strings, "short string"),
        (_pin_id, "record id 3"),
        (_two_header_records, "not exactly the header record"),
        (_set("Extra", b"x"), "unexpected streams"),
    ],
)
def test_reader_negative_controls(change: Callable[[dict[str, bytes]], None], message: str) -> None:
    with pytest.raises(ReadError, match=message):
        read_schlib(_rebuild(change))


def test_stray_byte_caught() -> None:
    def stray(streams: dict[str, bytes]) -> None:
        streams["RES/Data"] += b"\0"

    with pytest.raises(ReadError, match="RES/Data"):
        read_schlib(_rebuild(stray))


def test_pin_with_a_byte_left_over() -> None:
    pin = pin_record(worked_pin())
    payload = pin[4:] + b"\0"
    bad = struct.pack("<I", 1 << 24 | len(payload)) + payload
    symbol = sample_symbols()["FenoliteSample.SchLib:RES"]
    data = data_stream(symbol, library=LIBRARY)
    data = _replace_record(data, 1, bad)
    library = write_compound(
        [("FileHeader", read_compound(sample_library())["FileHeader"]), Storage("X", (("Data", data),))]
    )
    with pytest.raises(ReadError):
        read_schlib(library)


def test_reader_returns_records() -> None:
    library: dict[str, list[LibRecord]] = read_schlib(sample_library())
    assert all(records[0]["RECORD"] == "1" for records in library.values())
