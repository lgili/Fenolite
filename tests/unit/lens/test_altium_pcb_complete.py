# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The complete board of an Altium build (capability altium-build, "Complete board in an Altium build";
capability altium-pcb-writer, "Unpoured polygons are a contract" and "Written items are accounted"; change
c0085; hypothesis ``H-A-PCBX-READBACK``).

The six-layer sample (``tests/_altium_board6.py``) must give the five files under
``tests/data/altium/board6/`` byte for byte; ``FENOLITE_GOLDEN_WRITE=1`` rewrites them, and the SHA-256
values of Part X of ``docs/evidence/altium-pcb.md`` are then updated (``-k protocol`` checks them). With
``FENOLITE_ALTIUM_BOARD6=<folder>`` the files are also written there for the maintainer to open in Altium
Designer; the folder must lie outside the repository.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import subprocess
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium_board6 import (
    FILES,
    IMPORT_LAYERS,
    LAYERS,
    NAME,
    at,
    board6_build,
    board6_model,
    imported_point,
    near,
    project_files,
    read_document,
)
from _altium_copper import plane_model, routed_build, routed_model

from fenolite.core.coords import Point
from fenolite.lens import altium_copper
from fenolite.lens.build import BuildOutput
from fenolite.model.board import ComponentBody, FootprintInstance, Graphic, Hole, Keepout, Layer, Via
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[2].parent
BOARD6_DIR = ROOT / "tests" / "data" / "altium" / "board6"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-pcb.md"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
HANDOVER = os.environ.get("FENOLITE_ALTIUM_BOARD6")
SAMPLES = ("sample", "blink", "routed", "hier", "no_connect", "kicad_example", "read")
"""The folders under ``tests/data/altium/`` that earlier changes committed."""


@cache
def board6() -> BuildOutput:
    with tempfile.TemporaryDirectory() as folder:
        output = board6_build(Path(folder))
    assert not [found for found in output.issues if found.severity == "error"], output.issues
    return output


def _build(name: str) -> tuple[Design, BuildOutput, str]:
    with tempfile.TemporaryDirectory() as folder:
        if name == "board6":
            return board6_model(), board6(), f"{NAME}.PcbDoc"
        if name == "plane":
            model = plane_model()
            return model, routed_build(Path(folder), model, planes={"In1.Cu": "GND"}), "routed.PcbDoc"
        model = routed_model()
        return model, routed_build(Path(folder), model), "routed.PcbDoc"


def _one(found: list[object], what: str) -> None:
    assert len(found) == 1, f"{what}: {len(found)} matches"


