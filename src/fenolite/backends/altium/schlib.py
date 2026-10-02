# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic library file (``.SchLib``) of the Altium writer (change c0034, capability
altium-schematic-writer, "Schematic library file", "Library component records" and "Binary pin record").

Written from ``docs/formats/altium/schematic-library.md``. A library is a compound file (``cfb``): the
streams ``FileHeader`` (one header record listing the components), ``Storage`` (the empty icon storage),
``SectionKeys`` only when a lib ref needs a section key, then one storage per symbol, in the MS-CFB order
of the storage names, holding one stream ``Data``: the component, its binary pins, one rectangle per
part, the designator, the comment and the footprint chain. No record carries ``OWNERINDEX``: every record
after the component belongs to it. The bytes depend only on the symbols and the library name.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from fenolite.backends.altium.altsym import AltiumPin, AltiumSymbol
from fenolite.backends.altium.ascii import Field
from fenolite.backends.altium.binary import frame_record, storage_stream
from fenolite.backends.altium.cfb import FORBIDDEN, MAX_NAME, Entry, Storage, name_key, write_compound
from fenolite.core.evidence import Evidence, Level

HEADER_TEXT = "Protel for Windows - Schematic Library Editor Binary File Version 5.0"
"""The value of the library header's ``HEADER`` key."""
FONT_NAME = "Times New Roman"
FONT_SIZE = 10
FILE_HEADER_STREAM = "FileHeader"
STORAGE_STREAM = "Storage"
SECTION_KEYS_STREAM = "SectionKeys"
DATA_STREAM = "Data"
BINARY = 1
"""The record type of a binary record, in the top byte of the length word."""
PIN_RECORD = 2
FORMALTYPE = 1
"""S-0130's value; S-0150 (version 1) writes 0 (``H-A-SCHLIB-PIN``)."""
COMPONENT_COLOR = "128"
COMPONENT_FILL = "11599871"
TEXT_COLOR = "8388608"
MILS_PER_UNIT = 10
DESIGNATOR_RISE = 100
COMMENT_DROP = 200
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-SCHLIB-IMPLIDX",
        "H-A-SCHLIB-KICAD",
        "H-A-SCHLIB-OPEN",
        "H-A-SCHLIB-PARTS",
        "H-A-SCHLIB-PIN",
        "H-A-SCHLIB-SECTIONKEY",
    ),
)
"""The library is inferred from public sources; the kicad-cli oracle checks only what KiCad reads."""

_INT16 = (-32768, 32767)


def storage_name(lib_ref: str) -> str:
    """The storage name of a symbol: ``lib_ref`` when it is a valid compound-file name, else its section
    key (``/`` replaced by ``_``, cut to 31 characters); ``ValueError`` when the key is still invalid."""
    if not lib_ref:
        raise ValueError("a lib ref cannot be empty")
    if len(lib_ref) <= MAX_NAME and not any(ch in FORBIDDEN for ch in lib_ref):
        return lib_ref
    key = lib_ref.replace("/", "_")[:MAX_NAME]
    if any(ch in FORBIDDEN for ch in key):
        raise ValueError(f"the lib ref {lib_ref!r} holds one of \\ : !, which no storage name may hold")
    return key


def _units(mils: int, what: str) -> int:
    if mils % MILS_PER_UNIT:
        raise ValueError(f"{what}: {mils} mil is not a multiple of {MILS_PER_UNIT} mil")
    units = mils // MILS_PER_UNIT
    if not _INT16[0] <= units <= _INT16[1]:
        raise ValueError(f"{what}: {units} units lie outside the signed 16-bit range")
    return units


def _coord(name: str, x: int, y: int) -> tuple[Field, Field]:
    """``<name>.X`` and ``<name>.Y`` of a symbol-relative point in mils (negative values allowed)."""
    return (f"{name}.X", str(_units(x, name))), (f"{name}.Y", str(_units(y, name)))


def _short(text: str, what: str) -> bytes:
    try:
        data = text.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(f"{what} {text!r} is not 7-bit ASCII") from None
    if len(data) > 255:
        raise ValueError(f"{what} {text[:20]!r}… has {len(data)} bytes, more than a short string holds")
    return bytes((len(data),)) + data


