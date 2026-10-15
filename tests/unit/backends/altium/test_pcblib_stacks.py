# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Full-stack pads and holes that are not round (capability altium-pcb-writer, "Full-stack pad records";
change c0160; hypothesis ``H-A-CONV-PADSTACK``).

The scenario "Per-layer stack read back": a footprint with a pad of 1.6 mm round on top and bottom and
1.2 mm round on the inner layers is written with **stack mode 1** and every layer reads back with the shape
and size of the model; a stack whose inner layers differ is written with **mode 2**.

A hole that is not round is written with its shape, its slot length and its slot rotation. That is the
reason the census of c0159 gives for the 108 pads it loses, and every one of them is a slotted hole (the
design's "Found on 2026-10-10 (implementation)"), so the last tests cover it.

The records are read with ``tests/_altium_pcb_read.py``, the independent decoder written from
``pcb-records.md``, and the layers with the Altium backend's own reader.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from _altium_pcb_read import PadRecord, decode_primitives

from fenolite.backends.altium import pcblib
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad, Padstack, PadstackLayer
from fenolite.model.library import FootprintDef

PADSTACK_ID = "pst_00000000-0000-4000-8000-000000000001"
PAD_ID = "pad_00000000-0000-4000-8000-000000000001"
FOUR_LAYER = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def mm(text: str) -> int:
    return int(Decimal(text) * 1_000_000)


def units(nm: int) -> int:
    return rec.to_units(nm)


def close(first: int, second: int) -> bool:
    """Whether two lengths agree within the record's unit, 1/10 000 mil (2.54 nm): a length written into
    a record and read back may move by one unit, which is the format's own limit."""
    return abs(first - second) <= 2


def sizes_close(got: Size, want: Size) -> bool:
    return close(got.w, want.w) and close(got.h, want.h)


def layer(name: str, shape: str, width: str, height: str | None = None) -> PadstackLayer:
    return PadstackLayer(name, shape, Size(mm(width), mm(height or width)))


def pad(
    *,
    size: str = "1.6",
    shape: str = "circle",
    drill: str | None = "0.8",
    kind: str = "thru_hole",
    number: str = "1",
    stack: Padstack | None = None,
    rotation: int = 0,
) -> Pad:
    return Pad(
        id=PAD_ID,
        number=number,
        kind=kind,
        shape=shape,
        size=Size(mm(size), mm(size)),
        position=Point(0, 0),
        rotation=rotation,
        drill=mm(drill) if drill is not None else None,
        layers=("*.Cu",) if kind not in ("smd", "connect") else ("F.Cu",),
        padstack=stack,
    )


def definition(pad_: Pad, name: str = "Mini_Slot") -> FootprintDef:
    return FootprintDef(id="fpd_00000000-0000-4000-8000-000000000001", name=name, pads=(pad_,))


def record_of(pad_: Pad, *, copper_layers: tuple[str, ...] = ()) -> PadRecord:
    """The one pad record ``pad_bytes`` writes, read with the independent decoder."""
    data = pcblib.pad_bytes(
        pad_,
        pcblib.PadExtras(),
        at=Point(0, 0),
        rotation_udeg=pad_.rotation,
        copper_layers=copper_layers,
    )
    found = [item for item in decode_primitives(data)]
    assert len(found) == 1 and isinstance(found[0], PadRecord), found
    return found[0]


def read_back(defn: FootprintDef, tmp_path: Path) -> Pad:
    """Write a library holding ``defn`` and read its first pad with the Altium backend."""
    assert pcblib.check_footprint(defn, {}).refusal is None
    data = pcblib.write_pcblib([pcblib.LibFootprint(defn, {})])
    path = tmp_path / f"{defn.name}.PcbLib"
    path.write_bytes(data)
    library = AltiumBackend().read(path).content
    return library.footprints[0].pads[0]


# --- the stack --------------------------------------------------------------------------------------


def test_mode_1_when_the_inner_layers_share_one_shape_and_size() -> None:
    """The scenario: 1.6 mm round on top and bottom, 1.2 mm round inside, mode 1."""
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            layer("In*.Cu", "circle", "1.2"),
            layer("B.Cu", "circle", "1.6"),
        ),
    )
    found = record_of(pad(stack=stack))
    assert found.mode == 1
    assert found.shapes == (1, 1, 1)
    assert found.sizes == ((units(mm("1.6")),) * 2, (units(mm("1.2")),) * 2, (units(mm("1.6")),) * 2)
    assert found.hole_shape == 0 and found.hole == units(mm("0.8"))


