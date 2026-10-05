# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""PCB document reading (capability altium-pcb-reader, "PCB document reading", "Lossless PCB records",
"Nets, components and classes" and "Text records and wide strings", change c0041)."""

from __future__ import annotations

from pathlib import Path

import _altium_pcb_read as independent
import pytest
from _altium_long import block, document, long_text, wide_strings

from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import TYPED_STORAGES, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, PcbReadError, TextRecord, TrackRecord

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


def test_a_stream_is_rebuilt() -> None:
    data = BLINK.read_bytes()
    doc = read_pcbdoc(data)
    compound = open_compound(data)
    typed: set[str] = set()
    for storage in TYPED_STORAGES:
        path = f"{storage}/Data"
        if path in compound:
            assert doc.rebuild(storage) == compound.read(path), storage
            assert doc.trailing(storage) == b""
            typed.add(compound.node(path).path)
    for path in compound.streams():
        if path in typed:
            continue
        storage, _, stream = path.partition("/") if "/" in path else ("", "", path)
        assert doc.storages[storage][stream] == compound.read(path), path
    assert "Header" in doc.storages["Tracks6"]


def test_fenolites_document() -> None:
    data = BLINK.read_bytes()
    doc = read_pcbdoc(data)
    other = independent.read_pcbdoc(data)
    assert doc.issues == ()
    assert [n.name for n in doc.nets] == [n["NAME"] for n in other.nets]
    assert len(doc.components) == 3 == len(other.components)
    assert len(doc.pads) == len(other.pads)
    for mine, theirs in zip(doc.pads, other.pads, strict=True):
        assert isinstance(mine, PadRecord)
        assert (mine.name, mine.x, mine.y, mine.hole, mine.rotation) == (
            theirs.name, theirs.x, theirs.y, theirs.hole, theirs.rotation,
        )  # fmt: skip
        assert (mine.size_top, mine.size_mid, mine.size_bottom) == theirs.sizes
        net = 0xFFFF if mine.prefix.net is None else mine.prefix.net
        assert (net, mine.prefix.layer) == (theirs.prefix.net, theirs.prefix.layer)
    assert [(t.x1, t.y1, t.x2, t.y2, t.width) for t in doc.tracks if isinstance(t, TrackRecord)] == [
        (t.x1, t.y1, t.x2, t.y2, t.width) for t in other.tracks
    ]
    assert len(doc.arcs) == len(other.arcs)
    assert [t.text for t in doc.texts if isinstance(t, TextRecord)] == [
        other.wide_strings.get(t.wide_index or 0, t.text) for t in other.texts
    ]
    assert doc.fills == () and doc.regions == () and doc.shape_regions == ()
    assert doc.header_text == "PCB 6.0 Binary File" and doc.unique_id is not None
    assert doc.evidence.hypotheses and doc.evidence.level.value == "CORPUS-VERIFIED"


def test_not_a_binary_document() -> None:
    with pytest.raises(PcbReadError) as raised:
        read_pcbdoc(b"|RECORD=Board|KIND=Protel_Advanced_PCB|\r\n", file="x.PcbDoc")
    assert "only the binary form" in str(raised.value)
    with pytest.raises(PcbReadError) as raised:
        read_pcbdoc(open_compound((ROOT / "tests/data/altium/blink/blink.PcbLib").read_bytes()), strict=False)
    assert "only the binary form" in str(raised.value)


def test_components_of_fenolites_document() -> None:
    doc = read_pcbdoc(BLINK.read_bytes())
    designators = {c.source_designator: c for c in doc.components}
    assert set(designators) == {"D1", "R1", "U1"}
    assert designators["D1"].layer == "BOTTOM"
    for index in range(len(doc.components)):
        pads = [p for p in doc.primitives_of(index) if isinstance(p, PadRecord)]
        assert pads
        assert any(p.prefix.net is not None for p in pads)
        assert all(doc.net_name(p.prefix.net) is not None for p in pads if p.prefix.net is not None)


def test_designator_text() -> None:
    doc = read_pcbdoc(BLINK.read_bytes())
    for index, component in enumerate(doc.components):
        texts = [t for t in doc.primitives_of(index) if isinstance(t, TextRecord) and t.is_designator]
        assert len(texts) == 1 and texts[0].text == component.source_designator


def test_wide_strings_resolve_texts() -> None:
    doc = read_pcbdoc(
        document(
            {
                "Texts6": [long_text(252, text="x", wide_index=0), long_text(252, text="y", wide_index=9)],
                "WideStrings6": [wide_strings({0: "Ω1", 1: ""})],
            }
        )
    )
    first, second = doc.texts
    assert isinstance(first, TextRecord) and isinstance(second, TextRecord)
    assert first.text == "Ω1" and second.text == "y"
    assert dict(doc.wide_strings) == {0: "Ω1", 1: ""}


def test_empty_wide_string_without_bytes() -> None:
    table = b"\x00\x00\x00\x00\x02\x00\x00\x00" + wide_strings({1: "A"})
    doc = read_pcbdoc(document({"WideStrings6": (2, table)}))
    assert dict(doc.wide_strings) == {0: "", 1: "A"} and doc.issues == ()
    assert doc.rebuild("WideStrings6") == table


def test_bad_wide_string_table() -> None:
    table = wide_strings({0: "A"}) + b"\x01\x00\x00\x00\xff\x00\x00\x00"
    doc = read_pcbdoc(
        document({"Texts6": [long_text(137, text="s", wide_index=0)], "WideStrings6": (1, table)})
    )
    assert [i.code for i in doc.issues] == ["altium.pcb-read.bad-frame"]
    assert isinstance(doc.texts[0], TextRecord) and doc.texts[0].text == "s"
    assert doc.rebuild("WideStrings6") == table


def test_pad_unique_ids_and_regions_of() -> None:
    uids = [block("|PRIMITIVEINDEX=0|PRIMITIVEOBJECTID=Pad|UNIQUEID=AAAAAAAA")]
    doc = read_pcbdoc(document({"UniqueIDPrimitiveInformation": uids}))
    assert dict(doc.pad_unique_ids) == {0: "AAAAAAAA"}
    assert doc.regions_of(0) == ()
