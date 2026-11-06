# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A flip in an edit session moves a component's texts and pads to the other side together with their long
layer ids (change c0430, S-1890: Altium Designer 24.5 showed the designator of a flipped part on Top
Overlay, because the saved text record still named Top Overlay by its long layer id).

The saved forms are authored here: the records the kit board holds, lengthened to the saved lengths of a
text (252 bytes, the long layer id at 226) and of a pad's geometry subrecord (194 bytes, the long layer id
at 114), as the row "Long layer ids of texts and pads" of ``pcb-records.md`` records them."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.edit import integrity, ops
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.libboard import long_id
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PAD, TEXT, ArcRecord, PadRecord, TextRecord, TrackRecord
from tests.unit.backends.altium.edit.conftest import OPEN

ROOT = Path(__file__).resolve().parents[5]
TOP_OVERLAY, BOTTOM_OVERLAY, TOP, BOTTOM, MULTI_LAYER = 33, 34, 1, 32, 74
TEXT_SAVED, TEXT_LONG_AT = 252, 226
PAD_SAVED, PAD_LONG_AT = 194, 114


def _saved_form(raw: bytes) -> bytes:
    """A kit text or pad in the saved length, its long layer id that of its layer byte."""
    kind, subs = rec.split(raw)
    index, length, at = (4, PAD_SAVED, PAD_LONG_AT) if kind == PAD else (0, TEXT_SAVED, TEXT_LONG_AT)
    body = bytearray(subs[index] + bytes(length - len(subs[index])))
    struct.pack_into("<I", body, at, long_id(body[0]))
    subs[index] = bytes(body)
    return rec.join(kind, subs)


def _lengthen(board: Path) -> Path:
    state = State.of(board.read_bytes(), file=board.name)
    for storage in ("Texts6", "Pads6"):
        for position, raw in enumerate(state.get(storage)):
            state.replace(storage, position, _saved_form(raw))
    board.write_bytes(state.data())
    return board


def _flip(board: Path, out: Path, side: str, *refs: str) -> PcbDocument:
    session = edit.open(board, gates={name: True for name in OPEN})
    assert isinstance(session, edit.Session)
    for ref in refs:
        session = session.flip(edit.Component(ref), old_side=side)
    receipt = session.declare_connectivity("MID", "GND", "VIN").commit(out, backup=False)
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    assert integrity.check_pcbdoc(data) == ()
    return read_pcbdoc(data)


def _index(doc: PcbDocument, ref: str) -> int:
    return next(i for i, c in enumerate(doc.components) if c.source_designator == ref)


def _long(raw: bytes) -> int | None:
    offset = rec.long_layer_offset(raw)
    if offset is None:
        return None
    kind, subs = rec.split(raw)
    (value,) = struct.unpack_from("<I", subs[4 if kind == PAD else 0], offset)
    return int(value)


def _texts(doc: PcbDocument, index: int) -> list[TextRecord]:
    return [t for t in doc.texts if isinstance(t, TextRecord) and t.prefix.component == index]


def _pads(doc: PcbDocument, index: int) -> list[PadRecord]:
    return [p for p in doc.pads if isinstance(p, PadRecord) and p.prefix.component == index]


def test_long_layer_offsets_of_texts_and_pads() -> None:
    """The saved lengths hold the id (232 and 252 for a text, 170 to 194 for a pad's geometry); the forms
    Fenolite writes (137, 114) hold none; another length is refused."""
    for length, wanted in ((137, None), (232, TEXT_LONG_AT), (252, TEXT_LONG_AT)):
        assert (
            rec.long_layer_offset(rec.join(TEXT, [bytes([TOP_OVERLAY]) + bytes(length - 1), b""])) == wanted
        )
    with pytest.raises(rec.RecordError):
        rec.long_layer_offset(rec.join(TEXT, [bytes([TOP_OVERLAY]) + bytes(199), b""]))
    pad = [b"\x00", b"\x00", b"", b"\x00", bytes([TOP]) + bytes(113), b""]
    assert rec.long_layer_offset(rec.join(PAD, pad)) is None
    for length in (170, 185, 186, 194):
        pad[4] = bytes([TOP]) + bytes(length - 1)
        assert rec.long_layer_offset(rec.join(PAD, pad)) == PAD_LONG_AT