def test_a_kicad_inner_layer_is_the_wildcard() -> None:
    """The KiCad reader spells the wildcard ``Inner``, not ``In*.Cu``: both name the one mode 1 stack."""
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            layer("Inner", "circle", "1.2"),
            layer("B.Cu", "rect", "1.5"),
        ),
    )
    found = record_of(pad(stack=stack), copper_layers=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
    assert found.mode == 1
    assert found.shapes == (1, 1, 2)


def test_a_mode_1_pad_reads_back_with_every_layer(tmp_path: Path) -> None:
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            layer("In*.Cu", "circle", "1.2"),
            layer("B.Cu", "circle", "1.6"),
        ),
    )
    pad_ = pad(stack=stack)
    written = read_back(definition(pad_), tmp_path)
    assert written.padstack is not None
    entries = {entry.layer: (entry.shape, entry.size) for entry in written.padstack.layers}
    assert set(entries) == {"F.Cu", "In*.Cu", "B.Cu"}
    assert entries["F.Cu"][0] == "circle" and sizes_close(entries["F.Cu"][1], Size(mm("1.6"), mm("1.6")))
    assert entries["In*.Cu"][0] == "circle" and sizes_close(entries["In*.Cu"][1], Size(mm("1.2"), mm("1.2")))
    assert entries["B.Cu"][0] == "circle" and sizes_close(entries["B.Cu"][1], Size(mm("1.6"), mm("1.6")))


def test_mode_2_when_an_inner_layer_differs() -> None:
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            layer("In1.Cu", "circle", "1.2"),
            layer("In2.Cu", "rect", "1.2", "0.9"),
            layer("B.Cu", "circle", "1.6"),
        ),
    )
    found = record_of(pad(stack=stack))
    assert found.mode == 2
    assert found.shapes[1] == 1
    assert found.sizes[1] == (units(mm("1.2")), units(mm("1.2")))
    assert found.inner_shapes[:2] == (2, 1)
    assert found.inner_sizes[0] == (units(mm("1.2")), units(mm("0.9")))
    assert found.inner_sizes[1] == found.sizes[1], "an unnamed layer keeps the middle geometry"


def test_a_mode_2_pad_reads_back_as_mid_layer_1_to_30(tmp_path: Path) -> None:
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            layer("In1.Cu", "circle", "1.2"),
            layer("In2.Cu", "rect", "1.2", "0.9"),
            layer("B.Cu", "circle", "1.6"),
        ),
    )
    written = read_back(definition(pad(stack=stack)), tmp_path)
    assert written.padstack is not None
    names = [entry.layer for entry in written.padstack.layers]
    assert names == ["F.Cu"] + [f"In{n}.Cu" for n in range(1, 31)] + ["B.Cu"]
    assert written.padstack.layers[1].shape == "circle"
    assert sizes_close(written.padstack.layers[1].size, Size(mm("1.2"), mm("1.2")))
    assert written.padstack.layers[2].layer == "In2.Cu"
    assert written.padstack.layers[2].shape == "rect"
    assert sizes_close(written.padstack.layers[2].size, Size(mm("1.2"), mm("0.9")))


def test_full_stack_keeps_the_thirtieth_inner_layer(tmp_path: Path) -> None:
    stack = Padstack(
        id=PADSTACK_ID,
        layers=(
            layer("F.Cu", "circle", "1.6"),
            *(layer(f"In{n}.Cu", "circle", "1.2") for n in range(1, 30)),
            layer("In30.Cu", "rect", "1.4", "1.1"),
            layer("B.Cu", "circle", "1.6"),
        ),
    )
    pad_ = pad(stack=stack)
    found = record_of(pad_)
    assert found.mode == 2 and len(found.inner_sizes) == 29
    assert found.inner_shapes[-1] == 2
    assert found.inner_sizes[-1] == (units(mm("1.4")), units(mm("1.1")))
    written = read_back(definition(pad_), tmp_path)
    assert written.padstack is not None
    last = written.padstack.layers[-2]
    assert (last.layer, last.shape) == ("In30.Cu", "rect")
    assert sizes_close(last.size, Size(mm("1.4"), mm("1.1")))


