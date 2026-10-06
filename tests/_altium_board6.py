# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The six-layer sample of the complete Altium PCB document (change c0085, capability altium-build,
"Complete board in an Altium build"): the blink design named ``board6`` on six copper layers, with one item
of every kind the document writes.

Every value here is authored for this sample; none comes from another project. The board is 50 mm by
30 mm; positions are millimetres from the outline's top-left corner (Y down):

- the copper layers ``F.Cu``, ``In1.Cu`` … ``In4.Cu``, ``B.Cu`` with the stack-up ``STACKUP``; ``In2.Cu`` is
  an internal plane on ``GND`` (``PLANES``);
- three vias (``VIAS``): one through, one blind from ``F.Cu`` to ``In1.Cu`` and one buried from ``In1.Cu``
  to the plane ``In2.Cu``;
- tracks on ``F.Cu``, ``In1.Cu``, ``In3.Cu``, ``In4.Cu`` and ``B.Cu`` (``TRACKS``);
- four texts on four layers, one with accented characters and one rotated (``TEXTS``);
- graphics: a line, an arc, a circle, a drawn rectangle and a filled polygon (``GRAPHICS``);
- one keep-out for tracks and vias on every copper layer (``KEEPOUT``);
- one non-plated mounting hole of 3.2 mm (``HOLE``);
- two ``GND`` zones, on ``F.Cu`` and on ``B.Cu`` (``ZONES``), written as unpoured polygons.

The model has no slot among its board holes and the document writes no component body (the design of
c0085, "Found on 2026-10-06"), so the sample holds neither.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from pathlib import Path

from _altium import BLINK, blink_resolver, blink_tree
from _buildhelp import MARKS as BLINK_MARKS

