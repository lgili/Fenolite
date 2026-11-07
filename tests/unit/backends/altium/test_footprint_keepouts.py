# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule areas of a footprint in the Altium writers (change c0411, altium-pcb-writer "Footprint rule
areas"): a PCB library writes them as keep-out regions of the footprint, and a PCB document as keep-out
regions of the component; Fenolite reads them back as rule areas of the footprint. Fenolite reads what
Fenolite wrote: every level here is ``INFERRED``."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

from fenolite.backends.altium import lower
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.adapter.library import import_footprints
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.pcblib import (
    LibFootprint,
    check_footprint,
    footprint_keepout_problem,
    footprint_primitives,
    keepout_layer_ids,
    write_pcblib,
)
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.core.coords import Point, Size
from fenolite.model.board import FootprintInstance, Keepout, Pad, placed_keepout
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

ROOT = Path(__file__).resolve().parents[4]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
MM = 1_000_000
TOLERANCE = 3
"""A length is written in units of 2.54 nm: a point comes back within this much (nm)."""

SQUARE = (Point(MM, 0), Point(3 * MM, 0), Point(3 * MM, 2 * MM), Point(MM, 2 * MM))


def area(
    ident: str,
    layers: tuple[str, ...],
    *,
    no_tracks: bool = False,
    no_vias: bool = False,
    no_pads: bool = False,
    no_copper_pour: bool = False,
    no_footprints: bool = False,
) -> Keepout:
    return Keepout(
        id=ident,
        outline=SQUARE,
        layers=layers,
        no_tracks=no_tracks,
        no_vias=no_vias,
        no_pads=no_pads,
        no_copper_pour=no_copper_pour,
        no_footprints=no_footprints,
    )


def close(a: Keepout, b: Keepout) -> bool:
    return (
        a.layers == b.layers
        and (a.no_tracks, a.no_vias, a.no_pads, a.no_copper_pour)
        == (b.no_tracks, b.no_vias, b.no_pads, b.no_copper_pour)
        and len(a.outline) == len(b.outline)
        and all(
            abs(p.x - q.x) <= TOLERANCE and abs(p.y - q.y) <= TOLERANCE
            for p, q in zip(a.outline, b.outline, strict=True)
        )
    )


def library_definition(*areas: Keepout) -> FootprintDef:
    pad = Pad(id="pad1", number="1", shape="rect", size=Size(MM, MM), position=Point(0, 0),
              layers=("F.Cu", "F.Mask", "F.Paste"))  # fmt: skip
    return FootprintDef(id="fp", name="KO", pads=(pad,), keepouts=areas)


def test_the_regions_of_a_rule_area() -> None:
    """One region on the Keep-Out layer for an area on every copper layer, else one per copper layer."""
    assert keepout_layer_ids(area("a", ("*.Cu",), no_vias=True)) == [rec.KEEPOUT_LAYER]
    assert keepout_layer_ids(area("b", ("B.Cu", "F.Cu"), no_vias=True)) == [1, 32]
    both = area("c", ("F.Cu", "B.Cu"), no_vias=True)
    assert keepout_layer_ids(both, copper_layers=("F.Cu", "B.Cu")) == [rec.KEEPOUT_LAYER]
    # a KiCad footprint's zone on its 32 copper layers, on a board of two
    kicad = area("d", ("F.Cu", "B.Cu", *(f"In{n}.Cu" for n in range(1, 31))), no_vias=True)
    assert footprint_keepout_problem(kicad, ("F.Cu", "B.Cu")) is None
    assert keepout_layer_ids(kicad, copper_layers=("F.Cu", "B.Cu")) == [rec.KEEPOUT_LAYER]
    assert footprint_keepout_problem(area("e", ("F.Cu", "In5.Cu"), no_vias=True), ("F.Cu", "B.Cu"))


def test_a_rule_area_without_a_written_restriction_is_refused() -> None:
    check = check_footprint(library_definition(area("a", ("F.Cu",), no_footprints=True)), {})
    assert check.refusal is not None and "no restriction" in check.refusal
    check = check_footprint(library_definition(area("b", ("F.SilkS",), no_vias=True)), {})
    assert check.refusal is not None and "F.SilkS" in check.refusal


def test_library_rule_areas_survive_a_write() -> None:
    areas = (
        area("kpo_a", ("F.Cu",), no_tracks=True, no_vias=True),
        area("kpo_b", ("*.Cu",), no_tracks=True, no_vias=True, no_pads=True, no_copper_pour=True),
        area("kpo_c", ("B.Cu",), no_copper_pour=True),
    )
    footprint = LibFootprint(library_definition(*areas))
    regions = [kind for kind, _ in footprint_primitives(footprint) if kind == "Region"]
    assert len(regions) == 3
    data = write_pcblib([footprint], filename="ko.PcbLib")
    library = import_footprints(
        read_pcblib(data), name="ko", file="ko.PcbLib", sha256=hashlib.sha256(data).hexdigest()
    )
    (read,) = library.footprints
    assert len(read.keepouts) == 3
    for mine, theirs in zip(areas, read.keepouts, strict=True):
        assert close(mine, theirs), (mine, theirs)


