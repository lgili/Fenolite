# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board footprints, the pad frame and the synthesised circuit (kicad-file-backend, design-model; c0009)."""

from __future__ import annotations

import pytest
from _boards import FIXTURE, SCENARIOS

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.pcb import pad_angle_from_board, pad_angle_to_board, read_board
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.base import Opaque
from fenolite.model.board import FootprintInstance

DEG = 1_000_000


def _fp(ref: str) -> FootprintInstance:
    design = read_board(FIXTURE)
    assert design.board is not None
    component = design.by_ref[ref]
    return next(fp for fp in design.board.footprints if fp.component_id == component.id)


def test_top_footprint_at_ninety_degrees() -> None:
    r1 = _fp("R1")
    assert (r1.position, r1.rotation, r1.side, r1.attributes) == (
        Point(20_000_000, 15_000_000),
        90 * DEG,
        "top",
        ("smd",),
    )
    assert [p.rotation for p in r1.pads] == [0, 0]
    assert [p.position for p in r1.pads] == [Point(-800_000, 0), Point(800_000, 0)]


def test_bottom_footprint_keeps_stored_coordinates() -> None:
    d1 = _fp("D1")
    assert (d1.side, d1.rotation, d1.attributes) == ("bottom", 30 * DEG, ("through_hole",))
    pad2 = next(p for p in d1.pads if p.number == "2")
    assert (pad2.position, pad2.rotation) == (Point(2_540_000, -1_000_000), 0)
    assert pad2.layers == ("F.Cu", "B.Cu", "F.Mask", "B.Mask")
    assert pad2.drill == 800_000 and pad2.kind == "thru_hole"


def test_wildcard_layers_are_projected() -> None:
    pad2 = next(p for p in _fp("D1").pads if p.number == "2")
    layers = [
        s for s in slotlib.from_ext(pad2.ext["kicad"]) if isinstance(s, Opaque) and "layers" in s.fragment
    ]
    assert layers == [Opaque('(layers "*.Cu" "*.Mask")', "20241229")]


@pytest.mark.parametrize("footprint", [0, 30 * DEG, -90 * DEG, 270 * DEG])
@pytest.mark.parametrize("stored", [0, 30 * DEG, 90 * DEG, 270 * DEG, 359 * DEG])
def test_angle_pair_round_trip(stored: int, footprint: int) -> None:
    relative = pad_angle_from_board(stored, footprint)
    assert 0 <= relative < 360 * DEG
    assert pad_angle_to_board(relative, footprint) == stored


def test_unknown_attribute_atom() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["attr"], issues=issues)
    assert design.board is not None
    fp = design.board.footprints[0]
    assert fp.attributes == ("smd",)
    assert Opaque("(attr smd frobnicate)", "20241229") in slotlib.from_ext(fp.ext["kicad"])
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.kept-opaque", "info")]


def test_components_of_the_authored_board() -> None:
    design = read_board(FIXTURE)
    d1 = design.by_ref["D1"]
    assert d1.lib_footprint_ref == "Fenolite_Test:LED_THT_3mm" and d1.value == "LED"
    assert [(p.number, p.name, p.etype) for p in d1.pins] == [("1", "K", "passive"), ("2", "A", "passive")]
    assert d1.properties["Reference"] == "D1" and not d1.dnp


def test_footprint_property_is_projected() -> None:
    design = read_board(FIXTURE)
    assert design.by_ref["R1"].ref == "R1"
    fp = _fp("R1")
    props = [
        s for s in slotlib.from_ext(fp.ext["kicad"]) if isinstance(s, Opaque) and "Reference" in s.fragment
    ]
    assert len(props) == 1 and "(effects " in props[0].fragment


def test_unmapped_pin_type_keeps_its_text() -> None:
    design = read_board(SCENARIOS["pintype"])
    (pin,) = design.circuit.components[0].pins
    assert pin.etype == "unspecified"
    assert pin.ext["kicad"].payload == (("pintype", "passive+no_connect"),)


def test_footprint_ids_follow_uuids() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    for fp in design.board.footprints:
        component = design.by_id[fp.component_id]
        assert fp.native_ids["kicad"] and component.id != fp.id
        assert all(p.native_ids.get("kicad") for p in fp.pads)


def test_inventory_rows_match_inside_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    original = versions.min_version

    def spy(kind: versions.FileKind, token_path: str, *, value: str | None = None) -> int | None:
        calls.append((kind.value, token_path))
        return original(kind, token_path, value=value)

    monkeypatch.setattr(versions, "min_version", spy)
    design = read_board(SCENARIOS["padstack"])
    assert ("kicad_pcb", "kicad_pcb/footprint/pad/padstack") in calls
    assert design.board is not None
    pad = design.board.footprints[0].pads[0]
    slots = slotlib.from_ext(pad.ext["kicad"])
    (padstack,) = [s for s in slots if isinstance(s, Opaque) and "padstack" in s.fragment]
    assert padstack.min_version is not None and int(padstack.min_version) >= 20240929
    assert pad.padstack is not None and [layer.layer for layer in pad.padstack.layers] == ["F.Cu", "In1.Cu"]