def _byte(value: int, what: str) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"{what} {value} lies outside 0 … 255")
    return value


def pin_record(pin: AltiumPin) -> bytes:
    """One framed binary pin record: the word ``(1 << 24) | <length>``, then the payload, without a NUL."""
    where = f"pin {pin.designator}"
    if not _INT16[0] <= pin.part <= _INT16[1]:
        raise ValueError(f"{where}: part {pin.part} lies outside the signed 16-bit range")
    payload = b"".join(
        (
            struct.pack("<iBhB", PIN_RECORD, 0, pin.part, 0),
            bytes(
                (
                    _byte(pin.inner_edge, f"{where} inner-edge code"),
                    _byte(pin.outer_edge, f"{where} outer-edge code"),
                    0,
                    0,
                )
            ),
            _short("", "description"),
            bytes(
                (
                    FORMALTYPE,
                    _byte(pin.electrical, f"{where} electrical type"),
                    _byte(pin.conglomerate, f"{where} conglomerate"),
                )
            ),
            struct.pack(
                "<hhhI",
                _units(pin.length, f"{where} length"),
                _units(pin.x, f"{where} x"),
                _units(pin.y, f"{where} y"),
                0,
            ),
            _short(pin.name, f"{where} name"),
            _short(pin.designator, f"{where} designator"),
            _short("", "swap group"),
            _short("", "part and sequence"),
            _short("", "default value"),
        )
    )
    return struct.pack("<I", BINARY << 24 | len(payload)) + payload


def footprint_chain(library: str, footprint: str) -> list[list[Field]]:
    """The records 44, 45, 46 and 48 of a footprint model, without owner keys (0-based data file keys)."""
    return [
        [("RECORD", "44")],
        [
            ("RECORD", "45"),
            ("MODELNAME", footprint),
            ("MODELTYPE", "PCBLIB"),
            ("DATAFILECOUNT", "1"),
            ("MODELDATAFILEENTITY0", footprint),
            ("MODELDATAFILEKIND0", "PCBLIB"),
            ("MODELDATAFILE0", library),
            ("ISCURRENT", "T"),
        ],
        [("RECORD", "46")],
        [("RECORD", "48")],
    ]


def component_record(symbol: AltiumSymbol, *, library: str) -> list[Field]:
    """``RECORD=1`` of a library component."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    record: list[Field] = [("RECORD", "1"), ("LIBREFERENCE", symbol.lib_ref)]
    if symbol.description:
        record.append(("COMPONENTDESCRIPTION", symbol.description))
    record += [
        ("PARTCOUNT", str(symbol.parts + 1)),
        ("DISPLAYMODECOUNT", "1"),
        ("OWNERPARTID", "-1"),
        ("CURRENTPARTID", "1"),
        ("UNIQUEID", unique_id(f"schlib:{library}:{symbol.lib_ref}")),
        ("DESIGNITEMID", symbol.lib_ref),
        ("COLOR", COMPONENT_COLOR),
        ("AREACOLOR", COMPONENT_FILL),
    ]
    return record


def data_records(symbol: AltiumSymbol, *, library: str) -> list[bytes]:
    """Every framed record of the symbol's ``Data`` stream, in order."""
    if symbol.parts < 1 or [r.part for r in symbol.rectangles] != list(range(1, symbol.parts + 1)):
        raise ValueError(f"{symbol.lib_ref}: one rectangle per part 1 … {symbol.parts} is needed")
    records = [frame_record(component_record(symbol, library=library))]
    records += [pin_record(pin) for pin in symbol.pins]
    for rect in symbol.rectangles:
        fields: list[Field] = [
            ("RECORD", "14"),
            ("OWNERPARTID", str(rect.part)),
            *_coord("LOCATION", rect.x0, rect.y0),
            *_coord("CORNER", rect.x1, rect.y1),
            ("LINEWIDTH", "1"),
            ("COLOR", COMPONENT_COLOR),
            ("AREACOLOR", COMPONENT_FILL),
            ("ISSOLID", "T"),
        ]
        records.append(frame_record(fields))
    first = symbol.rectangle(1)
    for kind, name, text, y in (
        ("34", "Designator", f"{symbol.prefix}?", first.y1 + DESIGNATOR_RISE),
        ("41", "Comment", symbol.comment, first.y0 - COMMENT_DROP),
    ):
        fields = [
            ("RECORD", kind),
            ("OWNERPARTID", "-1"),
            ("NAME", name),
            ("TEXT", text),
            *_coord("LOCATION", first.x0, y),
            ("FONTID", "1"),
            ("COLOR", TEXT_COLOR),
        ]
        records.append(frame_record(fields))
    if symbol.footprint is not None:
        records += [frame_record(r) for r in footprint_chain(*symbol.footprint)]
    return records