from fenolite.backends.altium.adapter.board import import_board
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.board import (
    Arc,
    Graphic,
    Hole,
    Keepout,
    Layer,
    StackLayer,
    Stackup,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.design import Design as ModelDesign

NAME = "board6"
MM = 1_000_000
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
PLANES = {"In2.Cu": "GND"}
BOARD_LINE = "design.board(mm(50), mm(30))"
FILES = tuple(f"{NAME}.{suffix}" for suffix in ("PcbDoc", "PcbLib", "PrjPcb", "SchDoc", "SchLib"))
STACKUP: tuple[tuple[str, str, int, str, str], ...] = (
    ("F.Cu", "copper", 35_000, "", ""),
    ("dielectric 1", "dielectric", 110_000, "FR-4 prepreg", "4.2"),
    ("In1.Cu", "copper", 17_500, "", ""),
    ("dielectric 2", "dielectric", 200_000, "FR-4 core", "4.5"),
    ("In2.Cu", "copper", 17_500, "", ""),
    ("dielectric 3", "dielectric", 800_000, "FR-4 prepreg", "4.2"),
    ("In3.Cu", "copper", 17_500, "", ""),
    ("dielectric 4", "dielectric", 200_000, "FR-4 core", "4.5"),
    ("In4.Cu", "copper", 17_500, "", ""),
    ("dielectric 5", "dielectric", 110_000, "FR-4 prepreg", "4.2"),
    ("B.Cu", "copper", 35_000, "", ""),
)
"""(name, kind, thickness in nm, material, dielectric constant), top to bottom."""
VIA_DIAMETER, VIA_DRILL = 600_000, 300_000
VIAS: tuple[tuple[str, str, tuple[float, float], tuple[str, str], str], ...] = (
    ("v1", "VIN", (11.2, 18.75), ("F.Cu", "B.Cu"), "through"),
    ("v2", "LED_A", (32.8, 9.0), ("F.Cu", "In1.Cu"), "blind"),
    ("v3", "GND", (20.0, 24.0), ("In1.Cu", "In2.Cu"), "buried"),
)
"""(key, net, position, span, type)."""
TRACKS: tuple[tuple[str, str, str, tuple[float, float], tuple[float, float], int], ...] = (
    ("t1", "F.Cu", "LED_DRV", (9.85, 12.2), (9.85, 9.0), 250_000),
    ("t2", "F.Cu", "LED_DRV", (9.85, 9.0), (31.2, 9.0), 250_000),
    ("t3", "In1.Cu", "LED_A", (32.8, 9.0), (40.54, 20.0), 250_000),
    ("t4", "In1.Cu", "GND", (20.0, 24.0), (26.0, 24.0), 500_000),
    ("t5", "In3.Cu", "VIN", (11.2, 18.75), (11.2, 26.0), 500_000),
    ("t6", "In4.Cu", "VIN", (11.2, 18.75), (5.0, 18.75), 500_000),
    ("t7", "B.Cu", "VIN", (11.2, 18.75), (18.0, 18.75), 500_000),
)
"""(key, layer, net, start, end, width in nm)."""
ARC = ("a1", "B.Cu", "VIN", (18.0, 18.75), (18.707107, 19.042893), (19.0, 19.75), 500_000)
"""A quarter circle of 1 mm radius around (18.0, 19.75): start, mid, end."""
TEXTS: tuple[tuple[str, str, str, tuple[float, float], float, float, int], ...] = (
    ("x1", "Tensão 5 V", "F.SilkS", (22.0, 4.0), 1.0, 0.15, 0),
    ("x2", "BOARD6 REV A", "B.SilkS", (30.0, 27.0), 1.2, 0.18, 0),
    ("x3", "ASSEMBLY TOP", "F.Fab", (3.0, 28.0), 0.8, 0.12, 0),
    ("x4", "BOTTOM", "B.Fab", (47.0, 12.0), 1.0, 0.15, 90),
)
"""(key, string, layer, position, height in mm, stroke in mm, rotation in degrees)."""
GRAPHICS: tuple[tuple[str, str, str, tuple[tuple[float, float], ...], float, bool], ...] = (
    ("g1", "line", "F.Fab", ((2.0, 2.0), (12.0, 2.0)), 0.1, False),
    ("g2", "arc", "F.SilkS", ((44.0, 4.0), (45.414214, 4.585786), (46.0, 6.0)), 0.15, False),
    ("g3", "circle", "F.SilkS", ((4.0, 25.0), (6.0, 25.0)), 0.15, False),
    ("g4", "rect", "B.Fab", ((36.0, 22.0), (44.0, 27.0)), 0.1, False),
    ("g5", "polygon", "F.SilkS", ((40.0, 2.0), (42.0, 2.0), (41.0, 3.5)), 0.0, True),
)
"""(key, kind, layer, points, width in mm, filled)."""
KEEPOUT = ("k1", ((22.0, 12.0), (30.0, 12.0), (30.0, 17.0), (22.0, 17.0)))
"""A keep-out for tracks and vias on every copper layer."""
HOLE = ("h1", (4.0, 25.0), 3_200_000)
ZONES: tuple[tuple[str, str, str, tuple[tuple[float, float], ...]], ...] = (
    ("z1", "GND", "F.Cu", ((1.0, 1.0), (49.0, 1.0), (49.0, 29.0), (1.0, 29.0))),
    ("z2", "GND", "B.Cu", ((1.0, 1.0), (49.0, 1.0), (49.0, 29.0), (1.0, 29.0))),
)


def at(x: float, y: float) -> Point:
    """A point given in millimetres from the outline's corner, in the frame of the placements."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


def _id(prefix: str, key: str) -> str:
    return derived_id(prefix, "dsl", f"board6:{key}")


def board6_script() -> str:
    """The sample's script: the blink example renamed ``board6``."""
    source = BLINK.read_text(encoding="utf-8")
    assert BLINK_MARKS in source
    source = source.replace(BLINK_MARKS, "")
    old = 'Design("blink")'
    assert old in source and BOARD_LINE in source
    return source.replace(old, f'Design("{NAME}")')


def board6_design() -> Design:
    namespace: dict[str, object] = {}
    exec(compile(board6_script(), str(BLINK), "exec"), namespace)  # noqa: S102
    design = namespace["design"]
    assert isinstance(design, Design)
    return design


def board6_placements() -> Mapping[str, object]:
    return placements(board6_design())


def stackup() -> Stackup:
    return Stackup(
        id=_id("stk", "stackup"),
        layers=tuple(
            StackLayer(
                id=_id("sly", name),
                name=name,
                kind=kind,  # type: ignore[arg-type]
                thickness=thickness,
                material=material,
                epsilon_r=epsilon,
            )
            for name, kind, thickness, material, epsilon in STACKUP
        ),
    )


def board6_model() -> ModelDesign:
    """The sample's model: the script's model with the six copper layers, the stack-up and the items."""
    model = to_model(board6_design())
    assert model.board is not None
    nets = {net.name: net.id for net in model.circuit.nets}
    key, outline = KEEPOUT
    hole_key, hole_at, hole_drill = HOLE
    arc_key, arc_layer, arc_net, start, mid, end, arc_width = ARC
    board = dataclasses.replace(
        model.board,
        layers=tuple(
            Layer(id=_id("lay", name), name=name, kind="copper", ordinal=n) for n, name in enumerate(LAYERS)
        ),
        stackup=stackup(),
        tracks=tuple(
            Track(id=_id("trk", k), start=at(*a), end=at(*b), width=width, layer=layer, net_id=nets[net])
            for k, layer, net, a, b, width in TRACKS
        ),
        arcs=(
            Arc(
                id=_id("arc", arc_key),
                start=at(*start),
                mid=at(*mid),
                end=at(*end),
                width=arc_width,
                layer=arc_layer,
                net_id=nets[arc_net],
            ),
        ),
        vias=tuple(
            Via(
                id=_id("via", k),
                position=at(*xy),
                diameter=VIA_DIAMETER,
                drill=VIA_DRILL,
                layers=span,
                net_id=nets[net],
                via_type=kind,  # type: ignore[arg-type]
            )
            for k, net, xy, span, kind in VIAS
        ),
        zones=tuple(
            Zone(id=_id("zon", k), outline=tuple(at(*p) for p in points), layers=(layer,), net_id=nets[net])
            for k, net, layer, points in ZONES
        ),
        keepouts=(
            Keepout(
                id=_id("kpo", key),
                outline=tuple(at(*p) for p in outline),
                layers=LAYERS,
                no_tracks=True,
                no_vias=True,
            ),
        ),
        texts=tuple(
            Text(
                id=_id("txt", k),
                text=string,
                position=at(*xy),
                layer=layer,
                size=Size(round(height * MM), round(height * MM)),
                thickness=round(stroke * MM),
                rotation=rotation * 1_000_000,
            )
            for k, string, layer, xy, height, stroke, rotation in TEXTS
        ),
        graphics=tuple(
            Graphic(
                id=_id("gfx", k),
                kind=kind,  # type: ignore[arg-type]
                layer=layer,
                points=tuple(at(*p) for p in points),
                width=round(width * MM),
                filled=filled,
            )
            for k, kind, layer, points, width, filled in GRAPHICS
        ),
        holes=(Hole(id=_id("hol", hole_key), position=at(*hole_at), drill=hole_drill),),
    )
    return dataclasses.replace(model, board=board)


def board6_build(root: Path, model: ModelDesign | None = None, **kwargs: object) -> BuildOutput:
    """The Altium build of ``model`` (the sample by default) in a blink tree under ``root``."""
    project = root / "examples" / "blink_2layer"
    if not project.is_dir():
        project = blink_tree(root)
    requested = board6_placements()
    kwargs.setdefault("copper", len(LAYERS))
    kwargs.setdefault("planes", PLANES)
    kwargs.setdefault("placed", tuple(requested))
    kwargs.setdefault("placements", requested)
    return build_altium(
        board6_model() if model is None else model,
        name=NAME,
        resolver=blink_resolver(root, project),
        **kwargs,  # type: ignore[arg-type]
    )


def project_files(output: BuildOutput) -> dict[str, bytes]:
    """The five project files of a build (without the ``.fenolite/`` cache)."""
    return {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}


# --- reading a written document back (the tests of change c0085) --------------------------------------

OUTLINE = (at(0, 0), at(50, 0), at(50, 30), at(0, 30))
OFFSET_NM = 25_400_000
"""The document puts the outline's lower-left corner at (1000 mil, 1000 mil)."""
IMPORT_LAYERS = {"F.Fab": "Mech.13", "B.Fab": "Mech.14", "F.CrtYd": "Mech.15", "B.CrtYd": "Mech.16"}
"""Layer of the writer's map → the neutral name the import gives its Altium layer (``import.md``)."""


def imported_point(point: Point, outline: tuple[Point, ...] = OUTLINE) -> Point:
    """Where the import of a written document puts the model point ``point``: the document's frame with Y
    negated again (a translation of the model's frame)."""
    min_x, max_y = min(p.x for p in outline), max(p.y for p in outline)
    return Point(point.x - min_x + OFFSET_NM, point.y - max_y - OFFSET_NM)


def near(a: Point, b: Point, tolerance: int = 2) -> bool:
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance


def bare_spec(**fields: object) -> PcbDocSpec:
    """A document spec that holds the sample's outline and ``fields`` only (no component)."""
    return PcbDocSpec(outline=OUTLINE, **fields)  # type: ignore[arg-type]


def read_back(spec: PcbDocSpec, filename: str = "bare.PcbDoc") -> tuple[PcbDocument, ModelDesign]:
    """``spec`` written and read again with the product reader, strictly: the document and its import."""
    return read_document(write_pcbdoc(spec, filename=filename), filename)


def read_document(data: bytes, filename: str) -> tuple[PcbDocument, ModelDesign]:
    """The bytes of a PCB document read with the product reader, strictly, and imported."""
    document = read_pcbdoc(data, file=filename, strict=True)
    assert not [found for found in document.issues if found.severity == "error"], document.issues
    return document, import_board(document, file=filename, sha256=hashlib.sha256(data).hexdigest())