@pytest.mark.parametrize("saved", [True, False], ids=["saved-form", "written-form"])
def test_flip_to_the_bottom_and_back(board: Path, tmp_path: Path, saved: bool) -> None:
    """Top to bottom: D1's and R1's designator and comment on Bottom Overlay, mirrored, by layer byte and long
    layer id; R1's SMD pads on Bottom Layer; D1's through-hole pads stay on Multi-Layer; both components on
    BOTTOM. Bottom to top: every text and pad record is again the one the board held."""
    source = _lengthen(board) if saved else board
    before = read_pcbdoc(source.read_bytes())
    down = _flip(source, tmp_path / "down.PcbDoc", "TOP", "D1", "R1")
    for ref, pads in (("D1", MULTI_LAYER), ("R1", BOTTOM)):
        index = _index(down, ref)
        assert down.components[index].layer == "BOTTOM"
        texts = _texts(down, index)
        assert sorted((t.is_designator, t.is_comment) for t in texts) == [(False, True), (True, False)]
        for text in texts:
            assert (text.prefix.layer, text.mirrored) == (BOTTOM_OVERLAY, True)
            assert _long(text.raw) == (long_id(BOTTOM_OVERLAY) if saved else None)
        for pad in _pads(down, index):
            assert pad.prefix.layer == pads
            assert _long(pad.raw) == (long_id(pads) if saved else None)
    if saved:
        assert long_id(BOTTOM_OVERLAY) == 0x01030007 and long_id(BOTTOM) == 0x0100FFFF
    up = _flip(tmp_path / "down.PcbDoc", tmp_path / "up.PcbDoc", "BOTTOM", "D1", "R1")
    for ref in ("D1", "R1"):
        index = _index(up, ref)
        assert up.components[index].layer == "TOP"
        assert [t.raw for t in _texts(up, index)] == [t.raw for t in _texts(before, index)]
        assert [p.raw for p in _pads(up, index)] == [p.raw for p in _pads(before, index)]
        assert {(t.prefix.layer, t.mirrored) for t in _texts(up, index)} == {(TOP_OVERLAY, False)}


def test_relayer_moves_a_text_and_a_pad_with_their_long_layer_ids(board: Path) -> None:
    """``relayer`` patches the byte and the id alone; the record keeps its length."""
    state = State.of(_lengthen(board).read_bytes(), file=board.name)
    text = state.get("Texts6")[0]
    pad = next(raw for raw in state.get("Pads6") if rec.prefix_of(raw)[0] == TOP)
    for raw, layer in ((text, BOTTOM_OVERLAY), (pad, BOTTOM)):
        moved = ops.relayer(raw, layer)
        assert len(moved) == len(raw) and rec.prefix_of(moved)[0] == layer and _long(moved) == long_id(layer)
        kind, before = rec.split(raw)
        offset = rec.long_layer_offset(raw)
        assert offset is not None
        index = 4 if kind == PAD else 0
        after = rec.split(moved)[1][index]
        assert {i for i, (a, b) in enumerate(zip(before[index], after, strict=True)) if a != b} <= {
            0,
            *range(offset, offset + 4),
        }


@pytest.mark.parametrize(
    ("ref", "layer", "mirrored"), [("D1", BOTTOM_OVERLAY, True), ("R1", TOP_OVERLAY, False)]
)
def test_written_board_puts_the_texts_on_the_part_side(ref: str, layer: int, mirrored: bool) -> None:
    """The Altium write of the blink sample, whose D1 lies on the bottom: D1's designator and comment on
    Bottom Overlay and mirrored, R1's on Top Overlay and not mirrored."""
    design = AltiumBackend().read(ROOT / "tests/data/altium/blink/blink.PcbDoc").design
    written = AltiumBackend().write(design)
    (name,) = [n for n in written.files if n.endswith(".PcbDoc")]
    doc = read_pcbdoc(written.files[name])
    index = _index(doc, ref)
    assert doc.components[index].layer == ("BOTTOM" if mirrored else "TOP")
    texts = [t for t in _texts(doc, index) if t.is_designator or t.is_comment]
    assert len(texts) == 2
    assert {(t.prefix.layer, t.mirrored) for t in texts} == {(layer, mirrored)}


# --- mechanical layers: only the pairs the board declares (S-1892, case J9) ---------------------------

