# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader of Altium schematic libraries (``.SchLib``), change c0040.

``read_schlib(data)`` reads the library header, the section keys and one component per storage into a
``SchLibrary``. Each component keeps its ``Data`` records (property lists and binary pins) with an owner
tree, its pin side streams and any other stream as bytes. ``PinFrac`` is decoded when it matches the layout of
``docs/formats/altium/schematic-library.md`` to its last byte; the other side streams stay opaque. Nothing is
lost: ``encode_stream`` rebuilds ``FileHeader``, ``SectionKeys``, ``Storage`` and every ``Data`` stream.
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from typing import TypeVar

from fenolite.backends.altium.read.sch import _container
from fenolite.backends.altium.read.sch._build import (
    Context,
    check_parts,
    frame_record,
    header_record,
    link,
    settle,
)
from fenolite.backends.altium.read.sch._build import record_bytes as _record_bytes
from fenolite.backends.altium.read.sch.document import (
    BINARY_HEADER,
    LIBRARY_HEADER,
    EmbeddedFile,
    embedded_file,
    filter_children,
)
from fenolite.backends.altium.read.sch.framing import Frame, deframe, enframe
from fenolite.backends.altium.read.sch.issues import IssueLog
from fenolite.backends.altium.read.sch.props import DEFAULT_CODEPAGE, check_codepage, parse, parse_int
from fenolite.backends.altium.read.sch.records import (
    Component,
    Font,
    Pin,
    PropertyRecord,
    RecordRef,
    SchRecord,
    UnknownRecord,
    read_fonts,
)
from fenolite.core.errors import FormatError, Issue

SIDE_STREAMS = ("PinFrac", "PinWideText", "PinTextData", "PinSymbolLineWidth")
"""The pin side streams of a component storage; the spellings with ``Pins`` are the same streams."""
SIDE_STREAMS_DECODED: tuple[str, ...] = ("PinFrac",)
"""The side streams the reader decodes; each has a layout row with a permitted source."""
FRAC_MARK = 0xD0
FRAC_SIZE = 12
_SIDE_NAMES = {name.upper(): name for name in SIDE_STREAMS} | {
    name.upper().replace("PIN", "PINS", 1): name for name in SIDE_STREAMS
}

R = TypeVar("R", bound=SchRecord)


@dataclass(frozen=True, slots=True)
class SchLibComponent:
    """One component storage: ``name`` (the header's lib ref, else ``LIBREFERENCE``, else the storage name),
    its ``Data`` records with owners, its side streams and other streams as bytes."""

    name: str
    storage_name: str
    description: str
    records: tuple[SchRecord, ...]
    side_streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    extra_streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    data: bytes = b""

    @property
    def component(self) -> Component | None:
        first = self.records[0] if self.records else None
        return first if isinstance(first, Component) else None

    @property
    def pins(self) -> tuple[Pin, ...]:
        return tuple(record for record in self.records if isinstance(record, Pin))

    @property
    def part_count(self) -> int:
        component = self.component
        return 1 if component is None else component.part_count

    @property
    def display_mode_count(self) -> int:
        component = self.component
        return 1 if component is None else component.display_mode_count

    @property
    def parts(self) -> range:
        return range(1, self.part_count + 1)

    @property
    def modes(self) -> range:
        return range(self.display_mode_count)

    def get(self, ref: RecordRef) -> SchRecord:
        return self.records[ref.index]

    def children(self, part: int | None = None, mode: int | None = None) -> tuple[SchRecord, ...]:
        """The direct children of the component record, filtered by part and display mode as
        ``SchDocument.children_of`` filters them."""
        if not self.records:
            return ()
        return filter_children(tuple(self.get(ref) for ref in self.records[0].children), part, mode)

    def of_type(self, cls: type[R]) -> tuple[R, ...]:
        return tuple(record for record in self.records if isinstance(record, cls))


@dataclass(frozen=True, slots=True)
class SchLibrary:
    """A schematic library as read."""

    file: str
    codepage: str
    header: PropertyRecord
    header_tail: bytes
    listed_names: tuple[str, ...]
    components: tuple[SchLibComponent, ...]
    section_keys_records: tuple[SchRecord, ...] = ()
    section_keys: dict[str, str] = field(default_factory=dict[str, str], hash=False)
    storage_header: PropertyRecord | None = None
    embedded: tuple[EmbeddedFile, ...] = ()
    streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    extra_streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    issues: tuple[Issue, ...] = ()

    @property
    def fonts(self) -> tuple[Font, ...]:
        return read_fonts(self.header.props)

    def get(self, name: str) -> SchLibComponent:
        """The component whose lib ref is ``name``, compared without letter case; ``KeyError`` otherwise."""
        folded = name.casefold()
        for component in self.components:
            if component.name.casefold() == folded:
                return component
        raise KeyError(name)

    def stream_mismatches(self) -> tuple[str, ...]:
        return check_library(self)

    def census(self) -> dict[str, object]:
        from fenolite.backends.altium.read.sch.census import library_census

        return library_census(self)