@pytest.mark.parametrize("name", ["board6", "routed", "plane"])
def test_readback(name: str) -> None:
    """``H-A-PCBX-READBACK``: the written document, read with the product reader and imported, holds the
    items of the model it was written from, inside the written scope and within 2 nm."""
    model, output, file_name = _build(name)
    board = model.board
    assert board is not None and board.outline is not None
    outline = board.outline.points
    _document, design = read_document(output.files[file_name], file_name)
    read = design.board
    assert read is not None
    nets = {net.id: net.name for net in model.circuit.nets}
    read_nets = {net.id: net.name for net in design.circuit.nets}

    def moved(point: Point) -> Point:
        return imported_point(point, outline)

    for track in board.tracks:
        found = [
            t
            for t in read.tracks
            if t.layer == track.layer
            and read_nets.get(t.net_id or "") == nets.get(track.net_id or "")
            and near(t.start, moved(track.start))
            and near(t.end, moved(track.end))
            and abs(t.width - track.width) <= 2
        ]
        _one(found, track.id)  # type: ignore[arg-type]
    for via in board.vias:
        found_vias = [
            v
            for v in read.vias
            if set(v.layers) == set(via.layers)
            and v.via_type == via.via_type
            and near(v.position, moved(via.position))
            and abs(v.diameter - via.diameter) <= 2
            and abs(v.drill - via.drill) <= 2
            and read_nets.get(v.net_id or "") == nets.get(via.net_id or "")
        ]
        _one(found_vias, via.id)  # type: ignore[arg-type]
    planes = set(output.summary["copper"]["planes"])  # type: ignore[index]
    wanted_zones = [(z, layer) for z in board.zones for layer in z.layers if layer not in planes]
    assert len(read.zones) == len(wanted_zones)
    for zone, layer in wanted_zones:
        found_zones = [
            z
            for z in read.zones
            if z.layers == (layer,)
            and read_nets.get(z.net_id or "") == nets.get(zone.net_id or "")
            and len(z.outline) == len(zone.outline)
            and all(near(a, moved(b)) for a, b in zip(z.outline, zone.outline, strict=True))
            and z.fills == ()
        ]
        _one(found_zones, zone.id)  # type: ignore[arg-type]
    assert len(read.texts) == len(board.texts)
    for text in board.texts:
        found_texts = [
            t
            for t in read.texts
            if t.text == text.text
            and t.layer == IMPORT_LAYERS.get(text.layer, text.layer)
            and near(t.position, moved(text.position))
            and abs(t.size.h - text.size.h) <= 2
            and abs(t.thickness - text.thickness) <= 2
            and t.rotation == text.rotation
        ]
        _one(found_texts, text.id)  # type: ignore[arg-type]
    holes = [fp for fp in read.footprints if fp.attributes == ("board_only",)]
    assert len(holes) == len(board.holes)
    for hole in board.holes:
        found_holes = [
            fp
            for fp in holes
            if near(fp.position, moved(hole.position))
            and fp.pads[0].drill is not None
            and abs(fp.pads[0].drill - hole.drill) <= 2
            and (fp.pads[0].kind == "thru_hole") == hole.plated
        ]
        _one(found_holes, hole.id)  # type: ignore[arg-type]
    drawn = [g for g in read.graphics if g.layer not in ("Edge.Cuts", "Altium.KeepOut")]
    for graphic in board.graphics:
        layer = IMPORT_LAYERS.get(graphic.layer, graphic.layer)
        on_layer = [g for g in drawn if g.layer == layer]
        if graphic.kind == "rect":
            assert sum(g.kind == "line" for g in on_layer) >= 4, graphic.id
            continue
        if graphic.kind == "circle":
            same = [g for g in on_layer if g.kind == "circle" and near(g.points[0], moved(graphic.points[0]))]
        else:
            same = [
                g
                for g in on_layer
                if g.kind == graphic.kind
                and len(g.points) == len(graphic.points)
                and any(
                    all(near(a, moved(b)) for a, b in zip(order, graphic.points, strict=True))
                    for order in (g.points, g.points[::-1])
                )
            ]
        _one(same, graphic.id)  # type: ignore[arg-type]
    keepouts = [g for g in read.graphics if g.layer == "Altium.KeepOut"]
    assert len(keepouts) == len(board.keepouts)
    for keepout in board.keepouts:
        assert any(
            all(near(a, moved(b)) for a, b in zip(g.points, keepout.outline, strict=True)) for g in keepouts
        ), keepout.id


# --- the six-layer sample ------------------------------------------------------------------------------


