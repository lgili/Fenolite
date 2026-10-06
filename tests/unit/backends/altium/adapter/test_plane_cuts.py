# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Objects on an internal plane (capability altium-import, "Objects on an internal plane", "Layers and
stack-up" and "Tracks, arcs and vias"; change c0124; ``H-A-IMP-PLANE-CUT``).

An internal plane (Altium id 39 to 54) is stored in negative: a free primitive on its layer is a place
without copper. The import makes no entity of it, counts it as ``plane-cuts`` and holds the count of each
layer in the layer's bag. Every document here is authored record by record.
"""

from __future__ import annotations

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import EXT_KEYS, Ids
from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.backends.altium.read.pcb import PcbDocument
from fenolite.core.errors import Issue
from fenolite.model.board import Board

MIL = rec.MIL
PLANE, MID = 39, 3
CHAIN = (1, PLANE, MID, 32)
LINE = ((0, 0), (500 * MIL, 0))
TRIANGLE = [(0, 0), (90, 0), (90, 90)]
KINDS = ("tracks", "arcs", "texts", "fills", "regions")


def imported(document: PcbDocument) -> tuple[Board, list[Issue]]:
    issues: list[Issue] = []
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None
    return design.board, issues


def document(chain: tuple[int, ...] = CHAIN, plane_net: str | None = "GND", **parts: object) -> PcbDocument:
    extra = {} if plane_net is None else {"PLANE1NETNAME": plane_net}
    nets = parts.pop("nets", ["GND"])
    return rec.document(rec.board(chain, extra=extra), nets=nets, **parts)  # type: ignore[arg-type]


def pairs(board: Board, name: str) -> dict[str, str]:
    (layer,) = [layer for layer in board.layers if layer.name == name]
    return dict(layer.ext["altium"].payload)


def unmapped(issues: list[Issue]) -> str:
    found = [i.message for i in issues if i.code == "altium.import.unmapped"]
    return found[0] if found else ""


def drawn(board: Board) -> list[object]:
    return [g for g in board.graphics if g.layer != "Edge.Cuts"]


def census_adds_up(doc: PcbDocument) -> None:
    parts = read_board(doc, file="a.PcbDoc", sha256=rec.SHA, ids=Ids("altium_pcbdoc", EVIDENCE))
    for kind in KINDS:
        assert parts.census.total(kind) == len(getattr(doc, kind)), kind


# --- which layer is a plane ----------------------------------------------------------------------------


def test_plane_is_a_layer_of_the_chain_with_an_id_from_39_to_54() -> None:
    layers = LayerMap((1, 39, 3, 54, 32))
    assert [layers.is_plane(i) for i in (1, 3, 32, 39, 54)] == [False, False, False, True, True]
    # a plane id that the chain does not hold is no layer of the board, and so no plane of it
    assert not layers.is_plane(40) and not LayerMap((1, 32)).is_plane(39)
    assert not layers.is_plane(38) and not layers.is_plane(55) and not layers.is_plane(74)


def test_bag_key_is_in_the_closed_table_after_the_plane_net() -> None:
    assert EXT_KEYS.index("plane_cuts") == EXT_KEYS.index("plane_net") + 1


# --- scenario "Line on a plane is no track" ------------------------------------------------------------


def test_line_on_a_plane_is_no_track() -> None:
    kept = [rec.track(*LINE, layer=MID), rec.track(*LINE, layer=1, net=0)]
    cut = rec.track(*LINE, layer=PLANE)
    board, issues = imported(document(tracks=[*kept, cut]))
    assert sorted(t.layer for t in board.tracks) == ["F.Cu", "In2.Cu"] and board.arcs == ()
    assert drawn(board) == []
    assert "plane-cuts 1" in unmapped(issues)
    assert pairs(board, "In1.Cu") == {
        "layer_id": "39",
        "altium_name": "Layer 39",
        "plane_net": "GND",
        "plane_cuts": "1",
    }
    # the tracks that stay are what they are in the import of the document without the cut
    without, _ = imported(document(tracks=kept))
    assert [(t.id, t.provenance) for t in board.tracks] == [(t.id, t.provenance) for t in without.tracks]
    assert pairs(without, "In1.Cu") == {"layer_id": "39", "altium_name": "Layer 39", "plane_net": "GND"}


def test_kept_ids_do_not_depend_on_where_the_cut_is_in_the_stream() -> None:
    """A content id counts earlier entities of equal content only, and a cut is no entity: two equal
    tracks on a signal layer keep their two ids with a cut before, between or after them."""
    twin = rec.track(*LINE, layer=MID)
    cut = rec.track(*LINE, layer=PLANE)
    plain, _ = imported(document(tracks=[twin, twin]))
    ids = [t.id for t in plain.tracks]
    assert len(set(ids)) == 2
    for stream in ([cut, twin, twin], [twin, cut, twin], [twin, twin, cut]):
        board, _ = imported(document(tracks=stream))
        assert [t.id for t in board.tracks] == ids
        locators = [t.provenance.locator for t in board.tracks if t.provenance is not None]
        assert locators == [f"Tracks6/Data#{i}" for i, item in enumerate(stream) if item is twin]


def test_mid_layer_keeps_its_tracks() -> None:
    board, issues = imported(
        document(chain=(1, 2, MID, 32), plane_net=None, tracks=[rec.track(*LINE, layer=2)])
    )
    assert [t.layer for t in board.tracks] == ["In1.Cu"] and "plane-cuts" not in unmapped(issues)
    assert "plane_cuts" not in pairs(board, "In1.Cu")


# --- scenario "Every kind of object on a plane" --------------------------------------------------------


def test_every_kind_of_object_on_a_plane() -> None:
    doc = document(
        chain=(1, PLANE, 32),
        tracks=[rec.track(*LINE, layer=PLANE), rec.track(*LINE, layer=PLANE, net=0)],
        arcs=[
            rec.arc((0, 0), 100 * MIL, 0.0, 90.0, layer=PLANE),
            rec.arc((0, 0), 100 * MIL, 0.0, 360.0, layer=PLANE),
        ],
        fills=[rec.fill((0, 0), (90 * MIL, 90 * MIL), layer=PLANE)],
        regions=[rec.region(TRIANGLE, layer=PLANE)],
        texts=[rec.text("GND", layer=PLANE)],
    )
    board, issues = imported(doc)
    assert (board.tracks, board.arcs, board.texts, board.zones) == ((), (), (), ())
    assert drawn(board) == []
    assert "plane-cuts 7" in unmapped(issues)
    codes = {i.code for i in issues}
    assert "altium.import.copper-shape" not in codes and "altium.import.bad-geometry" not in codes
    assert pairs(board, "In1.Cu")["plane_cuts"] == "7"
    census_adds_up(doc)


def test_a_net_makes_no_copper_of_a_cut() -> None:
    board, issues = imported(document(tracks=[rec.track(*LINE, layer=PLANE, net=0)]))
    assert board.tracks == () and "plane-cuts 1" in unmapped(issues)


def test_cut_needs_no_width_and_no_radius() -> None:
    doc = document(
        tracks=[rec.track(*LINE, width=0, layer=PLANE)],
        arcs=[
            rec.arc((0, 0), 0, 0.0, 90.0, layer=PLANE),
            rec.arc((0, 0), 9, 0.0, 90.0, width=0, layer=PLANE),
        ],
        regions=[rec.region(TRIANGLE[:2], layer=PLANE)],
    )
    board, issues = imported(doc)
    assert "plane-cuts 4" in unmapped(issues)
    assert not [i for i in issues if i.code == "altium.import.bad-geometry"]
    assert pairs(board, "In1.Cu")["plane_cuts"] == "4"
    census_adds_up(doc)


def test_same_objects_on_a_signal_layer_are_what_they_were() -> None:
    """The control of the scenario: on the mid layer the same records are copper and shapes."""
    board, issues = imported(
        document(
            tracks=[rec.track(*LINE, layer=MID)],
            arcs=[rec.arc((0, 0), 100 * MIL, 0.0, 90.0, layer=MID)],
            fills=[rec.fill((0, 0), (90 * MIL, 90 * MIL), layer=MID)],
            regions=[rec.region(TRIANGLE, layer=MID)],
            texts=[rec.text("GND", layer=MID)],
        )
    )
    assert len(board.tracks) == len(board.arcs) == len(board.texts) == 1 and len(drawn(board)) == 2
    assert {item.layer for item in (*board.tracks, *board.arcs, *board.texts)} == {"In2.Cu"}
    assert "plane-cuts" not in unmapped(issues)
    (shape,) = [i for i in issues if i.code == "altium.import.copper-shape"]
    assert shape.message.startswith("2 fill(s) and region(s)")


# --- scenario "Plane without a net name" ---------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "(No Net)"])
def test_plane_without_a_net_name(name: str | None) -> None:
    board, issues = imported(
        document(chain=(1, PLANE, 32), plane_net=name, tracks=[rec.track(*LINE, layer=PLANE)])
    )
    assert board.tracks == () and "plane-cuts 1" in unmapped(issues)
    assert pairs(board, "In1.Cu") == {"layer_id": "39", "altium_name": "Layer 39", "plane_cuts": "1"}


def test_count_is_per_plane_layer() -> None:
    chain = (1, 39, 40, 32)
    tracks = [rec.track(*LINE, layer=39), rec.track(*LINE, layer=40), rec.track(*LINE, layer=40)]
    board, issues = imported(
        document(chain=chain, tracks=tracks, arcs=[rec.arc((0, 0), 9, 0.0, 90.0, layer=40)])
    )
    assert (pairs(board, "In1.Cu")["plane_cuts"], pairs(board, "In2.Cu")["plane_cuts"]) == ("1", "3")
    assert "plane-cuts 4" in unmapped(issues)


# --- what this change does not move --------------------------------------------------------------------


def test_owned_primitives_on_a_plane_keep_their_category() -> None:
    """A primitive of a component or of a polygon was not lowered before and is counted as before: the
    pull-back of a plane carries the split-plane polygon index."""
    from fenolite.backends.altium.read.pcb import SPLIT_PLANE_POLYGON

    doc = document(
        components=[rec.component("R1")],
        polygons=[rec.polygon()],
        tracks=[
            rec.track(*LINE, layer=PLANE, component=0),
            rec.track(*LINE, layer=PLANE, polygon=SPLIT_PLANE_POLYGON),
            rec.track(*LINE, layer=PLANE, polygon=0),
        ],
        arcs=[rec.arc((0, 0), 9, 0.0, 90.0, layer=PLANE, polygon=SPLIT_PLANE_POLYGON)],
        regions=[rec.region(TRIANGLE, layer=PLANE, polygon=SPLIT_PLANE_POLYGON)],
    )
    board, issues = imported(doc)
    message = unmapped(issues)
    assert board.tracks == () and board.arcs == () and "plane-cuts" not in message
    assert "footprint-graphics 1" in message and "pour-primitives 3" in message
    assert "plane_cuts" not in pairs(board, "In1.Cu")
    census_adds_up(doc)


def test_via_and_pad_through_a_plane_are_kept() -> None:
    board, _ = imported(
        document(
            vias=[rec.via((0, 0), net=0)],
            pads=[rec.pad("1", hole=30 * MIL, layer=74, net=0)],
            tracks=[rec.track(*LINE, layer=PLANE)],
        )
    )
    assert len(board.vias) == 1 and board.vias[0].layers == ("F.Cu", "B.Cu")
    assert sum(len(f.pads) for f in board.footprints) == 1 and board.tracks == ()


def test_no_entity_is_made_for_the_plane() -> None:
    board, _ = imported(document(tracks=[rec.track(*LINE, layer=PLANE)]))
    assert board.zones == () and board.keepouts == ()
    assert [layer.kind for layer in board.layers if layer.name == "In1.Cu"] == ["copper"]
