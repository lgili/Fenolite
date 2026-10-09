# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads of a converted board (capability altium-pcb-writer, "Full-stack pad records", "Slotted pad holes" and
"Connector and free pads"; change c0160, ``H-A-CONV-PADSTACK``).

The KiCad sample ``blink`` is read, one pad is changed in the model, the board is written with
``lower.write_design`` and the PCB document is read back with the Altium backend. ``D1`` is a through-hole
LED on the bottom side, so its pads also go through the writer's flip.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.altium import lower, pcblib
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Layer, Pad, Padstack, PadstackLayer
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
BLINK = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10" / "blink.kicad_pcb"
UNIT_NM = 3
"""A length is written in units of 2.54 nm: a read-back length is within 3 nm of the model's."""
MM = 1_000_000


def _blink() -> Design:
    """The sample with the corner ratios of its pads, as a conversion projects it."""
    return fpitems.with_footprint_items(KicadBackend().read(BLINK).design).design


def _four_layers(design: Design) -> Design:
    """``design`` with the inner copper layers ``In1.Cu`` and ``In2.Cu`` between its outer layers."""
    board = design.board
    assert board is not None
    layers = list(board.layers)
    inner = [
        Layer(id=derived_id("lay", "test", name), name=name, kind="copper", ordinal=ordinal)
        for ordinal, name in ((1, "In1.Cu"), (2, "In2.Cu"))
    ]
    layers[1:1] = inner
    return dataclasses.replace(design, board=dataclasses.replace(board, layers=tuple(layers)))


def _with_pad(design: Design, ref: str, pin: str, **changes: object) -> tuple[Design, Pad]:
    """``design`` with the pad ``pin`` of ``ref`` changed, and the changed pad."""
    board = design.board
    assert board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    footprints = []
    changed: Pad | None = None
    for fp in board.footprints:
        if refs.get(fp.component_id) == ref:
            pads = []
            for pad in fp.pads:
                if pad.number == pin and changed is None:
                    pad = dataclasses.replace(pad, **changes)  # type: ignore[arg-type]
                    changed = pad
                pads.append(pad)
            fp = dataclasses.replace(fp, pads=tuple(pads))
        footprints.append(fp)
    assert changed is not None
    return dataclasses.replace(
        design, board=dataclasses.replace(board, footprints=tuple(footprints))
    ), changed


def _stack(*layers: tuple[str, str, int], hole: str = "round", length: int | None = None) -> Padstack:
    return Padstack(
        id=derived_id("pst", "test", repr(layers) + hole),
        layers=tuple(PadstackLayer(name, shape, Size(size, size)) for name, shape, size in layers),
        hole_shape=hole,  # type: ignore[arg-type]
        hole_length=length,
    )


