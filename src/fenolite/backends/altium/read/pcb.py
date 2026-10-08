# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader of binary Altium PCB documents (``.PcbDoc``) into typed records, losing no byte
(``docs/formats/altium/pcb-read.md``; change c0041). The container is reached only through
``read.cfb``.

Every typed storage rebuilds to its ``Data`` stream from its records' ``raw`` and its ``trailing``
bytes (:meth:`PcbDocument.rebuild`); every other stream is returned unchanged in ``storages``. Problems are
located issues; ``strict=True`` raises :class:`PcbReadError` on the first error.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction
from types import MappingProxyType
from typing import Literal, TypeVar

from fenolite.backends.altium.read.cfb import CompoundFile, is_compound, open_compound
from fenolite.backends.altium.read.pcbprims import (
    ARC,
    FILL,
    PAD,
    REGION,
    TEXT,
    TRACK,
    VIA,
    ArcRecord,
    FillRecord,
    PadRecord,
    PcbReadError,
    Primitive,
    RawPrimitive,
    RegionRecord,
    TextRecord,
    TrackRecord,
    ViaRecord,
    decode_primitives,
    error_of,
    primitive_type,
)
from fenolite.backends.altium.read.pcbprops import (
    CODEC,
    PropertyRecord,
    issue,
    parse_blocks,
)
from fenolite.backends.altium.read.pcbstack import (
    BoardRecord,
    KeyReader,
    OutlineVertex,
    read_board,
    read_outline,
)
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level

BINARY_ONLY = "only the binary form of an Altium PCB file is read"
NO_INDEX = 0xFFFF
SPLIT_PLANE_POLYGON = 0xFFFE
"""The polygon index of a plane's pull-back primitives; it names no polygon and is not counted."""
TYPED_STORAGES = (
    "Board6",
    "Nets6",
    "Components6",
    "Classes6",
    "Rules6",
    "Polygons6",
    "Pads6",
    "Vias6",
    "Tracks6",
    "Arcs6",
    "Texts6",
    "Fills6",
    "Regions6",
    "ShapeBasedRegions6",
    "WideStrings6",
    "UniqueIDPrimitiveInformation",
)
"""The storages whose ``Data`` the reader types; their names are matched without case."""
PRIMITIVE_STORAGES: Mapping[str, int] = MappingProxyType(
    {
        "Pads6": PAD,
        "Vias6": VIA,
        "Tracks6": TRACK,
        "Arcs6": ARC,
        "Texts6": TEXT,
        "Fills6": FILL,
        "Regions6": REGION,
        "ShapeBasedRegions6": REGION,
    }
)
HYPOTHESES = (
    "H-A-RD-PCB-FRAME",
    "H-A-RD-PCB-IDENTITY",
    "H-A-RD-PCB-LENGTHS",
    "H-A-RD-PCB-REGION",
    "H-A-RD-PCB-TEXT-2",
    "H-A-RD-PCB-RULE",
    "H-A-RD-PCB-POLYNAME",
    "H-A-RD-PCB-CODEC",
)
EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=HYPOTHESES)
"""The evidence of a document read: the lowest of the framing rows, ``CORPUS-VERIFIED`` since the census
of the eleven corpus rows passed (2026-10-05, ``docs/evidence/altium-pcb-read.md``)."""
_CODES = re.compile(r"\d+(?:,\d+)*")


# --- container ---------------------------------------------------------------------------------------


def _open(source: bytes | CompoundFile, *, file: str = "") -> CompoundFile:
    """The container of ``source``: bytes are opened with ``read.cfb.open_compound``; a ``CompoundFile``
    is used as it is. Bytes that are not a compound file raise ``PcbReadError``."""
    if isinstance(source, CompoundFile):
        return source
    if not is_compound(source):
        raise PcbReadError(f"not a compound file: {BINARY_ONLY}", file=file, locator="", offset=0)
    return open_compound(source, file=file)


open_container = _open
"""The one way to the container for the library reader (``read.pcblib``): ``_open``."""