def test_board6_golden_files() -> None:
    """Scenario "Six-layer sample": nothing is left out, and the committed files equal a fresh build."""
    output = board6()
    assert output.summary["pcb"] == {  # type: ignore[comparison-overlap]
        "written": {
            "footprint": 3, "pad": 36, "track": 7, "arc": 1, "via": 3, "zone": 2, "text": 4, "graphic": 5,
            "keep-out": 1, "hole": 1, "body": 0, "rule": 0,
        },
        "not_lowered": {},
    }  # fmt: skip
    assert output.summary["copper"]["layers"] == 6  # type: ignore[index]
    assert not [i for i in output.issues if i.code == "altium.not-lowered"]
    files = project_files(output)
    if HANDOVER:
        target = Path(HANDOVER).resolve()
        assert ROOT.resolve() not in (target, *target.parents), "the folder is inside the repository"
        target.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (target / name).write_bytes(files[name])
    if WRITE:
        BOARD6_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (BOARD6_DIR / name).write_bytes(files[name])
        pytest.skip("board6 golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.name for p in BOARD6_DIR.iterdir()) == sorted(FILES)
    for name in FILES:
        assert (BOARD6_DIR / name).read_bytes() == files[name], f"{name} differs from a fresh build"


def test_board6_two_polygons() -> None:
    """Scenario "Two polygons": two unpoured polygons, no region of poured copper, one info with 2."""
    output = board6()
    document, _design = read_document(output.files[f"{NAME}.PcbDoc"], f"{NAME}.PcbDoc")
    assert [(p.layer, p.polygon_type, p.record.get("NET") is not None) for p in document.polygons] == [
        ("TOP", "Polygon", True),
        ("BOTTOM", "Polygon", True),
    ]
    assert all(region.prefix.polygon is None for region in document.regions)  # type: ignore[union-attr]
    assert not any(t.prefix.polygon is not None for t in (*document.tracks, *document.arcs))  # type: ignore[union-attr]
    (info,) = [i for i in output.issues if i.code == "altium.zones-unpoured"]
    assert info.severity == "info" and info.message.startswith("2 polygon(s) are written without poured")
    assert "Repour All" in info.message


def test_board6_island_removal_is_written() -> None:
    model = board6_model()
    assert model.board is not None
    first, second = model.board.zones
    kept = dataclasses.replace(first, settings=dataclasses.replace(first.settings, island_removal="never"))
    board = dataclasses.replace(model.board, zones=(kept, second))
    with tempfile.TemporaryDirectory() as folder:
        output = board6_build(Path(folder), dataclasses.replace(model, board=board))
    document, _design = read_document(output.files[f"{NAME}.PcbDoc"], f"{NAME}.PcbDoc")
    assert [p.record.get("REMOVEDEAD") for p in document.polygons] == ["FALSE", "TRUE"]


def test_board6_protocol_names_the_bytes() -> None:
    """Part X of the protocol names the SHA-256 of every committed file of the sample and its steps."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert text.count("## Part X") == 1
    part = text[text.index("## Part X") :]
    digests = dict(
        re.findall(r"^\| `tests/data/altium/board6/([^`]+)` \| `([0-9a-f]{64})` \|", part, flags=re.MULTILINE)
    )
    assert sorted(digests) == sorted(FILES)
    for name, digest in digests.items():
        assert hashlib.sha256((BOARD6_DIR / name).read_bytes()).hexdigest() == digest, name
    for step in range(1, 12):
        assert f"**X{step}**" in part, step
    for row in ("STACK", "VIASPAN", "TEXT", "KEEPOUT", "HOLE", "REPOUR"):
        assert f"H-A-PCBX-{row}" in part, row


# --- accounting ----------------------------------------------------------------------------------------


def _counts(model: Design, source: Design | None = None) -> dict[str, int]:
    board = model.board
    assert board is not None
    copper = (source or model).board
    assert copper is not None
    return {
        "track": len(copper.tracks),
        "arc": len(copper.arcs),
        "via": len(copper.vias),
        "zone": len(copper.zones),
        "text": len(board.texts),
        "graphic": len(board.graphics),
        "keep-out": len(board.keepouts),
        "hole": len(board.holes),
        "body": sum(len(fp.bodies) for fp in board.footprints),
    }


def _uid(prefix: str, number: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{number:012d}"


def _unwritable() -> Design:
    """The sample with one item of every kind that has no record."""
    model = board6_model()
    board = model.board
    assert board is not None
    body = ComponentBody(id=_uid("bdy", 1), kind="extruded", height=2_500_000)
    component = model.circuit.components[0]
    footprint = FootprintInstance(
        id=_uid("fp", 1),
        component_id=component.id,
        lib_ref=component.lib_footprint_ref,
        position=at(10, 10),
        bodies=(body,),
    )
    outline = board.keepouts[0].outline
    extra = dataclasses.replace(
        board,
        footprints=(footprint,),
        vias=(
            *board.vias,
            Via(
                id=_uid("via", 2),
                position=at(40, 25),
                diameter=300_000,
                drill=100_000,
                layers=("F.Cu", "In1.Cu"),
                via_type="micro",
            ),
        ),
        graphics=(
            *board.graphics,
            Graphic(id=_uid("gfx", 3), kind="line", layer="F.Cu", points=(at(1, 1), at(2, 2)), width=100_000),
            Graphic(id=_uid("gfx", 4), kind="line", layer="Edge.Cuts", points=(at(0, 0), at(50, 0))),
        ),
        keepouts=(
            *board.keepouts,
            Keepout(id=_uid("kpo", 5), outline=outline, layers=("F.Cu",), no_footprints=True),
            Keepout(id=_uid("kpo", 6), outline=outline, layers=LAYERS, no_tracks=True, no_footprints=True),
        ),
        texts=(*board.texts, dataclasses.replace(board.texts[0], id=_uid("txt", 7), layer="F.Cu")),
        holes=(*board.holes, Hole(id=_uid("hol", 8), position=at(45, 25), drill=0)),
    )
    return dataclasses.replace(model, board=extra)


@pytest.mark.parametrize("name", ["board6", "routed", "plane", "unwritable"])
def test_accounted(name: str) -> None:
    """Scenario "Nothing is lost silently": per kind, written plus not lowered is the number of items in
    the model, and each item that is not lowered has an issue naming it."""
    if name == "unwritable":
        model = _unwritable()
        with tempfile.TemporaryDirectory() as folder:
            output = board6_build(Path(folder), model)
    else:
        model, output, _file = _build(name)
    assert not [found for found in output.issues if found.severity == "error"], output.issues
    pcb = output.summary["pcb"]
    assert isinstance(pcb, dict) and tuple(pcb["written"]) == altium_copper.KINDS
    for kind, total in _counts(model).items():
        assert pcb["written"][kind] + pcb["not_lowered"].get(kind, 0) == total, kind
    wheres = [i.where for i in output.issues if i.code in ("altium.not-lowered", "altium.via-unsupported")]
    words = {"keep-out": "keepout"}
    for kind, count in pcb["not_lowered"].items():
        named = [w for w in wheres if w.startswith(f"{words.get(kind, kind)}/")]
        assert len(set(named)) >= count, (kind, named)
    if name == "unwritable":
        assert pcb["not_lowered"] == {"via": 1, "text": 1, "graphic": 1, "keep-out": 1, "hole": 1, "body": 1}
        assert pcb["written"]["keep-out"] == 2 and pcb["written"]["graphic"] == 6  # the outline's line counts
        lost = [i for i in output.issues if i.where == f"keepout/{_uid('kpo', 6)}"]
        assert len(lost) == 1 and "no_footprints" in lost[0].message and lost[0].severity == "info"
        (body,) = [i for i in output.issues if i.where.startswith("body/")]
        assert "2.5 mm" in body.message
    else:
        assert pcb["not_lowered"] == {}


def test_accounted_refuses_an_item_in_neither_count() -> None:
    """An item that is neither written nor reported is an internal error, never a silent loss."""
    output = board6()
    model = board6_model()
    assert output.design.board is not None
    plan = altium_copper.lower_copper(output.design, copper=6, planes={"In2.Cu": "GND"}, document="x.PcbDoc")
    from fenolite.backends.altium.pcbdoc import PcbDocSpec

    spec = altium_copper.with_copper(PcbDocSpec(outline=output.design.board.outline.points), plan)  # type: ignore[union-attr]
    assert altium_copper.account(output.design, spec, plan)["written"]["text"] == 4
    lost = dataclasses.replace(plan, counts={**plan.counts, "text": (3, 0)})
    with pytest.raises(RuntimeError, match="4 text item\\(s\\) in the model, 3 written and 0 reported"):
        altium_copper.account(output.design, spec, lost)
    assert model.board is not None


def test_odd_count_refused(tmp_path: Path) -> None:
    """Scenario "Odd count refused": ``altium.not-lowered`` with ``where`` ``stackup`` and the default
    stack; no partial stack is written."""
    model = routed_model(())
    assert model.board is not None
    five = tuple(
        Layer(id=f"lay_00000000-0000-4000-8000-00000000002{n}", name=name, kind="copper", ordinal=n)
        for n, name in enumerate(("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "B.Cu"))
    )
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, layers=five))
    output = routed_build(tmp_path, model, copper=5)
    (found,) = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "stackup"]
    assert "5 copper layers is not written" in found.message and "F.Cu and B.Cu alone" in found.message
    document, _design = read_document(output.files["routed.PcbDoc"], "routed.PcbDoc")
    assert document.board.copper_chain == (1, 32)
    assert output.summary["copper"]["layers"] == 2  # type: ignore[index]


def test_no_document_keeps_the_infos_per_kind(tmp_path: Path) -> None:
    """Without a PCB document the board's items stay in the model, one info per kind, as before."""
    model = board6_model()
    assert model.board is not None
    bare = dataclasses.replace(model, board=dataclasses.replace(model.board, outline=None))
    output = board6_build(tmp_path, bare)
    wheres = sorted(i.where for i in output.issues if i.code == "altium.not-lowered")
    assert {"graphics", "holes", "keepouts", "texts"} <= set(wheres)
    assert output.summary["pcb"] is None and f"{NAME}.PcbDoc" not in output.files


# --- samples of earlier changes ------------------------------------------------------------------------


def test_altium_samples_of_earlier_changes_keep_their_bytes() -> None:
    """Scenario "Old samples unchanged": the committed samples of earlier changes are untouched, and the
    routed sample still builds to its committed bytes."""
    paths = [f"tests/data/altium/{name}/" for name in SAMPLES]
    proc = subprocess.run(
        ["git", "diff", "--exit-code", "--quiet", "6cdf0aea", "--", *paths],
        cwd=ROOT, capture_output=True, check=False,
    )  # fmt: skip
    if proc.returncode in (0, 1):
        assert proc.returncode == 0, "a sample of an earlier change differs from the base of change c0085"
    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder))
    for name, data in project_files(output).items():
        assert (ROOT / "tests" / "data" / "altium" / "routed" / name).read_bytes() == data, name