# --- reading ----------------------------------------------------------------------------------------------


def read_schlib(
    data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None
) -> SchLibrary:
    """Read a schematic library. Raises ``FormatError`` only when no result can be returned."""
    codec = check_codepage(codepage)
    if not _container.is_compound(data):
        raise FormatError("not a compound file, so not a schematic library", file=file, locator="", offset=0)
    log = IssueLog()
    ctx = Context(codec, log)
    compound = _container.open_container(data, file=file, issues=log.items)
    streams = _container.root_streams(compound)
    if "FILEHEADER" not in streams:
        raise FormatError("the stream FileHeader is missing", file=file, locator="FileHeader")
    read: dict[str, bytes] = {}
    path = streams["FILEHEADER"]
    read[path] = compound.read(path)
    header, tail = _library_header(read[path], file=file, ctx=ctx)
    listed_names = _name_list(tail, codec)

    section_records: tuple[SchRecord, ...] = ()
    section_keys: dict[str, str] = {}
    if "SECTIONKEYS" in streams:
        path = streams["SECTIONKEYS"]
        read[path] = compound.read(path)
        section_records = _stream_records(read[path], name="SectionKeys", file=file, ctx=ctx)
        section_keys = _section_keys(section_records, ctx)

    storage_header: PropertyRecord | None = None
    embedded: list[EmbeddedFile] = []
    if "STORAGE" in streams:
        path = streams["STORAGE"]
        read[path] = compound.read(path)
        storage_header, embedded = _storage(read[path], file=file, ctx=ctx)

    extra: dict[str, bytes] = {}
    known = {streams[name] for name in ("FILEHEADER", "SECTIONKEYS", "STORAGE") if name in streams}
    for stream_path in streams.values():
        if stream_path in known:
            continue
        extra[stream_path] = compound.read(stream_path)
        log.add(
            "altium.sch.unknown-stream", f"stream {stream_path} is kept as bytes and not read", stream_path
        )

    storages: dict[str, tuple[tuple[str, str], ...]] = {}
    for storage in _container.root_storages(compound):
        inside = _container.storage_streams(compound, storage)
        if not any(name.upper() == "DATA" for name, _ in inside):
            for _, stream_path in inside:
                extra[stream_path] = compound.read(stream_path)
                log.add(
                    "altium.sch.unknown-stream",
                    f"storage {storage} holds no Data stream; its stream {stream_path} is kept as bytes",
                    stream_path,
                )
            continue
        storages[storage] = inside

    order, listed = _order(header, section_keys, tuple(storages), ctx)
    components: list[SchLibComponent] = []
    for storage in order:
        lib_ref, description = listed.get(storage, ("", ""))
        component = _component(compound, storage, storages[storage], lib_ref, description, read, file, ctx)
        components.append(component)
        if storage not in listed:
            log.add(
                "altium.schlib.unlisted-component",
                f"storage {storage} holds a component that the header does not list",
                storage,
            )
    _counts(header, components, ctx)
    library = SchLibrary(
        file=file,
        codepage=codec,
        header=header,
        header_tail=tail,
        listed_names=listed_names,
        components=tuple(components),
        section_keys_records=section_records,
        section_keys=section_keys,
        storage_header=storage_header,
        embedded=tuple(embedded),
        streams=read,
        extra_streams=extra,
        issues=tuple(log.items),
    )
    if issues is not None:
        issues.extend(library.issues)
    return library