def detect_pcb(source: bytes | CompoundFile) -> Literal["pcbdoc", "pcblib"] | None:
    """``"pcblib"`` for a compound file with ``Library/Data``, ``"pcbdoc"`` for one with ``Board6/Data``,
    ``None`` otherwise (also for bytes that are no compound file)."""
    if not isinstance(source, CompoundFile) and not is_compound(source):
        return None
    compound = _open(source)
    if "Library/Data" in compound:
        return "pcblib"
    if "Board6/Data" in compound:
        return "pcbdoc"
    return None


class Issues:
    """The issues of one read, in order; in strict mode the first error raises."""

    def __init__(self, *, file: str, strict: bool) -> None:
        self.file = file
        self.strict = strict
        self.items: list[Issue] = []

    def add(self, *found: Issue) -> None:
        for item in found:
            self.items.append(item)
            if self.strict and item.severity == "error":
                raise error_of(item, file=self.file)


def storages_of(compound: CompoundFile, typed: set[str]) -> dict[str, dict[str, bytes]]:
    """Every stream of ``compound`` except the paths of ``typed`` (upper case), by storage name as stored
    (root streams under ``""``) and stream path inside it."""
    out: dict[str, dict[str, bytes]] = {}
    for path in compound.streams():
        if path.upper() in typed:
            continue
        storage, _, stream = path.partition("/") if "/" in path else ("", "", path)
        out.setdefault(storage, {})[stream] = compound.read(path)
    return out


def header_count(compound: CompoundFile, path: str) -> int | None:
    """The 32-bit count of a ``Header`` stream, or ``None`` without one of 4 bytes."""
    if path not in compound:
        return None
    data = compound.read(path)
    return struct.unpack("<I", data)[0] if len(data) == 4 else None


def string_header(data: bytes) -> tuple[str | None, int]:
    """A 32-bit length, one length byte and the characters: the text and the offset after it."""
    if len(data) < 5:
        return None, len(data)
    count = data[4]
    if 5 + count > len(data):
        return None, len(data)
    return data[5 : 5 + count].decode(CODEC), 5 + count


def file_header(data: bytes) -> tuple[str | None, float | None, str | None]:
    """The text, the version double and the unique id of a ``FileHeaderSix`` or library ``FileHeader``;
    ``None`` for each part a shorter header lacks."""
    text, at = string_header(data)
    if text is None or at + 8 > len(data):
        return text, None, None
    (version,) = struct.unpack_from("<d", data, at)
    unique, _ = string_header(data[at + 8 :])
    return text, version, unique


# --- property kinds ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NetRecord:
    record: PropertyRecord
    name: str | None
    unique_id: str | None

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


@dataclass(frozen=True, slots=True)
class ComponentRecord:
    """A component; ``x``, ``y`` in units (exact), ``rotation`` in degrees; a missing key gives ``None``."""

    record: PropertyRecord
    layer: str | None
    x: Fraction | None
    y: Fraction | None
    rotation: float | None
    pattern: str | None
    locked: bool | None
    name_on: bool | None
    comment_on: bool | None
    source_designator: str | None
    source_unique_id: str | None
    source_hierarchical_path: str | None
    source_footprint_library: str | None
    source_component_library: str | None
    source_lib_reference: str | None
    unique_id: str | None

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


@dataclass(frozen=True, slots=True)
class ClassRecord:
    record: PropertyRecord
    name: str | None
    kind: int | None
    superclass: bool | None
    members: tuple[str, ...]

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


@dataclass(frozen=True, slots=True)
class PolygonRecord:
    """A polygon pour; ``name`` decodes a list of decimal character codes, and ``net`` is an index."""

    record: PropertyRecord
    layer: str | None
    net: int | None
    polygon_type: str | None
    hatch_style: str | None
    pour_index: int | None
    name: str
    vertices: tuple[OutlineVertex, ...]

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


@dataclass(frozen=True, slots=True)
class RuleRecord:
    """A design rule kept opaque: ``fields`` holds every pair in order (the typed keys included), the
    input of c0042's ``read.rules.map_rules``; no scope is parsed. ``raw`` includes the kind number."""

    record: PropertyRecord
    kind_number: int
    rule_kind: str | None
    name: str | None
    enabled: bool | None
    priority: int | None
    scope1: str | None
    scope2: str | None
    comment: str | None
    unique_id: str | None

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