def data_stream(symbol: AltiumSymbol, *, library: str) -> bytes:
    """The ``Data`` stream of ``symbol`` in the library file ``library``."""
    return b"".join(data_records(symbol, library=library))


def ordered(symbols: Sequence[AltiumSymbol]) -> list[AltiumSymbol]:
    """``symbols`` in the MS-CFB order of their storage names; ``ValueError`` for two equal names."""
    keyed = sorted(symbols, key=lambda s: name_key(storage_name(s.lib_ref)))
    for before, after in zip(keyed, keyed[1:], strict=False):
        if name_key(storage_name(before.lib_ref)) == name_key(storage_name(after.lib_ref)):
            raise ValueError(
                f"the symbols {before.lib_ref!r} and {after.lib_ref!r} get one storage name under the "
                "MS-CFB order"
            )
    return keyed


def header_record(symbols: Sequence[AltiumSymbol], weight: int) -> list[Field]:
    """The library header: text, weight, one font, then the component list."""
    record: list[Field] = [
        ("HEADER", HEADER_TEXT),
        ("WEIGHT", str(weight)),
        ("FONTIDCOUNT", "1"),
        ("SIZE1", str(FONT_SIZE)),
        ("FONTNAME1", FONT_NAME),
        ("COMPCOUNT", str(len(symbols))),
    ]
    for index, symbol in enumerate(symbols):
        record.append((f"LIBREF{index}", symbol.lib_ref))
        if symbol.description:
            record.append((f"COMPDESCR{index}", symbol.description))
        record.append((f"PARTCOUNT{index}", str(symbol.parts + 1)))
    return record


def write_schlib(symbols: Sequence[AltiumSymbol], *, library: str) -> bytes:
    """The bytes of the schematic library ``library`` holding ``symbols``.

    ``ValueError`` for an invalid or repeated storage name, an unwritable text or value;
    ``cfb.CompoundTooLarge`` past the compound file's size limit.
    """
    symbols = ordered(symbols)
    streams = {s.lib_ref: data_records(s, library=library) for s in symbols}
    weight = sum(len(records) for records in streams.values()) + 1
    entries: list[Entry] = [
        (FILE_HEADER_STREAM, frame_record(header_record(symbols, weight))),
        (STORAGE_STREAM, storage_stream()),
    ]
    keyed = [s for s in symbols if storage_name(s.lib_ref) != s.lib_ref]
    if keyed:
        keys: list[Field] = [("KEYCOUNT", str(len(keyed)))]
        for index, symbol in enumerate(keyed):
            keys += [(f"LIBREF{index}", symbol.lib_ref), (f"SECTIONKEY{index}", storage_name(symbol.lib_ref))]
        entries.append((SECTION_KEYS_STREAM, frame_record(keys)))
    for symbol in symbols:
        data = b"".join(streams[symbol.lib_ref])
        entries.append(Storage(storage_name(symbol.lib_ref), ((DATA_STREAM, data),)))
    return write_compound(entries)


__all__ = [
    "EVIDENCE",
    "FORMALTYPE",
    "HEADER_TEXT",
    "component_record",
    "data_records",
    "data_stream",
    "footprint_chain",
    "header_record",
    "ordered",
    "pin_record",
    "storage_name",
    "write_schlib",
]
