# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing geometry of the public Draftsman documents (capability draftsman-viewer, scenario "Public
drawings"; change c0180, task 2.1; ``H-A-DWF-GEOM``).

The four rows ``altium-third-party-pcbdwf-01`` to ``-04`` (S-0785, S-0786) are compared with the boards they
were made from (S-0187 ``-pcbdoc-08``, a heavy row, and S-0174 ``-pcbdoc-05``). Only counts are kept; no
value or name of a document's content is.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends import registry
from fenolite.backends.altium.read.draftsman import read_draftsman
from fenolite.backends.altium.read.dwfdraw import Drawing, place, read_drawing
from fenolite.model.design import Design
from fenolite.view.drawing import drawing_scene

pytestmark = pytest.mark.needs_corpus
DRAWINGS = {item.id: item for item in manifest_items("altium-draftsman")}
BOARDS = {item.id: item for item in manifest_items("rta")}
UNIT = 96 / 25.4e6
"""Nanometres to 1/96 inch."""
PAIRS = {
    "altium-third-party-pcbdwf-01": "altium-third-party-pcbdoc-08",
    "altium-third-party-pcbdwf-02": "altium-third-party-pcbdoc-08",
    "altium-third-party-pcbdwf-03": "altium-third-party-pcbdoc-05",
    "altium-third-party-pcbdwf-04": "altium-third-party-pcbdoc-05",
}
PARTS = {
    "altium-third-party-pcbdwf-01": (540, 239),
    "altium-third-party-pcbdwf-02": (0, 0),
    "altium-third-party-pcbdwf-03": (23, 0),
    "altium-third-party-pcbdwf-04": (23, 0),
}
"""Placed parts with pads, and of them the bottom parts, per document."""
VIEWS = ["BoardAssemblyViewData", "BoardFabricationViewData", "DrillViewView"]


def _drawing(item: CorpusItem) -> Drawing:
    return read_drawing(read_draftsman(require(item).read_bytes()))


def _pads(path: Path) -> dict[str, list[tuple[float, float]]]:
    backend = registry.for_path(path)
    assert backend is not None
    design = backend.read(path).content
    assert isinstance(design, Design)
    found: dict[str, list[tuple[float, float]]] = {}
    for pad in backend.board_pads(design):  # type: ignore[attr-defined]
        found.setdefault(pad.ref, []).append((pad.position.x * UNIT, -pad.position.y * UNIT))
    return found


def test_rows_declared() -> None:
    assert sorted(DRAWINGS) == sorted(PAIRS)
    assert all(board in BOARDS for board in PAIRS.values())


@pytest.mark.parametrize("dwf", sorted(PAIRS))
def test_parts_land_on_board_pads(dwf: str) -> None:
    """Fact 5: every part's local pads, placed by the rule, land on the board's pads of the same designator
    within 0.05 unit; a bottom part is mirrored in Y before its turn."""
    drawing = _drawing(DRAWINGS[dwf])
    pads = _pads(require(BOARDS[PAIRS[dwf]]))
    placed = [part for part in drawing.board.parts if part.pads and part.ref in pads]
    assert (len(placed), sum(part.side == "Bottom" for part in placed)) == PARTS[dwf]
    for part in placed:
        for x, y in part.pads:
            assert min(math.dist((x, y), p) for p in pads[part.ref]) < 0.05, part.ref
    assert place((1, 0), (0, 0), 90, True) == pytest.approx((0, 1))


@pytest.mark.parametrize("dwf", sorted(PAIRS))
def test_views_fit_their_sheets(dwf: str) -> None:
    """Fact 9: with the sheet's Y up, a top or bottom view's location is the lower-left corner of the board's
    bounds on the sheet, and the view lies inside its sheet."""
    drawing = _drawing(DRAWINGS[dwf])
    _bx, _by, bw, bh = drawing.board.bounds
    views = 0
    for page in drawing.pages:
        for item in page.items:
            if item.kind not in VIEWS or item.fields["side"] not in ("Top", "Bottom"):
                continue
            views += 1
            (x, y), scale = item.fields["location"], item.fields["scale"]
            assert x >= 0 and y >= 0 and x + bw * scale <= page.width and y + bh * scale <= page.height
    assert views > 0


@pytest.mark.parametrize("dwf", sorted(PAIRS))
def test_one_scene_item_per_sheet(dwf: str) -> None:
    path = require(DRAWINGS[dwf])
    scene = drawing_scene(path)
    pages = read_drawing(read_draftsman(path.read_bytes())).pages
    assert scene["lib"] == "drawing" and len(scene["items"]) == len(pages)
    assert all(item["scene"]["prims"] for item in scene["items"])
    assert not scene["meta"]["panel"]
