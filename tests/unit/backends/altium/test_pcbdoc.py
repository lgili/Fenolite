# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium PCB document writer (change c0035, capability altium-pcb-writer, "PCB document file",
"PCB document placement", "PCB document links and nets")."""

from __future__ import annotations

import base64
import dataclasses
import struct
import zlib
from functools import cache

import pytest
from _altium import blink_pcbdoc_spec
from _altium_pcb_read import PcbDoc, read_pcbdoc

from fenolite.backends.altium.docboard import angle_text
from fenolite.backends.altium.libboard import guid
from fenolite.backends.altium.pcbdoc import (
    COPPER_STORAGES,
    EMPTY_STORAGES,
    NO_CONSTRAINTS,
    OPTION_STORAGES,
    PcbDocSpec,
    degrees_text,
    record_layer,
    write_pcbdoc,
)
from fenolite.core.coords import Point
from fenolite.model.board import Arc, Track, Via

STORAGES = (
    "Board6",
    "Nets6",
    "Components6",
    "Pads6",
    "Tracks6",
    "Arcs6",
    "Texts6",
    "WideStrings6",
    "UniqueIDPrimitiveInformation",
)
COMMON = ["SELECTION", "LAYER", "LOCKED", "POLYGONOUTLINE", "USERROUTED", "KEEPOUT", "UNIONINDEX"]


@cache
def blink_doc() -> tuple[PcbDoc, PcbDocSpec]:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    return read_pcbdoc(write_pcbdoc(spec, filename="blink.PcbDoc")), spec


# --- 4.1: headers, board, nets --------------------------------------------------------------------


def test_storages_of_the_sample() -> None:
    """Scenario "Storages of the sample": root streams and 42 storages, counts equal, empty ones empty."""
    doc, _spec = blink_doc()
    assert sorted(doc.storages) == sorted((*STORAGES, *OPTION_STORAGES, *COPPER_STORAGES, *EMPTY_STORAGES))
    assert len(doc.storages) == 42 and len(EMPTY_STORAGES) == 21
    assert len(doc.board_fields) == 2231
    for name in (*EMPTY_STORAGES, *COPPER_STORAGES):
        assert doc.storages[name] == (0, b"")
    assert doc.file_header == struct.pack("<I", 19) + "PCB 5.0 Bi".encode("utf-16-le")
    start = struct.pack("<IB", 19, 19) + b"PCB 6.0 Binary File" + struct.pack("<d", 5.01)
    assert doc.file_header_six.startswith(start + struct.pack("<IB", 38, 38) + b"{")
    assert len(doc.file_header_six) == len(start) + 5 + 38 and doc.file_header_six.endswith(b"}")


def test_option_storages() -> None:
    """Scenario "Option storages": the fixed blocks, the pad-template libraries and the wide strings."""
    doc, _spec = blink_doc()
    headers = {name: doc.storages[name][0] for name in OPTION_STORAGES}
    assert headers == {
        "Advanced Placer Options6": 1,
        "Pin Swap Options6": 1,
        "Design Rule Checker Options6": 1,
        "PadViaLibrary": 0,
        "PadViaLibraryCache": 0,
        "LayerKindMapping": 1,
        "ConstraintManager": 1,
        "SignalClasses": 1,
    }
    placer, swap, checker = (doc.options[name] for name in OPTION_STORAGES[:3])
    assert len(placer) == 9 and placer["PLACELARGECLEAR"] == "50mil" and placer["PLACESMALLCLEAR"] == "20mil"
    assert len(swap) == 14 and swap["CROSSOVERRATIO"] == "50" and swap["IGNORENETS"] == ""
    assert len(checker) == 21 and checker["MAXVIOLATIONCOUNT"] == "500" and checker["REPORTFILENAME"] == ""
    assert checker["RULESETTOCHECK"].split(",")[:3] == ["0", "1", "2"]
    libraries = [doc.options[name] for name in ("PadViaLibrary", "PadViaLibraryCache")]
    assert [list(lib) for lib in libraries] == [
        ["PADVIALIBRARY.LIBRARYID", "PADVIALIBRARY.LIBRARYNAME", "PADVIALIBRARY.DISPLAYUNITS"]
    ] * 2
    assert [lib["PADVIALIBRARY.LIBRARYID"] for lib in libraries] == [
        guid("pcbdoc:blink.PcbDoc:padvia"),
        guid("pcbdoc:blink.PcbDoc:padviacache"),
    ]
    assert doc.storages["LayerKindMapping"][1] == struct.pack("<I", 8) + "1.0\0".encode("utf-16-le") + bytes(
        8
    )
    assert NO_CONSTRAINTS == base64.b64encode(zlib.compress(b"", 9)).decode("ascii")
    text = (NO_CONSTRAINTS + "\0").encode("utf-16-le")
    assert doc.storages["ConstraintManager"][1] == struct.pack("<I", len(text)) + text
    signals = doc.options["SignalClasses"]
    assert list(signals)[:7] == COMMON and signals["LAYER"] == "MULTILAYER"
    assert signals["NAME"] == "All xSignals" and signals["KIND"] == "10" and len(signals["UNIQUEID"]) == 8


def test_unique_id_of_every_pad() -> None:
    from fenolite.backends.altium.project import unique_id

    doc, _spec = blink_doc()
    assert len(doc.unique_ids) == len(doc.pads) == 36
    assert [u["UNIQUEID"] for u in doc.unique_ids] == [
        unique_id(f"pcbdoc:blink.PcbDoc:pad:{index}") for index in range(36)
    ]


def test_two_layer_stack() -> None:
    """Scenario "Two-layer stack": NEXT from 1 gives 32, then 0; five outline vertices, closed."""
    doc, _spec = blink_doc()
    board = doc.board
    layer, walk = 1, []
    while layer:
        walk.append(layer)
        layer = int(board[f"LAYER{layer}NEXT"])
    assert walk == [1, 32] and board["LAYER32PREV"] == "1"
    assert board["LAYER1NAME"] == "Top Layer" and board["LAYER74NAME"] == "Multi-Layer"
    assert all(f"LAYER{i}NAME" in board for i in range(1, 83)) and "LAYER83NAME" not in board
    enabled = [i for i in range(1, 83) if board[f"LAYER{i}MECHENABLED"] == "TRUE"]
    assert enabled == [69, 70, 71, 72]
    vertices = [(board[f"VX{k}"], board[f"VY{k}"]) for k in range(5)]
    assert (
        "VX5" not in board
        and vertices[0] == vertices[-1]
        and [board[f"KIND{k}"] for k in range(5)] == ["0"] * 5
    )
    assert vertices[0] == ("1000mil", "1000mil") or ("1000mil", "1000mil") in vertices
    assert board["ORIGINX"] == board["ORIGINY"] == board["GR0_OX"] == board["GR0_OY"] == "1000mil"
    assert board["KIND"] == "Protel_Advanced_PCB" and board["VERSION"] == "5.01"
    assert board["FILENAME"] == "blink.PcbDoc" and board["V9_SUBSTACK0_NAME"] == "Board Layer Stack"


def test_board_record_marks_the_used_layers() -> None:
    """``USEDBYPRIMS`` is TRUE for exactly the layers the written primitives lie on."""
    doc, spec = blink_doc()
    layers = {p.prefix.layer for p in (*doc.pads, *doc.tracks, *doc.arcs, *doc.texts)}
    assert layers == {1, 33, 34, 69, 70, 71, 72, 74}
    names = {1: "Top Layer", 33: "Top Overlay", 34: "Bottom Overlay", 74: "Multi-Layer"}
    names.update({56 + n: f"Mechanical {n}" for n in (13, 14, 15, 16)})
    board = doc.board
    used = {
        board[f"V9_CACHE_LAYER{i}_NAME"]
        for i in range(102)
        if board[f"V9_CACHE_LAYER{i}_USEDBYPRIMS"] == "TRUE"
    }
    assert used == {names[layer] for layer in layers}
    raw = write_pcbdoc(spec, filename="blink.PcbDoc")
    assert raw == write_pcbdoc(spec, filename="blink.PcbDoc") != write_pcbdoc(spec)
    pad_record = bytes((2,)) + b"".join(
        struct.pack("<I", len(x)) + x for x in (b"\x011", b"", b"", b"", b"\x4a")
    )
    assert record_layer(pad_record) == 74 and record_layer(bytes((4,)) + struct.pack("<I", 1) + b"\x21") == 33


def test_nets_in_name_order() -> None:
    doc, _spec = blink_doc()
    assert [n["NAME"] for n in doc.nets] == ["GND", "LED_A", "LED_DRV", "VIN"]
    keys = [*COMMON, "PRIMITIVELOCK", "NAME", "VISIBLE", "COLOR", "LOOPREMOVAL", "OVERRIDECOLORFORDRAW"]
    for net in doc.nets:
        assert list(net) == [*keys, "UNIQUEID", "JUMPERSVISIBLE"] and net["LAYER"] == "TOP"
    assert len({n["UNIQUEID"] for n in doc.nets}) == 4


def test_bytes_depend_only_on_the_spec() -> None:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    assert write_pcbdoc(spec) == write_pcbdoc(spec)


COMPONENT_KEYS = [
    "SELECTION",
    "LAYER",
    "LOCKED",
    "POLYGONOUTLINE",
    "USERROUTED",
    "KEEPOUT",
    "PRIMITIVELOCK",
    "X",
    "Y",
    "PATTERN",
    "NAMEON",
    "COMMENTON",
    "GROUPNUM",
    "COUNT",
    "ROTATION",
    "UNIONINDEX",
    "CHANNELOFFSET",
    "SOURCEDESIGNATOR",
    "SOURCEUNIQUEID",
    "SOURCEHIERARCHICALPATH",
    "SOURCEFOOTPRINTLIBRARY",
    "SOURCECOMPONENTLIBRARY",
    "SOURCELIBREFERENCE",
    "UNIQUEID",
    "JUMPERSVISIBLE",
]


def test_component_record_keys() -> None:
    doc, _spec = blink_doc()
    for index, record in enumerate(doc.components):
        assert list(record) == COMPONENT_KEYS and record["CHANNELOFFSET"] == str(index)
    assert len({c["UNIQUEID"] for c in doc.components}) == 3


def test_degrees_text() -> None:
    assert [degrees_text(u) for u in (0, 90_000_000, 12_500_000, -90_000_000, 1)] == [
        "0", "90", "12.5", "270", "0.000001",
    ]  # fmt: skip


# --- 4.2: components, texts, links and nets ------------------------------------------------------


def test_link_keys_of_the_components() -> None:
    """``SOURCEUNIQUEID`` is a backslash and the schematic unique id; the other source keys follow."""
    from fenolite.backends.altium.project import component_path, unique_id

    doc, spec = blink_doc()
    _spec, model = blink_pcbdoc_spec()
    by_ref = {c.ref: c for c in model.circuit.components}  # type: ignore[attr-defined]
    assert [c["SOURCEDESIGNATOR"] for c in doc.components] == ["D1", "R1", "U1"]
    for record in doc.components:
        component = by_ref[record["SOURCEDESIGNATOR"]]
        assert record["SOURCEUNIQUEID"] == "\\" + unique_id(component.id)
        assert record["SOURCEFOOTPRINTLIBRARY"] == "blink.PcbLib"
        assert record["SOURCECOMPONENTLIBRARY"] == "blink.SchLib"
        assert record["SOURCEHIERARCHICALPATH"] == ""
        assert record["NAMEON"] == "TRUE" and record["COMMENTON"] == "FALSE"
        assert component_path(component) == record["SOURCEDESIGNATOR"]
    assert {c["SOURCEDESIGNATOR"]: c["PATTERN"] for c in doc.components} == {
        "D1": "Mini_LED_THT_3mm",
        "R1": "Mini_R_0603",
        "U1": "Mini_QFP-32_7x7mm_P0.8mm",
    }
    assert {c["SOURCEDESIGNATOR"]: c["LOCKED"] for c in doc.components}["U1"] == "TRUE"


def test_pad_nets() -> None:
    """Scenario "Pad nets": R1's pad 1 on LED_DRV, pad 2 on LED_A; unconnected pads carry no net."""
    doc, _spec = blink_doc()
    names = [n["NAME"] for n in doc.nets]
    r1 = [c["SOURCEDESIGNATOR"] for c in doc.components].index("R1")
    pads = {p.name: p.prefix.net for p in doc.pads if p.prefix.component == r1}
    assert pads == {"1": names.index("LED_DRV"), "2": names.index("LED_A")}
    u1 = [c["SOURCEDESIGNATOR"] for c in doc.components].index("U1")
    u1_pads = {p.name: p.prefix.net for p in doc.pads if p.prefix.component == u1}
    assert u1_pads["9"] == names.index("VIN") and u1_pads["2"] == 0xFFFF and len(u1_pads) == 32


