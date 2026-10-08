# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The footprint items of a KiCad board: nothing moves on a read or a write, and a projection gives them on
request (capability design-model, "Models without footprint items"; capability kicad-file-backend,
"Footprint items projected on request"; ``H-K-PCB-FPGFX``, ``H-K-PCB-FPGFX-BYTES``; change c0126).

The digests of ``UNCHANGED`` were measured with the code of the commit before the change (``f17b03e9``,
which gives the designs of release 0.2.1 for these boards).
"""

from __future__ import annotations

import dataclasses
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import fenolite
import fenolite.backends.kicad.slots as slotlib
from fenolite.backends.kicad import fpitems, pcb
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers, flip_layer
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.slots import Opaque
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.board import FootprintInstance, Graphic, Text
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

BOARDS = Path(__file__).resolve().parents[3] / "data" / "kicad" / "board"
UNCHANGED = {
    "dimension.kicad_pcb": "5ed9bf093487dcfd77938669f8a5eed537e9d8dfb43a7276c289969620560496",
    "two_layer.kicad_pcb": "a9b8bc33549c24ab6f8ae050ca53ecb2d4e34b0774c84b0dca960b4a2f857dea",
}
"""Board file → SHA-256 of ``canonical.dumps(read_board(text))`` before change c0126, with the header's
``fenolite_version`` of that commit, ``PINNED_VERSION``."""
PINNED_VERSION = "0.2.1"
"""The version the canonical text carried when ``UNCHANGED`` was measured: ``canonical.dumps`` writes the
running version into the header, so the digest is taken with that field set back (change c0150)."""


def _pinned_digest(design: Design) -> str:
    """The SHA-256 of the canonical text of ``design`` with the header's version of ``UNCHANGED``."""
    text = canonical.dumps(design)
    field = f'"fenolite_version": "{fenolite.__version__}"'
    assert text.count(field) == 1, field
    pinned = text.replace(field, f'"fenolite_version": "{PINNED_VERSION}"')
    return hashlib.sha256(pinned.encode("utf-8")).hexdigest()


def _read(name: str) -> Design:
    path = BOARDS / name
    return read_board(path.read_text(encoding="utf-8"), file=path.name)


def test_every_board_is_pinned() -> None:
    assert sorted(path.name for path in BOARDS.glob("*.kicad_pcb")) == sorted(UNCHANGED)


@pytest.mark.parametrize("name", sorted(UNCHANGED))
def test_read_is_unchanged(name: str) -> None:
    """Scenario "A KiCad read is unchanged": no footprint holds a graphic or a text, no pad a ratio, and
    the canonical text of the design is the one of the commit before the change."""
    design = _read(name)
    assert design.board is not None and (design.board.footprints or name == "dimension.kicad_pcb")
    for footprint in design.board.footprints:
        assert footprint.graphics == () and footprint.texts == ()
        assert all(pad.corner_ratio is None for pad in footprint.pads)
    assert _pinned_digest(design) == UNCHANGED[name]


# --- the projection on request (kicad-file-backend, "Footprint items projected on request") ---------------

MINI = Path(__file__).resolve().parents[3] / "data" / "libs" / "Mini.pretty"
PART = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", value="X")
AT = Point(20_000_000, 15_000_000)
COMPARED = ("kind", "layer", "points", "width", "filled")


def _plain(graphic: Graphic) -> tuple[object, ...]:
    return tuple(getattr(graphic, name) for name in COMPARED)


def _ratios(defn: FootprintDef) -> dict[str, int]:
    """Pad number → ppm of the ``roundrect_rratio`` of the library pad, read from its own opaque child."""
    found: dict[str, int] = {}
    for pad in defn.pads:
        for slot in slotlib.from_ext(pad.ext["kicad"]):
            if isinstance(slot, Opaque) and slot.fragment.startswith("(roundrect_rratio"):
                ppm = fpitems.ratio_ppm(slot.fragment.strip("()").split()[1])
                assert ppm is not None
                found[pad.number] = ppm
    return found