def decode_name(value: str) -> str:
    """A polygon name: a value made only of decimal numbers joined by commas is a list of character codes;
    any other value is the name itself."""
    if _CODES.fullmatch(value) and all(int(code) <= 0x10FFFF for code in value.split(",")):
        return "".join(chr(int(code)) for code in value.split(","))
    return value


def net_record(record: PropertyRecord) -> NetRecord:
    return NetRecord(record, record.get("NAME"), record.get("UNIQUEID"))


def component_record(record: PropertyRecord, values: KeyReader) -> ComponentRecord:
    return ComponentRecord(
        record=record,
        layer=record.get("LAYER"),
        x=values.mil("X"),
        y=values.mil("Y"),
        rotation=values.angle("ROTATION"),
        pattern=record.get("PATTERN"),
        locked=values.bool("LOCKED"),
        name_on=values.bool("NAMEON"),
        comment_on=values.bool("COMMENTON"),
        source_designator=record.get("SOURCEDESIGNATOR"),
        source_unique_id=record.get("SOURCEUNIQUEID"),
        source_hierarchical_path=record.get("SOURCEHIERARCHICALPATH"),
        source_footprint_library=record.get("SOURCEFOOTPRINTLIBRARY"),
        source_component_library=record.get("SOURCECOMPONENTLIBRARY"),
        source_lib_reference=record.get("SOURCELIBREFERENCE"),
        unique_id=record.get("UNIQUEID"),
    )


def class_record(record: PropertyRecord, values: KeyReader) -> ClassRecord:
    members: list[str] = []
    while (member := record.get(f"M{len(members)}")) is not None:
        members.append(member)
    return ClassRecord(
        record, record.get("NAME"), values.int("KIND"), values.bool("SUPERCLASS"), tuple(members)
    )


def polygon_record(record: PropertyRecord, values: KeyReader) -> PolygonRecord:
    return PolygonRecord(
        record=record,
        layer=record.get("LAYER"),
        net=values.int("NET"),
        polygon_type=record.get("POLYGONTYPE"),
        hatch_style=record.get("HATCHSTYLE"),
        pour_index=values.int("POURINDEX"),
        name=decode_name(record.text("NAME")),
        vertices=read_outline(values),
    )


def rule_record(record: PropertyRecord, values: KeyReader) -> RuleRecord:
    return RuleRecord(
        record=record,
        kind_number=struct.unpack("<H", record.lead)[0],
        rule_kind=record.get("RULEKIND"),
        name=record.get("NAME"),
        enabled=values.bool("ENABLED"),
        priority=values.int("PRIORITY"),
        scope1=record.get("SCOPE1EXPRESSION"),
        scope2=record.get("SCOPE2EXPRESSION"),
        comment=record.get("COMMENT"),
        unique_id=record.get("UNIQUEID"),
    )


def wide_table(data: bytes) -> tuple[dict[int, str], tuple[bytes, ...]] | None:
    """The entries of a ``WideStrings6/Data`` table and their bytes, or ``None`` when it does not parse.
    An entry whose length is 2 or less is empty and no text bytes follow it."""
    table: dict[int, str] = {}
    raws: list[bytes] = []
    at = 0
    while at < len(data):
        if at + 8 > len(data):
            return None
        index, length = struct.unpack_from("<2I", data, at)
        end = at + 8 + (length if length > 2 else 0)
        if end > len(data) or length % 2:
            return None
        text = data[at + 8 : end]
        table[index] = (text[:-2] if text.endswith(b"\0\0") else text).decode("utf-16-le", errors="replace")
        raws.append(data[at:end])
        at = end
    return table, tuple(raws)


def resolve_texts(texts: tuple[Primitive, ...], table: Mapping[int, str]) -> tuple[Primitive, ...]:
    """Each text with ``text`` set to the wide string at its index when the table holds it."""
    return tuple(
        replace(t, text=table[t.wide_index])
        if isinstance(t, TextRecord) and t.wide_index is not None and t.wide_index in table
        else t
        for t in texts
    )


# --- document ----------------------------------------------------------------------------------------

P = TypeVar("P")