def _written(design: Design, tmp_path: Path) -> tuple[lower.ProjectWrite, Design]:
    written = lower.write_design(design, allow_lossy=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name, data in written.files.items():
        (tmp_path / name).write_bytes(data)
    document = next(tmp_path / name for name in written.files if name.endswith(".PcbDoc"))
    return written, AltiumBackend().read(document).design


def _pad_of(design: Design, ref: str, number: str) -> Pad:
    board = design.board
    assert board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return next(
        pad
        for fp in board.footprints
        if refs.get(fp.component_id) == ref
        for pad in fp.pads
        if pad.number == number
    )


def _copper(pad: Pad, layer: str) -> tuple[str, int, int]:
    """The shape and size of ``pad`` on the copper layer ``layer``, resolving the inner wildcard."""
    entries = {entry.layer: entry for entry in (pad.padstack.layers if pad.padstack else ())}
    inner = layer.startswith("In")
    entry = entries.get(layer) or (entries.get("In*.Cu") if inner else None)
    if entry is None:
        return pad.shape, pad.size.w, pad.size.h
    return entry.shape, entry.size.w, entry.size.h


def _close(a: tuple[str, int, int], b: tuple[str, int, int]) -> bool:
    return a[0] == b[0] and abs(a[1] - b[1]) <= UNIT_NM and abs(a[2] - b[2]) <= UNIT_NM


LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def test_per_layer_stack_read_back(tmp_path: Path) -> None:
    """Scenario "Per-layer stack read back": 1.6 mm round on top and bottom, 1.2 mm on the inner layers of
    a 4-layer board: stack mode 1, and the shape and size per copper layer equal the model's."""
    stack = _stack(
        ("F.Cu", "circle", 1_600_000), ("In*.Cu", "circle", 1_200_000), ("B.Cu", "circle", 1_600_000)
    )
    design, model = _with_pad(
        _four_layers(_blink()), "D1", "2", padstack=stack, size=Size(1_600_000, 1_600_000)
    )
    written, back = _written(design, tmp_path)
    assert not any(model.id in ids for ids in written.inputs.lost.get("pad", {}).values())
    read = _pad_of(back, "D1", "2")
    assert dict(lower.pairs_of(read)).get("stack_mode") == "1"
    for layer in LAYERS:
        assert _close(_copper(read, layer), _copper(model, layer)), layer


def test_full_stack_read_back(tmp_path: Path) -> None:
    """Two inner layers of different copper and a bottom unlike the top: stack mode 2, every layer back,
    on a footprint of the bottom side."""
    stack = _stack(
        ("F.Cu", "circle", 1_600_000),
        ("In1.Cu", "circle", 1_200_000),
        ("In2.Cu", "rect", 1_400_000),
        ("B.Cu", "circle", 1_800_000),
    )
    design, model = _with_pad(
        _four_layers(_blink()), "D1", "2", padstack=stack, size=Size(1_600_000, 1_600_000)
    )
    _written_files, back = _written(design, tmp_path)
    read = _pad_of(back, "D1", "2")
    assert dict(lower.pairs_of(read)).get("stack_mode") == "2"
    for layer in LAYERS:
        assert _close(_copper(read, layer), _copper(model, layer)), layer


def test_slot_read_back(tmp_path: Path) -> None:
    """Scenario "Slot read back": a 1.2 by 2.4 mm oval pad with a 0.6 by 1.8 mm oval drill."""
    stack = _stack(hole="slot", length=1_800_000)
    design, _model = _with_pad(
        _blink(), "D1", "1", padstack=stack, size=Size(1_200_000, 2_400_000), shape="oval", drill=600_000
    )
    written, back = _written(design, tmp_path)
    assert "pad" not in written.inputs.lost
    read = _pad_of(back, "D1", "1")
    assert read.padstack is not None and read.padstack.hole_shape == "slot"
    assert read.drill is not None and abs(read.drill - 600_000) <= UNIT_NM
    assert read.padstack.hole_length is not None and abs(read.padstack.hole_length - 1_800_000) <= UNIT_NM


def test_slot_record_holds_its_length_and_rotation() -> None:
    """The sixth subrecord of a slotted pad: hole shape 2, the length in units, the rotation in degrees."""
    stack = dataclasses.replace(_stack(hole="slot", length=2_540_000), hole_rotation=90_000_000)
    pad = Pad(
        id=derived_id("pad", "test", "slot"),
        number="1",
        shape="oval",
        size=Size(1_200_000, 3_000_000),
        position=Point(0, 0),
        kind="thru_hole",
        drill=600_000,
        layers=("*.Cu",),
        padstack=stack,
    )
    record = pcblib.stack_record(pad, pcblib.PadExtras())
    assert record is not None
    assert (record.mode, record.hole_shape, record.slot_length, record.slot_rotation) == (
        0,
        2,
        1_000_000,
        90.0,
    )


@pytest.mark.parametrize(
    ("layers", "reason"),
    [
        ((("F.Cu", "custom", 1_600_000),), "has the shape custom on F.Cu of its padstack"),
        ((("User.1", "circle", 1_600_000),), "has a padstack layer User.1, which no Altium stack holds"),
    ],
)
def test_unwritten_stack_stays_a_loss(layers: tuple[tuple[str, str, int], ...], reason: str) -> None:
    """A stack with a custom shape or a layer no Altium stack holds keeps the pad a lost ``pad``."""
    design, model = _with_pad(_blink(), "D1", "2", padstack=_stack(*layers))
    written = lower.write_design(design, allow_lossy=True)
    found = {r: ids for r, ids in written.inputs.lost["pad"].items() if model.id in ids}
    assert len(found) == 1 and reason in next(iter(found))


def test_record_without_stack_keeps_its_bytes(tmp_path: Path) -> None:
    """The blink sample, unchanged, gives pad records that the reader reads as Simple pads with no hole
    form: the stack fields are written only for a stack or a slot."""
    written, _back = _written(_blink(), tmp_path)
    document = read_pcbdoc(written.files["blink.PcbDoc"], file="blink.PcbDoc")
    assert {pad.stack_mode for pad in document.pads} == {0}
    assert {pad.hole_shape for pad in document.pads if pad.hole_shape is not None} <= {0}


def test_connect_pad(tmp_path: Path) -> None:
    """Scenario "Connector pad": a ``connect`` pad on ``F.Cu`` alone is a surface pad on its copper layer
    whose paste and solder-mask expansions are manual and remove both openings; it is counted ``changed``,
    not lost."""
    design, model = _with_pad(_blink(), "R1", "1", kind="connect", layers=("F.Cu",))
    written, back = _written(design, tmp_path)
    assert "pad" not in written.inputs.lost
    assert [ids for ids in written.inputs.changed["pad"].values()] == [(model.id,)]
    read = _pad_of(back, "R1", "1")
    assert read.kind == "smd" and read.layers == ("F.Cu",)
    pairs = dict(lower.pairs_of(read))
    size = max(model.size.w, model.size.h) * 50 // 127
    assert pairs["paste"].split(",")[0] == pairs["mask"].split(",")[0] == "2"
    assert -int(pairs["paste"].split(",")[1]) >= size and -int(pairs["mask"].split(",")[1]) >= size


def test_connect_pad_with_mask_keeps_its_opening(tmp_path: Path) -> None:
    """A KiCad connector pad that lists ``F.Mask`` keeps its mask opening: the paste is removed, the mask
    follows the rules."""
    design, _model = _with_pad(_blink(), "R1", "1", kind="connect", layers=("F.Cu", "F.Mask"))
    _written_files, back = _written(design, tmp_path)
    pairs = dict(lower.pairs_of(_pad_of(back, "R1", "1")))
    assert pairs["paste"].split(",")[0] == "2" and "mask" not in pairs


def test_unnamed_pad(tmp_path: Path) -> None:
    """Scenario "Unnamed pad": a pad without a number inside a footprint is written as a pad of that
    footprint with an empty designator (saved documents hold such pads, ``pcb-library.md``) and is neither
    lost nor changed."""
    design, model = _with_pad(_blink(), "U1", "1", number="")
    written, back = _written(design, tmp_path)
    assert "pad" not in written.inputs.lost and "pad" not in written.inputs.changed
    read = _pad_of(back, "U1", "")
    assert read.shape == model.shape and abs(read.size.w - model.size.w) <= UNIT_NM
