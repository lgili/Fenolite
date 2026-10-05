# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census and identity of the Altium PCB reader on the public corpus (capability altium-pcb-reader,
"Corpus census and identity", change c0041; ``H-A-RD-PCB-FRAME``, ``-IDENTITY``, ``-LENGTHS``,
``-REGION``, ``-TEXT``, ``-RULE``, ``-POLYNAME``, ``-CODEC``).

Every row is read with the product reader. The test writes counts and lengths only: no name, path or
other value of the files reaches its output, which a check of the output itself enforces.
"""

from __future__ import annotations

import json
import struct
from collections import Counter
from collections.abc import Iterable
from typing import Any

import pytest
from _altium_long import document, long_track
from _boards import census
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import TYPED_STORAGES, PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcblib import PcbLibrary, read_pcblib
from fenolite.backends.altium.read.pcbprims import (
    ArcRecord,
    FillRecord,
    PadRecord,
    Primitive,
    RawPrimitive,
    RegionRecord,
    TextRecord,
    TrackRecord,
    ViaRecord,
)

pytestmark = pytest.mark.needs_corpus
DOCUMENTS = manifest_items("altium-pcbdoc")
LIBRARIES = manifest_items("altium-pcblib")
OBSERVED: dict[str, frozenset[int]] = {
    "track": frozenset({45, 49}),
    "arc": frozenset({56, 60}),
    "via": frozenset({299, 321, 351}),
    "fill": frozenset({46, 50}),
    "text": frozenset({232, 252}),
    "pad": frozenset({170, 171, 185, 186, 194}),
    "pad-layers": frozenset({0, 651}),
}
"""The subrecord lengths of the corpus (``pcb-read.md``, "Record lengths"); a new one fails on purpose."""
DESIGNATOR_EXCEPTIONS = {"altium-third-party-pcbdoc-01": (84, 2)}
"""Row id → designator texts that show the logical designator with a channel suffix (components of a
repeated sheet) and that differ otherwise; every other row shows ``SOURCEDESIGNATOR`` exactly
(``H-A-RD-PCB-TEXT`` refuted, ``H-A-RD-PCB-TEXT-2``)."""
KINDS = {TrackRecord: "track", ArcRecord: "arc", ViaRecord: "via", FillRecord: "fill", TextRecord: "text"}


def _lengths(raw: bytes) -> list[int]:
    out: list[int] = []
    at = 1
    while at < len(raw):
        (length,) = struct.unpack_from("<I", raw, at)
        out.append(length)
        at += 4 + length
    return out


def lengths_of(items: Iterable[Primitive]) -> Counter[tuple[str, int]]:
    """``(kind, subrecord length)`` of each typed primitive (the pad's fifth and sixth subrecords)."""
    seen: Counter[tuple[str, int]] = Counter()
    for item in items:
        sizes = _lengths(item.raw)
        if isinstance(item, PadRecord):
            seen[("pad", sizes[4])] += 1
            seen[("pad-layers", sizes[5])] += 1
        elif type(item) in KINDS:
            seen[(KINDS[type(item)], sizes[0])] += 1
    return seen


def length_problems(seen: Counter[tuple[str, int]]) -> list[str]:
    """One message ``<kind> <length>`` per length outside :data:`OBSERVED`."""
    return [f"{kind} {length}" for kind, length in sorted(seen) if length not in OBSERVED[kind]]


def _non_ascii(records: Iterable[Any]) -> tuple[int, int]:
    """Non-ASCII bytes and ``%UTF8%`` keys over property records."""
    high = utf8 = 0
    for record in records:
        high += sum(1 for b in record.raw if b > 0x7F)
        utf8 += sum(1 for key, _ in record.fields if key.upper().startswith("%UTF8%"))
    return high, utf8


def _values_absent(output: str, values: Iterable[str | None]) -> list[str]:
    return [v for v in values if v and len(v) >= 4 and not v.isdigit() and v in output]


def document_census(doc: PcbDocument, data: bytes) -> tuple[dict[str, Any], list[str]]:
    """The counts of one document and the problems the census finds."""
    problems: list[str] = []
    errors = [i for i in doc.issues if i.severity == "error" or i.code == "altium.pcb-read.short-record"]
    problems += [f"issue {i.code} at {i.where.split('#')[0]}" for i in errors]
    compound = open_compound(data)
    for storage in TYPED_STORAGES:
        if f"{storage}/Data" in compound:
            if doc.rebuild(storage) != compound.read(f"{storage}/Data"):
                problems.append(f"{storage} does not rebuild")
            if doc.trailing(storage):
                problems.append(f"{storage} has {len(doc.trailing(storage))} trailing bytes")
    primitives = [*doc.pads, *doc.tracks, *doc.arcs, *doc.vias, *doc.fills, *doc.texts]
    seen = lengths_of(primitives)
    problems += [f"new length {p}" for p in length_problems(seen)]
    raw = sum(isinstance(p, RawPrimitive) for p in [*primitives, *doc.regions, *doc.shape_regions])
    regions = [r for r in (*doc.regions, *doc.shape_regions) if isinstance(r, RegionRecord)]
    problems += [f"a region has a tail of {len(r.tail)} bytes" for r in regions if r.tail]
    if len(doc.regions) != len(doc.shape_regions):
        problems.append(f"Regions6 {len(doc.regions)} and ShapeBasedRegions6 {len(doc.shape_regions)} differ")
    designators, channel, other = designator_texts(doc)
    names = [p.name for p in doc.polygons if p.name]
    problems += ["a polygon name is not printable" for n in names if not n.isprintable()]
    high, utf8 = _non_ascii(
        [doc.board.record, *doc.nets, *doc.components, *doc.classes, *doc.rules, *doc.polygons]
    )
    counts: dict[str, Any] = {
        "nets": len(doc.nets),
        "components": len(doc.components),
        "classes": len(doc.classes),
        "rules": len(doc.rules),
        "polygons": len(doc.polygons),
        "named_polygons": len(names),
        "pads": len(doc.pads),
        "vias": len(doc.vias),
        "tracks": len(doc.tracks),
        "arcs": len(doc.arcs),
        "texts": len(doc.texts),
        "designator_texts": designators,
        "designators_with_channel_suffix": channel,
        "designators_changed_on_the_board": other,
        "fills": len(doc.fills),
        "regions": len(doc.regions),
        "shape_regions": len(doc.shape_regions),
        "raw_primitives": raw,
        "wide_strings": len(doc.wide_strings),
        "copper_layers": len(doc.board.copper_chain),
        "stack_entries": len(doc.board.stack),
        "untyped_storages": len([s for s in doc.storages if s]),
        "lengths": {f"{k} {n}": c for (k, n), c in sorted(seen.items())},
        "non_ascii_bytes": high,
        "utf8_keys": utf8,
        "issues": dict(Counter(i.code for i in doc.issues)),
    }
    return counts, problems


def library_census(lib: PcbLibrary, data: bytes) -> tuple[dict[str, Any], list[str]]:
    problems = [f"issue {i.code}" for i in lib.issues if i.severity == "error" or "short-record" in i.code]
    compound = open_compound(data)
    primitives: list[Primitive] = []
    for footprint in lib.footprints:
        if footprint.rebuild() != compound.read(f"{footprint.storage}/Data"):
            problems.append("a footprint does not rebuild")
        if footprint.trailing:
            problems.append(f"a footprint has {len(footprint.trailing)} trailing bytes")
        primitives += footprint.primitives
    seen = lengths_of(primitives)
    problems += [f"new length {p}" for p in length_problems(seen)]
    regions = [p for p in primitives if isinstance(p, RegionRecord)]
    problems += [f"a region has a tail of {len(r.tail)} bytes" for r in regions if r.tail]
    high, utf8 = _non_ascii([lib.board.record, *(f.parameters for f in lib.footprints)])
    counts: dict[str, Any] = {
        "footprints": len(lib.footprints),
        "names": len(lib.names),
        "primitives": len(primitives),
        "pads": sum(isinstance(p, PadRecord) for p in primitives),
        "tracks": sum(isinstance(p, TrackRecord) for p in primitives),
        "arcs": sum(isinstance(p, ArcRecord) for p in primitives),
        "texts": sum(isinstance(p, TextRecord) for p in primitives),
        "regions": len(regions),
        "raw_primitives": sum(isinstance(p, RawPrimitive) for p in primitives),
        "lengths": {f"{k} {n}": c for (k, n), c in sorted(seen.items())},
        "non_ascii_bytes": high,
        "utf8_keys": utf8,
        "issues": dict(Counter(i.code for i in lib.issues)),
    }
    return counts, problems


def designator_texts(doc: PcbDocument) -> tuple[int, int, int]:
    """Designator texts of components, those whose shown string is the component's ``SOURCEDESIGNATOR``
    with a suffix while that designator is shared by several components (a repeated sheet), and the
    other ones that differ from it (``H-A-RD-PCB-TEXT-2``)."""
    shared = Counter(c.source_designator for c in doc.components)
    total = channel = other = 0
    for text in doc.texts:
        if isinstance(text, TextRecord) and text.is_designator and text.prefix.component is not None:
            total += 1
            source = doc.components[text.prefix.component].source_designator or ""
            if text.text == source:
                continue
            if text.text.startswith(source) and shared[source] > 1:
                channel += 1
            else:
                other += 1
    return total, channel, other


def _document_values(doc: PcbDocument) -> list[str | None]:
    return [
        doc.board.filename,
        *(n.name for n in doc.nets),
        *(c.source_designator for c in doc.components),
        *(c.pattern for c in doc.components),
        *(p.name for p in doc.polygons),
        *(r.name for r in doc.rules),
    ]


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_document_census(item: CorpusItem) -> None:
    data = require(item).read_bytes()
    doc = read_pcbdoc(data)
    counts, problems = document_census(doc, data)
    output = json.dumps(counts, sort_keys=True)
    assert not _values_absent(output, _document_values(doc)), "a value of the file reached the output"
    census("altium_pcb_read", item.id, counts)
    print(item.id, output)
    assert not problems, "; ".join(problems)
    found = (counts["designators_with_channel_suffix"], counts["designators_changed_on_the_board"])
    assert found == DESIGNATOR_EXCEPTIONS.get(item.id, (0, 0)), (
        "designator texts differ from SOURCEDESIGNATOR"
    )


@pytest.mark.parametrize("item", LIBRARIES, ids=lambda item: item.id)
def test_library_census(item: CorpusItem) -> None:
    data = require(item).read_bytes()
    lib = read_pcblib(data)
    counts, problems = library_census(lib, data)
    output = json.dumps(counts, sort_keys=True)
    values = [lib.board.filename, *lib.names, *(f.description for f in lib.footprints)]
    assert not _values_absent(output, values), "a value of the file reached the output"
    census("altium_pcb_read", item.id, counts)
    print(item.id, output)
    assert not problems, "; ".join(problems)


def test_rule_kinds_over_the_corpus() -> None:
    texts: dict[int, set[str | None]] = {}
    read = 0
    for item in DOCUMENTS:
        data = require(item).read_bytes()
        for rule in read_pcbdoc(data).rules:
            texts.setdefault(rule.kind_number, set()).add(rule.rule_kind)
        read += 1
    assert read == 7
    assert all(len(kinds) == 1 for kinds in texts.values()), "a kind number has several RULEKIND texts"
    census("altium_pcb_read_rules", "kinds", {str(k): sorted(map(str, v)) for k, v in sorted(texts.items())})


def test_eleven_rows() -> None:
    assert len(DOCUMENTS) == 7 and len(LIBRARIES) == 4
    for item in (*DOCUMENTS, *LIBRARIES):
        require(item)


def test_a_new_length() -> None:
    doc = read_pcbdoc(document({"Tracks6": [long_track(53)]}))
    assert isinstance(doc.tracks[0], TrackRecord) and doc.issues == ()
    assert length_problems(lengths_of(doc.tracks)) == ["track 53"]
