# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Model placement of imported footprints (capability design-conversion, "Model placement of imported
footprints"; changes c0223 and c0423)."""

from __future__ import annotations

import dataclasses
import itertools
import math
from collections import Counter
from pathlib import Path

import pytest

from fenolite.backends.base import BodyModel
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.model.base import Provenance
from fenolite.model.board import ComponentBody, FootprintInstance
from fenolite.model.library import FootprintDef, ModelPlacement

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
DEG = 1_000_000
STEP = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
LOCATOR = "ComponentBodies6/Data#0"


def _model(definition: str) -> Node:
    found = parse(definition).nodes("model")
    assert len(found) == 1
    return found[0]


def test_writer_writes_a_placement() -> None:
    """The footprint writer writes one ``model`` child per placement, Y and the turn negated for KiCad."""
    placement = ModelPlacement(
        "${KIPRJMOD}/m.step", offset=(1_000_000, 2_000_000, 500_000), rotation=(0, 0, 90 * DEG)
    )
    text = write_footprint(FootprintDef(id="fpd-a", name="A", placements=(placement,)), target=10)
    assert dumps(_model(text), style="compact") == (
        '(model "${KIPRJMOD}/m.step" (offset (xyz 1 -2 0.5)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 -90)))'
    )


def test_writer_refuses_placements_beside_read_models() -> None:
    read = read_footprint(
        '(footprint "A" (version 20241229) (generator "pcbnew") (layer "F.Cu")\n  (model "a.step")\n)\n'
    )
    assert read.models == ("a.step",)
    with pytest.raises(LossyWriteError):
        write_footprint(dataclasses.replace(read, placements=(ModelPlacement("b.step"),)), target=10)


def _source(side: str = "top"):
    """The authored project ``blink`` whose LED footprint holds a body that names an embedded model, turned
    by 90° about Z beyond the part and raised by 0.5 mm, with the model on its origin."""
    from fenolite.convert.sources import read_source

    source = read_source(BLINK)
    board = source.design.board
    assert board is not None
    counts = Counter(fp.lib_ref for fp in board.footprints)
    index, chosen = next((i, fp) for i, fp in enumerate(board.footprints) if counts[fp.lib_ref] == 1)
    where = Provenance(backend="altium", file="blink.PcbDoc", file_sha256="", locator=LOCATOR)
    body = ComponentBody(id="bdy-led", provenance=where, kind="model", height=5_000_000, model="led.step")
    placed = dataclasses.replace(chosen, bodies=(body,), side=side)  # type: ignore[arg-type]
    footprints = (*board.footprints[:index], placed, *board.footprints[index + 1 :])
    design = dataclasses.replace(source.design, board=dataclasses.replace(board, footprints=footprints))
    model = BodyModel(
        locator=LOCATOR,
        name="led.step",
        format="step",
        data=STEP,
        position=Point(chosen.position.x, chosen.position.y),
        z=500_000,
        rotation=(0, 0, (chosen.rotation + 90 * DEG) % (360 * DEG)),
    )
    return dataclasses.replace(source, design=design), chosen, model


def _convert(monkeypatch: pytest.MonkeyPatch, side: str = "top"):
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.convert import convert_project

    source, chosen, model = _source(side)
    monkeypatch.setattr(AltiumBackend, "body_models", lambda self, path, **_: (model,))
    conversion = convert_project(source, to="kicad", kicad_version=10, allow_lossy=True)
    return conversion, chosen


def test_a_rotated_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A rotated body"."""
    conversion, chosen = _convert(monkeypatch)
    pattern = chosen.lib_ref.rsplit(":", 1)[-1]
    text = conversion.files[f"blink.pretty/{pattern}.kicad_mod"].decode()
    model = _model(text)
    path = model.atoms()[0].value
    assert path.startswith("${KIPRJMOD}/blink.3dshapes/") and path.endswith(".step")
    assert dumps(model, style="compact").endswith(
        "(offset (xyz 0 0 0.5)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 -90)))"
    )
    assert conversion.files[path.removeprefix("${KIPRJMOD}/")] == STEP
    row = conversion.report.row("model")
    assert row is not None and row.changed == 1 and row.lost == 0


