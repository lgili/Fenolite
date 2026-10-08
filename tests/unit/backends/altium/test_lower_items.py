# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The graphics, the fields and the texts of a footprint instance in a write of the model (capability
altium-pcb-writer, "Footprint items of a written component"; ``H-A-PCBX-FPGFX``, ``H-A-PCBX-FPTEXT``,
``H-A-PCBX-MECH``; change c0126). Fenolite reads what Fenolite wrote: every level here is ``INFERRED``."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _altium_records as rec
import pytest

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.base import ModelScope
from fenolite.checks.diff import diff_designs
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.model.board import Board, FootprintInstance, Graphic, Text
from fenolite.model.design import Design, DesignHeader

ROOT = Path(__file__).resolve().parents[4]
SAMPLES = ROOT / "tests" / "data" / "altium"
DOCUMENTS = ("blink/blink.PcbDoc", "routed/routed.PcbDoc", "board6/board6.PcbDoc")
GRAPHICS = ModelScope({"footprint_graphic": ("kind", "layer", "points", "width", "filled")}, 2)
"""The graphics of the footprints, lengths within 2 nm: a length is written in units of 2.54 nm."""
PADS = ModelScope({"pad": ("number", "shape", "size", "position", "corner_ratio")}, 2)
MM = 1_000_000


def _read(path: Path) -> Design:
    return AltiumBackend().read(path).design


def _reading_of(written: lower.ProjectWrite, folder: Path) -> Design:
    folder.mkdir(parents=True, exist_ok=True)
    (name,) = [name for name in written.files if name.endswith(".PcbDoc")]
    (folder / name).write_bytes(written.files[name])
    return _read(folder / name)


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def _footprint(design: Design, ref: str) -> FootprintInstance:
    ident = next(component.id for component in design.circuit.components if component.ref == ref)
    return next(footprint for footprint in _board(design).footprints if footprint.component_id == ident)


def _with_footprint(design: Design, new: FootprintInstance) -> Design:
    board = _board(design)
    footprints = tuple(new if footprint.id == new.id else footprint for footprint in board.footprints)
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=footprints))


@pytest.mark.parametrize("document", DOCUMENTS)
def test_own_document_keeps_its_silkscreen(document: str, tmp_path: Path) -> None:
    """Scenario "Silkscreen survives a rewrite": each footprint of the reading of the rewrite holds the
    graphics of the first reading within 2 nm, 27 per document, on overlay and mechanical layers, and the
    corner ratios of its pads; no ``footprint-graphic`` is counted as not written."""
    first = _read(SAMPLES / document)
    written = AltiumBackend().write(first)
    second = _reading_of(written, tmp_path)
    assert sum(len(fp.graphics) for fp in _board(first).footprints) == 27
    assert written.inputs.written["footprint-graphic"] == 27
    assert not {"footprint-graphic", "footprint-copper", "footprint-text"} & set(written.inputs.counts())
    assert diff_designs(first, second, scope=GRAPHICS).changes == ()
    assert diff_designs(first, second, scope=PADS).changes == ()
    layers = {graphic.layer for fp in _board(second).footprints for graphic in fp.graphics}
    assert layers & {"F.SilkS", "B.SilkS"} and any(layer.startswith("Mech.") for layer in layers)


def test_bottom_footprint_keeps_its_layers_and_points(tmp_path: Path) -> None:
    """Scenario "A bottom footprint": the graphics of ``D1`` of the blink sample, on the bottom side."""
    first = _read(SAMPLES / "blink" / "blink.PcbDoc")
    second = _reading_of(AltiumBackend().write(first), tmp_path)
    mine, theirs = _footprint(first, "D1"), _footprint(second, "D1")
    assert mine.side == "bottom" and mine.graphics
    assert sorted(g.layer for g in mine.graphics) == sorted(g.layer for g in theirs.graphics)
    assert any(layer == "B.SilkS" for layer in (g.layer for g in theirs.graphics))
    for a in mine.graphics:
        assert any(
            a.kind == b.kind
            and a.layer == b.layer
            and all(
                abs(p.x - q.x) <= 2 and abs(p.y - q.y) <= 2 for p, q in zip(a.points, b.points, strict=False)
            )
            for b in theirs.graphics
        ), a.id


