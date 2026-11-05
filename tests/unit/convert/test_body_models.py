# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated models of imported bodies (capability design-conversion, "Generated models of imported
bodies"; change c0423, tasks 2.3 and 3.1): the authored document of ``tests/_altium_models.py``
converted to KiCad. Where KiCad puts what is written is the oracle's
(``tests/kicad/convert/test_altium_model_pose.py``)."""

from __future__ import annotations

import tempfile
from functools import cache
from pathlib import Path

import _altium_models as am
import pytest

from fenolite.backends import step
from fenolite.backends.altium import models3d
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import Conversion, convert_project
from fenolite.convert.models import (
    CARRIED,
    GENERATED,
    NOT_CYLINDER,
    NOT_SPHERE,
    PRISM,
    UNKNOWN,
    body_solid,
)
from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody

MIL = am.MIL


@cache
def _conversion(unknown: bool = False) -> Conversion:
    with tempfile.TemporaryDirectory(prefix="fenolite-c0423-") as folder:
        return convert_project(am.write_folder(Path(folder), unknown=unknown), to="kicad", allow_lossy=True)


def _board_models(conversion: Conversion) -> dict[str, list[str]]:
    board = parse(conversion.files[conversion.read_back].decode())
    out: dict[str, list[str]] = {}
    for footprint in board.nodes("footprint"):
        refs = [p.atoms()[1].value for p in footprint.nodes("property") if p.atoms()[0].value == "Reference"]
        out[refs[0]] = [m.atoms()[0].value for m in footprint.nodes("model")]
    return out


def test_the_document_holds_every_body_shape() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = am.write_folder(Path(folder))
        forms = models3d.body_forms(path)
        models = models3d.body_models(path)
    assert [f.shape for f in forms] == [c.shape for c in am.CASES]
    assert [f.rotation for f in forms[:8]] == [tuple(t * 1_000_000 for t in c.turns) for c in am.CASES[:8]]
    assert len(models) == 8 and {m.data for m in models} == {am.marker_step()}


def test_every_body_type() -> None:
    """Scenario "Every body type": no ``body`` and no ``model`` loss; every footprint names its files."""
    conversion = _conversion()
    body, model = conversion.report.row("body"), conversion.report.row("model")
    assert body is not None and model is not None
    assert (body.source, body.changed, body.lost) == (15, 15, 0)
    assert (model.source, model.changed, model.lost) == (8, 8, 0)
    reasons = {r.reason: len(r.ids) for r in body.reasons}
    assert reasons == {CARRIED: 8, GENERATED: 6, PRISM.format(why=NOT_CYLINDER): 1}
    assert not [i for i in conversion.issues if i.code == "convert.lossy"]
    for ref, paths in _board_models(conversion).items():
        assert len(paths) == 1, ref
        assert paths[0].removeprefix("${KIPRJMOD}/") in conversion.files, ref


def test_the_files_the_board_names_are_written() -> None:
    """Decision 4: every instance shares one library footprint, the first's; the files of the others,
    which only the board names, are written too."""
    conversion = _conversion()
    named = {p for paths in _board_models(conversion).values() for p in paths}
    written = {key for key in conversion.files if ".3dshapes/" in key}
    assert {p.removeprefix("${KIPRJMOD}/") for p in named} == written
    assert len(written) == 8  # the shared marker and one generated file per non-model component


def test_a_generated_file_is_the_solid_of_its_body() -> None:
    """E1's file is the STEP prism of its outline with Y up, from standoff to overall height."""
    conversion = _conversion()
    (path,) = _board_models(conversion)["E1"]
    data = conversion.files[path.removeprefix("${KIPRJMOD}/")]
    item = am.case("E1")
    ring = tuple((x * MIL, -y * MIL) for x, y in item.outline)
    name = path.rsplit("/", 1)[1].rsplit("_", 1)[0]
    assert data == step.write_solids(
        name, [step.Prism(ring, item.standoff * MIL, item.overall * MIL, "body")]
    )


def test_a_lost_body_is_reported() -> None:
    """Scenario "A loss is reported": a body whose projection is not proved is a ``body`` loss with a
    ``convert.lossy`` warning."""
    conversion = _conversion(unknown=True)
    row = conversion.report.row("body")
    assert row is not None and row.lost == 1
    assert [r.reason for r in row.reasons if r.outcome == "lost"] == [UNKNOWN]
    lossy = [i for i in conversion.issues if i.code == "convert.lossy"]
    assert [i.where for i in lossy] == ["body"] and lossy[0].severity == "warning"


def _square(side: int, low: int, high: int) -> ComponentBody:
    half = side // 2
    outline = (Point(-half, -half), Point(half, -half), Point(half, half), Point(-half, half))
    return ComponentBody(
        id="b", kind="extruded", height=high, standoff=low, outline=outline, z_min=low, z_max=high
    )


@pytest.mark.parametrize(
    ("shape", "body", "rotation", "made", "reason"),
    [
        ("cylinder", _square(40 * MIL, 0, 60 * MIL), (0, 0, 30_000_000), step.Prism, GENERATED),
        (
            "cylinder",
            _square(40 * MIL, 0, 60 * MIL),
            (90_000_000, 0, 0),
            step.Prism,
            PRISM.format(why=NOT_CYLINDER),
        ),
        ("sphere", _square(80 * MIL, -40 * MIL, 40 * MIL), (0, 0, 0), step.Sphere, GENERATED),
        ("sphere", _square(80 * MIL, 0, 40 * MIL), (0, 0, 0), step.Prism, PRISM.format(why=NOT_SPHERE)),
        ("extruded", _square(80 * MIL, 0, 40 * MIL), (0, 0, 0), step.Prism, GENERATED),
    ],
)
def test_body_solid(
    shape: str, body: ComponentBody, rotation: tuple[int, int, int], made: type, reason: str
) -> None:
    found = body_solid(body, "top", shape, rotation)  # type: ignore[arg-type]
    assert isinstance(found.solid, made) and found.reason == reason
    if shape == "cylinder" and reason == GENERATED:
        assert isinstance(found.solid, step.Prism) and len(found.solid.ring) == step.sides(20 * MIL)


def test_a_bottom_body_keeps_the_pad_frame_y() -> None:
    """On the bottom the outline is written with the pad frame's Y, so that KiCad's flip puts it back."""
    body = ComponentBody(
        id="b", kind="extruded", height=5, outline=(Point(0, 0), Point(3, 0), Point(0, 2)), z_min=0, z_max=5
    )
    top, bottom = (
        body_solid(body, "top", "extruded", (0, 0, 0)),
        body_solid(body, "bottom", "extruded", (0, 0, 0)),
    )
    assert isinstance(top.solid, step.Prism) and isinstance(bottom.solid, step.Prism)
    assert top.solid.ring == ((0, 0), (3, 0), (0, -2)) and bottom.solid.ring == ((0, 0), (3, 0), (0, 2))
