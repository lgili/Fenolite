# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL-authored footprint definitions and validation (change c0055)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, Footprint, Part, mm
from fenolite.dsl.convert import to_model


def test_design_registers_footprint_outside_model() -> None:
    design = Design("authored")
    footprint = Footprint("Local", "TwoPin", kind="smd")
    footprint.pad("1", at=(mm(-1), mm(0)), size=(mm(1), mm(1)))
    footprint.pad("2", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
    footprint.rect((mm(-2), mm(-1)), (mm(2), mm(1)), layer="F.SilkS", width=mm(0.12))

    design.add_footprint(footprint)

    assert design.footprints == {"Local:TwoPin": footprint}
    assert [pad.number for pad in footprint.definition.pads] == ["1", "2"]
    assert footprint.definition.graphics[0].kind == "rect"
    assert not hasattr(to_model(design), "footprints")


def test_duplicate_ids_and_duplicate_pads_are_refused() -> None:
    design = Design("authored")
    footprint = Footprint("Local", "Pad")
    footprint.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    with pytest.raises(DslError, match="declared twice"):
        footprint.pad("1", at=(mm(1), mm(0)), size=(mm(1), mm(1)))
    design.add_footprint(footprint)
    with pytest.raises(DslError, match="registered twice"):
        design.add_footprint(Footprint("Local", "Pad"))


def test_shared_pad_numbers_round_trip_with_stable_unique_ids() -> None:
    footprint = Footprint("Local", "Tab")
    footprint.pad("2", at=(mm(0), mm(-1)), size=(mm(1), mm(1)))
    footprint.pad("2", at=(mm(0), mm(1)), size=(mm(2), mm(2)), shared=True)

    pads = footprint.definition.pads
    assert [pad.number for pad in pads] == ["2", "2"]
    assert pads[0].id != pads[1].id
    assert [pad.id for pad in pads] == [pad.id for pad in footprint.definition.pads]
    repeated = Footprint("Local", "Tab")
    repeated.pad("2", at=(mm(0), mm(-1)), size=(mm(1), mm(1)))
    repeated.pad("2", at=(mm(0), mm(1)), size=(mm(2), mm(2)), shared=True)
    assert [pad.id for pad in repeated.definition.pads] == [pad.id for pad in pads]

    unique = Footprint("Local", "Unique")
    unique.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    assert unique.definition.pads[0].id == derived_id("pad", "fenolite.dsl", "Local:Unique:pad:1")

    issues = []
    text = write_footprint(footprint.definition, target=10, issues=issues)
    round_trip = read_footprint(text, library="Local")
    assert issues == []
    assert [pad.number for pad in round_trip.pads] == ["2", "2"]
    assert len({pad.id for pad in round_trip.pads}) == 2


def test_shared_pad_requires_an_earlier_matching_number() -> None:
    footprint = Footprint("Local", "Tab")
    with pytest.raises(DslError, match="no earlier pad"):
        footprint.pad("2", at=(mm(0), mm(0)), size=(mm(1), mm(1)), shared=True)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"kind": "smd", "drill": mm(0.3)}, "only belongs to a through-hole"),
        ({"kind": "thru_hole"}, "needs a positive drill"),
        ({"kind": "thru_hole", "drill": mm(1.1)}, "cannot be larger than its pad"),
    ],
)
def test_invalid_drills_are_refused(kwargs: dict[str, object], message: str) -> None:
    footprint = Footprint("Local", "Pad")
    with pytest.raises(DslError, match=message):
        footprint.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), **kwargs)


def test_through_hole_footprint_defaults_pad_kind_and_layers() -> None:
    footprint = Footprint("Local", "THT", kind="through_hole")
    footprint.pad("1", at=(mm(0), mm(0)), size=(mm(2), mm(2)), drill=mm(0.8))
    pad = footprint.definition.pads[0]
    assert pad.kind == "thru_hole"
    assert pad.layers == ("*.Cu", "*.Mask")


def test_slot_drill_geometry_is_modeled() -> None:
    footprint = Footprint("Local", "Slot", kind="through_hole")
    footprint.pad(
        "1",
        at=(mm(0), mm(0)),
        size=(mm(2), mm(1)),
        rotation=90,
        drill=mm(0.8),
        drill_shape="slot",
        drill_length=mm(1.6),
        drill_rotation=90,
    )
    pad = footprint.definition.pads[0]
    assert pad.drill == 800_000
    assert pad.padstack is not None
    assert (pad.padstack.hole_shape, pad.padstack.hole_length, pad.padstack.hole_rotation) == (
        "slot",
        1_600_000,
        90_000_000,
    )


def test_slot_needs_valid_length() -> None:
    footprint = Footprint("Local", "Slot", kind="through_hole")
    with pytest.raises(DslError, match="slot length"):
        footprint.pad(
            "1",
            at=(mm(0), mm(0)),
            size=(mm(2), mm(1)),
            drill=mm(0.8),
            drill_shape="slot",
            drill_length=mm(0.5),
        )


def test_part_pin_pad_map_is_checked_and_ordered() -> None:
    part = Part("U1", "Local:IC", pad_map={"2": "3", "1": "4"})
    assert tuple(part.pad_map.items()) == (("1", "4"), ("2", "3"))
    with pytest.raises(DslError, match="more than one pin"):
        Part("U2", "Local:IC", pad_map={"1": "3", "2": "3"})