def _library_header(stream: bytes, *, file: str, ctx: Context) -> tuple[PropertyRecord, bytes]:
    """The header record of ``FileHeader`` and the bytes after it."""
    locator = "FileHeader/record 0"
    if len(stream) < 4:
        raise FormatError("the stream FileHeader holds no record", file=file, locator=locator, offset=0)
    (word,) = struct.unpack_from("<I", stream, 0)
    length, kind = word & 0xFFFFFF, word >> 24
    if 4 + length > len(stream):
        raise FormatError(f"the payload of {length} bytes is cut", file=file, locator=locator, offset=0)
    payload = stream[4 : 4 + length]
    if kind != 0 or not payload.endswith(b"\0"):
        raise FormatError("the first record is not a property list", file=file, locator=locator, offset=0)
    text = payload[:-1]
    props = parse(text, codepage=ctx.codepage)
    found = props.text("HEADER")
    if found.casefold() != LIBRARY_HEADER.casefold():
        if found.casefold() == BINARY_HEADER.casefold():
            message = "this is a schematic document: read it with read_schematic"
        else:
            message = f"unexpected header text {found!r}"
        raise FormatError(message, file=file, locator=locator, offset=0)
    record = header_record(
        props, ref=RecordRef("header", -1), kind=0, payload=payload, offset=0, segments=((len(text), b"\0"),)
    )
    return record, stream[4 + length :]


def _name_list(tail: bytes, codepage: str) -> tuple[str, ...]:
    """The names of the name list after the header record (a 4-byte count, then one framed short string per
    component), or ``()`` when the bytes do not have that layout exactly."""
    if len(tail) < 4:
        return ()
    (count,) = struct.unpack_from("<I", tail, 0)
    try:
        frames = deframe(tail[4:], where="FileHeader")
    except FormatError:
        return ()
    if len(frames) != count:
        return ()
    names: list[str] = []
    for frame in frames:
        payload = frame.payload
        if not payload or payload[0] != len(payload) - 1:
            return ()
        names.append(payload[1:].decode(codepage, errors="replace"))
    return tuple(names)


def _stream_records(data: bytes, *, name: str, file: str, ctx: Context) -> tuple[SchRecord, ...]:
    """The frames of a header-like stream (``SectionKeys``) as header records, or unknown records."""
    out: list[SchRecord] = []
    for index, frame in enumerate(deframe(data, where=name, file=file)):
        ref = RecordRef(name.lower(), index)
        if frame.kind == 0 and frame.payload.endswith(b"\0"):
            text = frame.payload[:-1]
            props = parse(text, codepage=ctx.codepage)
            out.append(
                header_record(
                    props,
                    ref=ref,
                    kind=0,
                    payload=frame.payload,
                    offset=frame.offset,
                    segments=((len(text), b"\0"),),
                )
            )
        else:
            ctx.log.add(
                "altium.sch.malformed-record",
                f"{name} holds a record that is not a property list",
                f"{name}/record {index}",
            )
            out.append(UnknownRecord(ref, frame.kind, frame.payload, frame.offset, None))
    return tuple(out)


def _section_keys(records: tuple[SchRecord, ...], ctx: Context) -> dict[str, str]:
    """Lib ref → storage name, from the ``LIBREF<i>`` and ``SECTIONKEY<i>`` keys that exist."""
    keys: dict[str, str] = {}
    first = next((record for record in records if record.props is not None), None)
    if first is None or first.props is None:
        return keys
    props = first.props
    numbers = sorted({int(m.group(1)) for key in props.keys() if (m := re.match(r"^LIBREF(\d+)$", key))})
    for n in numbers:
        keys[props.text(f"LIBREF{n}")] = props.text(f"SECTIONKEY{n}")
    stated = parse_int(props.raw("KEYCOUNT"))
    if stated is not None and stated != len(numbers):
        ctx.log.add(
            "altium.sch.bad-value",
            f"SectionKeys key KEYCOUNT is {stated} but {len(numbers)} item(s) are present; those are read",
            "SectionKeys/record 0",
        )
    return keys


def _storage(stream: bytes, *, file: str, ctx: Context) -> tuple[PropertyRecord | None, list[EmbeddedFile]]:
    frames = deframe(stream, where="Storage", file=file)
    if not frames:
        return None, []
    header: PropertyRecord | None = None
    first = frames[0]
    rest: tuple[Frame, ...] = frames
    if first.kind == 0 and first.payload.endswith(b"\0"):
        text = first.payload[:-1]
        header = header_record(
            parse(text, codepage=ctx.codepage), ref=RecordRef("storage", -1), kind=0, payload=first.payload,
            offset=first.offset, segments=((len(text), b"\0"),),
        )  # fmt: skip
        rest = frames[1:]
    start = 1 if header is not None else 0
    files = [
        embedded_file(
            i, frame, file=file, codepage=ctx.codepage, log=ctx.log, where=f"Storage/record {i + start}"
        )
        for i, frame in enumerate(rest)
    ]
    return header, files