def test_a_layer_the_stack_leaves_out_is_refused() -> None:
    stack = Padstack(id=PADSTACK_ID, layers=(layer("F.Cu", "circle", "1.6"), layer("B.Cu", "circle", "1.6")))
    check = pcblib.check_footprint(definition(pad(stack=stack)), {}, copper_layers=FOUR_LAYER)
    assert check.refusal is not None and "names no layer for In1.Cu" in check.refusal
    assert pcblib.check_footprint(definition(pad(stack=stack)), {}).refusal is None


def test_a_custom_layer_keeps_the_pad_a_loss() -> None:
    stack = Padstack(id=PADSTACK_ID, layers=(layer("F.Cu", "custom", "1.6"), layer("B.Cu", "circle", "1.6")))
    check = pcblib.check_footprint(definition(pad(stack=stack)), {})
    assert check.refusal is not None and "the shape custom" in check.refusal


# --- holes that are not round -----------------------------------------------------------------------


def test_a_slot_hole_is_written_and_read_back(tmp_path: Path) -> None:
    """The measured reason the census loses 108 pads: a slotted hole."""
    stack = Padstack(
        id=PADSTACK_ID, layers=(), hole_shape="slot", hole_length=mm("1.4"), hole_rotation=90_000_000
    )
    pad_ = pad(size="1.2", rotation=30_000_000, stack=stack)
    found = record_of(pad_)
    assert found.hole_shape == 2
    assert found.hole == units(mm("0.8"))
    written = read_back(definition(pad_), tmp_path)
    assert written.padstack is not None
    assert written.padstack.hole_shape == "slot"
    assert close(written.padstack.hole_length, mm("1.4"))
    assert written.padstack.hole_rotation == 90_000_000, "the reader adds the pad's own angle"
    assert written.padstack.layers == ()


def test_a_square_hole_is_written() -> None:
    stack = Padstack(id=PADSTACK_ID, layers=(), hole_shape="square")
    found = record_of(pad(size="1.2", stack=stack))
    assert found.hole_shape == 1
    assert found.hole == units(mm("0.8"))


def test_a_round_hole_keeps_the_record_it_had() -> None:
    """No sixth subrecord for a plain round pad: the bytes every committed sample has."""
    found = record_of(pad())
    assert found.mode == 0 and found.hole_shape is None and found.layers_size == 0
    assert found.shapes == (1, 1, 1)


# --- connector pads and pads without a number (change c0160) ----------------------------------------


def test_connector_pad_writes_no_masks(tmp_path: Path) -> None:
    """The scenario "Connector pad": a pad of kind ``connect`` is a surface pad on its copper layer with
    no paste and no mask opening, and it is not refused."""
    pad_ = pad(kind="connect", drill=None)
    found = record_of(pad_)
    assert found.mode == 0 and found.hole == 0 and found.plated == 0
    assert found.mask_modes == (0, 0) and found.expansions == (0, 0)
    assert pcblib.check_footprint(definition(pad_), {}).refusal is None
    written = read_back(definition(pad_), tmp_path)
    assert written.kind == "smd" and written.drill is None
    assert written.layers == ("F.Cu",)


def test_a_connect_pad_differs_only_in_the_solder_mask() -> None:
    """A normal surface pad keeps the solder mask from the rules; a connector pad takes neither mask."""
    assert record_of(pad(kind="smd", drill=None)).mask_modes == (0, 1)
    assert record_of(pad(kind="connect", drill=None)).mask_modes == (0, 0)


def test_unnamed_pad_is_left_out_of_a_library() -> None:
    """A library footprint cannot hold a pad without a number: it is dropped, not refused, and not kept."""
    check = pcblib.check_footprint(definition(pad(number="")), {})
    assert check.refusal is None
    assert check.pads == ()
    assert any("no number" in note for note in check.dropped)
