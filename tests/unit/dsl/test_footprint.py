# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL-authored footprint definitions and validation (change c0055)."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Footprint, mm
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