def test_designator_and_comment_texts() -> None:
    doc, _spec = blink_doc()
    assert len(doc.texts) == 6
    refs = [c["SOURCEDESIGNATOR"] for c in doc.components]
    for index, ref in enumerate(refs):
        designator, comment = doc.texts[2 * index], doc.texts[2 * index + 1]
        assert designator.text == ref and designator.is_designator == 1 and designator.is_comment == 0
        assert comment.is_comment == 1 and comment.is_designator == 0
        assert designator.prefix.component == comment.prefix.component == index
        assert designator.size == 137 and designator.height == 393701 and designator.width == 59055
        assert designator.y > comment.y
        assert doc.wide_strings[designator.wide_index or 0] == ref
    d1 = refs.index("D1")
    assert doc.texts[2 * d1].prefix.layer == 34 and doc.texts[2 * d1].mirrored == 1
    assert doc.texts[0 if d1 else 2].prefix.layer in (33, 34)


# --- 4.3: placement --------------------------------------------------------------------------------

UNIT = 2.54


def _expected(spec: PcbDocSpec, ref: str) -> list[tuple[str, float, float, float]]:
    """(pad, x, y, rotation) of ``ref``'s pads by the rule of "PCB document placement", in units."""
    from fenolite.geometry.transform import Transform

    component = next(c for c in spec.components if c.ref == ref)
    min_x = min(p.x for p in spec.outline)
    max_y = max(p.y for p in spec.outline)
    transform = Transform.placement(component.at, component.rotation, mirror=component.side == "bottom")
    out = []
    for pad in component.footprint.defn.pads:
        at = transform.apply(pad.position)
        x = (at.x - min_x) / UNIT + 10_000_000
        y = (max_y - at.y) / UNIT + 10_000_000
        out.append((pad.number, x, y, transform.apply_angle(pad.rotation) / 1e6))
    return out


