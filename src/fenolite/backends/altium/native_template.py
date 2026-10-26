# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Apply caller-supplied native binary sheet records without neutral drawing conversion (c0164).

Format facts: ``docs/formats/altium/sheet-template.md``, ``schematic-records.md`` and
``schematic-binary.md``. Native and generated owner indices are rebased; graphic coordinates and
original fonts stay fixed.
Readback proves preservation, not Altium's display: application is INFERRED.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.backends.altium.binary import frame_record
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.sch.framing import Frame, deframe, enframe
from fenolite.backends.altium.read.sch.props import Prop, PropertyList, parse
from fenolite.backends.altium.schdot import parameter_record
from fenolite.core.evidence import Evidence, Level

TEMPLATE_PATH = "templates/sheet.SchDot"
TEMPLATE_REFERENCE = TEMPLATE_PATH.replace("/", "\\")
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-RD-SHT-OWNER",))
_FONT = re.compile(r"^(FONTNAME|SIZE|ITALIC|BOLD|UNDERLINE|ROTATION)(\d+)$")
_CIRCUIT = frozenset((1, 2, 15, 17, 18, 22, 25, 26, 27, 29, 37, 43, 44, 45, 46, 48))


def _props(frame: Frame) -> PropertyList:
    if frame.kind != 0:
        raise ValueError("native templates require property-list schematic records")
    return parse(frame.payload.removesuffix(b"\0"))


def _edit(frame: Frame, values: dict[str, bytes]) -> Frame:
    """Change only named fields; retain raw bytes of all other fields, including opaque properties."""
    props = _props(frame)
    changed = dict(values)
    items: list[Prop] = []
    for prop in props.items:
        key = prop.folded
        if key.startswith("%UTF8%") and key[6:] in values:
            continue
        if key in values:
            if key in changed:
                items.append(Prop(prop.key, changed.pop(key)))
        else:
            items.append(prop)
    items.extend(Prop(key, value) for key, value in changed.items())
    suffix = b"\0" if frame.payload.endswith(b"\0") else b""
    return Frame(0, PropertyList(tuple(items)).to_bytes() + suffix, frame.offset)


def _streams(data: bytes) -> dict[str, bytes]:
    compound = open_compound(data)
    names = {"fileheader": "FileHeader", "storage": "Storage", "additional": "Additional"}
    return {names.get(path.casefold(), path): compound.read(path) for path in compound.streams()}