@dataclass(frozen=True)
class PcbDocument:
    """A PCB document. Record tuples keep the stream order, so a record's index is its position;
    primitives shorter than their minimum stay in the tuple as ``RawPrimitive``."""

    header_text: str | None
    unique_id: str | None
    board: BoardRecord
    nets: tuple[NetRecord, ...]
    components: tuple[ComponentRecord, ...]
    classes: tuple[ClassRecord, ...]
    rules: tuple[RuleRecord, ...]
    polygons: tuple[PolygonRecord, ...]
    pads: tuple[PadRecord | RawPrimitive, ...]
    vias: tuple[ViaRecord | RawPrimitive, ...]
    tracks: tuple[TrackRecord | RawPrimitive, ...]
    arcs: tuple[ArcRecord | RawPrimitive, ...]
    texts: tuple[TextRecord | RawPrimitive, ...]
    fills: tuple[FillRecord | RawPrimitive, ...]
    regions: tuple[RegionRecord | RawPrimitive, ...]
    shape_regions: tuple[RegionRecord | RawPrimitive, ...]
    wide_strings: Mapping[int, str]
    pad_unique_ids: Mapping[int, str]
    storages: Mapping[str, Mapping[str, bytes]]
    issues: tuple[Issue, ...]
    evidence: Evidence
    others: Mapping[str, tuple[Primitive, ...]] = field(default_factory=lambda: MappingProxyType({}))
    """Per primitive storage, the records whose type differs from the storage's."""
    parts: Mapping[str, tuple[tuple[bytes, ...], bytes]] = field(default_factory=lambda: MappingProxyType({}))
    """Per typed storage present, its records' bytes in stream order and its ``trailing`` bytes."""

    def rebuild(self, storage: str) -> bytes:
        """The ``Data`` stream of a typed storage (``storage`` without case) from its records."""
        name = _typed_name(storage)
        raws, trailing = self.parts.get(name, ((), b""))
        return b"".join(raws) + trailing

    def trailing(self, storage: str) -> bytes:
        """The bytes after the last whole record of a typed storage."""
        return self.parts.get(_typed_name(storage), ((), b""))[1]

    def net_name(self, index: int | None) -> str | None:
        """The name of net ``index``; ``None`` for ``0xFFFF``, ``None`` or an index past the count."""
        if index is None or index == NO_INDEX or not 0 <= index < len(self.nets):
            return None
        return self.nets[index].name

    def primitives_of(self, component: int) -> tuple[Primitive, ...]:
        """The pads, tracks, arcs, texts, fills, regions and vias of component ``component``, each kind in
        stream order."""
        out: list[Primitive] = []
        for items in (self.pads, self.tracks, self.arcs, self.texts, self.fills, self.regions, self.vias):
            out += [p for p in items if not isinstance(p, RawPrimitive) and p.prefix.component == component]
        return tuple(out)

    def regions_of(self, polygon: int) -> tuple[RegionRecord, ...]:
        """The regions of ``Regions6`` whose polygon index is ``polygon``: the poured copper."""
        return tuple(r for r in self.regions if isinstance(r, RegionRecord) and r.prefix.polygon == polygon)


def _typed_name(storage: str) -> str:
    wanted = storage.upper()
    for name in TYPED_STORAGES:
        if name.upper() == wanted:
            return name
    raise KeyError(f"{storage} is not a typed storage")


def _counted(found: Issues, compound: CompoundFile, storage: str, count: int) -> None:
    """One ``count-mismatch`` warning when ``Header`` differs from the records read; a storage that
    stopped early (non-empty ``trailing``) is not compared."""
    header = header_count(compound, f"{storage}/Header")
    if header is not None and header != count:
        found.add(
            issue(
                "altium.pcb-read.count-mismatch",
                f"Header says {header} records, Data holds {count}",
                f"{storage}/Header",
            )
        )


def _bad_index(found: Issues, storage: str, kind: str, count: int, limit: int) -> None:
    if count:
        found.add(
            issue(
                "altium.pcb-read.bad-index",
                f"{count} records in {storage} name a {kind} past the {limit} {kind}s",
                f"{storage}/Data",
            )
        )


