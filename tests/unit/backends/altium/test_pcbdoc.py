# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium PCB document writer (change c0035, capability altium-pcb-writer, "PCB document file",
"PCB document placement", "PCB document links and nets")."""

from __future__ import annotations

import struct
from functools import cache

from _altium import blink_pcbdoc_spec
from _altium_pcb_read import PcbDoc, read_pcbdoc

from fenolite.backends.altium.pcbdoc import EMPTY_STORAGES, PcbDocSpec, degrees_text, write_pcbdoc

STORAGES = ("Board6", "Nets6", "Components6", "Pads6", "Tracks6", "Arcs6", "Texts6", "WideStrings6")


@cache
def blink_doc() -> tuple[PcbDoc, PcbDocSpec]:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    return read_pcbdoc(write_pcbdoc(spec)), spec


# --- 4.1: headers, board, nets --------------------------------------------------------------------


def test_storages_of_the_sample() -> None:
    """Scenario "Storages of the sample": root streams and 20 storages, counts equal, empty ones empty."""
    doc, _spec = blink_doc()
    assert sorted(doc.storages) == sorted((*STORAGES, *EMPTY_STORAGES)) and len(doc.storages) == 20
    for name in EMPTY_STORAGES:
        assert doc.storages[name] == (0, b"")
    assert doc.file_header == struct.pack("<I", 19) + "PCB 5.0 Bi".encode("utf-16-le")
    start = struct.pack("<IB", 19, 19) + b"PCB 6.0 Binary File" + struct.pack("<d", 5.01)
    assert doc.file_header_six.startswith(start + struct.pack("<IB", 38, 38) + b"{")
    assert len(doc.file_header_six) == len(start) + 5 + 38 and doc.file_header_six.endswith(b"}")


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
    assert all(f"LAYER{i}NAME" in board for i in range(1, 75)) and "LAYER75NAME" not in board
    assert [board[f"LAYER{i}MECHENABLED"] for i in (69, 70, 71, 72)] == ["TRUE"] * 4
    vertices = [(board[f"VX{k}"], board[f"VY{k}"]) for k in range(5)]
    assert (
        "VX5" not in board
        and vertices[0] == vertices[-1]
        and [board[f"KIND{k}"] for k in range(5)] == ["0"] * 5
    )
    assert vertices[0] == ("1000mil", "1000mil") or ("1000mil", "1000mil") in vertices
    assert board["ORIGINX"] == board["ORIGINY"] == "1000mil"
    assert board["KIND"] == "Protel_Advanced_PCB" and board["VERSION"] == "5.00"


def test_nets_in_name_order() -> None:
    doc, _spec = blink_doc()
    assert [n["NAME"] for n in doc.nets] == ["GND", "LED_A", "LED_DRV", "VIN"]


def test_bytes_depend_only_on_the_spec() -> None:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    assert write_pcbdoc(spec) == write_pcbdoc(spec)


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
        assert record["ROTATION"] == degrees_text(component.rotation)


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