def test_copper_inside_a_footprint_needs_allow_lossy(tmp_path: Path) -> None:
    """Scenario "Copper inside a footprint"."""
    first = _read(SAMPLES / "blink" / "blink.PcbDoc")
    r1 = _footprint(first, "R1")
    line = Graphic(
        id="gfx_copper", kind="line", layer="F.Cu", points=(Point(0, 0), Point(MM, 0)), width=200_000
    )
    design = _with_footprint(first, dataclasses.replace(r1, graphics=(*r1.graphics, line)))
    with pytest.raises(lower.LossyWriteError) as refused:
        AltiumBackend().write(design)
    assert [(found.code, found.severity, found.where) for found in refused.value.issues] == [
        ("altium.not-lowered", "warning", "footprint-copper")
    ]
    written = AltiumBackend().write(design, allow_lossy=True)
    assert written.inputs.counts() == {"footprint-copper": 1}
    assert written.inputs.not_lowered["footprint-copper"] == ("gfx_copper",)
    second = _reading_of(written, tmp_path)
    assert len(_footprint(second, "R1").graphics) == len(r1.graphics)


def test_field_places_are_written(tmp_path: Path) -> None:
    """Scenario "Designator at its place" (``H-A-PCBX-FPTEXT``): the field ``Reference`` of ``R1`` moved by
    2 mm and its field ``Value`` made visible come back at those places, both visible."""
    first = _read(SAMPLES / "blink" / "blink.PcbDoc")
    r1 = _footprint(first, "R1")
    reference, value = r1.fields
    moved = dataclasses.replace(
        reference, position=Point(reference.position.x + 2 * MM, reference.position.y)
    )
    shown = dataclasses.replace(value, visible=True)
    design = _with_footprint(first, dataclasses.replace(r1, fields=(moved, shown)))
    second = _reading_of(AltiumBackend().write(design), tmp_path)
    again = {field.name: field for field in _footprint(second, "R1").fields}
    for wanted in (moved, shown):
        found = again[wanted.name]
        assert (
            abs(found.position.x - wanted.position.x) <= 2 and abs(found.position.y - wanted.position.y) <= 2
        )
        assert found.visible and found.layer == wanted.layer and found.rotation == wanted.rotation
        assert abs(found.size.h - wanted.size.h) <= 2
    # the other components keep the visibility they had
    other = {field.name: field.visible for field in _footprint(second, "D1").fields}
    assert other == {field.name: field.visible for field in _footprint(first, "D1").fields}


def test_items_are_counted_once_per_kind() -> None:
    """Scenario "Counted once per kind": the model of the six-layer sample."""
    first = _read(SAMPLES / "board6" / "board6.PcbDoc")
    issues: list[Issue] = []
    inputs = lower.from_design(first, issues=issues)
    assert inputs.counts() == {"graphic": 1}
    assert [(found.code, found.severity, found.where) for found in issues] == [
        ("altium.not-lowered", "info", "graphic")
    ]
    assert inputs.written["footprint-graphic"] == 27
    assert set(lower.MORE_KINDS) >= {"footprint-graphic", "footprint-copper", "footprint-text"}
    assert "footprint-copper" in lower.LOSS_KINDS and not set(lower.KINDS) & {"footprint-graphic"}


def _mechanical_document() -> Design:
    document = rec.document(
        components=[rec.component("R1", rotation=90.0)],
        pads=[rec.pad("1", at=(2000 * rec.MIL, 1500 * rec.MIL), component=0)],
        tracks=[
            rec.track(
                (2000 * rec.MIL, 1500 * rec.MIL), (2100 * rec.MIL, 1500 * rec.MIL), layer=57, component=0
            ),
            rec.track(
                (2000 * rec.MIL, 1550 * rec.MIL), (2100 * rec.MIL, 1550 * rec.MIL), layer=61, component=0
            ),
        ],
        texts=[
            rec.text("R1", (2000 * rec.MIL, 1600 * rec.MIL), designator=True, component=0),
            rec.text("note", (2000 * rec.MIL, 1450 * rec.MIL), layer=57, component=0),
        ],
        fills=[
            rec.fill(
                (2000 * rec.MIL, 1500 * rec.MIL), (2050 * rec.MIL, 1520 * rec.MIL), layer=35, component=0
            )
        ],
        regions=[
            rec.region(
                [
                    (2000 * rec.MIL, 1500 * rec.MIL),
                    (2050 * rec.MIL, 1500 * rec.MIL),
                    (2050 * rec.MIL, 1540 * rec.MIL),
                ],
                layer=57,
                component=0,
            )
        ],
    )
    return import_board(document, file="mech.PcbDoc", sha256=rec.SHA)