def test_a_rule_area_that_restricts_nothing_is_a_keep_out_of_the_value_0() -> None:
    """A component's keep-out fill of a public document holds the restrictions 0 (``pcb-records.md``): the
    area read from it restricts nothing, and the PCB library writes such an area as a keep-out region of
    the value 0 that reads back the same."""
    nothing = area("kpo_none", ("B.Cu",))
    assert footprint_keepout_problem(nothing) is None
    data = write_pcblib([LibFootprint(library_definition(nothing))], filename="ko.PcbLib")
    library = import_footprints(
        read_pcblib(data), name="ko", file="ko.PcbLib", sha256=hashlib.sha256(data).hexdigest()
    )
    (read,) = library.footprints
    (theirs,) = read.keepouts
    assert close(nothing, theirs), (nothing, theirs)


def _footprint(design: Design, ref: str) -> FootprintInstance:
    ident = next(c.id for c in design.circuit.components if c.ref == ref)
    assert design.board is not None
    return next(fp for fp in design.board.footprints if fp.component_id == ident)


@pytest.mark.parametrize(
    ("ref", "layers"),
    (("R1", ("F.Cu",)), ("D1", ("B.Cu",)), ("R1", ("F.Cu", "B.Cu")), ("D1", ("F.Cu", "B.Cu"))),
)
def test_document_rule_areas_survive_a_write(ref: str, layers: tuple[str, ...], tmp_path: Path) -> None:
    """A rule area of a top footprint (``R1``) and of a bottom one (``D1``) of the blink sample comes back
    as a rule area of the same footprint, in its pad frame and on its copper side, at the same place on
    the board; an area on both copper layers is a keep-out region of the Keep-Out layer and comes back
    with its restrictions."""
    first = AltiumBackend().read(BLINK).design
    fp = _footprint(first, ref)
    assert fp.side == ("bottom" if layers == ("B.Cu",) or ref == "D1" else "top")
    mine = area("kpo_mine", layers, no_tracks=True, no_vias=True)
    design = first.replace_entity(dataclasses.replace(fp, keepouts=(mine,)))
    written = AltiumBackend().write(design)
    (name,) = [n for n in written.files if n.endswith(".PcbDoc")]
    (tmp_path / name).write_bytes(written.files[name])
    second = AltiumBackend().read(tmp_path / name).design
    assert second.board is not None and not second.board.keepouts
    again = _footprint(second, ref)
    (theirs,) = again.keepouts
    assert close(mine, theirs), (mine, theirs)
    assert close(placed_keepout(fp, mine), placed_keepout(again, theirs))


def _written(ref: str, *areas: Keepout, derive: bool = False) -> lower.ProjectWrite:
    first = AltiumBackend().read(BLINK).design
    fp = _footprint(first, ref)
    design = first.replace_entity(dataclasses.replace(fp, keepouts=areas))
    return lower.write_design(design, allow_lossy=True, derive_library=derive)


def test_a_footprint_area_off_the_copper_layers_is_reported_not_raised(tmp_path: Path) -> None:
    """A KiCad footprint's zone may name a courtyard (``BT1`` of the public row ``-06``: ``B.Cu`` and
    ``B.CrtYd``) or inner layers the board lacks (``U1`` of ``-13``). An Altium keep-out lies on a copper
    layer or the Keep-Out layer and restricts copper only (``pcb-records.md``; S-1711): the area keeps its
    copper layers of the board, a non-copper layer is counted changed under ``keep-out``, and an area with
    no copper layer of the board is counted lost; the write raises nothing."""
    both = area("kpo_both", ("F.Cu", "F.CrtYd"), no_vias=True)
    silk = area("kpo_silk", ("F.CrtYd",), no_vias=True)
    inner = area("kpo_inner", ("F.Cu", "In3.Cu"), no_vias=True)
    written = _written("R1", both, silk, inner, derive=True)
    lost = written.inputs.lost["keep-out"]
    assert [ids for reason, ids in lost.items() if "F.CrtYd" in reason] == [("kpo_silk",)]
    changed = written.inputs.changed["keep-out"]
    assert [ids for reason, ids in changed.items() if "F.CrtYd" in reason] == [("kpo_both",)]
    (name,) = [n for n in written.files if n.endswith(".PcbDoc")]
    (tmp_path / name).write_bytes(written.files[name])
    again = _footprint(AltiumBackend().read(tmp_path / name).design, "R1")
    # both copper areas come back on F.Cu: the courtyard and the inner layer the board lacks hold nothing
    assert sorted(k.layers for k in again.keepouts) == [("F.Cu",), ("F.Cu",)]
    assert any(n.endswith(".PcbLib") for n in written.files)


def test_a_library_area_on_an_inner_layer_is_a_region_of_its_mid_layer() -> None:
    """A library has no stack: an area on ``In3.Cu`` is a keep-out region of Mid-Layer 3, layer byte 4
    (``V7_LAYER`` ``MID<n>`` at n + 1, ``pcb-records.md``)."""
    footprint = LibFootprint(library_definition(area("kpo_in3", ("In3.Cu",), no_tracks=True)))
    (region,) = [record for kind, record in footprint_primitives(footprint) if kind == "Region"]
    assert keepout_layer_ids(area("x", ("In3.Cu",), no_tracks=True)) == [4]
    assert b"MID3" in region