def test_place_pads_of_every_component() -> None:
    doc, spec = blink_doc()
    refs = [c["SOURCEDESIGNATOR"] for c in doc.components]
    for index, ref in enumerate(refs):
        pads = {p.name: p for p in doc.pads if p.prefix.component == index}
        for number, x, y, rotation in _expected(spec, ref):
            pad = pads[number]
            assert abs(pad.x - x) <= 0.5 and abs(pad.y - y) <= 0.5, (ref, number)
            assert pad.rotation == rotation, (ref, number)


def test_place_component_origin() -> None:
    doc, spec = blink_doc()
    min_x = min(p.x for p in spec.outline)
    max_y = max(p.y for p in spec.outline)
    for record in doc.components:
        component = next(c for c in spec.components if c.ref == record["SOURCEDESIGNATOR"])
        x = round((component.at.x - min_x) * 50 / 127) + 10_000_000
        y = round((max_y - component.at.y) * 50 / 127) + 10_000_000
        from fenolite.backends.altium.pcbrecords import mil_text

        assert (record["X"], record["Y"]) == (mil_text(x), mil_text(y))
        assert record["ROTATION"] == angle_text(component.rotation)


def test_bottom_part() -> None:
    """Scenario "A bottom part": D1 on the bottom, its overlay arcs on 34 and courtyard on 72."""
    doc, _spec = blink_doc()
    d1 = [c["SOURCEDESIGNATOR"] for c in doc.components].index("D1")
    assert doc.components[d1]["LAYER"] == "BOTTOM"
    arcs = [a for a in doc.arcs if a.prefix.component == d1]
    tracks = [t for t in doc.tracks if t.prefix.component == d1]
    assert sorted({a.prefix.layer for a in arcs}) == [34, 70]
    assert {t.prefix.layer for t in tracks} == {72}
    assert {p.prefix.layer for p in doc.pads if p.prefix.component == d1} == {74}
    top = [c["SOURCEDESIGNATOR"] for c in doc.components].index("R1")
    assert {t.prefix.layer for t in doc.tracks if t.prefix.component == top} == {33, 69, 71}


