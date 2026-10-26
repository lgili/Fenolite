# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board cut-outs and free holes of a PCB document (capability altium-import, "Board cut-outs and free
holes of a document"; change c0168)."""

from __future__ import annotations

import hashlib

import _altium_slotcases as cases
import pytest

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad.outline import edge_outline
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Hole
from fenolite.model.design import Design

MM = 1_000_000


def _import(data: bytes) -> Design:
    return import_board(read_pcbdoc(data), file="slots.PcbDoc", sha256=hashlib.sha256(data).hexdigest())


def _near(a: int, b: int) -> bool:
    """Within the rounding of one length to whole units and back (1.27 nm each way)."""
    return abs(a - b) <= 2


def _relative(points: tuple[Point, ...], corner: Point) -> set[tuple[int, int]]:
    return {(p.x - corner.x, p.y - corner.y) for p in points}


def test_written_fixture_read_back() -> None:
    """Scenario "Written fixture read back": ``Board.holes`` holds the round ``H1`` and the three drilled
    slots, ``edge_outline`` gives the three cut-out rings of the document within 1 µm, and no board-only
    footprint is made for them."""
    design = _import(cases.FIXTURE.read_bytes())
    board = design.board
    assert board is not None and not board.footprints
    assert not design.circuit.components
    holes = sorted(board.holes, key=lambda h: (h.length or 0, h.rotation))
    wanted = [
        (3_200_000, None, 0),
        (2 * MM, 10 * MM, 0),
        (2 * MM, 10 * MM, 90_000_000),
        (2 * MM, 12 * MM, 30_000_000),
    ]
    assert not any(h.plated for h in holes)
    for hole, (drill, length, rotation) in zip(holes, wanted, strict=True):
        assert _near(hole.drill, drill) and hole.rotation == rotation
        assert (hole.length is None) == (length is None) and _near(hole.length or 0, length or 0)
    outline = edge_outline(design)
    assert outline is not None and len(outline.cutouts) == 3
    corner = Point(min(p.x for p in outline.points), min(p.y for p in outline.points))
    written = cases.written_cutouts(cases.FIXTURE.read_bytes())
    # the document's frame: Y up, the board's lower-left corner at (1000 mil, 1000 mil)
    height = max(p.y for p in outline.points) - corner.y
    for ring in written:
        wanted = {(p.x - cases.OFFSET, height - (p.y - cases.OFFSET)) for p in ring}
        assert any(
            all(
                any(abs(x - a) <= 1_000 and abs(y - b) <= 1_000 for a, b in wanted)
                for x, y in _relative(cut, corner)
            )
            and len(cut) == len(ring)
            for cut in outline.cutouts
        )
    # the round hole H1 lies at (52, 32) mm of the board
    (h1,) = [h for h in holes if h.length is None]
    assert _near(h1.position.x - corner.x, 52 * MM) and _near(h1.position.y - corner.y, 32 * MM)


def _hole_document(*holes: Hole) -> bytes:
    board = (Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM))
    return write_pcbdoc(PcbDocSpec(outline=board, holes=holes), filename="h.PcbDoc")


def test_a_turned_slot_reads_back_as_a_hole() -> None:
    hole = Hole(
        id=derived_id("hol", "test", "H"), position=Point(20 * MM, 20 * MM), drill=2 * MM, length=12 * MM,
        rotation=210_000_000,
    )  # fmt: skip
    (read,) = _import(_hole_document(hole)).board.holes  # type: ignore[union-attr]
    assert _near(read.drill, 2 * MM) and _near(read.length or 0, 12 * MM) and read.rotation == 210_000_000


@pytest.mark.parametrize(
    ("name", "size", "net"),
    [("", (40_000, 40_000), None), ("1", (20_000, 20_000), None), ("", (20_000, 20_000), 0)],
)
def test_a_free_pad_with_copper_a_name_or_a_net_is_no_hole(
    name: str, size: tuple[int, int], net: int | None
) -> None:
    """A free pad with a ring of copper, a name or a net is no board hole: it stays a footprint."""
    from fenolite.backends.altium.adapter.board import free_hole
    from fenolite.backends.altium.read.pcbprims import PadRecord, decode_primitives

    data = rec.pad_record(
        name=name, layer=rec.MULTI_LAYER, x=0, y=0, size=size, shape=1, rotation=0.0, hole=20_000,
        net=rec.NO_INDEX if net is None else net,
    )  # fmt: skip
    ((record,), _rest, _issues) = decode_primitives(data, where="Pads6")
    assert isinstance(record, PadRecord)
    assert free_hole(record, None, 0, "") is None  # type: ignore[arg-type]  # refused before any context


def test_a_polygon_cut_out_is_not_an_edge() -> None:
    """``KIND=1`` (a polygon cut-out) is no board cut-out."""
    from fenolite.backends.altium.adapter.copper import is_board_cutout

    data = cases.candidate_document("kind1-multilayer-boardcutout")
    (region,) = read_pcbdoc(data).regions
    assert not is_board_cutout(region)  # type: ignore[arg-type]
    (region,) = read_pcbdoc(cases.candidate_document("kind0-keepout-boardcutout")).regions
    assert is_board_cutout(region)  # type: ignore[arg-type]
    edges = [g for g in _import(data).board.graphics if g.layer == "Edge.Cuts"]  # type: ignore[union-attr]
    assert len(edges) == 4  # the board's own outline only


@pytest.mark.parametrize("name", ["kind0-keepout-boardcutout", "kind0-multilayer-boardcutout"])
def test_a_board_cut_out_is_an_edge(name: str) -> None:
    edges = [g for g in _import(cases.candidate_document(name)).board.graphics if g.layer == "Edge.Cuts"]  # type: ignore[union-attr]
    (cut,) = [g for g in edges if g.kind == "polygon"]
    assert cut.width == 0 and not cut.filled and len(cut.points) == 4