def _order(
    header: PropertyRecord, section_keys: dict[str, str], storages: tuple[str, ...], ctx: Context
) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """The storages in the header's ``LIBREF<i>`` order (through ``SectionKeys``), then the unlisted ones in
    directory order; storage → (lib ref, description) for the listed ones."""
    props = header.props
    assert props is not None
    by_folded = {storage.upper(): storage for storage in storages}
    numbers = sorted({int(m.group(1)) for key in props.keys() if (m := re.match(r"^LIBREF(\d+)$", key))})
    order: list[str] = []
    listed: dict[str, tuple[str, str]] = {}
    for n in numbers:
        lib_ref = props.text(f"LIBREF{n}")
        key = section_keys.get(lib_ref, lib_ref)
        storage = by_folded.get(key.upper()) or by_folded.get(key.replace("/", "_").upper())
        if storage is None:
            ctx.log.add(
                "altium.schlib.missing-component",
                f"the header lists component {n} but no storage of that name holds a Data stream",
                f"FileHeader/record 0 LIBREF{n}",
            )
            continue
        if storage in listed:
            continue
        listed[storage] = (lib_ref, props.text(f"COMPDESCR{n}"))
        order.append(storage)
    order += [storage for storage in storages if storage not in listed]
    return order, listed


def _component(
    compound: _container.CompoundFile,
    storage: str,
    inside: tuple[tuple[str, str], ...],
    lib_ref: str,
    description: str,
    read: dict[str, bytes],
    file: str,
    ctx: Context,
) -> SchLibComponent:
    data_path = next(path for name, path in inside if name.upper() == "DATA")
    data = compound.read(data_path)
    read[data_path] = data
    stream = f"{storage}/Data"
    records: list[SchRecord] = []
    if not data:
        ctx.log.add("altium.sch.empty-stream", f"the Data stream of {storage} holds no byte", stream)
    for index, frame in enumerate(deframe(data, where=stream, file=file)):
        ref = RecordRef("data", index)
        records.append(
            frame_record(
                frame.kind,
                frame.payload,
                ref=ref,
                offset=frame.offset,
                ctx=ctx,
                where=f"{stream}/record {index}",
            )
        )
    ctx.report_unknown()
    if records and not isinstance(records[0], Component):
        ctx.log.add(
            "altium.schlib.no-component",
            "record 0 of Data is not the component (RECORD=1)",
            f"{stream}/record 0",
        )
    trailing = sum(1 for record in records if isinstance(record, Pin) and record.tail)
    if trailing:
        ctx.log.add(
            "altium.sch.pin-trailing-bytes",
            f"{trailing} binary pin(s) of {storage} hold bytes after their last known field; kept in tail",
            stream,
        )
    side: dict[str, bytes] = {}
    extra: dict[str, bytes] = {}
    for name, path in inside:
        if path == data_path:
            continue
        content = compound.read(path)
        if name.upper() in _SIDE_NAMES:
            side[name] = content
        else:
            extra[name] = content
            ctx.log.add("altium.sch.unknown-stream", f"stream {path} is kept as bytes and not read", path)
    for name, content in side.items():
        canonical = _SIDE_NAMES[name.upper()]
        if canonical == "PinFrac":
            fractions = decode_pin_frac(content)
            if fractions is not None:
                records = _apply_fractions(records, fractions, storage, name, ctx)
                continue
        ctx.log.add(
            "altium.schlib.side-stream-opaque",
            f"side stream {name} of {storage} is kept as bytes and not decoded; no pin changes",
            f"{storage}/{name}",
        )
    linked = link([records], _library_owner, ctx, lambda r: f"{stream}/record {r.ref.index}", warn=False)[0]

    def get(ref: RecordRef) -> SchRecord:
        return linked[ref.index]

    if linked:
        check_parts([linked[0]], get, ctx, lambda r: f"{stream}/record {r.ref.index}")
    first = linked[0] if linked else None
    name = lib_ref or (
        first.lib_reference if isinstance(first, Component) and first.lib_reference else storage
    )
    if not description and isinstance(first, Component):
        description = first.description
    return SchLibComponent(name, storage, description, tuple(linked), side, extra, data)


def _library_owner(record: SchRecord) -> tuple[RecordRef | None, str]:
    """An ``OWNERINDEX`` naming an earlier record of the same ``Data`` is the owner; any other record after
    record 0 belongs to record 0."""
    if record.ref.index == 0:
        return None, ""
    index = record.owner_index
    if index is not None and 0 <= index < record.ref.index:
        return RecordRef("data", index), ""
    return RecordRef("data", 0), ""