# --- the link of a part on a module sheet (change c0037) ---------------------------------------------


def test_sheet_link_of_a_part_on_a_module_sheet() -> None:
    """``PlacedComponent.sheet`` gives the two-id path and the hierarchical path; ``None`` keeps the one-id
    form and the empty path."""
    _doc, spec = blink_doc()
    assert all(c.sheet is None for c in spec.components)
    first, *rest = spec.components
    moved = dataclasses.replace(first, sheet=("ABCDEFGH", "led"))
    doc = read_pcbdoc(
        write_pcbdoc(dataclasses.replace(spec, components=(moved, *rest)), filename="blink.PcbDoc")
    )
    record, *others = doc.components
    assert record["SOURCEDESIGNATOR"] == first.ref
    assert record["SOURCEUNIQUEID"] == f"\\ABCDEFGH\\{first.unique_id}"
    assert record["SOURCEHIERARCHICALPATH"] == "blink\\led"
    assert list(record) == COMPONENT_KEYS
    for other, component in zip(others, rest, strict=True):
        assert other["SOURCEUNIQUEID"] == "\\" + component.unique_id
        assert other["SOURCEHIERARCHICALPATH"] == ""


def test_sheet_link_changes_only_the_two_link_keys() -> None:
    _doc, spec = blink_doc()
    plain = read_pcbdoc(write_pcbdoc(spec, filename="blink.PcbDoc"))
    linked = tuple(dataclasses.replace(c, sheet=("ABCDEFGH", "m")) for c in spec.components)
    doc = read_pcbdoc(write_pcbdoc(dataclasses.replace(spec, components=linked), filename="blink.PcbDoc"))
    for before, after in zip(plain.components, doc.components, strict=True):
        changed = {key for key in before if before[key] != after[key]}
        assert changed == {"SOURCEUNIQUEID", "SOURCEHIERARCHICALPATH"}
    assert plain.pads == doc.pads and plain.nets == doc.nets


