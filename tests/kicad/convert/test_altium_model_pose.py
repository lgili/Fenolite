# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad shows the source's pose of every converted body and model (change c0423, task 4.1; capability
design-conversion, "Generated models of imported bodies", scenario "KiCad shows the source pose").

The authored document of ``tests/_altium_models.py`` holds:

- embedded models turned about X, Y and Z, on the top and on the bottom;
- extruded bodies, cylinders and spheres;
- a cylinder whose outline is no square.

It is converted to KiCad, and each component is exported alone with ``kicad-cli pcb export stl
--component-filter``. The truth is computed from the document's own bytes and the facts of
``pcb-bodies.md``, independently of Fenolite's reader and of ``convert.models``:

- **A model point.** It lies at `F · (Rz · Ry · Rx · p + (0, 0, DZ)) + (MODEL.2D − component place, face)`,
  where `F` is a half turn about X on the bottom (``H-A-BODY-MODEL-PLACE``).
- **A generated body.** It is the record's outline between its two heights, a cylinder in its square, or
  a sphere in its square.

The faces are those of the two unturned models, ``M1`` and ``M5``.
"""

from __future__ import annotations

import math
import tempfile
from functools import cache
from pathlib import Path

import _altium_models as am
import pytest
from _probes import runner
from _stl import FLIP, IDENTITY, Vector, apply, plus, times, turn, vertices, without_corners, worst

from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.convert import convert_project

pytestmark = pytest.mark.needs_kicad

UNIT_MM = 0.00000254
"""One unit of the document (1/10 000 mil) in mm."""
MIL_MM = 0.0254
TOLERANCE = 0.002
MODELS = [c.ref for c in am.CASES if c.shape == "model"]
GENERATED = [c.ref for c in am.CASES if c.shape != "model"]


@cache
def _converted() -> tuple[dict[str, bytes], bytes, str]:
    with tempfile.TemporaryDirectory(prefix="fenolite-c0423-") as folder:
        path = am.write_folder(Path(folder))
        document = path.read_bytes()
        conversion = convert_project(path, to="kicad", kicad_version=runner().major(), allow_lossy=True)
    return dict(conversion.files), document, conversion.read_back


def _footprints(board: str) -> dict[str, tuple[float, float, Node]]:
    out: dict[str, tuple[float, float, Node]] = {}
    for footprint in parse(board).nodes("footprint"):
        refs = [p.atoms()[1].value for p in footprint.nodes("property") if p.atoms()[0].value == "Reference"]
        at = footprint.nodes("at")[0].atoms()
        out[refs[0]] = (float(at[0].value), float(at[1].value), footprint)
    return out


def _corners(board: str) -> list[tuple[float, float]]:
    """Every point an ``Edge.Cuts`` drawing names, in the export's Y-up frame."""
    points: list[tuple[float, float]] = []
    for item in parse(board).children:
        if not isinstance(item, Node) or not item.name.startswith("gr_"):
            continue
        layers = [n.atoms()[0].value for n in item.nodes("layer")]
        if layers != ["Edge.Cuts"]:
            continue
        for head in ("start", "end", "mid", "center"):
            for node in item.nodes(head):
                x, y = (float(a.value) for a in node.atoms()[:2])
                points.append((x, -y))
        for pts in item.nodes("pts"):
            for xy in pts.nodes("xy"):
                x, y = (float(a.value) for a in xy.atoms()[:2])
                points.append((x, -y))
    return points


@cache
def _export(ref: str) -> list[Vector]:
    """The vertices of ``ref``'s models, relative to its footprint's place (mm, Y up)."""
    files, _document, board_name = _converted()
    board = files[board_name].decode()
    x, y, _node = _footprints(board)[ref]
    cli = runner()
    args = ["pcb", "export", "stl", "--force", "--user-origin", "0x0mm", "--component-filter", ref]
    if cli.major() >= 10:  # 9.0.9 refuses --no-board-body ("No valid PCB assembly")
        args.append("--no-board-body")
    args += ["-o", "out.stl", board_name]
    run = cli.run(args, files=files)
    assert run.returncode == 0, run.stderr
    assert "out.stl" in run.outputs, run.stdout
    found = without_corners(vertices(run.outputs["out.stl"]), _corners(board))
    return [(px - x, py + y, pz) for px, py, pz in found]


def _case_record(ref: str) -> tuple[dict[str, str], list[tuple[float, float]], tuple[int, int]]:
    _files, document, _name = _converted()
    index = [c.ref for c in am.CASES].index(ref)
    keys, outline = am.outlines(document)[index]
    return keys, outline, am.places(document)[ref]


def _mil(text: str) -> float:
    assert text.endswith("mil"), text
    return float(text[:-3]) * MIL_MM