def test_mechanical_layers_of_a_rewrite(tmp_path: Path) -> None:
    """Scenario "Mechanical layers of a rewrite" (``H-A-PCBX-MECH``): a line on Mechanical 1 and one on
    Mechanical 5 come back on ``Mech.1`` and ``Mech.5``, and the board record of the written document
    enables both; a document that uses neither enables Mechanical 13 to 16 alone, as before."""
    first = _mechanical_document()
    written = AltiumBackend().write(first, allow_lossy=True)
    assert "footprint-graphic" not in written.inputs.counts()
    second = _reading_of(written, tmp_path)
    assert diff_designs(first, second, scope=GRAPHICS).changes == ()
    (footprint,) = [fp for fp in _board(second).footprints if fp.graphics]
    lines = sorted(graphic.layer for graphic in footprint.graphics if graphic.kind == "line")
    assert lines == ["Mech.1", "Mech.5"]
    (name,) = [name for name in written.files if name.endswith(".PcbDoc")]
    record = read_pcbdoc(written.files[name], file=name).board
    enabled = {layer.id - 56 for layer in record.layers if layer.mech_enabled and 57 <= layer.id <= 72}
    assert enabled == {1, 5, 13, 14, 15, 16}
    fields = dict(record.record.fields)
    (sets,) = [fields[key[:-4] + "LAYERS"] for key, value in fields.items() if value == "&Mechanical Layers"]
    assert sets.split(",") == [f"Mechanical{n}" for n in (1, 5, 13, 14, 15, 16)]
    plain = _read(SAMPLES / "blink" / "blink.PcbDoc")
    rewritten = AltiumBackend().write(plain)
    (name,) = [name for name in rewritten.files if name.endswith(".PcbDoc")]
    record = read_pcbdoc(rewritten.files[name], file=name).board
    assert {layer.id - 56 for layer in record.layers if layer.mech_enabled} == {13, 14, 15, 16}


def test_free_text_of_a_footprint_is_written(tmp_path: Path) -> None:
    """Group 5a: a text of a footprint that is no field is a text record of the component, with its string
    as stored; a text that the record cannot hold is counted under ``footprint-text``."""
    first = _mechanical_document()
    (footprint,) = [fp for fp in _board(first).footprints if fp.texts]
    assert [text.text for text in footprint.texts] == ["note"]
    written = AltiumBackend().write(first, allow_lossy=True)
    assert written.inputs.written["footprint-text"] == 1 and "footprint-text" not in written.inputs.counts()
    second = _reading_of(written, tmp_path)
    (again,) = [fp for fp in _board(second).footprints if fp.texts]
    (text,) = again.texts
    (wanted,) = footprint.texts
    assert (text.text, text.layer, text.rotation) == (wanted.text, wanted.layer, wanted.rotation)
    assert abs(text.position.x - wanted.position.x) <= 2 and abs(text.position.y - wanted.position.y) <= 2
    assert _board(second).texts == ()
    broken = Text(
        id="txt_bad", text="a\nb", layer="Mech.1", position=Point(0, 0), size=Size(MM, MM), thickness=MM // 10
    )
    unknown = dataclasses.replace(wanted, id="txt_layer", layer="User.9")
    design = _with_footprint(first, dataclasses.replace(footprint, texts=(wanted, broken, unknown)))
    inputs = lower.from_design(design, issues=[])
    assert inputs.not_lowered["footprint-text"] == ("txt_bad", "txt_layer")
    assert inputs.written["footprint-text"] == 1


def test_fill_and_region_of_a_footprint_are_regions(tmp_path: Path) -> None:
    """Group 5b: a fill on a paste layer and a region on a mechanical layer are region records with the
    component's index; they read back as filled graphics of the footprint."""
    first = _mechanical_document()
    written = AltiumBackend().write(first, allow_lossy=True)
    second = _reading_of(written, tmp_path)
    (footprint,) = [fp for fp in _board(second).footprints if fp.graphics]
    filled = sorted((graphic.kind, graphic.layer) for graphic in footprint.graphics if graphic.filled)
    assert filled == [("polygon", "Mech.1"), ("rect", "F.Paste")]
    assert [g for g in _board(second).graphics if g.layer != "Edge.Cuts"] == []
    assert written.inputs.written["footprint-graphic"] == 4
    assert isinstance(written.inputs.pcb, pcbdoc.PcbDocSpec)