# --- copper (change c0038): routed tracks and arcs, vias --------------------------------------------

MM = 1_000_000
FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def at(x: float, y: float) -> Point:
    """A point of the board frame of the placements (the outline starts at 100 mm, 100 mm)."""
    return Point(100 * MM + round(x * MM), 100 * MM + round(y * MM))


def copper_spec(**changes: object) -> PcbDocSpec:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    changes.setdefault("nets", (*spec.nets, "SIG"))
    return dataclasses.replace(spec, **changes)  # type: ignore[arg-type]


def copper_doc(**changes: object) -> tuple[PcbDoc, PcbDocSpec]:
    spec = copper_spec(**changes)
    return read_pcbdoc(write_pcbdoc(spec, filename="blink.PcbDoc")), spec


def test_copper_storages_are_apart_from_the_empty_ones() -> None:
    assert COPPER_STORAGES == ("Vias6", "Polygons6", "Classes6", "Rules6")
    assert len(EMPTY_STORAGES) == 21 and not set(COPPER_STORAGES) & set(EMPTY_STORAGES)


def test_routed_track_on_an_inner_layer() -> None:
    """Scenario "Track on an inner layer"."""
    track = Track(id="trk_a", start=at(10, 10), end=at(30, 10), width=200_000, layer="In1.Cu", net_id="SIG")
    doc, spec = copper_doc(copper_layers=FOUR, tracks=(track,))
    plain, _ = copper_doc(copper_layers=FOUR)
    assert len(doc.tracks) == len(plain.tracks) + 1 and len(doc.free_tracks) == 1
    last = doc.tracks[-1]
    assert last is doc.free_tracks[0] and last.size == 36
    assert last.prefix.layer == 2 and last.prefix.component == 0xFFFF and last.prefix.polygon == 0xFFFF
    assert doc.nets[last.prefix.net]["NAME"] == "SIG" and last.width == 78740
    assert last.y1 == last.y2 and abs((last.x2 - last.x1) - 7874016) <= 1
    assert last.x1 == 10_000_000 + 3_937_008 and last.y1 == 10_000_000 + 7_874_016  # 10 mm right, 20 mm up
    assert sorted(spec.nets).index("SIG") == last.prefix.net


