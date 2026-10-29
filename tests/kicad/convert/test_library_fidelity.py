# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's reading of what change c0223 writes: the frame of a model placement (``H-K-MODEL-PLACE``), the
openings of converted Altium pads (``H-K-PAD-MARGIN``) and a library made from a board
(``H-K-LIB-FROM-BOARD``)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import _a2kcases
import pytest
from _probes import runner

pytestmark = pytest.mark.needs_kicad

TRIANGLE = b"""#VRML V2.0 utf8
Shape {
  appearance Appearance { material Material { diffuseColor 1 0 0 } }
  geometry IndexedFaceSet {
    coord Coordinate { point [ 0 0 0, 1 0 0, 0 1 0 ] }
    coordIndex [ 0, 1, 2, -1 ]
  }
}
"""
PROBE = """(kicad_pcb (version 20241229) (generator "fenolite-probe") (generator_version "9.0")
 (general (thickness 1.6) (legacy_teardrops no))
 (paper "A4")
 (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) (1 "F.Mask" user) (3 "B.Mask" user)
  (13 "F.Paste" user) (15 "B.Paste" user) (5 "F.SilkS" user))
 (setup (pad_to_mask_clearance 0))
 (net 0 "")
 (footprint "P:X" (layer "F.Cu") (at 10 20 0)
  (property "Reference" "U1" (at 0 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.1)
   (solder_paste_margin -0.05))
  (model "${KIPRJMOD}/tri.wrl" (offset (xyz 1 2 3)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 90)))
 )
 (gr_rect (start 0 0) (end 30 30) (stroke (width 0.1) (type solid)) (fill no) (layer "Edge.Cuts"))
)
"""
INCH_TENTHS = 2.54
"""The VRML export writes its coordinates in tenths of an inch under one scale of 2.54."""


@pytest.mark.kicad_min_major(10)  # kicad-cli 9.0.9 placed no model in this export (CI, 2026-10-28)
def test_frame() -> None:
    """``H-K-MODEL-PLACE``: a footprint at (10, 20) of a 30 × 30 board, offset (1, 2, 3) and rotate
    (0, 0, 90), puts the model at (−4, −3) around the board centre in VRML's Y-up frame, 3 mm above the top
    face (the face lies 0.8 mm above the centre), turned by −90° about Z. A shape needs an appearance to be
    exported."""
    cli = runner()
    run = cli.run(
        ["pcb", "export", "vrml", "--units", "mm", "-o", "out.wrl", "probe.kicad_pcb"],
        files={"probe.kicad_pcb": PROBE.encode(), "tri.wrl": TRIANGLE},
    )
    assert run.returncode == 0, run.stderr
    text = run.outputs["out.wrl"].decode()
    turns = re.findall(r"rotation\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", text)
    moves = re.findall(r"translation\s+(\S+)\s+(\S+)\s+(\S+)", text)
    placed = [(t, m) for t, m in zip(turns, moves, strict=False) if any(float(v) for v in m)]
    assert len(placed) == 1, placed
    (ax, ay, az, angle), move = placed[0]
    assert (float(ax), float(ay), float(az)) == (0.0, 0.0, -1.0) and abs(float(angle) - 1.5707963) < 1e-6
    x, y, z = (float(value) * INCH_TENTHS for value in move)
    assert abs(x + 4) < 1e-3 and abs(y + 3) < 1e-3 and abs(z - 3.8) < 1e-3


def test_openings_load() -> None:
    """``H-K-PAD-MARGIN``: the converted ``blink`` project, whose pads carry their openings, loads and
    runs DRC, and its derived library exports."""
    cli = runner()
    with tempfile.TemporaryDirectory(prefix="fenolite-c0223-") as temp:
        folder = Path(temp)
        conversion = _a2kcases.write(_a2kcases.SAMPLE, folder, cli.major())
        board = folder / conversion.read_back
        files = {name: folder / name for name in conversion.files if name != conversion.read_back}
        assert cli.load_board_svg(board, files=files).ok
        report = cli.drc(board, files=files).report
        assert report is not None
        pretty = folder / "blink.pretty"
        run = cli.run(
            ["fp", "export", "svg", "-o", "out", "blink.pretty"],
            files={"blink.pretty": pretty},
            folders=("out",),
        )
        assert run.returncode == 0, run.stderr
        assert len([name for name in run.outputs if name.endswith(".svg")]) == len(list(pretty.iterdir()))


def test_library_from_a_board() -> None:
    """``H-K-LIB-FROM-BOARD``: every footprint that ``fenolite library`` makes from the authored two-layer
    board (one of them on the bottom side, turned by 30°) loads in ``kicad-cli fp export svg``."""
    from fenolite.library import derive_library

    cli = runner()
    board = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    derived = derive_library(board.read_text(encoding="utf-8"), library="lib", target=cli.major())
    files: dict[str, Path | bytes] = {
        f"lib.pretty/{name}": text.encode() for name, text in derived.files().items()
    }
    run = cli.run(["fp", "export", "svg", "-o", "out", "lib.pretty"], files=files, folders=("out",))
    assert run.returncode == 0, run.stderr
    assert len([name for name in run.outputs if name.endswith(".svg")]) == len(derived.footprints) == 2