def test_kicad_board_written_with_its_silkscreen(tmp_path: Path) -> None:
    """Task 5.5: ``lens.altium.write_model`` projects a design that was read from a KiCad board, so the
    written footprints hold their silkscreen, their rounded pads are written from the projected ratio, and
    ``AltiumBackend.write`` of the unprojected design still refuses the rounded pads."""
    from fenolite.backends.kicad.backend import KicadBackend
    from fenolite.lens.altium import write_model

    path = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10" / "blink.kicad_pcb"
    first = KicadBackend().read(path).design
    assert all(not fp.graphics for fp in _board(first).footprints)
    with pytest.raises(lower.LossyWriteError):
        AltiumBackend().write(first)
    written = write_model(first)
    assert written.inputs.written["footprint-graphic"] > 0 and "pad" not in written.inputs.counts()
    second = _reading_of(written, tmp_path)
    layers = {graphic.layer for fp in _board(second).footprints for graphic in fp.graphics}
    assert {"F.SilkS", "B.SilkS"} <= layers
    rounded = [pad for fp in _board(second).footprints for pad in fp.pads if pad.shape == "roundrect"]
    assert rounded and all(pad.corner_ratio == 250_000 for pad in rounded)
    # a rectangle is written as its four tracks, so the reading holds at least as many graphics
    read_back = sum(len(fp.graphics) for fp in _board(second).footprints)
    assert read_back >= written.inputs.written["footprint-graphic"]


def test_in_model_frame_names_fenolite_mechanical_layers() -> None:
    """Capability altium-verification, "Footprint graphics in the Altium round trips": for a model that was
    not read from Altium, the reading's footprint graphics on Mechanical 13 to 16 are named ``F.Fab``,
    ``B.Fab``, ``F.CrtYd`` and ``B.CrtYd``, the inverse of ``pcbrecords.LAYER_MAP``; a model that was read
    from Altium keeps ``Mech.<n>``."""
    assert dict(lower.FENOLITE_MECHANICAL) == {
        "Mech.13": "F.Fab",
        "Mech.14": "B.Fab",
        "Mech.15": "F.CrtYd",
        "Mech.16": "B.CrtYd",
    }
    line = Graphic(id="gfx_a", kind="line", layer="Mech.15", points=(Point(0, 0), Point(1, 0)), width=1)
    other = dataclasses.replace(line, id="gfx_b", layer="Mech.2")
    footprint = FootprintInstance(
        id="fp_r", component_id="cmp_r", lib_ref="L:F", position=Point(0, 0), graphics=(line, other)
    )
    header = DesignHeader(id="dsn_m", name="m", schema_version="0", fenolite_version="0")
    reading = Design(header, board=Board(id="brd_r", footprints=(footprint,)))
    named = AltiumBackend().in_model_frame(Design(header, board=Board(id="brd_m")), reading)
    assert [g.layer for g in _board(named).footprints[0].graphics] == ["F.CrtYd", "Mech.2"]
    read = Design(header, board=Board(id="brd_m", native_ids={"altium": "x.PcbDoc"}))
    kept = AltiumBackend().in_model_frame(read, reading)
    assert [g.layer for g in _board(kept).footprints[0].graphics] == ["Mech.15", "Mech.2"]


def test_rta3_takes_out_the_footprint_items_that_are_not_written(tmp_path: Path) -> None:
    """Capability altium-verification, "Round-trip level RT-A3": ``rta3.without_unwritten`` takes out of the
    first model the footprint graphics that the write counts under ``footprint-copper`` and
    ``footprint-graphic`` (here a track of the component on the top copper layer and a track of zero width
    on Mechanical 1), so the first model and the reading of the rewrite are equal in the written scope
    (design of c0126, "Found on 2026-10-08", 16)."""
    from fenolite.backends.altium.rta3 import without_unwritten

    first = _mechanical_document()
    owner = next(fp for fp in _board(first).footprints if fp.graphics)
    copper = dataclasses.replace(owner.graphics[0], id="gfx_copper", layer="F.Cu")
    thin = dataclasses.replace(owner.graphics[0], id="gfx_thin", width=0)
    design = _with_footprint(first, dataclasses.replace(owner, graphics=(*owner.graphics, copper, thin)))
    written = AltiumBackend().write(design, allow_lossy=True, rewrite=True)
    kept = written.inputs.not_lowered
    assert kept["footprint-copper"] == ("gfx_copper",) and kept["footprint-graphic"] == ("gfx_thin",)
    second = _reading_of(written, tmp_path)
    assert diff_designs(design, second, scope=GRAPHICS).changes != ()
    stripped = without_unwritten(design, kept, from_board=True)
    assert diff_designs(stripped, second, scope=GRAPHICS).changes == ()