def _property_storage(
    compound: CompoundFile,
    storage: str,
    found: Issues,
    parts: dict[str, tuple[tuple[bytes, ...], bytes]],
    make: Callable[[PropertyRecord, KeyReader], P],
    *,
    lead: int = 0,
) -> tuple[P, ...]:
    path = f"{storage}/Data"
    if path not in compound:
        return ()
    records, trailing, problems = parse_blocks(compound.read(path), lead=lead, where=path)
    found.add(*problems)
    parts[storage] = (tuple(r.raw for r in records), trailing)
    out: list[P] = []
    for number, record in enumerate(records):
        values = KeyReader(record, f"{path}#{number}")
        out.append(make(record, values))
        found.add(*values.issues)
    if not trailing:
        _counted(found, compound, storage, len(records))
    return tuple(out)


def read_pcbdoc(source: bytes | CompoundFile, *, file: str = "", strict: bool = False) -> PcbDocument:
    """A binary PCB document. ``source`` is the file's bytes or an open ``CompoundFile``. A source that is
    no compound file, or has no ``Board6/Data``, raises ``PcbReadError`` in both modes; a container error of
    ``read.cfb`` is passed on unchanged."""
    compound = _open(source, file=file)
    found = Issues(file=file, strict=strict)
    found.add(*compound.notes)
    if "Board6/Data" not in compound:
        raise PcbReadError(
            f"no Board6/Data: {BINARY_ONLY} (a PCB document)", file=file, locator="Board6/Data"
        )
    parts: dict[str, tuple[tuple[bytes, ...], bytes]] = {}

    def board_of(record: PropertyRecord, values: KeyReader) -> BoardRecord:
        board, problems = read_board(record, where=values.where)
        values.issues += problems
        return board

    boards = _property_storage(compound, "Board6", found, parts, board_of)
    if not boards:
        raise PcbReadError(f"Board6/Data holds no record: {BINARY_ONLY}", file=file, locator="Board6/Data")
    nets = _property_storage(compound, "Nets6", found, parts, lambda r, _: net_record(r))
    components = _property_storage(compound, "Components6", found, parts, component_record)
    classes = _property_storage(compound, "Classes6", found, parts, class_record)
    rules = _property_storage(compound, "Rules6", found, parts, rule_record, lead=2)
    polygons = _property_storage(compound, "Polygons6", found, parts, polygon_record)
    uids = _property_storage(compound, "UniqueIDPrimitiveInformation", found, parts, lambda r, _: r)

    decoded: dict[str, tuple[Primitive, ...]] = {}
    others: dict[str, tuple[Primitive, ...]] = {}
    for storage, kind in PRIMITIVE_STORAGES.items():
        path = f"{storage}/Data"
        if path not in compound:
            decoded[storage] = ()
            continue
        items, trailing, problems = decode_primitives(
            compound.read(path), where=path, shape_based=storage == "ShapeBasedRegions6"
        )
        found.add(*problems)
        parts[storage] = (tuple(p.raw for p in items), trailing)
        if not trailing:
            _counted(found, compound, storage, len(items))
        wrong = tuple(p for p in items if primitive_type(p) != kind)
        if wrong:
            found.add(
                issue(
                    "altium.pcb-read.wrong-type",
                    f"{len(wrong)} records of {storage} have another type; they are in others",
                    path,
                )
            )
            others[storage] = wrong
        decoded[storage] = tuple(p for p in items if primitive_type(p) == kind)
        _check_indexes(found, storage, decoded[storage], len(nets), len(components), len(polygons))
    bad_nets = sum(1 for p in polygons if p.net is not None and not 0 <= p.net < len(nets))
    _bad_index(found, "Polygons6", "net", bad_nets, len(nets))

    wide: dict[int, str] = {}
    if "WideStrings6/Data" in compound:
        data = compound.read("WideStrings6/Data")
        table = wide_table(data)
        if table is None:
            found.add(
                issue(
                    "altium.pcb-read.bad-frame",
                    "the wide-string table does not parse; texts keep their 8-bit strings",
                    "WideStrings6/Data",
                )
            )
            parts["WideStrings6"] = ((), data)
        else:
            wide, raws = table
            parts["WideStrings6"] = (raws, b"")
            _counted(found, compound, "WideStrings6", len(raws))

    pad_ids: dict[int, str] = {}
    for record in uids:
        index = record.get("PRIMITIVEINDEX")
        if (record.get("PRIMITIVEOBJECTID") or "").upper() == "PAD" and index is not None and index.isdigit():
            pad_ids[int(index)] = record.text("UNIQUEID")

    six = compound.read("FileHeaderSix") if "FileHeaderSix" in compound else None
    header_text: str | None = None
    unique_id: str | None = None
    if six is not None:
        header_text, _, unique_id = file_header(six)
    elif "FileHeader" in compound:
        header_text = _old_header(compound.read("FileHeader"))
    typed = {f"{name}/DATA".upper() for name in parts}
    return PcbDocument(
        header_text=header_text,
        unique_id=unique_id,
        board=boards[0],
        nets=nets,
        components=components,
        classes=classes,
        rules=rules,
        polygons=polygons,
        pads=_only(decoded["Pads6"], PadRecord),
        vias=_only(decoded["Vias6"], ViaRecord),
        tracks=_only(decoded["Tracks6"], TrackRecord),
        arcs=_only(decoded["Arcs6"], ArcRecord),
        texts=_only(resolve_texts(decoded["Texts6"], wide), TextRecord),
        fills=_only(decoded["Fills6"], FillRecord),
        regions=_only(decoded["Regions6"], RegionRecord),
        shape_regions=_only(decoded["ShapeBasedRegions6"], RegionRecord),
        wide_strings=MappingProxyType(wide),
        pad_unique_ids=MappingProxyType(pad_ids),
        storages=MappingProxyType({k: MappingProxyType(v) for k, v in storages_of(compound, typed).items()}),
        issues=tuple(found.items),
        evidence=EVIDENCE,
        others=MappingProxyType(others),
        parts=MappingProxyType(parts),
    )