def test_routed_records_follow_the_component_primitives_in_geometric_order() -> None:
    tracks = (
        Track(id="trk_z", start=at(1, 1), end=at(2, 1), width=250_000, layer="B.Cu", net_id="GND"),
        Track(id="trk_y", start=at(5, 1), end=at(6, 1), width=250_000, layer="F.Cu", net_id="VIN"),
        Track(id="trk_x", start=at(3, 1), end=at(4, 1), width=250_000, layer="F.Cu", net_id="VIN"),
        Track(id="trk_w", start=at(9, 1), end=at(9, 2), width=250_000, layer="F.Cu", net_id="GND"),
        Track(id="trk_v", start=at(7, 1), end=at(8, 1), width=250_000, layer="F.Cu"),
    )
    arc = Arc(
        id="arc_a", start=at(10, 10), mid=at(11, 9), end=at(12, 10), width=250_000, layer="F.Cu", net_id="VIN"
    )
    doc, _ = copper_doc(tracks=tracks, arcs=(arc,))
    plain, _ = copper_doc()
    assert doc.tracks[: len(plain.tracks)] == plain.tracks and doc.arcs[: len(plain.arcs)] == plain.arcs
    names = [n["NAME"] for n in doc.nets]
    order = [(t.prefix.layer, names[t.prefix.net] if t.prefix.net != 0xFFFF else "") for t in doc.free_tracks]
    assert order == [(1, ""), (1, "GND"), (1, "VIN"), (1, "VIN"), (32, "GND")]
    assert doc.free_tracks[2].x1 < doc.free_tracks[3].x1
    again, _ = copper_doc(tracks=tuple(reversed(tracks)), arcs=(arc,))
    assert again.streams["Tracks6/Data"] == doc.streams["Tracks6/Data"]
    (free,) = doc.free_arcs
    assert free.size == 47 and free.prefix.layer == 1 and names[free.prefix.net] == "VIN"
    assert free.radius == 393701 and (free.start, free.end) == (0.0, 180.0)  # it bulges up in Altium's frame
    assert doc.storages["Tracks6"][0] == len(doc.tracks) and doc.storages["Arcs6"][0] == len(doc.arcs)


def test_routed_track_on_an_unknown_layer_refused() -> None:
    """Scenario "Unknown layer refused"."""
    track = Track(id="trk_in", start=at(1, 1), end=at(2, 1), width=200_000, layer="In1.Cu")
    with pytest.raises(ValueError, match="trk_in: the layer In1.Cu is not a copper layer"):
        write_pcbdoc(copper_spec(tracks=(track,)))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"width": 0}, "trk_bad: a track needs a positive width"),
        ({"end": at(1, 1)}, "trk_bad: the track has zero length"),
        ({"net_id": "NOPE"}, "trk_bad: the net 'NOPE' is not a net of the document"),
        ({"layer": "F.SilkS"}, "trk_bad: the layer F.SilkS is not a copper layer"),
    ],
)
def test_routed_track_refusals(changes: dict[str, object], message: str) -> None:
    track = Track(id="trk_bad", start=at(1, 1), end=at(2, 1), width=200_000, layer="F.Cu", net_id="GND")
    with pytest.raises(ValueError, match=message):
        write_pcbdoc(copper_spec(tracks=(dataclasses.replace(track, **changes),)))  # type: ignore[arg-type]