def _model_points(ref: str, face: float) -> list[Vector]:
    """The source's pose of the marker model of ``ref``, from its record's keys."""
    keys, _outline, (cx, cy) = _case_record(ref)
    rx, ry, rz = (float(keys[f"MODEL.3D.ROT{axis}"]) for axis in "XYZ")
    rotation = times(turn(2, rz), times(turn(1, ry), turn(0, rx)))
    side = am.case(ref).side
    flip = FLIP if side == "bottom" else IDENTITY
    shift = (
        (_mil(keys["MODEL.2D.X"]) - cx * UNIT_MM),
        (_mil(keys["MODEL.2D.Y"]) - cy * UNIT_MM),
        face,
    )
    dz = (0.0, 0.0, _mil(keys["MODEL.3D.DZ"]))
    lo, hi = am.MARKER_Z
    marker = [(x * MIL_MM, y * MIL_MM, z * MIL_MM) for z in (lo, hi) for x, y in am.MARKER]
    return [plus(apply(flip, plus(apply(rotation, p), dz)), shift) for p in marker]


@cache
def _faces() -> dict[str, float]:
    """The faces from the unturned top and bottom models: the marker starts 20 mil from its face."""
    low = am.MARKER_Z[0] * MIL_MM
    return {"top": min(p[2] for p in _export("M1")) - low, "bottom": max(p[2] for p in _export("M5")) + low}


def test_the_faces_are_beyond_the_board() -> None:
    """The two faces lie a board thickness apart, plus at most 0.2 mm of copper and mask, about the board
    body, which the export writes from 0 up."""
    files, _document, board_name = _converted()
    general = parse(files[board_name].decode()).nodes("general")[0]
    thickness = float(general.nodes("thickness")[0].atoms()[0].value)
    faces = _faces()
    assert faces["bottom"] < 0.0 < faces["top"], faces
    assert thickness <= faces["top"] - faces["bottom"] <= thickness + 0.2, (faces, thickness)


@pytest.mark.parametrize("ref", MODELS)
def test_model_pose(ref: str) -> None:
    """Every vertex of the placed model where the source's pose puts it."""
    face = _faces()[am.case(ref).side]
    assert worst(_model_points(ref, face), _export(ref)) < TOLERANCE


def _heights(ref: str) -> tuple[float, float, float]:
    keys, _outline, _place = _case_record(ref)
    side = am.case(ref).side
    sign = -1.0 if side == "bottom" else 1.0
    return _faces()[side], sign * _mil(keys["STANDOFFHEIGHT"]), sign * _mil(keys["OVERALLHEIGHT"])


def _relative_outline(ref: str) -> list[tuple[float, float]]:
    _keys, outline, (cx, cy) = _case_record(ref)
    return [((x - cx) * UNIT_MM, (y - cy) * UNIT_MM) for x, y in outline]


@pytest.mark.parametrize("ref", ["E1", "E2", "K1"])
def test_prism_pose(ref: str) -> None:
    """An extruded body, and the cylinder that does not fit its outline, as the record's prism."""
    face, low, high = _heights(ref)
    expected = [(x, y, face + z) for z in (low, high) for x, y in _relative_outline(ref)]
    assert worst(expected, _export(ref)) < TOLERANCE


def _box(ref: str) -> tuple[float, float, float]:
    """The centre and half the side of the record's square outline, turned with its component."""
    outline = _relative_outline(ref)
    assert len(outline) == 4
    cx = sum(x for x, _ in outline) / 4
    cy = sum(y for _, y in outline) / 4
    return cx, cy, math.dist(outline[0], outline[1]) / 2


@pytest.mark.parametrize("ref", ["C1", "C2"])
def test_cylinder_pose(ref: str) -> None:
    """Every vertex on the circle of the record's square, at one of its two heights."""
    face, low, high = _heights(ref)
    cx, cy, radius = _box(ref)
    found = _export(ref)
    assert len(found) >= 48
    for x, y, z in found:
        assert abs(math.hypot(x - cx, y - cy) - radius) < TOLERANCE
        assert min(abs(z - face - low), abs(z - face - high)) < TOLERANCE


@pytest.mark.parametrize("ref", ["S1", "S2"])
def test_sphere_pose(ref: str) -> None:
    """Every vertex on the sphere in the record's square, centred between its heights."""
    face, low, high = _heights(ref)
    cx, cy, radius = _box(ref)
    centre = (cx, cy, face + (low + high) / 2)
    found = _export(ref)
    assert len(found) > 100
    assert abs(abs(high - low) / 2 - radius) < TOLERANCE
    for point in found:
        assert abs(math.dist(point, centre) - radius) < TOLERANCE
    assert max(p[2] for p in found) - min(p[2] for p in found) == pytest.approx(2 * radius, abs=TOLERANCE)


def test_every_component_has_its_models() -> None:
    files, _document, board_name = _converted()
    footprints = _footprints(files[board_name].decode())
    for item in am.CASES:
        models = footprints[item.ref][2].nodes("model")
        assert len(models) == 1, item.ref
        path = models[0].atoms()[0].value.removeprefix("${KIPRJMOD}/")
        assert path in files, path
