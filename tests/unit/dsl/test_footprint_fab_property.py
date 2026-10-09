# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``Footprint.pad(fab_property=)`` (capability dsl-footprint-authoring, "Assembly and test properties on
authored pads"; change c0118)."""

from __future__ import annotations

import typing

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.dsl import DslError, Footprint, mm
from fenolite.model.board import PadFabProperty

VALUES: tuple[str, ...] = typing.get_args(PadFabProperty)


def ball(**options: object) -> Footprint:
    fp = Footprint("Local", "Ball", kind="smd")
    fp.pad("A1", at=(mm(0), mm(0)), size=(mm(0.3), mm(0.3)), shape="circle", **options)  # type: ignore[arg-type]
    return fp


def test_a_marked_bga_ball() -> None:
    """Scenario "A marked BGA ball"."""
    fp = ball(fab_property="bga")
    assert fp.definition.pads[0].fab_property == "bga"
    written = write_footprint(fp.definition, target=10)
    assert "(property pad_prop_bga)" in written
    assert read_footprint(written, library="Local").pads[0].fab_property == "bga"


def test_a_pad_without_the_keyword_is_unchanged() -> None:
    plain, explicit = ball(), ball(fab_property=None)
    assert plain.definition.pads[0].fab_property is None
    for target in (9, 10):
        text = write_footprint(plain.definition, target=target)
        assert "pad_prop" not in text
        assert write_footprint(explicit.definition, target=target) == text


def test_refused_marks() -> None:
    """Scenario "Refused marks"."""
    fp = Footprint("Local", "Edge", kind="smd")
    with pytest.raises(DslError) as castellated:
        fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), fab_property="castellated")
    assert "castellated" in str(castellated.value) and "thru_hole" in str(castellated.value)
    with pytest.raises(DslError, match="fab_property"):
        fp.pad("2", at=(mm(2), mm(0)), size=(mm(1), mm(1)), fab_property="fiducial")
    assert fp.definition.pads == ()


@pytest.mark.parametrize("value", ["castellated", "mechanical"])
def test_plated_hole_marks(value: str) -> None:
    smd = Footprint("Local", "Smd", kind="smd")
    with pytest.raises(DslError, match=value):
        smd.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), fab_property=value)
    npth = Footprint("Local", "Npth", kind="through_hole")
    with pytest.raises(DslError, match="thru_hole"):
        npth.pad(
            "1", at=(mm(0), mm(0)), size=(mm(2), mm(2)), kind="np_thru_hole", drill=mm(1), fab_property=value
        )
    tht = Footprint("Local", "Tht", kind="through_hole")
    tht.pad("1", at=(mm(0), mm(0)), size=(mm(2), mm(2)), drill=mm(1), fab_property=value)
    assert tht.definition.pads[0].fab_property == value


@pytest.mark.parametrize("value", [v for v in VALUES if v not in ("castellated", "mechanical")])
def test_every_other_mark_on_an_smd_pad(value: str) -> None:
    assert ball(fab_property=value).definition.pads[0].fab_property == value