@dataclass(frozen=True, slots=True)
class NativeTemplate:
    """Validated caller data. Storage and opaque stream bytes are never decoded or regenerated."""

    data: bytes
    streams: dict[str, bytes]
    records: tuple[Frame, ...]

    @classmethod
    def read(cls, data: bytes) -> NativeTemplate:
        document = read_schematic(data)
        if document.form != "binary" or document.sheet is None:
            raise ValueError("native application requires a binary .SchDot with a sheet record")
        if document.additional or any(issue.severity == "error" for issue in document.issues):
            raise ValueError("the native template has additional records or invalid record ownership")
        streams = _streams(data)
        records = deframe(streams["FileHeader"], where="FileHeader")[1:]
        sheet_props = _props(records[0])
        for index, record in enumerate(records):
            props = _props(record)
            if props.int("RECORD") in _CIRCUIT or props.int("RECORD") == 39:
                raise ValueError("a native sheet template must not contain circuits or nested templates")
            if props.bool("OWNERINDEXADDITIONALLIST"):
                raise ValueError("a native template cannot reference additional-list owners")
            if props.int("OWNERINDEX", -1) >= index and props.int("OWNERINDEX", -1) > 0:
                raise ValueError("the native template has an invalid owner index")
            for key in ("FONTID", "TEXTFONTID"):
                if props.int(key) > sheet_props.int("FONTIDCOUNT"):
                    raise ValueError("the native template has an invalid font reference")
        return cls(data, streams, records)

    def apply(self, generated: bytes, *, parameters: Sequence[tuple[str, str]] = ()) -> bytes:
        """Template records first, circuit after them, with valid owner and font references."""
        streams = _streams(generated)
        generated_records = deframe(streams["FileHeader"], where="FileHeader")[1:]
        generated_records += tuple(
            Frame(0, frame_record(parameter_record(name, value))[4:], 0) for name, value in parameters
        )
        original_sheet = _props(self.records[0])
        generated_sheet = _props(generated_records[0])
        count = original_sheet.int("FONTIDCOUNT")
        generated_count = generated_sheet.int("FONTIDCOUNT")
        owner = 1
        shift = len(self.records)  # template records plus record 39, minus generated sheet record 0
        settings = {
            "TEMPLATEFILENAME": TEMPLATE_REFERENCE.encode("ascii"),
            "SHOWTEMPLATEGRAPHICS": b"T",
            "FONTIDCOUNT": str(count + generated_count).encode("ascii"),
        }
        for prop in generated_sheet.items:
            match = _FONT.fullmatch(prop.folded)
            if match and prop.raw is not None:
                settings[f"{match[1]}{count + int(match[2])}"] = prop.raw
        # Generated values take precedence without duplicating template defaults.
        defaults: dict[str, Frame] = {}
        for record in generated_records[1:]:
            props = _props(record)
            if props.int("RECORD") == 41 and props.int("OWNERINDEX", -1) <= 0:
                defaults[props.text("NAME").casefold()] = record
        matched: set[str] = set()
        records = [
            _edit(self.records[0], settings),
            Frame(
                0,
                frame_record((("RECORD", "39"), ("FILENAME", TEMPLATE_REFERENCE), ("ISNOTACCESIBLE", "T")))[
                    4:
                ],
                0,
            ),
        ]
        for record in self.records[1:]:
            props = _props(record)
            values: dict[str, bytes] = {}
            if props.int("RECORD") == 41 and props.int("OWNERINDEX", -1) <= 0:
                override = defaults.get(props.text("NAME").casefold())
                if override is not None:
                    matched.add(props.text("NAME").casefold())
                    source = _props(override)
                    values["TEXT"] = source.raw("TEXT") or b""
                    for key in ("TEXT", "%UTF8%TEXT"):
                        value = source.raw(key)
                        if value is not None:
                            values[key] = value
            elif props.int("OWNERINDEX", -1) <= 0:
                values["OWNERINDEX"] = str(owner).encode("ascii")
            else:
                values["OWNERINDEX"] = str(props.int("OWNERINDEX") + 1).encode("ascii")
            records.append(_edit(record, values) if values else record)
        # Skip overridden defaults and map every owner explicitly: a parameter before a component
        # must not shift the component's children onto another record.
        kept: list[tuple[int, Frame]] = []
        for index, record in enumerate(generated_records[1:], 1):
            props = _props(record)
            if (
                props.int("RECORD") == 41
                and props.int("OWNERINDEX", -1) <= 0
                and props.text("NAME").casefold() in matched
            ):
                continue
            kept.append((index, record))
        indices = {0: 0, **{index: len(records) + at for at, (index, _) in enumerate(kept)}}
        for _, record in kept:
            moved = self._generated(record, shift=shift, fonts=count)
            props = _props(record)
            if props.has("OWNERINDEX") and props.int("OWNERINDEX", -1) >= 0:
                old = props.int("OWNERINDEX")
                if old not in indices:
                    raise ValueError("generated schematic refers to a replaced parameter")
                moved = _edit(moved, {"OWNERINDEX": str(indices[old]).encode("ascii")})
            records.append(moved)
        header = deframe(self.streams["FileHeader"], where="FileHeader")[0]
        streams["FileHeader"] = enframe(
            (_edit(header, {"WEIGHT": str(len(records)).encode("ascii")}), *records)
        )
        if "Additional" in streams:
            additional = deframe(streams["Additional"], where="Additional")
            streams["Additional"] = enframe(
                (additional[0], *(self._generated(r, shift=0, fonts=count) for r in additional[1:]))
            )
        # The generated circuit has no embedded images. Retain all native storage verbatim.
        for path, data in self.streams.items():
            if path == "FileHeader":
                continue
            if path == "Additional" and path in streams:
                continue  # read() proved the template's Additional holds no schematic records
            if path in streams and path != "Storage" and streams[path] != data:
                raise ValueError(f"native template stream conflicts with generated stream {path}")
            streams[path] = data
        return write_compound(tuple(streams.items()))

    @staticmethod
    def _generated(record: Frame, *, shift: int, fonts: int) -> Frame:
        props = _props(record)
        values: dict[str, bytes] = {}
        for key in ("OWNERINDEX", "INDEXINSHEET"):
            if props.has(key) and props.int(key, -1) >= 0:
                values[key] = str(props.int(key) + shift).encode("ascii")
        for key in ("FONTID", "TEXTFONTID"):
            if props.has(key) and props.int(key) > 0:
                values[key] = str(props.int(key) + fonts).encode("ascii")
        return _edit(record, values) if values else record
