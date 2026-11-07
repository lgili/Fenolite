# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas of poured copper alone are written as polygon cut-outs, not keep-outs (change c0439)."""

import dataclasses
from collections import Counter
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.model.design import Design

KEEPOUT_FLAG = 2
TOP, BOTTOM, KEEPOUT_LAYER, MULTI_LAYER = 1, 32, 56, 74


def _square(x: int, y: int, side: int = 2_000_000) -> tuple[Point, ...]:
    return (Point(x, y), Point(x + side, y), Point(x + side, y + side), Point(x, y + side))


def _design() -> Design:
    """The two-layer board with three pour-only rule areas (both copper layers, ``F.Cu``, ``B.Cu``) and one
    rule area that keeps tracks out of both layers, and a pour-only rule area in its first footprint."""
    design = two_layer()
    assert design.board is not None
    areas = (
        Keepout(id="kpo-both", outline=_square(0, 0), layers=("F.Cu", "B.Cu"), no_copper_pour=True),
        Keepout(id="kpo-top", outline=_square(5_000_000, 0), layers=("F.Cu",), no_copper_pour=True),
        Keepout(id="kpo-bottom", outline=_square(10_000_000, 0), layers=("B.Cu",), no_copper_pour=True),
        Keepout(id="kpo-tracks", outline=_square(15_000_000, 0), layers=("F.Cu", "B.Cu"), no_tracks=True),
    )
    first, *rest = design.board.footprints
    own = Keepout(id="kpo-own", outline=_square(-1_000_000, 2_000_000), layers=("*.Cu",), no_copper_pour=True)
    first = dataclasses.replace(first, keepouts=(own,))
    board = dataclasses.replace(design.board, keepouts=areas, footprints=(first, *rest))
    return dataclasses.replace(design, board=board)


def _regions(document: bytes) -> Counter[tuple[str, int, str]]:
    """The written regions by form (``keepout``, ``cutout`` or ``plain``), layer and owner."""
    found: Counter[tuple[str, int, str]] = Counter()
    for region in read_pcbdoc(document).regions:
        if not isinstance(region, RegionRecord):
            continue
        kind = dict(region.properties.fields).get("KIND", "0")
        form = "keepout" if region.prefix.flags2 == KEEPOUT_FLAG else "cutout" if kind == "1" else "plain"
        found[(form, region.prefix.layer, "free" if region.prefix.component is None else "component")] += 1
    return found


def test_pour_only_rule_areas_are_polygon_cutouts(tmp_path: Path) -> None:
    design = _design()
    written = lower.write_design(design, allow_lossy=True)
    document = written.files[f"{design.header.name}.PcbDoc"]
    regions = _regions(document)
    assert regions[("cutout", MULTI_LAYER, "free")] == 1
    assert regions[("cutout", TOP, "free")] == 1
    assert regions[("cutout", BOTTOM, "free")] == 1
    assert regions[("cutout", MULTI_LAYER, "component")] == 1
    assert regions[("keepout", KEEPOUT_LAYER, "free")] == 1
    assert sum(n for (form, _, _), n in regions.items() if form == "keepout") == 1
    path = tmp_path / "cutouts.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design
    assert back.board is not None

    def areas(items: tuple[Keepout, ...]) -> list[tuple[tuple[str, ...], bool, bool, bool, bool]]:
        return sorted(
            (tuple(sorted(k.layers)), k.no_copper_pour, k.no_tracks, k.no_vias, k.no_pads) for k in items
        )

    # the cut-outs read back as the pour-only rule areas they were written from; the free keep-out of the
    # Keep-Out layer is read as a drawing of that layer, from which ``convert`` makes its rule area (c0420)
    poured = tuple(k for k in design.board.keepouts if k.no_copper_pour)  # type: ignore[union-attr]
    assert areas(back.board.keepouts) == areas(poured)
    owned = [k for fp in back.board.footprints for k in fp.keepouts]
    restrictions = [(k.no_copper_pour, k.no_tracks, k.no_vias, k.no_pads) for k in owned]
    assert restrictions == [(True, False, False, False)]