MECHANICAL_13, MECHANICAL_14, MECHANICAL_15 = 69, 70, 71


def _long_drawings(state: State) -> None:
    """The kit's tracks and arcs in their saved 49- and 60-byte forms, each with its long layer id."""
    for storage, length, at in (("Tracks6", 49, 41), ("Arcs6", 60, 52)):
        for position, raw in enumerate(state.get(storage)):
            kind, subs = rec.split(raw)
            body = bytearray(subs[0] + bytes(length - len(subs[0])))
            struct.pack_into("<I", body, at, long_id(body[0]))
            subs[0] = bytes(body)
            state.replace(storage, position, rec.join(kind, subs))


def _declare(board: Path, pairs: dict[str, str]) -> Path:
    state = State.of(board.read_bytes(), file=board.name)
    _long_drawings(state)
    state.replace("Board6", 0, rec.set_property(state.get("Board6")[0], pairs))
    board.write_bytes(state.data())
    return board


def _drawings(doc: PcbDocument, index: int) -> list[tuple[int, int | None]]:
    return sorted(
        (r.prefix.layer, _long(r.raw))
        for r in (*doc.tracks, *doc.arcs)
        if isinstance(r, TrackRecord | ArcRecord) and r.prefix.component == index
    )


def test_mechanical_pairs_are_read_from_the_board(board: Path) -> None:
    """``MECHPAIR<i>L1`` and ``L2`` in any order and case; a pair without its other half is none."""
    _declare(board, {"MECHPAIR1L2": "MECHANICAL19", "MechPair0L1": "Mechanical13",
                     "MECHPAIR0L2": "MECHANICAL14", "MECHPAIR1L1": "MECHANICAL15",
                     "MECHPAIR2L1": "MECHANICAL2"})  # fmt: skip
    state = State.of(board.read_bytes(), file=board.name)
    assert ops.mechanical_pairs(state) == ((13, 14), (15, 19))


def test_flip_keeps_mechanical_layers_of_no_declared_pair(board: Path, tmp_path: Path) -> None:
    """The kit board declares no pair: D1's Mechanical 13 and 15 drawings stay on their layers, as in
    Altium's own flip of D1 (J09); its overlay drawings go to Bottom Overlay."""
    before = read_pcbdoc(board.read_bytes())
    index = _index(before, "D1")
    down = _flip(board, tmp_path / "down.PcbDoc", "TOP", "D1")
    old = {layer for layer, _ in _drawings(before, index)}
    new = {layer for layer, _ in _drawings(down, index)}
    assert MECHANICAL_15 in old and new == {
        BOTTOM_OVERLAY if layer == TOP_OVERLAY else layer for layer in old
    }


def test_flip_swaps_the_declared_mechanical_pairs(board: Path, tmp_path: Path) -> None:
    """With Mechanical 13 paired with 14 and 15 with 19, D1's drawings move to 14 and 19: Mechanical 19 by
    the layer byte of Mechanical 16 and the long layer id of 19 (S-1654). The flip back restores them."""
    _declare(board, {"MECHPAIR0L1": "MECHANICAL13", "MECHPAIR0L2": "MECHANICAL14",
                     "MECHPAIR1L1": "MECHANICAL15", "MECHPAIR1L2": "MECHANICAL19"})  # fmt: skip
    before = read_pcbdoc(board.read_bytes())
    index = _index(before, "D1")
    swap: dict[tuple[int, int | None], tuple[int, int | None]] = {
        (TOP_OVERLAY, long_id(TOP_OVERLAY)): (BOTTOM_OVERLAY, long_id(BOTTOM_OVERLAY)),
        (MECHANICAL_13, long_id(MECHANICAL_13)): (MECHANICAL_14, long_id(MECHANICAL_14)),
        (MECHANICAL_15, long_id(MECHANICAL_15)): (72, 0x01020013),
    }
    old = _drawings(before, index)
    assert (MECHANICAL_15, long_id(MECHANICAL_15)) in old
    down = _flip(board, tmp_path / "down.PcbDoc", "TOP", "D1")
    assert _drawings(down, index) == sorted(swap.get(item, item) for item in old)
    up = _flip(tmp_path / "down.PcbDoc", tmp_path / "up.PcbDoc", "BOTTOM", "D1")
    assert _drawings(up, index) == old
