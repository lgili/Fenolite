# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium schematic documents and templates (``.SchDoc``, ``.SchDot``) in the binary and the ASCII form.

``read_schematic`` takes the file's bytes and returns a ``SchDocument``: the header, the records of
``FileHeader`` (or of the ASCII file's first section) with their owner tree, the ``Additional`` records, the
``Storage`` header and embedded files, and every other stream kept as bytes. Nothing is opened, resolved or
decompressed. Facts: ``docs/formats/altium/schematic-records.md``, ``schematic-ascii.md`` and
``schematic-binary.md``.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar

from fenolite.backends.altium.read.sch import _container
from fenolite.backends.altium.read.sch._build import (
    Context,
    Resolver,
    check_parts,
    frame_record,
    header_record,
    link,
    record_bytes,
    typed_record,
)
from fenolite.backends.altium.read.sch.framing import Frame, deframe, enframe, line_end, split_lines
from fenolite.backends.altium.read.sch.issues import IssueLog
from fenolite.backends.altium.read.sch.props import (
    DEFAULT_CODEPAGE,
    PropertyList,
    check_codepage,
    parse,
    parse_int,
)
from fenolite.backends.altium.read.sch.records import (
    Bus,
    Component,
    HarnessConnector,
    HarnessEntry,
    HarnessType,
    Image,
    Junction,
    NetLabel,
    NoErc,
    Port,
    PowerPort,
    PropertyRecord,
    RecordRef,
    SchRecord,
    Sheet,
    SheetSymbol,
    Template,
    UnknownRecord,
    Wire,
)
from fenolite.core.errors import FormatError, Issue

BINARY_HEADER = "Protel for Windows - Schematic Capture Binary File Version 5.0"
ASCII_HEADER = "Protel for Windows - Schematic Capture Ascii File Version 5.0"
LIBRARY_HEADER = "Protel for Windows - Schematic Library Editor Binary File Version 5.0"
STORAGE_HEADER = "Icon storage"
BOM = b"\xef\xbb\xbf"
ASCII_PREFIX = b"|HEADER="
MAX_EMBEDDED = 64 * 1024 * 1024
"""The default cap of ``EmbeddedFile.data``: 64 MiB of decompressed bytes."""
EMBEDDED_MARK = 0xD0
CONTINUATION = b"|>"

R = TypeVar("R", bound=SchRecord)


@dataclass(frozen=True, slots=True)
class EmbeddedFile:
    """One record of ``Storage`` after its header. With the layout of ``schematic-records.md`` ("Storage"):
    0xD0, a one-byte name length, the name, a 4-byte little-endian size and that many bytes of zlib data,
    ``name`` and ``packed`` are set; otherwise ``name`` is ``""`` and ``packed`` is ``None`` (opaque)."""

    index: int
    kind: int
    payload: bytes
    offset: int
    name: str = ""
    name_raw: bytes = b""
    packed: bytes | None = None
    file: str = field(default="", compare=False)

    @property
    def opaque(self) -> bool:
        return self.packed is None

    def to_bytes(self) -> bytes:
        """The payload rebuilt from its parts."""
        if self.packed is None:
            return self.payload
        head = bytes([EMBEDDED_MARK, len(self.name_raw)]) + self.name_raw
        return head + struct.pack("<I", len(self.packed)) + self.packed

    def data(self, limit: int = MAX_EMBEDDED) -> bytes:
        """The decompressed file, on request only; ``FormatError`` when the output would pass ``limit`` bytes,
        when the data is not zlib, or when it is cut (S-0281)."""
        locator = f"Storage/record {self.index + 1}"
        if self.packed is None:
            raise FormatError("the embedded record is opaque: no compressed data to expand", file=self.file,
                              locator=locator)  # fmt: skip
        inflater = zlib.decompressobj()
        try:
            out = inflater.decompress(self.packed, limit + 1)
        except zlib.error as error:
            raise FormatError(
                f"the embedded file is not zlib data: {error}", file=self.file, locator=locator
            ) from None
        if len(out) > limit:
            raise FormatError(
                f"the embedded file expands past the limit of {limit} bytes", file=self.file, locator=locator
            )
        if not inflater.eof:
            raise FormatError(
                "the compressed data of the embedded file is cut", file=self.file, locator=locator
            )
        return out


def embedded_file(
    index: int, frame: Frame, *, file: str, codepage: str, log: IssueLog, where: str
) -> EmbeddedFile:
    """An ``EmbeddedFile`` from a ``Storage`` frame; an opaque one gets a ``storage-opaque`` info."""
    payload = frame.payload
    if frame.kind != 0 and len(payload) >= 6 and payload[0] == EMBEDDED_MARK:
        length = payload[1]
        size_at = 2 + length
        if size_at + 4 <= len(payload):
            (size,) = struct.unpack_from("<I", payload, size_at)
            packed = payload[size_at + 4 :]
            if len(packed) == size:
                name_raw = payload[2:size_at]
                name = name_raw.decode(codepage, errors="replace")
                return EmbeddedFile(index, frame.kind, payload, frame.offset, name, name_raw, packed, file)
    log.add(
        "altium.sch.storage-opaque",
        f"storage record {index + 1} ({len(payload)} bytes) lacks the embedded-file layout; kept as bytes",
        where,
    )
    return EmbeddedFile(index, frame.kind, payload, frame.offset, file=file)


@dataclass(frozen=True, slots=True)
class Harness:
    """A harness connector with its entries (in stream order) and its type record."""

    connector: HarnessConnector
    entries: tuple[HarnessEntry, ...]
    type: HarnessType | None


@dataclass(frozen=True, slots=True)
class AsciiSection:
    """A section of the ASCII form that the reader does not read: its header line and its records."""

    header: PropertyRecord
    records: tuple[SchRecord, ...]


@dataclass(frozen=True, slots=True)
class SchDocument:
    """A schematic document or template as read. ``records`` and ``additional`` are flat tuples; owners are
    ``RecordRef`` values. ``streams`` holds the bytes of every stream read, for comparison with
    ``encode_stream``."""

    file: str
    form: Literal["binary", "ascii"]
    codepage: str
    header: PropertyRecord
    records: tuple[SchRecord, ...]
    additional_header: PropertyRecord | None = None
    additional: tuple[SchRecord, ...] = ()
    storage_header: PropertyRecord | None = None
    embedded: tuple[EmbeddedFile, ...] = ()
    streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    extra_streams: dict[str, bytes] = field(default_factory=dict[str, bytes], hash=False)
    extra_sections: tuple[AsciiSection, ...] = ()
    blank_lines: tuple[UnknownRecord, ...] = ()
    preamble: bytes = b""
    issues: tuple[Issue, ...] = ()
    roots: tuple[RecordRef, ...] = ()

    # --- access ------------------------------------------------------------------------------------------

    @property
    def sheet(self) -> Sheet | None:
        """Record 0 when it is a ``Sheet``."""
        first = self.records[0] if self.records else None
        return first if isinstance(first, Sheet) else None

    def all_records(self) -> tuple[SchRecord, ...]:
        """``records`` then ``additional``."""
        return self.records + self.additional

    def get(self, ref: RecordRef) -> SchRecord:
        if ref.stream == "main":
            return self.records[ref.index]
        if ref.stream == "additional":
            return self.additional[ref.index]
        raise KeyError(ref)

    def owner_of(self, record: SchRecord) -> SchRecord | None:
        return None if record.owner is None else self.get(record.owner)

    def children_of(
        self, record: SchRecord, part: int | None = None, mode: int | None = None
    ) -> tuple[SchRecord, ...]:
        """The direct children of ``record`` in stream order. ``part=k`` keeps children of part ``k``, of Part
        Zero and of no part; ``mode=m`` keeps children of display mode ``m`` and of no part."""
        return filter_children(tuple(self.get(ref) for ref in record.children), part, mode)

    def shown_children(self, component: Component) -> tuple[SchRecord, ...]:
        """The children shown for the component's own ``CURRENTPARTID`` and ``DISPLAYMODE``."""
        return self.children_of(component, part=component.current_part, mode=component.display_mode)

    def walk(self, record: SchRecord) -> Iterator[SchRecord]:
        """``record`` and its descendants, depth first, in stream order, without recursion."""
        stack: list[RecordRef] = [record.ref]
        while stack:
            current = self.get(stack.pop())
            yield current
            stack.extend(reversed(current.children))

    def of_type(self, cls: type[R]) -> tuple[R, ...]:
        """Every record of ``cls``, ``records`` first, in stream order."""
        return tuple(record for record in self.all_records() if isinstance(record, cls))

    def components(self) -> tuple[Component, ...]:
        return self.of_type(Component)

    def wires(self) -> tuple[Wire, ...]:
        return self.of_type(Wire)

    def buses(self) -> tuple[Bus, ...]:
        return self.of_type(Bus)

    def net_labels(self) -> tuple[NetLabel, ...]:
        return self.of_type(NetLabel)

    def power_ports(self) -> tuple[PowerPort, ...]:
        return self.of_type(PowerPort)

    def ports(self) -> tuple[Port, ...]:
        return self.of_type(Port)

    def junctions(self) -> tuple[Junction, ...]:
        return self.of_type(Junction)

    def no_ercs(self) -> tuple[NoErc, ...]:
        return self.of_type(NoErc)

    def sheet_symbols(self) -> tuple[SheetSymbol, ...]:
        return self.of_type(SheetSymbol)

    def templates(self) -> tuple[Template, ...]:
        return self.of_type(Template)

    def template_children(self) -> tuple[SchRecord, ...]:
        """The records owned by a ``Template``, in stream order."""
        refs = {ref for template in self.templates() for ref in template.children}
        return tuple(record for record in self.all_records() if record.ref in refs)

    def harnesses(self) -> tuple[Harness, ...]:
        """One ``Harness`` per harness connector, in stream order."""
        out: list[Harness] = []
        for connector in self.of_type(HarnessConnector):
            kids = [self.get(ref) for ref in connector.children]
            entries = tuple(kid for kid in kids if isinstance(kid, HarnessEntry))
            types = [kid for kid in kids if isinstance(kid, HarnessType)]
            out.append(Harness(connector, entries, types[0] if types else None))
        return tuple(out)

    def image_data(self, image: Image) -> EmbeddedFile | None:
        """The embedded file whose name equals the image's ``FILENAME``, or ``None``."""
        name = image.file_name
        return next((item for item in self.embedded if not item.opaque and item.name == name), None)

    def stream_mismatches(self) -> tuple[str, ...]:
        """The streams whose bytes ``encode_stream`` does not rebuild exactly."""
        return tuple(name for name in stream_names(self) if encode_stream(self, name) != self.streams[name])

    def census(self) -> dict[str, object]:
        from fenolite.backends.altium.read.sch.census import document_census

        return document_census(self)


def filter_children(
    children: tuple[SchRecord, ...], part: int | None, mode: int | None
) -> tuple[SchRecord, ...]:
    out: list[SchRecord] = []
    for child in children:
        if part is not None and child.owner_part not in (part, 0, -1):
            continue
        if mode is not None and child.owner_part != -1 and child.owner_display_mode != mode:
            continue
        out.append(child)
    return tuple(out)


# --- detection ------------------------------------------------------------------------------------------


def _header_text(stream: bytes) -> str | None:
    """The ``HEADER`` value of the first frame of ``stream`` when it is a property list."""
    if len(stream) < 4:
        return None
    (word,) = struct.unpack_from("<I", stream, 0)
    length, kind = word & 0xFFFFFF, word >> 24
    payload = stream[4 : 4 + length]
    if kind != 0 or len(payload) != length:
        return None
    text = payload[:-1] if payload.endswith(b"\0") else payload
    return parse(text).text("HEADER")


def detect(data: bytes) -> str | None:
    """``"ascii"``, ``"binary"`` or ``"library"`` from the bytes alone, or ``None``."""
    body = data[len(BOM) :] if data.startswith(BOM) else data
    if body.startswith(ASCII_PREFIX):
        return "ascii"
    if not _container.is_compound(data):
        return None
    try:
        compound = _container.open_container(data, file="", issues=[])
        streams = _container.root_streams(compound)
        if "FILEHEADER" not in streams:
            return None
        text = _header_text(compound.read(streams["FILEHEADER"]))
    except FormatError:
        return None
    if text is None:
        return None
    folded = text.casefold()
    if folded == BINARY_HEADER.casefold():
        return "binary"
    if folded == LIBRARY_HEADER.casefold():
        return "library"
    return None


# --- reading --------------------------------------------------------------------------------------------


def read_schematic(
    data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE, issues: list[Issue] | None = None
) -> SchDocument:
    """Read a schematic document or template, binary or ASCII. Raises ``FormatError`` only when no result
    can be returned; everything else is an issue of ``ISSUE_CODES``, added to ``issues`` when given."""
    codec = check_codepage(codepage)
    body = data[len(BOM) :] if data.startswith(BOM) else data
    if body.startswith(ASCII_PREFIX):
        document = _read_ascii(data, file=file, codepage=codec)
    elif _container.is_compound(data):
        document = _read_binary(data, file=file, codepage=codec)
    else:
        raise FormatError(
            "neither an ASCII schematic (|HEADER=) nor a compound file", file=file, locator="", offset=0
        )
    if issues is not None:
        issues.extend(document.issues)
    return document


def _locator(stream: str, frame_index: int) -> str:
    return f"{stream}/record {frame_index}"


def _header(
    frame: Frame, *, stream: str, file: str, ctx: Context, expected: tuple[str, ...]
) -> PropertyRecord:
    """The header record of a binary stream, its text checked without letter case."""
    locator = _locator(stream, 0)
    if frame.kind != 0 or not frame.payload.endswith(b"\0"):
        raise FormatError("the first record is not a property list", file=file, locator=locator, offset=0)
    text = frame.payload[:-1]
    props = parse(text, codepage=ctx.codepage)
    header = props.text("HEADER")
    if header.casefold() not in {value.casefold() for value in expected}:
        if header.casefold() == LIBRARY_HEADER.casefold():
            raise FormatError(
                "this is a schematic library: read it with read_schlib", file=file, locator=locator, offset=0
            )
        raise FormatError(f"unexpected header text {header!r}", file=file, locator=locator, offset=0)
    ref = RecordRef(stream.lower() if stream != "FileHeader" else "main", -1)
    return header_record(
        props, ref=ref, kind=0, payload=frame.payload, offset=frame.offset, segments=((len(text), b"\0"),)
    )


def _weight(header: PropertyRecord, count: int, *, required: bool, ctx: Context, where: str) -> None:
    props = header.props
    assert props is not None
    weight = parse_int(props.raw("WEIGHT"))
    if weight is None and not props.has("WEIGHT") and (not required or count == 0):
        return
    if weight != count:
        stated = "missing" if weight is None else str(weight)
        ctx.log.add(
            "altium.sch.weight-mismatch",
            f"WEIGHT is {stated} but {count} record(s) follow the header",
            where,
        )


def _resolver(records: tuple[SchRecord, ...]) -> Resolver:
    def resolve(record: SchRecord) -> tuple[RecordRef | None, str]:
        props = record.props
        if props is None:
            return None, ""
        index = parse_int(props.raw("OWNERINDEX"))
        if record.ref.stream == "additional" and props.bool("OWNERINDEXADDITIONALLIST"):
            target = 0 if index is None else index
            if 0 <= target < record.ref.index:
                return RecordRef("additional", target), ""
            return None, (
                f"additional record {record.ref.index} names owner {target} of the Additional stream, "
                "which is not an earlier record; kept at the sheet level"
            )
        if index is None:
            return None, ""
        limit = record.ref.index if record.ref.stream == "main" else len(records)
        if 0 <= index < limit:
            return RecordRef("main", index), ""
        return None, (
            f"{record.ref.stream} record {record.ref.index} names owner {index}, which is not an earlier "
            "record; kept at the sheet level"
        )

    return resolve


def _finish(
    *,
    form: Literal["binary", "ascii"],
    ctx: Context,
    records: list[SchRecord],
    additional: list[SchRecord],
    where: dict[RecordRef, str],
) -> tuple[tuple[SchRecord, ...], tuple[SchRecord, ...], tuple[RecordRef, ...]]:
    """Report unknown ids, link owners, check the sheet and the parts; the linked records and the roots."""
    ctx.report_unknown()
    main_t = tuple(records)
    linked = link([main_t, tuple(additional)], _resolver(main_t), ctx, lambda r: where[r.ref])
    main_l, add_l = tuple(linked[0]), tuple(linked[1])
    if not main_l or not isinstance(main_l[0], Sheet):
        ctx.log.add(
            "altium.sch.no-sheet",
            "record 0 is not the sheet record (RECORD=31)",
            where[main_l[0].ref] if main_l else ("line 1" if form == "ascii" else "FileHeader"),
        )

    def get(ref: RecordRef) -> SchRecord:
        return main_l[ref.index] if ref.stream == "main" else add_l[ref.index]

    check_parts([*main_l, *add_l], get, ctx, lambda r: where[r.ref])
    tails = [r for r in (*main_l, *add_l) if r.pin_fields is not None and r.pin_fields.tail]
    if tails:
        # a binary pin of a document carries no owner index, so the finding is per document, not per component
        ctx.log.add(
            "altium.sch.pin-trailing-bytes",
            f"{len(tails)} binary pin(s) hold bytes after their last known field; kept in tail",
            where[tails[0].ref],
        )
    roots = tuple(r.ref for r in main_l if r.owner is None) + tuple(r.ref for r in add_l if r.owner is None)
    return main_l, add_l, roots


def _read_binary(data: bytes, *, file: str, codepage: str) -> SchDocument:
    log = IssueLog()
    ctx = Context(codepage, log)
    compound = _container.open_container(data, file=file, issues=log.items)
    streams = _container.root_streams(compound)
    if "FILEHEADER" not in streams:
        raise FormatError("the stream FileHeader is missing", file=file, locator="FileHeader")
    read: dict[str, bytes] = {}
    path = streams["FILEHEADER"]
    read[path] = compound.read(path)
    frames = deframe(read[path], where="FileHeader", file=file)
    if not frames:
        raise FormatError(
            "the stream FileHeader holds no record", file=file, locator="FileHeader/record 0", offset=0
        )
    header = _header(frames[0], stream="FileHeader", file=file, ctx=ctx, expected=(BINARY_HEADER,))
    where: dict[RecordRef, str] = {}
    records: list[SchRecord] = []
    for index, frame in enumerate(frames[1:]):
        ref = RecordRef("main", index)
        where[ref] = _locator("FileHeader", index + 1)
        records.append(
            frame_record(frame.kind, frame.payload, ref=ref, offset=frame.offset, ctx=ctx, where=where[ref])
        )
    _weight(header, len(records), required=True, ctx=ctx, where=_locator("FileHeader", 0))

    additional_header: PropertyRecord | None = None
    additional: list[SchRecord] = []
    if "ADDITIONAL" in streams:
        path = streams["ADDITIONAL"]
        read[path] = compound.read(path)
        if not read[path]:
            log.add("altium.sch.empty-stream", "the Additional stream holds no byte", "Additional")
        else:
            frames = deframe(read[path], where="Additional", file=file)
            additional_header = _header(
                frames[0], stream="Additional", file=file, ctx=ctx, expected=(BINARY_HEADER, ASCII_HEADER)
            )
            for index, frame in enumerate(frames[1:]):
                ref = RecordRef("additional", index)
                where[ref] = _locator("Additional", index + 1)
                additional.append(
                    frame_record(
                        frame.kind, frame.payload, ref=ref, offset=frame.offset, ctx=ctx, where=where[ref]
                    )
                )
            _weight(
                additional_header, len(additional), required=False, ctx=ctx, where=_locator("Additional", 0)
            )

    storage_header: PropertyRecord | None = None
    embedded: list[EmbeddedFile] = []
    if "STORAGE" in streams:
        path = streams["STORAGE"]
        read[path] = compound.read(path)
        storage_header, embedded = _storage(read[path], file=file, ctx=ctx)

    extra: dict[str, bytes] = {}
    known = {streams[name] for name in ("FILEHEADER", "ADDITIONAL", "STORAGE") if name in streams}
    for node in compound.nodes():
        if node.kind != "stream" or node.path in known:
            continue
        extra[node.path] = compound.read(node.path)
        log.add("altium.sch.unknown-stream", f"stream {node.path} is kept as bytes and not read", node.path)
    main_l, add_l, roots = _finish(
        form="binary", ctx=ctx, records=records, additional=additional, where=where
    )
    return SchDocument(
        file=file,
        form="binary",
        codepage=codepage,
        header=header,
        records=main_l,
        additional=add_l,
        issues=tuple(log.items),
        roots=roots,
        additional_header=additional_header,
        storage_header=storage_header,
        embedded=tuple(embedded),
        streams=read,
        extra_streams=extra,
    )


def _storage(stream: bytes, *, file: str, ctx: Context) -> tuple[PropertyRecord | None, list[EmbeddedFile]]:
    frames = deframe(stream, where="Storage", file=file)
    if not frames:
        return None, []
    header: PropertyRecord | None = None
    rest = frames
    first = frames[0]
    if first.kind == 0 and first.payload.endswith(b"\0"):
        text = first.payload[:-1]
        props = parse(text, codepage=ctx.codepage)
        header = header_record(
            props, ref=RecordRef("storage", -1), kind=0, payload=first.payload, offset=first.offset,
            segments=((len(text), b"\0"),),
        )  # fmt: skip
        rest = frames[1:]
    start = 1 if header is not None else 0
    files = [
        embedded_file(
            i, frame, file=file, codepage=ctx.codepage, log=ctx.log, where=_locator("Storage", i + start)
        )
        for i, frame in enumerate(rest)
    ]
    return header, files


# --- the ASCII form ---------------------------------------------------------------------------------------


@dataclass
class _Line:
    """A logical record of the ASCII form: its text (lines joined), segments, offset and first line number."""

    text: bytes
    segments: tuple[tuple[int, bytes], ...]
    raw: bytes
    offset: int
    number: int


def _logical_lines(data: bytes, start: int) -> list[_Line]:
    lines = split_lines(data[start:])
    out: list[_Line] = []
    offset = start
    number = 1
    pending: list[tuple[bytes, bytes, int]] = []  # (content, terminator, offset)
    first_offset, first_number = offset, number
    for line in lines:
        end = line_end(line)
        content = line[: len(line) - len(end)]
        if not pending:
            first_offset, first_number = offset, number
        if content.endswith(CONTINUATION):
            pending.append((content[: -len(CONTINUATION)], CONTINUATION + end, offset))
        else:
            pending.append((content, end, offset))
            text = b"".join(piece for piece, _, _ in pending)
            segments = tuple((len(piece), term) for piece, term, _ in pending)
            raw = b"".join(piece + term for piece, term, _ in pending)
            out.append(_Line(text, segments, raw, first_offset, first_number))
            pending = []
        offset += len(line)
        number += 1
    if pending:
        text = b"".join(piece for piece, _, _ in pending)
        segments = tuple((len(piece), term) for piece, term, _ in pending)
        raw = b"".join(piece + term for piece, term, _ in pending)
        out.append(_Line(text, segments, raw, first_offset, first_number))
    return out


def _first_key(props: PropertyList) -> str:
    for item in props.items:
        if item.raw is not None or item.key:
            return item.folded
    return ""


def _read_ascii(data: bytes, *, file: str, codepage: str) -> SchDocument:
    log = IssueLog()
    try:
        data.decode("utf-8")
        utf8 = True
    except UnicodeDecodeError:
        utf8 = False
    ctx = Context(codepage, log, utf8)
    preamble = BOM if data.startswith(BOM) else b""
    logical = _logical_lines(data, len(preamble))
    head = logical[0]
    head_props = parse(head.text, codepage=codepage, utf8=utf8)
    if head_props.text("HEADER").casefold() != ASCII_HEADER.casefold():
        if head_props.text("HEADER").casefold() == BINARY_HEADER.casefold():
            message = "the first line holds the binary header text, not the ASCII one"
        else:
            message = f"unexpected header text {head_props.text('HEADER')!r}"
        raise FormatError(message, file=file, locator="line 1", offset=len(preamble))
    header = header_record(
        head_props,
        ref=RecordRef("main", -1),
        kind=0,
        payload=head.raw,
        offset=head.offset,
        segments=head.segments,
    )
    where: dict[RecordRef, str] = {}
    sections: dict[str, list[SchRecord]] = {"main": [], "additional": []}
    additional_header: PropertyRecord | None = None
    storage_header: PropertyRecord | None = None
    embedded: list[EmbeddedFile] = []
    extra: list[tuple[PropertyRecord, list[SchRecord]]] = []
    blanks: list[UnknownRecord] = []
    current = "main"
    for line in logical[1:]:
        locator = f"line {line.number}"
        if not line.text and len(line.segments) == 1:
            blanks.append(UnknownRecord(RecordRef("blank", len(blanks)), 0, line.raw, line.offset, None))
            continue
        props = parse(line.text, codepage=codepage, utf8=utf8)
        if _first_key(props) == "HEADER":
            text = props.text("HEADER").casefold()
            section = header_record(
                props, ref=RecordRef("section", line.number), kind=0, payload=line.raw, offset=line.offset,
                segments=line.segments,
            )  # fmt: skip
            if text in (ASCII_HEADER.casefold(), BINARY_HEADER.casefold()) and additional_header is None:
                additional_header = section
                current = "additional"
            elif text == STORAGE_HEADER.casefold() and storage_header is None:
                storage_header = section
                current = "storage"
            else:
                extra.append((section, []))
                current = "extra"
                log.add(
                    "altium.sch.unknown-stream",
                    f"the section that starts at line {line.number} is kept as lines and not read",
                    locator,
                )
            continue
        if current == "storage":
            embedded.append(
                embedded_file(
                    len(embedded),
                    Frame(0, line.raw, line.offset),
                    file=file,
                    codepage=codepage,
                    log=log,
                    where=locator,
                )  # fmt: skip
            )
            continue
        if current == "extra":
            stream = "extra"
            ref = RecordRef(stream, sum(len(records) for _, records in extra))
            extra[-1][1].append(UnknownRecord(ref, 0, line.raw, line.offset, props, line.segments))
            continue
        group = sections[current]
        ref = RecordRef(current, len(group))
        where[ref] = locator
        group.append(
            typed_record(
                props,
                ref=ref,
                kind=0,
                payload=line.raw,
                offset=line.offset,
                segments=line.segments,
                ctx=ctx,
                where=locator,
            )  # fmt: skip
        )
    _weight(header, len(sections["main"]), required=True, ctx=ctx, where="line 1")
    if additional_header is not None:
        assert additional_header.props is not None
        _weight(
            additional_header,
            len(sections["additional"]),
            required=False,
            ctx=ctx,
            where=f"line {additional_header.ref.index}",
        )
    main_l, add_l, roots = _finish(
        form="ascii", ctx=ctx, records=sections["main"], additional=sections["additional"], where=where
    )
    return SchDocument(
        file=file,
        form="ascii",
        codepage=codepage,
        header=header,
        records=main_l,
        additional=add_l,
        issues=tuple(log.items),
        roots=roots,
        additional_header=additional_header,
        storage_header=storage_header,
        embedded=tuple(embedded),
        streams={"ascii": data},
        extra_sections=tuple(AsciiSection(h, tuple(r)) for h, r in extra),
        blank_lines=tuple(blanks),
        preamble=preamble,
    )


# --- rebuilding -----------------------------------------------------------------------------------------


def _frames_of(records: tuple[SchRecord, ...]) -> list[tuple[int, bytes]]:
    return [(record.kind, record_bytes(record)) for record in records]


def encode_stream(document: SchDocument, name: str) -> bytes:
    """The bytes of the stream ``name`` (``FileHeader``, ``Additional``, ``Storage``, or ``ascii`` for an
    ASCII file), rebuilt from the parsed records: property lists, pins and frames."""
    folded = name.upper()
    if document.form == "ascii":
        if folded != "ASCII":
            raise KeyError(name)
        return _encode_ascii(document)
    if folded == "FILEHEADER":
        return enframe([(0, record_bytes(document.header)), *_frames_of(document.records)])
    if folded == "ADDITIONAL":
        if document.additional_header is None:
            return b""
        return enframe([(0, record_bytes(document.additional_header)), *_frames_of(document.additional)])
    if folded == "STORAGE":
        frames: list[tuple[int, bytes]] = []
        if document.storage_header is not None:
            frames.append((0, record_bytes(document.storage_header)))
        frames += [(item.kind, item.to_bytes()) for item in document.embedded]
        return enframe(frames)
    raise KeyError(name)


def _encode_ascii(document: SchDocument) -> bytes:
    items: list[tuple[int, bytes]] = [(document.header.offset, record_bytes(document.header))]
    for record in (*document.records, *document.additional, *document.blank_lines):
        items.append((record.offset, record_bytes(record)))
    for section in (document.additional_header, document.storage_header):
        if section is not None:
            items.append((section.offset, record_bytes(section)))
    for item in document.embedded:
        items.append((item.offset, item.to_bytes()))
    for extra in document.extra_sections:
        items.append((extra.header.offset, record_bytes(extra.header)))
        items += [(record.offset, record_bytes(record)) for record in extra.records]
    items.sort(key=lambda pair: pair[0])
    return document.preamble + b"".join(chunk for _, chunk in items)


def stream_names(document: SchDocument) -> tuple[str, ...]:
    """The names ``encode_stream`` rebuilds for this document."""
    if document.form == "ascii":
        return ("ascii",)
    return tuple(document.streams)


class Rebuildable(Protocol):
    """A reading result that can compare its rebuilt streams with the bytes read."""

    def stream_mismatches(self) -> tuple[str, ...]: ...


def check_identity(result: Rebuildable) -> tuple[str, ...]:
    """The paths of the streams whose rebuilt bytes differ from the bytes read; ``()`` when every stream is
    rebuilt exactly. Takes a ``SchDocument`` or a ``SchLibrary``."""
    return result.stream_mismatches()


__all__ = [
    "ASCII_HEADER",
    "BINARY_HEADER",
    "LIBRARY_HEADER",
    "MAX_EMBEDDED",
    "AsciiSection",
    "EmbeddedFile",
    "Harness",
    "SchDocument",
    "Rebuildable",
    "check_identity",
    "detect",
    "embedded_file",
    "encode_stream",
    "filter_children",
    "read_schematic",
]
