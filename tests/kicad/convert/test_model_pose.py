# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's model pose, measured (``H-K-MODEL-POSE``, change c0423, design Decision 1): where
``kicad-cli pcb export stl`` puts the vertices of a footprint's STEP model for each side, footprint angle,
``offset`` and ``rotate``.

The model is an authored prism with six distinct vertices. The prediction is
``T(x, −y, face) · Rz(θ) · F · (Rz(−c) · Ry(−b) · Rx(−a) · p + o)``, with ``F`` a half turn about X on the
bottom. Every case must match it within 2 µm, and the case turned about all three axes must rule out the
five other orders of the turns.
"""

from __future__ import annotations

import itertools

import pytest
from _probes import runner
from _stl import FLIP, IDENTITY, Matrix, Vector, apply, plus, times, turn, vertices, without_corners, worst

from fenolite.backends.step import Prism, write_solids

pytestmark = pytest.mark.needs_kicad

MM = 1_000_000
TRIANGLE = ((0.0, 0.0), (3.0, 0.0), (0.0, 1.0))
HEIGHTS = (0.5, 2.5)
MODEL: list[Vector] = [(x, y, z) for z in HEIGHTS for x, y in TRIANGLE]
AT = (20.0, 15.0)
FACES = {"top": 1.595, "bottom": -0.085}
"""Where KiCad seats a model on this probe board of 1.6 mm (no stack-up): 0.085 mm beyond the 1.51 mm board
body that the export writes from 0 to 1.51 mm, on each side."""
CORNERS = ((0.0, 0.0), (40.0, 0.0), (40.0, -30.0), (0.0, -30.0))
TURNS = ((0, 0, 0), (30, 0, 0), (0, 40, 0), (0, 0, 50), (30, 40, 50), (90, 0, 90), (0, 90, 90))
CASES = [
    (side, theta, rotate)
    for side in ("top", "bottom")
    for theta in (0, 25)
    for rotate in TURNS
]  # fmt: skip
OFFSET = (1.0, 2.0, 3.0)
BOARD = """(kicad_pcb (version 20241229) (generator "fenolite-probe") (generator_version "9.0")
 (general (thickness 1.6) (legacy_teardrops no))
 (paper "A4")
 (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) (1 "F.Mask" user) (3 "B.Mask" user)
  (13 "F.Paste" user) (15 "B.Paste" user) (5 "F.SilkS" user) (7 "B.SilkS" user))
 (setup (pad_to_mask_clearance 0))
 (net 0 "")
 (footprint "P:X" (layer "{L}.Cu") (at 20 15 {theta})
  (property "Reference" "U1" (at 0 0 {theta}) (layer "{L}.SilkS")
   (effects (font (size 1 1) (thickness 0.15))))
  (attr smd)
  (pad "1" smd rect (at 0 0 {theta}) (size 1 1) (layers "{L}.Cu" "{L}.Paste" "{L}.Mask"))
  (model "${{KIPRJMOD}}/m.step" (offset (xyz 1 2 3)) (scale (xyz 1 1 1)) (rotate (xyz {a} {b} {c})))
 )
 (gr_rect (start 0 0) (end 40 30) (stroke (width 0.1) (type solid)) (fill no) (layer "Edge.Cuts"))
)
"""


def _model_step() -> bytes:
    ring = tuple((round(x * MM), round(y * MM)) for x, y in TRIANGLE)
    return write_solids("m", [Prism(ring, round(HEIGHTS[0] * MM), round(HEIGHTS[1] * MM), "body")])


def predict(side: str, theta: float, rotate: tuple[int, int, int], order: str = "zyx") -> list[Vector]:
    """The measured pose, or another ``order`` of the same turns (leftmost applied last)."""
    a, b, c = rotate
    angle = {"x": -a, "y": -b, "z": -c}
    matrix: Matrix = IDENTITY
    for axis in order:
        matrix = times(matrix, turn("xyz".index(axis), angle[axis]))
    flip = FLIP if side == "bottom" else IDENTITY
    place = times(turn(2, theta), flip)
    face = (AT[0], -AT[1], FACES[side])
    return [plus(apply(place, plus(apply(matrix, p), OFFSET)), face) for p in MODEL]


def _export(side: str, theta: int, rotate: tuple[int, int, int]) -> list[Vector]:
    cli = runner()
    a, b, c = rotate
    board = BOARD.format(L="F" if side == "top" else "B", theta=theta, a=a, b=b, c=c)
    args = ["pcb", "export", "stl", "--force", "--user-origin", "0x0mm", "-o", "out.stl", "probe.kicad_pcb"]
    if cli.major() >= 10:  # 9.0.9 refuses --no-board-body ("No valid PCB assembly")
        args.insert(3, "--no-board-body")
    run = cli.run(
        args, files={"probe.kicad_pcb": board.encode(), "probe.kicad_pro": b"{}\n", "m.step": _model_step()}
    )
    assert run.returncode == 0, run.stderr
    assert "out.stl" in run.outputs, run.stdout
    return without_corners(vertices(run.outputs["out.stl"]), CORNERS)


@pytest.mark.parametrize(("side", "theta", "rotate"), CASES)
def test_pose(side: str, theta: int, rotate: tuple[int, int, int]) -> None:
    """``H-K-MODEL-POSE``: every vertex where the measured transform puts it."""
    found = _export(side, theta, rotate)
    assert worst(predict(side, theta, rotate), found) < 0.002, found


@pytest.mark.parametrize("side", ["top", "bottom"])
def test_the_order_is_told_apart(side: str) -> None:
    """The case turned about all three axes rules out every other order of the turns."""
    found = _export(side, 25, (30, 40, 50))
    for order in ("".join(p) for p in itertools.permutations("xyz")):
        error = worst(predict(side, 25, (30, 40, 50), order), found)
        assert (error < 0.002) == (order == "zyx"), (order, error)
