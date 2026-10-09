# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The round-trip levels of Altium files (capability altium-verification; change c0044).

- ``rt_a0``: a copy of a compound file through the reader and the compound writer keeps every storage and
  every stream, byte for byte (RT-A0).
- ``rt_a1``: reading a file and encoding what was read gives equal records in every stream (RT-A1).
- ``RT_A2_SCOPE``: what the writers write of the model, the scope of RT-A2.
- ``diff_records``: the records that differ between two files of one kind, stream by stream.

- ``RT_A3_SCOPE``: the scope of RT-A3 (change c0090), which ``rta3.rt_a3`` judges: a document is read
  into the model, the model is written as new documents, and those are read again.

This module parses nothing itself. It holds one ``StreamCodec`` per read kind, built from the public
surface of the readers (``read.sch``, ``read.schlib``, ``read.pcb``, ``read.pcblib``, ``read.project``), and
it writes nothing: copies exist in memory only.
"""

from __future__ import annotations

import dataclasses
import difflib
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from fenolite.backends.altium import cfb as compound_writer
from fenolite.backends.altium import import_evidence
from fenolite.backends.altium.read import cfb, pcb, pcblib, project, sch, schlib
from fenolite.backends.altium.read.pcbprims import RawPrimitive
from fenolite.backends.base import (
    Change,
    ContainerLevel,
    ContainerRoundTrip,
    DiffReport,
    ModelScope,
)
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

COMPOUND_KINDS = frozenset({"altium_schdoc_binary", "altium_schlib", "altium_pcbdoc", "altium_pcblib"})
"""The read kinds that are compound files; the other two are text."""
TEXT_STREAMS: Mapping[str, str] = MappingProxyType({"altium_schdoc_ascii": "ascii", "altium_prjpcb": "text"})
"""The one stream name of each text kind."""
EVIDENCE_RT_A0 = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA0",))
"""The evidence of an RT-A0 verdict: ``INFERRED`` until ``H-A-VER-RTA0`` is confirmed over the corpus."""
PROJECT_READ_EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-RD-PRJ-INI",))
"""The evidence of the project file reader's byte identity (``docs/hypotheses.md``; the reader module
defines no constant of its own)."""
READER_EVIDENCE: Mapping[str, Evidence] = MappingProxyType(
    {
        "altium_pcbdoc": pcb.EVIDENCE,
        "altium_pcblib": pcblib.EVIDENCE,
        "altium_prjpcb": PROJECT_READ_EVIDENCE,
        "altium_schdoc_ascii": sch.EVIDENCE,
        "altium_schdoc_binary": sch.EVIDENCE,
        "altium_schlib": sch.EVIDENCE,
    }
)
"""The evidence of the reader of each read kind: what the records view of ``diff`` rests on."""
_RT_A1 = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA1",))
EVIDENCE_RT_A1: Mapping[str, Evidence] = MappingProxyType(
    {kind: Evidence.combine(evidence, _RT_A1) for kind, evidence in READER_EVIDENCE.items()}
)
"""The evidence of an RT-A1 verdict per read kind: the reader's evidence combined with ``INFERRED`` and
``H-A-VER-RTA1``, until that row is confirmed over the corpus."""

RT_A2_SCOPE = ModelScope(
    fields=MappingProxyType(
        {
            "component": ("ref", "value", "pin_pad_map"),
            "net": ("name", "members"),
            "no_connect": (),
            "netclass": ("name",),
            "footprint": ("position", "rotation", "side"),
            "pad": ("number", "net_id", "position", "size", "corner_ratio"),
            "footprint_graphic": ("kind", "layer", "points", "width", "filled"),
            "track": ("start", "end", "width", "layer", "net_id", "locked"),
            "arc": ("start", "mid", "end", "width", "layer", "net_id", "locked"),
            "via": ("position", "diameter", "drill", "net_id", "locked"),
            "zone": ("outline", "layers", "net_id"),
        }
    ),
    length_tolerance=2,
)
"""What the Altium writers write of the model, per entity kind: the scope of RT-A2 (``docs/altium.md``,
"Round trips", lists every field left out with its reason). A length is written in units of 2.54 nm, so
the written value is at most 1.27 nm from the model's and its reading is rounded to a whole nanometre: two
lengths within 2 nm are equal. Angles are written with six decimals of a degree and are compared exactly.
Since change c0126 the graphics of a footprint (``footprint_graphic``) and the corner ratio of a pad are in
the scope; the fields and the free texts of a footprint are written and not compared."""
EVIDENCE_RT_A2 = Evidence(Level.INFERRED, hypotheses=("H-A-VER-RTA2-3",))
"""RT-A2 never rises above ``INFERRED``: Fenolite's writers are read by Fenolite's readers, so the level
proves consistency, not that Altium reads the files."""
RT_A3_SCOPE = RT_A2_SCOPE
"""The scope of RT-A3 is the written scope of the writers (``AltiumBackend.written_scope()``): what a
write carries of a model is compared, whatever the model was read from."""
EVIDENCE_RT_A3 = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-VER-RTA3",))
"""The evidence of an RT-A3 verdict, at the level of its row: since change c0127 every listed public PCB
document is equal inside the written scope. Fenolite reads what Fenolite wrote, so the level says that
the write and the import agree on the model of a public document, not that Altium reads the documents.
``rta3.rt_a3`` combines it with the import's evidence, which is ``INFERRED``, so a verdict and a stage
stay ``INFERRED``."""
BODY_SCOPE = ModelScope(
    fields=MappingProxyType({"body": ("kind", "height", "standoff", "outline", "layer", "name")}),
    length_tolerance=2,
)
"""What a written component body carries of the model's body (change c0121; capability
altium-verification, "Component bodies in the round trips"). It is no part of ``RT_A2_SCOPE``: bodies are
written on request only, and they are compared, by ``bodydiff.body_differences``, exactly when they were
written."""
EVIDENCE_BODIES = Evidence(Level.INFERRED, hypotheses=("H-A-PCBX-BODY-READBACK",))
"""The evidence of a comparison of bodies: Fenolite reads what Fenolite wrote."""


def body_changes(
    differences: Sequence[tuple[str, str, Mapping[str, Any] | None, Mapping[str, Any] | None]],
) -> tuple[Change, ...]:
    """The differences of ``bodydiff.body_differences`` as the ``Change`` values of a report: each side is
    the compact canonical JSON of its compared view (``""`` for none)."""

    def text(view: Mapping[str, Any] | None) -> str:
        if view is None:
            return ""
        return json.dumps(view, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    return tuple(Change(path, cast(Any, change), text(a), text(b)) for path, change, a, b in differences)


def unwritten_pin_maps(design: Any) -> int:
    """The number of ``pin_pads`` records in the ``altium`` bags of the components of ``design`` (a
    ``Design``): what a footprint model says of its pins that the model's map cannot hold, and no writer
    writes (change c0123; a record without a pad, or with a pad that another pin holds)."""
    count = 0
    for component in design.circuit.components:
        bag = component.ext.get("altium")
        count += sum(1 for key, _value in (bag.payload if bag is not None else ()) if key == "pin_pads")
    return count


RECORD_PREFIX = "record:"
"""In ``ModelRoundTrip.unwritten`` of RT-A3, a key with this prefix counts records of the first reading
that gave no model entity (the import's census, by its category); a key without it counts model items."""
STAGE_EVIDENCE: Mapping[str, Evidence] = MappingProxyType(
    {
        "erc.lite": Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-VER-ERC",)),
        "netlist.assignment_compare": Evidence(
            import_evidence.LEVELS["H-A-IMP-NETLIST"], hypotheses=("H-A-IMP-NETLIST",)
        ),
        "roundtrip.rta2": EVIDENCE_RT_A2,
        "copper.clearance": Evidence(Level.INFERRED, hypotheses=("H-A-DRC-SAME",)),
        "parity": Evidence(Level.INFERRED, hypotheses=("H-A-DRC-PARITY",)),
        "roundtrip.rta3": EVIDENCE_RT_A3,
    }
)
"""What the Altium backend adds to the evidence of a check stage: the hypotheses its readings rest on for
that stage (``DocumentValidator.stage_evidence``)."""


@dataclass(frozen=True, slots=True)
class StreamCodec:
    """How one read kind is read and encoded again, stream by stream.

    ``read(data, file)`` gives the reading; ``streams(reading)`` the paths of the streams the reader types;
    ``encode(reading, path)`` the bytes of one of them, rebuilt from its records; ``records(reading, path)``
    its records in stream order (with the bytes the reader keeps beside them); ``opaque(reading)`` the number
    of records the reader keeps without a typed class.
    """

    read: Callable[[bytes, str], Any]
    streams: Callable[[Any], tuple[str, ...]]
    encode: Callable[[Any, str], bytes]
    records: Callable[[Any, str], Sequence[Any]]
    opaque: Callable[[Any], int]


# --- schematic documents ------------------------------------------------------------------------------------


def _sch_read(data: bytes, file: str) -> sch.SchDocument:
    return sch.read_schematic(data, file=file)


def _sch_streams(document: sch.SchDocument) -> tuple[str, ...]:
    return ("ascii",) if document.form == "ascii" else tuple(document.streams)


def _sch_records(document: sch.SchDocument, path: str) -> Sequence[Any]:
    folded = path.upper()
    if document.form == "ascii":
        return (
            document.header,
            *document.records,
            *document.additional,
            *document.blank_lines,
            *document.extra_sections,
            document.preamble,
        )
    if folded == "FILEHEADER":
        return (document.header, *document.records)
    if folded == "ADDITIONAL":
        head = () if document.additional_header is None else (document.additional_header,)
        return (*head, *document.additional)
    if folded == "STORAGE":
        head = () if document.storage_header is None else (document.storage_header,)
        return (*head, *document.embedded)
    raise KeyError(path)


def _sch_opaque(document: sch.SchDocument) -> int:
    return sum(isinstance(record, sch.UnknownRecord) for record in document.all_records())


_SCH = StreamCodec(_sch_read, _sch_streams, sch.encode_stream, _sch_records, _sch_opaque)

# --- schematic libraries ------------------------------------------------------------------------------------


def _schlib_read(data: bytes, file: str) -> schlib.SchLibrary:
    return schlib.read_schlib(data, file=file)


def _schlib_records(library: schlib.SchLibrary, path: str) -> Sequence[Any]:
    folded = path.upper()
    if folded == "FILEHEADER":
        return (library.header, library.header_tail)
    if folded == "SECTIONKEYS":
        return library.section_keys_records
    if folded == "STORAGE":
        head = () if library.storage_header is None else (library.storage_header,)
        return (*head, *library.embedded)
    storage = path.rpartition("/")[0].upper()
    for component in library.components:
        if component.storage_name.upper() == storage:
            return component.records
    raise KeyError(path)


def _schlib_opaque(library: schlib.SchLibrary) -> int:
    return sum(isinstance(r, sch.UnknownRecord) for c in library.components for r in c.records)


_SCHLIB = StreamCodec(
    _schlib_read,
    lambda library: tuple(library.streams),
    schlib.encode_stream,
    _schlib_records,
    _schlib_opaque,
)

# --- PCB documents ------------------------------------------------------------------------------------------

_PCB_TUPLES: Mapping[str, str] = MappingProxyType(
    {
        "Nets6": "nets",
        "Components6": "components",
        "Classes6": "classes",
        "Rules6": "rules",
        "Polygons6": "polygons",
        "Pads6": "pads",
        "Vias6": "vias",
        "Tracks6": "tracks",
        "Arcs6": "arcs",
        "Texts6": "texts",
        "Fills6": "fills",
        "Regions6": "regions",
        "ShapeBasedRegions6": "shape_regions",
    }
)
"""The record tuple of ``PcbDocument`` that holds each typed storage; the others compare their records'
bytes."""
_PRIMITIVE_TUPLES = ("pads", "vias", "tracks", "arcs", "texts", "fills", "regions", "shape_regions")


def _pcb_read(data: bytes, file: str) -> pcb.PcbDocument:
    return pcb.read_pcbdoc(data, file=file)


def _pcb_storage(document: pcb.PcbDocument, path: str) -> str:
    wanted = path.rpartition("/")[0].upper()
    for name in document.parts:
        if name.upper() == wanted:
            return name
    raise KeyError(path)


def _pcb_records(document: pcb.PcbDocument, path: str) -> Sequence[Any]:
    storage = _pcb_storage(document, path)
    raws, trailing = document.parts[storage]
    typed: Sequence[Any] | None = getattr(document, _PCB_TUPLES.get(storage, ""), None)
    if storage == "Board6":
        typed = (document.board,)
    items: Sequence[Any] = typed if typed is not None and len(typed) == len(raws) else raws
    return (*items, trailing) if trailing else tuple(items)


def _pcb_opaque(document: pcb.PcbDocument) -> int:
    kept = sum(isinstance(p, RawPrimitive) for name in _PRIMITIVE_TUPLES for p in getattr(document, name))
    return kept + sum(len(found) for found in document.others.values())


_PCB = StreamCodec(
    _pcb_read,
    lambda document: tuple(f"{storage}/Data" for storage in document.parts),
    lambda document, path: document.rebuild(_pcb_storage(document, path)),
    _pcb_records,
    _pcb_opaque,
)

# --- PCB libraries ------------------------------------------------------------------------------------------


def _pcblib_read(data: bytes, file: str) -> pcblib.PcbLibrary:
    return pcblib.read_pcblib(data, file=file)


def _footprint(library: pcblib.PcbLibrary, path: str) -> pcblib.LibFootprint:
    wanted = path.rpartition("/")[0].upper()
    for footprint in library.footprints:
        if footprint.storage.upper() == wanted:
            return footprint
    raise KeyError(path)


def _pcblib_records(library: pcblib.PcbLibrary, path: str) -> Sequence[Any]:
    footprint = _footprint(library, path)
    tail = (footprint.trailing,) if footprint.trailing else ()
    return (footprint.name_block, *footprint.primitives, *tail)


_PCBLIB = StreamCodec(
    _pcblib_read,
    lambda library: tuple(f"{footprint.storage}/Data" for footprint in library.footprints),
    lambda library, path: _footprint(library, path).rebuild(),
    _pcblib_records,
    lambda library: sum(isinstance(p, RawPrimitive) for f in library.footprints for p in f.primitives),
)

# --- project files ------------------------------------------------------------------------------------------


def _project_read(data: bytes, file: str) -> project.ProjectFile:
    return project.read_project(data, file=file)


_PROJECT = StreamCodec(
    _project_read,
    lambda listed: ("text",),
    lambda listed, path: listed.to_bytes(),
    lambda listed, path: (listed.ini.form.bom, *listed.ini.form.lines),
    lambda listed: 0,
)

CODECS: Mapping[str, StreamCodec] = MappingProxyType(
    {
        "altium_pcbdoc": _PCB,
        "altium_pcblib": _PCBLIB,
        "altium_prjpcb": _PROJECT,
        "altium_schdoc_ascii": _SCH,
        "altium_schdoc_binary": _SCH,
        "altium_schlib": _SCHLIB,
    }
)
"""One codec per read kind of the Altium backend."""


def _codec(kind: str) -> StreamCodec:
    codec = CODECS.get(kind)
    if codec is None:
        raise ValueError(f"{kind!r} is not an Altium read kind: {', '.join(sorted(CODECS))}")
    return codec


# --- RT-A0 --------------------------------------------------------------------------------------------------


def _verdict(
    level: ContainerLevel,
    evidence: Evidence,
    *,
    different: Sequence[str] = (),
    difference: str = "",
    reason: str = "",
    streams: int = 0,
    records: int = 0,
    bytes_equal: int = 0,
    opaque_count: int = 0,
) -> ContainerRoundTrip:
    """A verdict: not judged with a ``reason``, else passed exactly when no stream differs."""
    return ContainerRoundTrip(
        level,
        judged=not reason,
        passed=not reason and not different,
        streams=streams,
        different=tuple(different),
        records=records,
        bytes_equal=bytes_equal,
        opaque_count=opaque_count,
        difference=difference,
        reason=reason,
        evidence=evidence,
    )


def _copy_refusal(error: ValueError) -> str:
    return "too-large" if isinstance(error, compound_writer.CompoundTooLarge) else "writer-refused"


def rt_a0(data: bytes, *, kind: str, file: str = "") -> ContainerRoundTrip:
    """RT-A0 of the file ``data`` of read kind ``kind``: read it, write it again with the compound writer,
    read the copy, and compare storage paths, stream paths (with the stored spelling) and stream bytes.

    CLSIDs, state bits, times, the sector size and the sector layout are not compared. Not judged, with a
    reason: ``not-a-container`` for a text kind, ``too-large`` for a file that needs DIFAT sectors, and
    ``writer-refused`` for any other tree the writer does not write. The reader's ``CompoundError`` is raised
    unchanged; nothing is written to disk.
    """
    _codec(kind)
    if kind not in COMPOUND_KINDS:
        return _verdict("RT-A0", EVIDENCE_RT_A0, reason="not-a-container")
    first = cfb.open_compound(data, file=file)
    streams = first.streams()
    try:
        copy = compound_writer.write_compound(first.tree())
    except ValueError as error:
        return _verdict("RT-A0", EVIDENCE_RT_A0, reason=_copy_refusal(error), streams=len(streams))
    second = cfb.open_compound(copy, file=file)
    different = set(first.storages()) ^ set(second.storages())
    different |= set(streams) ^ set(second.streams())
    different |= {path for path in streams if path in second and first.read(path) != second.read(path)}
    found = sorted(different)
    first_found = found[0] if found else ""
    return _verdict("RT-A0", EVIDENCE_RT_A0, different=found, difference=first_found, streams=len(streams))


# --- RT-A1 --------------------------------------------------------------------------------------------------


def _same(a: Any, b: Any) -> bool:
    """Whether two records are equal in every field. ``==`` decides, except that two NaN values of one
    field are equal: a record holds what the bytes hold."""
    if a is b or a == b:
        return True
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return a != a and b != b  # both are NaN (no ``math`` in this package)
    if dataclasses.is_dataclass(a):
        return all(_same(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a) if f.compare)
    if isinstance(a, (tuple, list)):
        left, right = cast(Sequence[Any], a), cast(Sequence[Any], b)
        return len(left) == len(right) and all(_same(x, y) for x, y in zip(left, right, strict=True))
    if isinstance(a, Mapping):
        one, other = cast(Mapping[Any, Any], a), cast(Mapping[Any, Any], b)
        return one.keys() == other.keys() and all(_same(one[key], other[key]) for key in one)
    return False


def first_unequal(a: Sequence[Any], b: Sequence[Any]) -> int | None:
    """The index of the first record that differs between two sequences of one length, or ``None``."""
    for index, (left, right) in enumerate(zip(a, b, strict=True)):
        if not _same(left, right):
            return index
    return None


def _stream_bytes(data: bytes, kind: str, file: str) -> dict[str, bytes]:
    """The bytes of every stream of the file, by path in upper case (a text file is its one stream)."""
    if kind in TEXT_STREAMS:
        return {TEXT_STREAMS[kind].upper(): data}
    compound = cfb.open_compound(data, file=file)
    return {path.upper(): compound.read(path) for path in compound.streams()}


def _with_streams(data: bytes, kind: str, file: str, encoded: Mapping[str, bytes]) -> bytes:
    """The file with its typed streams replaced by ``encoded`` (paths in upper case); a compound file is
    written by the compound writer, whose ``ValueError`` is raised."""
    if kind in TEXT_STREAMS:
        return encoded[TEXT_STREAMS[kind].upper()]

    def replaced(entries: Sequence[Any], prefix: str) -> tuple[Any, ...]:
        out: list[Any] = []
        for entry in entries:
            if isinstance(entry, compound_writer.Storage):
                inner = replaced(entry.entries, f"{prefix}{entry.name}/")
                out.append(compound_writer.Storage(entry.name, inner))
            else:
                name, content = entry
                out.append((name, encoded.get(f"{prefix}{name}".upper(), content)))
        return tuple(out)

    return compound_writer.write_compound(replaced(cfb.open_compound(data, file=file).tree(), ""))


def rt_a1(data: bytes, *, kind: str, file: str = "") -> ContainerRoundTrip:
    """RT-A1 of the file ``data`` of read kind ``kind``: read it, encode every stream the reader types from
    what was read, read the encoded streams again with the same reader, and compare the records of each
    stream.

    ``streams`` counts the typed streams, ``records`` the records compared, ``bytes_equal`` the typed streams
    whose encoded bytes equal the bytes read, and ``opaque_count`` the records kept without a typed class
    plus the streams kept whole. ``different`` holds the streams whose records differ; ``difference`` is
    ``<stream>#<index>`` of the first differing record, or ``<stream>`` when the counts differ. The level is
    judged for every file that reads, with one exception: when a stream's encoded bytes differ from the bytes
    read and the compound writer cannot write the file that holds them, the verdict is not judged, with the
    reason of ``rt_a0``. The reader's ``FormatError`` is raised unchanged; nothing is written to disk.
    """
    codec = _codec(kind)
    evidence = EVIDENCE_RT_A1[kind]
    first = codec.read(data, file)
    names = codec.streams(first)
    stored = _stream_bytes(data, kind, file)
    encoded = {name.upper(): codec.encode(first, name) for name in names}
    bytes_equal = sum(stored.get(path) == content for path, content in encoded.items())
    opaque = codec.opaque(first) + len(set(stored) - set(encoded))

    def verdict(different: Sequence[str] = (), difference: str = "", reason: str = "", records: int = 0):  # noqa: ANN202
        return _verdict(
            "RT-A1", evidence, different=different, difference=difference, reason=reason, streams=len(names),
            records=records, bytes_equal=bytes_equal, opaque_count=opaque,
        )  # fmt: skip

    if bytes_equal == len(names):
        # Every encoded stream is the stream that was read: the file to read again is the file itself.
        second = codec.read(data, file)
    else:
        try:
            rebuilt = _with_streams(data, kind, file, encoded)
        except ValueError as error:
            return verdict(reason=_copy_refusal(error))
        try:
            second = codec.read(rebuilt, file)
        except FormatError:
            # The encoded streams do not read: every stream whose bytes changed has lost its records.
            lost = [name for name in names if stored.get(name.upper()) != encoded[name.upper()]]
            return verdict(lost, lost[0])
    again = {name.upper() for name in codec.streams(second)}
    different: list[str] = []
    difference = ""
    compared = 0
    for name in names:
        before = codec.records(first, name)
        after = codec.records(second, name) if name.upper() in again else ()
        compared += len(before)
        index = None if len(before) != len(after) else first_unequal(before, after)
        if len(before) == len(after) and index is None:
            continue
        different.append(name)
        if not difference:
            difference = name if index is None else f"{name}#{index}"
    return verdict(different, difference, records=compared)


# --- the records view ---------------------------------------------------------------------------------------

MAX_SHOWN = 80
"""A value is shown only when its text is at most this many bytes; a longer or binary one is given as its
length and SHA-256."""
LCS_CELLS = 4_000_000
"""The largest table of the exact alignment of two record runs; past it the runs are aligned greedily."""


def _digest(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _shown(value: Any) -> object:
    """A value of a record as the report shows it: short text and numbers as they are, anything else as a
    length and a SHA-256."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, bytes):
        return _digest(value)
    text = value if isinstance(value, str) else repr(value)
    data = text.encode("utf-8", errors="replace")
    printable = text.isprintable()
    return text if len(data) <= MAX_SHOWN and printable else _digest(data)


def _numbered(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    """Key and value pairs as a mapping; the k-th further use of one key is ``<key>#<k>``."""
    out: dict[str, Any] = {}
    seen: dict[str, int] = {}
    for key, value in pairs:
        count = seen.get(key, 0)
        seen[key] = count + 1
        out[key if not count else f"{key}#{count}"] = value
    return out


def record_fields(record: Any) -> tuple[str, dict[str, Any]]:
    """``(record kind, fields)`` of one record: the keys of its property list in file order, else its
    field names. The record kind is the reader's class name (``bytes`` for kept bytes)."""
    if isinstance(record, bytes):
        return "bytes", {"bytes": record}
    kind = type(record).__name__
    props = getattr(record, "props", None)
    if props is not None and hasattr(props, "items"):
        return kind, _numbered([(item.key, item.raw) for item in props.items])
    listed = getattr(record, "fields", None)
    if not isinstance(listed, tuple):  # a typed view that keeps its property record (the board record)
        listed = getattr(getattr(record, "record", None), "fields", None)
    if isinstance(listed, tuple):
        return kind, _numbered(cast(tuple[tuple[str, Any], ...], listed))
    if dataclasses.is_dataclass(record):
        return kind, {f.name: getattr(record, f.name) for f in dataclasses.fields(record) if f.compare}
    return kind, {"value": record}


def _text_of(kind: str, fields: Mapping[str, Any]) -> str:
    shown = {key: _shown(_plain(value)) for key, value in fields.items()}
    return json.dumps({"kind": kind, "fields": shown}, ensure_ascii=False, separators=(",", ":"))


def _plain(value: Any) -> Any:
    """A property value as text when it is short printable bytes, so that it reads as written."""
    if isinstance(value, bytes) and len(value) <= MAX_SHOWN:
        text = value.decode("latin-1")
        if text.isprintable():
            return text
    return value


def _whole(record: Any) -> str:
    kind, fields = record_fields(record)
    return _text_of(kind, fields)


def _changed(a: Any, b: Any) -> tuple[str, str]:
    """The texts of two records of one kind: the kind and the keys or fields that differ, with both values."""
    kind, left = record_fields(a)
    _, right = record_fields(b)
    keys = [key for key in left if key not in right or not _same(left[key], right[key])]
    keys += [key for key in right if key not in left]
    if not keys:  # equal fields in another order, or bytes outside the fields
        keys = ["(order or layout)"]
        left, right = {keys[0]: list(left)}, {keys[0]: list(right)}
    one = {key: left[key] for key in keys if key in left}
    other = {key: right[key] for key in keys if key in right}
    return _text_of(kind, one), _text_of(kind, other)


def record_content(record: Any) -> Any:
    """What a record holds, apart from where it lies: its frame kind and payload, or its bytes. Two records
    with equal content are the same record for the alignment, wherever they are in their streams (a
    record's index, offset and owner references follow from its place)."""
    if isinstance(record, bytes):
        return record
    payload = getattr(record, "payload", None)
    if isinstance(payload, bytes):
        return (getattr(record, "kind", None), payload)
    raw = getattr(record, "raw", None)
    if not isinstance(raw, bytes):
        raw = getattr(getattr(record, "record", None), "raw", None)
    if isinstance(raw, bytes):
        return (raw, getattr(record, "end", None))
    return record


def _aligned(a: Sequence[Any], b: Sequence[Any]) -> list[tuple[int, int]]:
    """The index pairs of a longest common subsequence of two content sequences. Equal items at both ends
    are paired first; a middle whose table would pass ``LCS_CELLS`` is aligned by ``difflib``'s matching
    blocks instead, which are common subsequences and need not be the longest."""
    start = 0
    while start < len(a) and start < len(b) and a[start] == b[start]:
        start += 1
    end_a, end_b = len(a), len(b)
    while end_a > start and end_b > start and a[end_a - 1] == b[end_b - 1]:
        end_a -= 1
        end_b -= 1
    pairs = [(index, index) for index in range(start)]
    rows, columns = end_a - start, end_b - start
    if rows and columns and rows * columns <= LCS_CELLS:
        table = [[0] * (columns + 1) for _ in range(rows + 1)]
        for i in range(rows - 1, -1, -1):
            for j in range(columns - 1, -1, -1):
                if a[start + i] == b[start + j]:
                    table[i][j] = table[i + 1][j + 1] + 1
                else:
                    table[i][j] = max(table[i + 1][j], table[i][j + 1])
        i = j = 0
        while i < rows and j < columns:
            if a[start + i] == b[start + j]:
                pairs.append((start + i, start + j))
                i, j = i + 1, j + 1
            elif table[i + 1][j] >= table[i][j + 1]:
                i += 1
            else:
                j += 1
    elif rows and columns:
        matcher = difflib.SequenceMatcher(None, a[start:end_a], b[start:end_b], autojunk=False)
        for block in matcher.get_matching_blocks():
            pairs += [(start + block.a + n, start + block.b + n) for n in range(block.size)]
    pairs += [(end_a + offset, end_b + offset) for offset in range(len(a) - end_a)]
    return pairs


def _record_changes(stream: str, a: Sequence[Any], b: Sequence[Any]) -> list[tuple[int, Change]]:
    """The changes between the records of one stream, each with the index it sorts by."""
    changes: list[tuple[int, Change]] = []
    last_a = last_b = 0
    content_a, content_b = [record_content(r) for r in a], [record_content(r) for r in b]
    try:
        hash((tuple(content_a), tuple(content_b)))
    except TypeError:  # a record without bytes of its own: compare by text
        content_a, content_b = [repr(item) for item in content_a], [repr(item) for item in content_b]
    for stop_a, stop_b in [*_aligned(content_a, content_b), (len(a), len(b))]:
        gap_a, gap_b = list(range(last_a, stop_a)), list(range(last_b, stop_b))
        for offset in range(max(len(gap_a), len(gap_b))):
            i = gap_a[offset] if offset < len(gap_a) else None
            j = gap_b[offset] if offset < len(gap_b) else None
            if i is not None and j is not None and record_fields(a[i])[0] == record_fields(b[j])[0]:
                changes.append((i, Change(f"/{stream}#{i}", "changed", *_changed(a[i], b[j]))))
                continue
            if i is not None:
                changes.append((i, Change(f"/{stream}#{i}", "removed", _whole(a[i]), "")))
            if j is not None:
                changes.append((j, Change(f"/{stream}#{j}", "added", "", _whole(b[j]))))
        last_a, last_b = stop_a + 1, stop_b + 1
    return changes


def diff_records(a: bytes, b: bytes, *, kind: str) -> DiffReport:
    """The differences between two Altium files of the read kind ``kind``, stream by stream (capability
    altium-verification, "Records view of two Altium files").

    Streams are matched by path. A stream on one side only is ``removed`` or ``added`` at ``/<stream>``; an
    opaque stream whose bytes differ is ``changed`` at ``/<stream>``, with the SHA-256 of each side. The
    records of a typed stream are aligned by a longest common subsequence of equal records: a record on one
    side only is ``removed`` or ``added`` at ``/<stream>#<index>`` (its own side's index), and two unaligned
    records at the same place of one record kind are one ``changed`` at ``/<stream>#<index of a>``. The
    changes are in stream order and, in a stream, in record order; ``summary`` maps each stream that has a
    change to its counts. The readers' ``FormatError`` is raised unchanged.
    """
    codec = _codec(kind)
    first, second = codec.read(a, ""), codec.read(b, "")
    typed_a = {name.upper(): name for name in codec.streams(first)}
    typed_b = {name.upper(): name for name in codec.streams(second)}
    bytes_a, bytes_b = _stream_bytes(a, kind, ""), _stream_bytes(b, kind, "")
    names = {path.upper(): path for path in _stream_names(b, kind)} | {
        path.upper(): path for path in _stream_names(a, kind)
    }
    changes: list[Change] = []
    summary: dict[str, dict[str, int]] = {}
    for folded in sorted(names):
        stream = names[folded]
        found: list[Change] = []
        if folded not in bytes_b:
            found.append(Change(f"/{stream}", "removed", json.dumps(_digest(bytes_a[folded])), ""))
        elif folded not in bytes_a:
            found.append(Change(f"/{stream}", "added", "", json.dumps(_digest(bytes_b[folded]))))
        elif folded in typed_a and folded in typed_b:
            before = codec.records(first, typed_a[folded])
            after = codec.records(second, typed_b[folded])
            ordered = sorted(
                _record_changes(stream, before, after), key=lambda item: (item[0], item[1].change)
            )
            found += [change for _, change in ordered]
        elif bytes_a[folded] != bytes_b[folded]:
            left = hashlib.sha256(bytes_a[folded]).hexdigest()
            right = hashlib.sha256(bytes_b[folded]).hexdigest()
            found.append(Change(f"/{stream}", "changed", left, right))
        if found:
            counts = summary.setdefault(stream, {"added": 0, "removed": 0, "changed": 0})
            for change in found:
                counts[change.change] += 1
            changes += found
    return DiffReport(not changes, tuple(changes), summary)


def _stream_names(data: bytes, kind: str) -> tuple[str, ...]:
    """The stream paths of the file with their stored spelling (a text file has its one stream name)."""
    if kind in TEXT_STREAMS:
        return (TEXT_STREAMS[kind],)
    return cfb.open_compound(data).streams()


__all__ = [
    "EVIDENCE_BODIES",
    "BODY_SCOPE",
    "body_changes",
    "LCS_CELLS",
    "MAX_SHOWN",
    "READER_EVIDENCE",
    "diff_records",
    "record_content",
    "record_fields",
    "CODECS",
    "COMPOUND_KINDS",
    "EVIDENCE_RT_A0",
    "EVIDENCE_RT_A1",
    "EVIDENCE_RT_A2",
    "EVIDENCE_RT_A3",
    "RECORD_PREFIX",
    "RT_A3_SCOPE",
    "PROJECT_READ_EVIDENCE",
    "RT_A2_SCOPE",
    "STAGE_EVIDENCE",
    "TEXT_STREAMS",
    "StreamCodec",
    "first_unequal",
    "rt_a0",
    "rt_a1",
    "unwritten_pin_maps",
]