def decode_pin_frac(stream: bytes) -> dict[int, tuple[int, int, int]] | None:
    """Pin index → (X, Y, length) fractions from a ``PinFrac`` stream, or ``None`` when the stream does not
    match the layout of ``schematic-library.md`` ("Pin side streams") to its last byte. Property-list records
    (the stream's header) are skipped; every other record must be 0xD0, a short string holding the decimal pin
    index, a 4-byte size and exactly that many bytes of zlib data that expand to three 4-byte integers."""
    try:
        frames = deframe(stream, where="PinFrac")
    except FormatError:
        return None
    out: dict[int, tuple[int, int, int]] = {}
    for frame in frames:
        payload = frame.payload
        if frame.kind == 0:
            if not payload.endswith(b"\0"):
                return None
            continue
        if len(payload) < 2 or payload[0] != FRAC_MARK:
            return None
        length = payload[1]
        index_text = payload[2 : 2 + length]
        size_at = 2 + length
        if size_at + 4 > len(payload) or not index_text.isdigit():
            return None
        (size,) = struct.unpack_from("<I", payload, size_at)
        packed = payload[size_at + 4 :]
        if len(packed) != size:
            return None
        inflater = zlib.decompressobj()
        try:
            values = inflater.decompress(packed, FRAC_SIZE + 1)
        except zlib.error:
            return None
        if len(values) != FRAC_SIZE or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            return None
        index = int(index_text)
        if index in out:
            return None
        out[index] = struct.unpack("<3i", values)
    return out


def _apply_fractions(
    records: list[SchRecord],
    fractions: dict[int, tuple[int, int, int]],
    storage: str,
    name: str,
    ctx: Context,
) -> list[SchRecord]:
    positions = [i for i, record in enumerate(records) if isinstance(record, Pin)]
    out = list(records)
    for index, values in sorted(fractions.items()):
        if index >= len(positions):
            ctx.log.add(
                "altium.schlib.side-stream-orphan",
                f"side stream {name} of {storage} has an entry for pin {index}, which does not exist; kept",
                f"{storage}/{name}",
            )
            continue
        at = positions[index]
        settle(out[at], pin_fracs=values)
    return out


def _counts(header: PropertyRecord, components: list[SchLibComponent], ctx: Context) -> None:
    props = header.props
    assert props is not None
    stated = parse_int(props.raw("COMPCOUNT"))
    if stated is not None and stated != len(components):
        ctx.log.add(
            "altium.sch.weight-mismatch",
            f"COMPCOUNT is {stated} but {len(components)} component(s) were read",
            "FileHeader/record 0",
        )
    weight = parse_int(props.raw("WEIGHT"))
    total = sum(len(component.records) for component in components) + 1
    if weight is not None and weight != total:
        ctx.log.add(
            "altium.sch.weight-mismatch",
            f"WEIGHT is {weight} but the Data streams hold {total - 1} record(s) (expected WEIGHT {total})",
            "FileHeader/record 0",
        )


# --- rebuilding -------------------------------------------------------------------------------------------


def encode_stream(library: SchLibrary, path: str) -> bytes:
    """The bytes of ``FileHeader``, ``SectionKeys``, ``Storage`` or ``<storage>/Data``, rebuilt from the
    parsed records."""
    folded = path.upper()
    if folded == "FILEHEADER":
        return enframe([(0, _record_bytes(library.header))]) + library.header_tail
    if folded == "SECTIONKEYS":
        return enframe([(record.kind, _record_bytes(record)) for record in library.section_keys_records])
    if folded == "STORAGE":
        frames: list[tuple[int, bytes]] = []
        if library.storage_header is not None:
            frames.append((0, _record_bytes(library.storage_header)))
        frames += [(item.kind, item.to_bytes()) for item in library.embedded]
        return enframe(frames)
    storage, _, stream = path.rpartition("/")
    if stream.upper() == "DATA":
        for component in library.components:
            if component.storage_name.upper() == storage.upper():
                return enframe([(record.kind, _record_bytes(record)) for record in component.records])
    raise KeyError(path)


def check_library(library: SchLibrary) -> tuple[str, ...]:
    """The streams of ``library`` whose rebuilt bytes differ from the bytes read."""
    return tuple(path for path, data in library.streams.items() if encode_stream(library, path) != data)


__all__ = [
    "SIDE_STREAMS",
    "SIDE_STREAMS_DECODED",
    "SchLibComponent",
    "SchLibrary",
    "check_library",
    "decode_pin_frac",
    "encode_stream",
    "read_schlib",
]
