# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's drawing layers on Altium's mechanical layers, and texts on copper (capability altium-pcb-writer,
"Mechanical layers of KiCad drawings" and "Copper texts and unmapped layers"; change c0160).

The KiCad sample ``blink`` gets free drawings and texts in the model, is written with
``lower.write_design`` and its PCB document is read back with the Altium backend, which names the
mechanical layers ``Mech.<n>``.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic, Text
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
BLINK = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10" / "blink.kicad_pcb"


def _blink() -> Design:
    return fpitems.with_footprint_items(KicadBackend().read(BLINK).design).design


def _line(layer: str) -> Graphic:
    return Graphic(
        id=derived_id("gfx", "test", f"line:{layer}"),
        kind="line",
        layer=layer,
        points=(Point(110_000_000, 110_000_000), Point(120_000_000, 110_000_000)),
        width=150_000,
    )


def _text(layer: str) -> Text:
    return Text(
        id=derived_id("txt", "test", f"text:{layer}"),
        text="REV A",
        position=Point(115_000_000, 120_000_000),
        layer=layer,
        size=Size(1_000_000, 1_000_000),
        thickness=150_000,
    )


def _with(design: Design, graphics: tuple[Graphic, ...] = (), texts: tuple[Text, ...] = ()) -> Design:
    board = design.board
    assert board is not None
    board = dataclasses.replace(board, graphics=(*board.graphics, *graphics), texts=(*board.texts, *texts))
    return dataclasses.replace(design, board=board)


def _read(written: lower.ProjectWrite, folder: Path) -> Design:
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    return AltiumBackend().read(folder / "blink.PcbDoc").design


def test_drawing_on_dwgs_user(tmp_path: Path) -> None:
    """Scenario "Drawing on Dwgs.User": the line is on Mechanical 9, the text on the top copper layer, and
    the report loses neither."""
    design = _with(_blink(), (_line("Dwgs.User"),), (_text("F.Cu"),))
    written = lower.write_design(design, allow_lossy=True)
    assert "graphic" not in written.inputs.lost and "text" not in written.inputs.lost
    back = _read(written, tmp_path)
    assert back.board is not None
    lines = [g for g in back.board.graphics if g.layer == "Mech.9"]
    assert len(lines) == 1 and lines[0].kind == "line"
    texts = [t for t in back.board.texts if t.text == "REV A"]
    assert len(texts) == 1 and texts[0].layer == "F.Cu"


@pytest.mark.parametrize(
    ("layer", "number"),
    [
        ("User.1", 1),
        ("User.8", 8),
        ("Dwgs.User", 9),
        ("Cmts.User", 10),
        ("Eco1.User", 11),
        ("Eco2.User", 12),
        ("F.Fab", 13),
        ("B.CrtYd", 16),
    ],
)
def test_layer_map(layer: str, number: int, tmp_path: Path) -> None:
    """Each layer of ``lower.KICAD_MECHANICAL`` is written on its mechanical layer, and the document names
    that layer after the KiCad layer."""
    assert lower.KICAD_MECHANICAL[layer] == 56 + number
    written = lower.write_design(_with(_blink(), (_line(layer),)), allow_lossy=True)
    back = _read(written, tmp_path)
    assert back.board is not None
    assert any(g.layer == f"Mech.{number}" and g.kind == "line" for g in back.board.graphics)
    board6 = open_compound(written.files["blink.PcbDoc"]).read("Board6/Data").decode("latin-1")
    assert f"NAME={layer}|" in board6


def test_text_on_bottom_copper(tmp_path: Path) -> None:
    """A text on ``B.Cu`` is a text record on the bottom copper layer."""
    written = lower.write_design(_with(_blink(), texts=(_text("B.Cu"),)), allow_lossy=True)
    assert "text" not in written.inputs.lost
    back = _read(written, tmp_path)
    assert back.board is not None
    assert [t.layer for t in back.board.texts if t.text == "REV A"] == ["B.Cu"]


def test_layer_outside_the_map(tmp_path: Path) -> None:
    """Scenario "Layer outside the map": a line on ``User.9`` is not written and is counted lost under
    ``graphic`` with the reason that names the layer."""
    design = _with(_blink(), (_line("User.9"),))
    written = lower.write_design(design, allow_lossy=True)
    (reason,) = written.inputs.lost["graphic"]
    assert "User.9" in reason and written.inputs.lost["graphic"][reason] == (_line("User.9").id,)


def test_a_build_keeps_its_layers() -> None:
    """The map is the write of a model of another source: a document that was read from Altium keeps its
    own ``Mech.<n>`` layers, and Mechanical 13 to 16 keep their names when nothing is converted."""
    assert set(lower.KICAD_MECHANICAL.values()) == set(range(57, 73))
    assert {lower.KICAD_MECHANICAL[name] for name in ("F.Fab", "B.Fab", "F.CrtYd", "B.CrtYd")} == {
        69,
        70,
        71,
        72,
    }