def test_a_model_on_the_bottom(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A model on the bottom turned about X and Y" (change c0423): the model is written and
    placed, and the report counts it changed."""
    conversion, chosen = _convert(monkeypatch, side="bottom")
    pattern = chosen.lib_ref.rsplit(":", 1)[-1]
    model = _model(conversion.files[f"blink.pretty/{pattern}.kicad_mod"].decode())
    assert conversion.files[model.atoms()[0].value.removeprefix("${KIPRJMOD}/")] == STEP
    row = conversion.report.row("model")
    assert row is not None and row.changed == 1 and row.lost == 0


def test_placement_in_the_frame_of_a_turned_footprint() -> None:
    """A model beside a footprint turned by 90°: the offset is in the footprint's own frame."""
    from fenolite.convert.models import placement
    from fenolite.model.board import FootprintInstance

    fp = FootprintInstance(
        id="fp", component_id="c", lib_ref="L:A", position=Point(10_000_000, 0), rotation=90 * DEG
    )
    model = BodyModel(LOCATOR, "m", "step", STEP, Point(10_000_000, -1_000_000), 0, (0, 0, 90 * DEG))
    placed = placement(model, fp, "m.step")
    assert placed.rotation == (0, 0, 0) and abs(placed.offset[0]) + abs(placed.offset[1]) == 1_000_000


# -- the pose, against an independent forward model (H-K-MODEL-POSE; H-A-BODY-MODEL-PLACE) --------------

Matrix = tuple[tuple[float, ...], ...]


def _turn(axis: int, udeg: float) -> Matrix:
    angle = math.radians(udeg / DEG)
    c, s = math.cos(angle), math.sin(angle)
    if axis == 0:
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _times(a: Matrix, b: Matrix) -> Matrix:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _apply(m: Matrix, p: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(sum(m[i][k] * p[k] for k in range(3)) for i in range(3))


FLIP: Matrix = ((1, 0, 0), (0, -1, 0), (0, 0, -1))
ONE: Matrix = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
PROBE = ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 2.0))


def _source_pose(model: BodyModel, side: str) -> list[tuple[float, ...]]:
    """``pcb-bodies.md``: ``T(position, face) · F · (Rz · Ry · Rx · p + (0, 0, z))``, in mm, Y up."""
    rx, ry, rz = model.rotation
    turns = _times(_turn(2, rz), _times(_turn(1, ry), _turn(0, rx)))
    flip = FLIP if side == "bottom" else ONE
    at = (model.position.x / 1e6, -model.position.y / 1e6, 0.0)
    out = []
    for p in PROBE:
        q = _apply(turns, p)
        q = _apply(flip, (q[0], q[1], q[2] + model.z / 1e6))
        out.append(tuple(a + b for a, b in zip(q, at, strict=True)))
    return out


def _kicad_pose(placed: ModelPlacement, fp: FootprintInstance) -> list[tuple[float, ...]]:
    """``H-K-MODEL-POSE`` of the written node: the writer negates Y and the angles (``placement_node``), and
    KiCad puts ``p`` at ``T(x, −y, face) · Rz(θ) · F · (Rz(−c) · Ry(−b) · Rx(−a) · p + o)``."""
    a, b, c = (-angle for angle in placed.rotation)
    ox, oy, oz = placed.offset[0] / 1e6, -placed.offset[1] / 1e6, placed.offset[2] / 1e6
    turns = _times(_turn(2, -c), _times(_turn(1, -b), _turn(0, -a)))
    flip = FLIP if fp.side == "bottom" else ONE
    place = _times(_turn(2, fp.rotation), flip)
    at = (fp.position.x / 1e6, -fp.position.y / 1e6, 0.0)
    out = []
    for p in PROBE:
        q = _apply(turns, p)
        q = _apply(place, (q[0] + ox, q[1] + oy, q[2] + oz))
        out.append(tuple(x + y for x, y in zip(q, at, strict=True)))
    return out


ANGLES = (0, 30 * DEG, 90 * DEG, -90 * DEG, 180 * DEG, 45_123_456, 270 * DEG)


@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("theta", [0, 25 * DEG, 90 * DEG, 180 * DEG, 333_333_333])
def test_the_solved_pose_is_the_source_pose(side: str, theta: int) -> None:
    """Every turn about X, Y and Z, on either side and any footprint angle: KiCad's pose of the placement
    equals the source's within 1 nm (the µdeg rounding moves a point 3 mm away by less than 0.1 nm)."""
    from fenolite.convert.models import placement
    from fenolite.model.board import FootprintInstance

    fp = FootprintInstance(
        id="fp", component_id="c", lib_ref="L:A", position=Point(12_345_678, -7_654_321), rotation=theta,
        side=side,  # type: ignore[arg-type]
    )  # fmt: skip
    for rx, ry, rz in itertools.product(ANGLES, repeat=3):
        model = BodyModel(LOCATOR, "m", "step", STEP, Point(13_000_000, -6_500_000), 254_000, (rx, ry, rz))
        placed = placement(model, fp, "m.step")
        assert all(-180 * DEG < angle <= 180 * DEG for angle in placed.rotation)
        for want, got in zip(_source_pose(model, side), _kicad_pose(placed, fp), strict=True):
            assert math.dist(want, got) < 1e-6, (rx, ry, rz, placed)


def test_a_turn_about_z_alone_keeps_c0223s_integers() -> None:
    """No turn about X or Y: the angle is the exact difference of the two turns, as change c0223 wrote it."""
    from fenolite.convert.models import placement
    from fenolite.model.board import FootprintInstance

    fp = FootprintInstance(id="fp", component_id="c", lib_ref="L:A", position=Point(0, 0), rotation=30 * DEG)
    model = BodyModel(LOCATOR, "m", "step", STEP, Point(0, 0), 0, (0, 0, 75_000_001))
    assert placement(model, fp, "m.step").rotation == (0, 0, 45_000_001)
    bottom = dataclasses.replace(fp, side="bottom")
    assert placement(model, bottom, "m.step").rotation == (0, 0, 105_000_001)
