# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Models of a KiCad board in an Altium target (capability design-conversion, "Models of a KiCad board in an
Altium target"; change c0449).

The board is the authored ``tests/data/kicad/convert/roundrect_roundtrip.kicad_pcb`` with ``R1`` turned by
90 degrees and ``J1`` moved to the bottom, each naming a box that ``backends.step`` writes in the test."""

from __future__ import annotations

import itertools
import struct
import zlib
from pathlib import Path

import pytest

from fenolite.api.board import read_board
from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends import stepbox
from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.base import BodyModel
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.pcb import model_ref_node, read_model_ref
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.step import Prism, write_solids
from fenolite.convert import models
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance, ModelRef

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "roundrect_roundtrip.kicad_pcb"
MM = 1_000_000
DEG = 1_000_000
TOLERANCE = 3
BOX = write_solids("box", [Prism(((0, 0), (2 * MM, 0), (2 * MM, MM), (0, MM)), 0, 3 * MM)])
PATH = "${KIPRJMOD}/m.3dshapes/box.step"
TOP_MODEL = f'(model "{PATH}" (offset (xyz 0.3 0.2 0.5)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 30)))'
BOTTOM_MODEL = f'(model "{PATH}" (offset (xyz -0.4 0.1 0.5)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 -45)))'
SPLIT = '\t(footprint "Fenolite_Test:Square_2"'
ANGLES = (0, 90 * DEG, 30 * DEG, -135 * DEG)
LOCATOR = "ComponentBodies6/Data#0"


def _board_text(r1_models: str, j1_models: str) -> str:
    """The fixture with ``R1`` turned by 90 degrees and ``J1`` on the bottom, each with ``…_models``."""
    text = FIXTURE.read_text(encoding="utf-8")
    head, rest = text.split(SPLIT, 1)
    j1, tail = rest.split("\t(segment", 1)
    head = head.replace("(at 15 15)", "(at 15 15 90)", 1)
    r1_end = head.rstrip().rfind(")")
    head = head[:r1_end] + r1_models + "\n\t" + head[r1_end:]
    j1 = (
        j1.replace('(layer "F.Cu")', '(layer "B.Cu")')
        .replace('"F.Cu" "F.Paste" "F.Mask"', '"B.Cu" "B.Paste" "B.Mask"')
        .replace('"F.SilkS"', '"B.SilkS"')
        .replace('"F.Fab"', '"B.Fab"')
    )
    j1_end = j1.rstrip().rfind(")")
    j1 = j1[:j1_end] + j1_models + "\n\t" + j1[j1_end:]
    return head + SPLIT + j1 + "\t(segment" + tail


def _project(folder: Path, r1_models: str, j1_models: str) -> Path:
    shapes = folder / "m.3dshapes"
    shapes.mkdir(parents=True)
    (shapes / "box.step").write_bytes(BOX)
    board = folder / "models.kicad_pcb"
    board.write_text(_board_text(r1_models, j1_models), encoding="utf-8")
    return board


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _row(result: ConversionResult) -> tuple[int, int, int, int, dict[str, int]]:
    (row,) = [r for r in result.conversion.report.rows if r.kind == models.KIND]
    return row.source, row.written, row.changed, row.lost, {r.reason: r.count for r in row.reasons}


def _footprints(path: Path) -> tuple[FootprintInstance, ...]:
    board = read_board(path).design.board
    assert board is not None
    return board.footprints


def _by_side(footprints: tuple[FootprintInstance, ...]) -> dict[str, FootprintInstance]:
    return {fp.side: fp for fp in footprints}


def _refs(footprint: FootprintInstance) -> list[ModelRef]:
    found = [read_model_ref(node) for node in fpitems.model_nodes(footprint)]
    assert all(ref is not None for ref in found)
    return [ref for ref in found if ref is not None]


# -- task 2.2: the reader of a model child --------------------------------------------------------------


def _model_node(text: str) -> Node:
    (found,) = parse(text).nodes("model") if not text.startswith("(model") else (parse(text),)
    return found


def test_placement_reader_inverts_the_writer() -> None:
    for ref in (
        ModelRef("a.step", (1_000_001, -2_000_000, 500_000), (10 * DEG, 0, -45_500_000), ("1", "1.5", "1")),
        ModelRef("${KIPRJMOD}/b.step", (0, 254, -1), (0, 0, 0), hidden=True),
    ):
        node = model_ref_node(ref)
        assert read_model_ref(parse(dumps(node))) == ref


def test_placement_reader_refuses_what_it_cannot_read() -> None:
    assert read_model_ref(_model_node('(model "a.step" (at (xyz 0 0 0)))')) is None
    assert read_model_ref(_model_node('(model "" (offset (xyz 0 0 0)))')) is None
    assert read_model_ref(_model_node('(model "a.step" (offset (xyz 0 x 0)))')) is None
    bare = read_model_ref(_model_node('(model "a.step" hide (offset (xyz 1 2 3)))'))
    assert bare is not None and bare.hidden and bare.offset == (MM, -2 * MM, 3 * MM)


# -- task 3.2: the pose, the inverse of c0423's placement --------------------------------------------


def _matrix(rotation: tuple[int, int, int]) -> list[list[float]]:
    return [list(row) for row in models.rotation_matrix(rotation)]


@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("theta", ANGLES)
def test_pose_inverts_placement(side: str, theta: int) -> None:
    fp = FootprintInstance(
        id="fp", component_id="c", lib_ref="L:A", position=Point(12_345_678, -7_654_321), rotation=theta,
        side=side,  # type: ignore[arg-type]
    )  # fmt: skip
    for rx, ry, rz in itertools.product(ANGLES, repeat=3):
        source = BodyModel(LOCATOR, "m", "step", b"", Point(13_000_000, -6_500_000), 254_000, (rx, ry, rz))
        placed = models.placement(source, fp, "m.step")
        ref = ModelRef("m.step", placed.offset, placed.rotation)
        pose = models.altium_pose(ref, fp, (0, 0, 0, MM, MM, MM))
        assert pose.position == source.position and pose.z == source.z
        want, got = _matrix(source.rotation), _matrix(pose.rotation)
        pairs = [(a, b) for u, v in zip(want, got, strict=True) for a, b in zip(u, v, strict=True)]
        assert max(abs(a - b) for a, b in pairs) < 1e-9
        if rx == ry == 0:  # a turn about Z alone comes back as the same integer
            assert (pose.rotation[2] - rz) % (360 * DEG) == 0 and pose.rotation[:2] == (0, 0)


def test_pose_outline_and_heights_of_the_box() -> None:
    """The box (0..2, 0..1, 0..3) mm, its origin at (1, 2) mm of the footprint (Y down) and raised 0.5 mm."""
    fp = FootprintInstance(id="fp", component_id="c", lib_ref="L:A", position=Point(0, 0))
    ref = ModelRef("m.step", (MM, 2 * MM, MM // 2))
    pose = models.altium_pose(ref, fp, (0, 0, 0, 2 * MM, MM, 3 * MM))
    assert pose.position == Point(MM, 2 * MM) and (pose.standoff, pose.height) == (MM // 2, 7 * MM // 2)
    xs, ys = {p.x for p in pose.outline}, {p.y for p in pose.outline}
    assert (min(xs), max(xs), min(ys), max(ys)) == (MM, 3 * MM, MM, 2 * MM)
    flipped = FootprintInstance(id="b", component_id="c", lib_ref="L:A", position=Point(0, 0), side="bottom")
    bottom = models.altium_pose(ref, flipped, (0, 0, 0, 2 * MM, MM, 3 * MM))
    assert bottom.position == Point(MM, -2 * MM)
    xs, ys = {p.x for p in bottom.outline}, {p.y for p in bottom.outline}
    # flipped about x: the model's +y runs along the board's +y
    assert (min(xs), max(xs), min(ys), max(ys)) == (MM, 3 * MM, -2 * MM, -MM)


# -- tasks 3.3 and 4.1: through Altium and back -----------------------------------------------------------


def test_roundtrip_of_two_models(tmp_path: Path) -> None:
    """Scenario "A model goes to Altium and comes back"."""
    board = _project(tmp_path / "kicad", TOP_MODEL, BOTTOM_MODEL)
    source = _footprints(board)
    wanted = models.footprint_models(source, board.parent)
    to_altium = convert(board, to="altium", allow_lossy=True, verify=False)
    assert _row(to_altium)[:4] == (2, 2, 0, 0)
    altium = _write(to_altium, tmp_path / "altium")
    (document_path,) = altium.glob("*.PcbDoc")
    document = read_pcbdoc(document_path.read_bytes(), file=document_path.name, strict=True)
    storage = document.storages["Models"]
    (record,) = model_records(storage["Data"])
    assert storage["Header"] == struct.pack("<I", 1) and zlib.decompress(storage["0"]) == BOX
    assert (
        record["ID"] == pcbrecords.model_id(BOX, "box.step") and record["NAME"] == "box.step"
    )  # a new model
    records = read_bodies(document.storages["ComponentBodies6"]["Data"])
    bodies = [b for b in records if b.properties.text("MODEL.MODELTYPE") == "1"]
    assert len(bodies) == 2 and {b.properties.text("MODELID") for b in bodies} == {record["ID"]}
    units = pcbrecords.to_units

    def size(xs: list[int], ys: list[int]) -> tuple[int, int]:
        return max(xs) - min(xs), max(ys) - min(ys)

    by_side = _by_side(source)
    for side in ("top", "bottom"):  # the written outline and heights are the placed box, in record units
        fp = by_side[side]
        (ref,) = _refs(fp)
        (model,) = wanted[fp.id]
        assert model.model is not None
        assert abs(model.standoff - ref.offset[2]) <= TOLERANCE  # the box stands on z = 0, raised 0.5 mm
        assert abs(model.height - (ref.offset[2] + 3 * MM)) <= TOLERANCE
        (body,) = [b for b in bodies if b.body_projection == (1 if side == "bottom" else 0)]
        assert (body.standoff_height, body.overall_height) == (units(model.standoff), units(model.height))
        want = size([units(p.x) for p in model.outline], [units(p.y) for p in model.outline])
        got = size([int(v.x) for v in body.outline], [int(v.y) for v in body.outline])
        assert all(abs(a - b) <= 2 for a, b in zip(want, got, strict=True)), (want, got)
    back = convert(document_path, to="kicad", allow_lossy=True, verify=False)
    kicad = _write(back, tmp_path / "back")
    (back_board,) = kicad.glob("*.kicad_pcb")
    returned = _by_side(_footprints(back_board))
    for side in ("top", "bottom"):
        (want,) = _refs(by_side[side])
        (got_ref,) = _refs(returned[side])
        file = models.model_path(got_ref.name, kicad)
        assert isinstance(file, Path) and file.read_bytes() == BOX, got_ref.name
        assert max(abs(a - b) for a, b in zip(want.offset, got_ref.offset, strict=True)) <= TOLERANCE
        turns = zip(want.rotation, got_ref.rotation, strict=True)
        assert [(a - b) % (360 * DEG) for a, b in turns] == [0, 0, 0]


def test_losses_of_models_that_cannot_be_embedded(tmp_path: Path) -> None:
    """Scenario "Models that cannot be embedded"."""
    board_models = "".join(
        (
            '(model "${KIPRJMOD}/m.3dshapes/missing.step" (offset (xyz 0 0 0)))',
            '(model "${KICAD9_3DMODEL_DIR}/x.step" (offset (xyz 0 0 0)))',
            '(model "m.3dshapes/x.wrl" (offset (xyz 0 0 0)))',
            f'(model "{PATH}" (offset (xyz 0 0 0)) (scale (xyz 1 2 1)))',
            '(model "kicad-embed://x.step" (offset (xyz 0 0 0)))',
        )
    )
    board = _project(tmp_path / "kicad", board_models, "")
    (board.parent / "m.3dshapes" / "x.wrl").write_text("#VRML V2.0 utf8\n", encoding="utf-8")
    result = convert(board, to="altium", allow_lossy=True, verify=False)
    source, written, changed, lost, reasons = _row(result)
    assert (source, written, changed, lost) == (5, 0, 0, 5)
    assert reasons == {
        models.MISSING: 1, models.VARIABLE: 1, models.NOT_STEP: 1, models.SCALED: 1, models.KICAD_EMBEDDED: 1
    }  # fmt: skip
    altium = _write(result, tmp_path / "altium")
    (document_path,) = altium.glob("*.PcbDoc")
    document = read_pcbdoc(document_path.read_bytes(), file=document_path.name, strict=True)
    assert document.storages["Models"] == {"Header": bytes(4), "Data": b""}


def test_losses_hidden_model_is_written_and_changed(tmp_path: Path) -> None:
    hidden = f'(model "{PATH}" (hide yes) (offset (xyz 0 0 0)))'
    board = _project(tmp_path / "kicad", hidden, "")
    result = convert(board, to="altium", allow_lossy=True, verify=False)
    assert _row(result) == (1, 0, 1, 0, {models.HIDDEN: 1})


def test_roundtrip_box_of_the_written_file_is_its_prism() -> None:
    assert stepbox.model_box(BOX) == (0, 0, 0, 2 * MM, MM, 3 * MM)


def test_losses_without_bodies_keep_the_document(tmp_path: Path) -> None:
    """``--altium-bodies off``: the model is lost with the reason of the bodies and ``Models`` stays empty."""
    board = _project(tmp_path / "kicad", TOP_MODEL, "")
    result = convert(board, to="altium", allow_lossy=True, verify=False, bodies="off")
    source, written, changed, lost, reasons = _row(result)
    assert (source, written, changed, lost) == (1, 0, 0, 1) and len(reasons) == 1
    (reason,) = reasons
    assert "--altium-bodies extruded" in reason
    altium = _write(result, tmp_path / "altium")
    (document_path,) = altium.glob("*.PcbDoc")
    document = read_pcbdoc(document_path.read_bytes(), file=document_path.name, strict=True)
    assert document.storages["Models"] == {"Header": bytes(4), "Data": b""}