def read_rule_fields(
    source: bytes | CompoundFile, *, file: str = ""
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """The pair list of every rule record of a PCB document, in stream order: the input of
    ``read.rules.map_rules``, read from ``Rules6/Data`` alone, so that asking for the rules does not decode
    the copper. ``()`` for a document without that stream; the errors are those of ``read_pcbdoc``."""
    compound = _open(source, file=file)
    path = "Rules6/Data"
    if path not in compound:
        return ()
    records, _trailing, _problems = parse_blocks(compound.read(path), lead=2, where=path)
    return tuple(record.fields for record in records)


T = TypeVar("T")


def _only(items: tuple[Primitive, ...], kind: type[T]) -> tuple[T | RawPrimitive, ...]:
    return tuple(p for p in items if isinstance(p, kind | RawPrimitive))


def _old_header(data: bytes) -> str | None:
    """The text of a ``FileHeader`` of the older form: a 32-bit length, then UTF-16LE characters."""
    rest = data[4:]
    return rest.decode("utf-16-le", errors="replace") if rest and len(rest) % 2 == 0 else None


def _check_indexes(
    found: Issues, storage: str, items: tuple[Primitive, ...], nets: int, components: int, polygons: int
) -> None:
    bad = {"net": 0, "component": 0, "polygon": 0}
    for item in items:
        if isinstance(item, RawPrimitive):
            continue
        pre = item.prefix
        bad["net"] += pre.net is not None and pre.net >= nets
        bad["component"] += pre.component is not None and pre.component >= components
        bad["polygon"] += (
            pre.polygon is not None and pre.polygon != SPLIT_PLANE_POLYGON and pre.polygon >= polygons
        )
    for kind, limit in (("net", nets), ("component", components), ("polygon", polygons)):
        _bad_index(found, storage, kind, bad[kind], limit)


__all__ = [
    "BINARY_ONLY",
    "EVIDENCE",
    "PRIMITIVE_STORAGES",
    "TYPED_STORAGES",
    "ClassRecord",
    "ComponentRecord",
    "Issues",
    "NetRecord",
    "PcbDocument",
    "PcbReadError",
    "PolygonRecord",
    "RuleRecord",
    "decode_name",
    "detect_pcb",
    "file_header",
    "open_container",
    "read_pcbdoc",
    "read_rule_fields",
    "resolve_texts",
    "storages_of",
    "string_header",
]