def test_routed_arc_refusals() -> None:
    arc = Arc(id="arc_bad", start=at(1, 1), mid=at(2, 1), end=at(3, 1), width=200_000, layer="F.Cu")
    with pytest.raises(ValueError, match="arc_bad: the arc points .* are collinear"):
        write_pcbdoc(copper_spec(arcs=(arc,)))
    bent = dataclasses.replace(arc, mid=at(2, 2))
    for changes, message in (
        ({"width": -1}, "arc_bad: an arc needs a positive width"),
        ({"layer": "In2.Cu"}, "arc_bad: the layer In2.Cu is not a copper layer"),
        ({"net_id": "NOPE"}, "arc_bad: the net 'NOPE'"),
    ):
        with pytest.raises(ValueError, match=message):
            write_pcbdoc(copper_spec(arcs=(dataclasses.replace(bent, **changes),)))  # type: ignore[arg-type]


def through(ident: str, x: float, y: float, net: str | None = "GND", **changes: object) -> Via:
    via = Via(
        id=ident, position=at(x, y), diameter=600_000, drill=300_000, layers=("F.Cu", "B.Cu"), net_id=net
    )
    return dataclasses.replace(via, **changes)  # type: ignore[arg-type]


def test_vias_in_their_storage() -> None:
    vias = (through("via_c", 20, 10, "VIN"), through("via_b", 30, 10), through("via_a", 10, 10, None))
    doc, _ = copper_doc(vias=vias)
    names = [n["NAME"] for n in doc.nets]
    assert doc.storages["Vias6"][0] == 3 and len(doc.storages["Vias6"][1]) == 3 * 326
    assert [names[v.prefix.net] if v.prefix.net != 0xFFFF else "" for v in doc.vias] == ["", "GND", "VIN"]
    first = doc.vias[0]
    assert (first.size, first.prefix.layer, first.start_layer, first.end_layer) == (321, 74, 1, 32)
    assert (first.diameter, first.hole) == (236220, 118110)
    assert (first.x, first.y) == (10_000_000 + 3_937_008, 10_000_000 + 7_874_016)
    board = doc.board
    assert board["V9_CACHE_LAYER0_NAME"] == "Multi-Layer" and board["V9_CACHE_LAYER0_USEDBYPRIMS"] == "TRUE"
    assert len(doc.unique_ids) == len(doc.pads)  # vias are not listed
    assert {u["PRIMITIVEOBJECTID"] for u in doc.unique_ids} == {"Pad"}
    for name in ("Polygons6", "Classes6", "Rules6"):
        assert doc.storages[name] == (0, b"")


def test_via_on_four_layers_spans_the_outer_layers() -> None:
    doc, _ = copper_doc(copper_layers=FOUR, vias=(through("via_a", 10, 10, layers=("F.Cu", "B.Cu")),))
    assert [(v.start_layer, v.end_layer) for v in doc.vias] == [(1, 32)]


def test_blind_via_refused() -> None:
    """Scenario "Blind via refused"."""
    blind = through("via_blind", 10, 10, via_type="blind", layers=("F.Cu", "In1.Cu"))
    with pytest.raises(ValueError, match="via_blind: a blind via is not written"):
        write_pcbdoc(copper_spec(copper_layers=FOUR, vias=(blind,)))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"layers": ("F.Cu", "In1.Cu")}, "via_bad: the via spans F.Cu, In1.Cu, not F.Cu to B.Cu"),
        ({"layers": ()}, "via_bad: the via spans no layer"),
        ({"drill": 600_000}, "via_bad: the drill of 600000 nm is not below the diameter of 600000 nm"),
        ({"drill": 0}, "via_bad: the drill of 0 nm"),
        ({"net_id": "NOPE"}, "via_bad: the net 'NOPE'"),
        ({"via_type": "micro"}, "via_bad: a micro via is not written"),
    ],
)
def test_via_refusals(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        write_pcbdoc(copper_spec(copper_layers=FOUR, vias=(through("via_bad", 10, 10, **changes),)))


def test_copper_layers_must_be_a_known_stack() -> None:
    with pytest.raises(ValueError, match="In1.Cu"):
        write_pcbdoc(copper_spec(copper_layers=("F.Cu", "In1.Cu", "B.Cu")))


def test_document_without_copper_keeps_its_bytes() -> None:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    explicit = dataclasses.replace(spec, copper_layers=("F.Cu", "B.Cu"), tracks=(), arcs=(), vias=())
    assert write_pcbdoc(spec, filename="blink.PcbDoc") == write_pcbdoc(explicit, filename="blink.PcbDoc")