@pytest.mark.parametrize("path", sorted(MINI.glob("*.kicad_mod")), ids=lambda path: path.stem)
def test_projection_equals_the_library_reading(path: Path) -> None:
    """Scenario "Projection equals the library reading" (``H-K-PCB-FPGFX``): placed on the top side at
    angle 0 the projected graphics are those of the definition, in order, and every rounded pad has the
    ppm of its ``roundrect_rratio``. The points are footprint-local, so another angle gives the same
    points; on the bottom side they are mirrored about the local X axis, on the other side's layer."""
    defn = read_footprint(path, library="Mini")
    top = place_footprint(defn, component=PART, at=AT, key="U1")
    items = fpitems.footprint_items(top)
    assert [_plain(g) for g in items.graphics] == [_plain(g) for g in defn.graphics]
    assert len({g.id for g in items.graphics}) == len(items.graphics)
    by_number = {pad.number: items.ratios[pad.id] for pad in top.pads if pad.id in items.ratios}
    assert by_number == _ratios(defn)
    assert all(pad.shape == "roundrect" for pad in top.pads if pad.id in items.ratios)
    for angle in (90_000_000, 180_000_000, 30_000_000):
        turned = place_footprint(defn, component=PART, at=AT, rotation=angle, key="U1")
        assert [_plain(g) for g in fpitems.footprint_items(turned).graphics] == [
            _plain(g) for g in defn.graphics
        ]
    try:
        bottom = place_footprint(defn, component=PART, at=AT, rotation=30_000_000, side="bottom", key="U1")
    except LossyWriteError:
        return  # a child that cannot be flipped: the footprint has no bottom copy
    mirrored = fpitems.footprint_items(bottom).graphics
    assert [(g.kind, g.layer, g.width, g.filled) for g in mirrored] == [
        (g.kind, flip_layer(g.layer), g.width, g.filled) for g in defn.graphics
    ]
    for mine, theirs in zip(mirrored, defn.graphics, strict=True):
        if mine.kind != "arc":  # a mirrored arc swaps its ends
            assert mine.points == tuple(Point(p.x, -p.y) for p in theirs.points)


@pytest.mark.parametrize("name", sorted(UNCHANGED))
@pytest.mark.parametrize("target", [9, 10])
def test_projection_changes_no_byte(name: str, target: int) -> None:
    """Scenario "The projection changes no byte": the board text with and without the projection."""
    design = _read(name)
    projection = fpitems.with_footprint_items(design)
    assert projection.design.board is not None and design.board is not None
    assert write_board(projection.design, target=target).text == write_board(design, target=target).text
    for footprint in projection.design.board.footprints:
        assert fpitems.is_projected(footprint)
    again = fpitems.with_footprint_items(projection.design)
    assert again.design == projection.design and again.projected == projection.projected
    # the unprojected design is untouched, and its canonical text is the pinned one
    assert _pinned_digest(design) == UNCHANGED[name]


def test_projection_of_the_two_layer_board_counts_what_it_holds() -> None:
    """Every drawing child of every footprint is projected or counted, and ids are unique and scoped."""
    design = _read("two_layer.kicad_pcb")
    projection = fpitems.with_footprint_items(design)
    assert projection.design.board is not None and design.board is not None
    drawn = 0
    for footprint in design.board.footprints:
        for slot in slotlib.from_ext(footprint.ext["kicad"]):
            if isinstance(slot, Opaque) and slot.fragment[1:].split(None, 1)[0] in fpitems.DRAWN_HEADS:
                drawn += 1
    assert drawn and drawn == (
        projection.projected["graphic"] + projection.projected["text"] + sum(projection.skipped.values())
    )
    ids = [
        item.id
        for footprint in projection.design.board.footprints
        for item in (*footprint.graphics, *footprint.texts)
    ]
    assert len(ids) == len(set(ids))
    assert not [issue for issue in projection.design.validate() if issue.code == "model.duplicate-id"]
    for footprint in projection.design.board.footprints:
        for graphic in footprint.graphics:
            native = graphic.native_ids.get("kicad")
            if native is not None:
                key = footprint.native_ids["kicad"]
                assert graphic.id == derived_id("gfx", "kicad", f"{key}:{native}")


def test_text_and_skipped_children() -> None:
    """One ``fp_text`` gives a ``Text`` with its angle relative to the footprint; a dashed line, a polygon
    with an arc, a text box, a text without a thickness and an inexact number are left out and counted."""
    design = _read("two_layer.kicad_pcb")
    assert design.board is not None
    footprint = design.board.footprints[0]
    turned = dataclasses.replace(footprint, rotation=90_000_000, graphics=(), texts=())
    extra = (
        '(fp_text user "note" (at 1 2 90) (layer "F.Fab") (uuid "00000000-0000-4000-8000-0000000000a1") '
        "(effects (font (size 1 0.8) (thickness 0.15))))",
        '(fp_text user "bare" (at 1 2) (layer "F.Fab") (effects (font (size 1 1))))',
        '(fp_line (start 0 0) (end 1 0) (stroke (width 0.1) (type dash)) (layer "F.SilkS"))',
        '(fp_line (start 0 0) (end 1.0000000001 0) (stroke (width 0.1) (type solid)) (layer "F.SilkS"))',
        '(fp_poly (pts (xy 0 0) (arc (start 0 0) (mid 1 1) (end 2 0))) (layer "F.SilkS"))',
        '(fp_text_box "box" (start 0 0) (end 1 1) (layer "F.SilkS"))',
    )
    bag = slotlib.to_ext([Opaque(text, None) for text in extra])
    items = fpitems.footprint_items(dataclasses.replace(turned, ext={"kicad": bag}))
    assert items.graphics == ()
    (text,) = items.texts
    assert (text.text, text.layer, text.rotation, text.thickness) == ("note", "F.Fab", 0, 150_000)
    assert text.position == Point(1_000_000, 2_000_000) and text.size == Size(800_000, 1_000_000)
    assert sorted(items.skipped) == ["fp_line", "fp_line", "fp_poly", "fp_text", "fp_text_box"]


def test_edited_projection_is_refused() -> None:
    """Scenario "An edited projection is refused": a moved footprint graphic and an added text each give
    ``kicad.board.projection-read-only`` naming the field; without the pair the fields are not looked at."""
    projected = fpitems.with_footprint_items(_read("two_layer.kicad_pcb")).design
    assert projected.board is not None
    index, footprint = next((i, fp) for i, fp in enumerate(projected.board.footprints) if fp.graphics)
    first = footprint.graphics[0]
    moved = dataclasses.replace(first, points=tuple(Point(p.x + 1_000_000, p.y) for p in first.points))

    def with_footprint(new: FootprintInstance) -> Design:
        assert projected.board is not None
        footprints = list(projected.board.footprints)
        footprints[index] = new
        board = dataclasses.replace(projected.board, footprints=tuple(footprints))
        return dataclasses.replace(projected, board=board)

    edited = dataclasses.replace(footprint, graphics=(moved, *footprint.graphics[1:]))
    with pytest.raises(LossyWriteError) as refused:
        write_board(with_footprint(edited), target=10)
    assert [issue.code for issue in refused.value.issues] == ["kicad.board.projection-read-only"]
    assert "'graphics'" in refused.value.issues[0].message
    note = Text(id="txt_new", text="x", layer="F.Fab", position=Point(0, 0), size=Size(1, 1), thickness=1)
    with pytest.raises(LossyWriteError) as refused:
        write_board(with_footprint(dataclasses.replace(footprint, texts=(*footprint.texts, note))), target=10)
    assert "'texts'" in refused.value.issues[0].message
    # without the pair the writer does not look at the fields: the children are written as read
    bag = footprint.ext["kicad"]
    bare = dataclasses.replace(bag, payload=tuple(p for p in bag.payload if p != fpitems.PROJECTED_PAIR))
    unmarked = dataclasses.replace(edited, ext={**footprint.ext, "kicad": bare})
    original = _read("two_layer.kicad_pcb")
    assert write_board(with_footprint(unmarked), target=10).text == write_board(original, target=10).text
    assert pcb.PROJECTED_PAIR == fpitems.PROJECTED_PAIR


def test_edited_corner_ratio_is_refused() -> None:
    defn = read_footprint(MINI / "Mini_R_0603.kicad_mod", library="Mini")
    placed = place_footprint(defn, component=PART, at=AT, key="U1")
    design = Design.new("ratio", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(placed,))
    design = dataclasses.replace(design, circuit=Circuit(components=(PART,)), board=board)
    read = read_board(write_board(design, target=10).text, file="ratio.kicad_pcb")
    projected = fpitems.with_footprint_items(read).design
    assert projected.board is not None
    (footprint,) = projected.board.footprints
    rounded = [pad for pad in footprint.pads if pad.corner_ratio is not None]
    assert rounded and all(pad.corner_ratio == 250_000 for pad in rounded)
    assert write_board(projected, target=10).text == write_board(read, target=10).text
    pads = tuple(
        dataclasses.replace(pad, corner_ratio=100_000) if pad is rounded[0] else pad for pad in footprint.pads
    )
    changed = dataclasses.replace(projected.board, footprints=(dataclasses.replace(footprint, pads=pads),))
    with pytest.raises(LossyWriteError) as refused:
        write_board(dataclasses.replace(projected, board=changed), target=10)
    assert "'corner_ratio'" in refused.value.issues[0].message


def test_no_reader_or_writer_imports_the_projection() -> None:
    """No module of the read or write path of a board imports ``fpitems`` at import time: ``pcb`` imports
    it inside its check of a projected footprint only."""
    code = (
        "import sys; import fenolite.backends.kicad.pcb, fenolite.backends.kicad.embed, "
        "fenolite.backends.kicad.mod, fenolite.backends.kicad.backend; "
        "print('fenolite.backends.kicad.fpitems' in sys.modules)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "False"


def test_footprint_without_a_kicad_bag_is_kept() -> None:
    """A footprint that holds no ``kicad`` bag was not read from a KiCad board (the stored board of an
    Altium build holds its own graphics, change c0126): the projection returns it as it is, unmarked."""
    design = _read("two_layer.kicad_pcb")
    assert design.board is not None and design.board.footprints
    line = Graphic(id="gfx_own", kind="line", layer="F.SilkS", points=(Point(0, 0), Point(1, 0)), width=1)
    own = dataclasses.replace(design.board.footprints[0], ext={}, graphics=(line,))
    footprints = (own, *design.board.footprints[1:])
    mixed = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    projected = fpitems.with_footprint_items(mixed).design
    assert projected.board is not None
    assert projected.board.footprints[0] == own and not fpitems.is_projected(projected.board.footprints[0])
    assert all(fpitems.is_projected(fp) for fp in projected.board.footprints[1:])
