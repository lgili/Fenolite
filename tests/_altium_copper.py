# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The routed sample of the Altium PCB copper (change c0038, capability altium-build, "Routed sample and
author report"): the blink design named ``routed`` on four copper layers, with copper authored for Fenolite.

Every value here is authored for this sample; none comes from another project. The copper, in millimetres
from the outline's top-left corner (Y down), is the table ``TRACKS``, ``ARC``, ``VIAS`` and ``ZONE``:

- ``LED_DRV`` runs on ``F.Cu`` from pin 1 of ``U1`` up, round a 1 mm arc and along to pad 1 of ``R1``;
- ``LED_A`` leaves pad 2 of ``R1`` through a via and crosses on ``In2.Cu`` to pin 2 of ``D1``;
- ``VIN`` leaves pin 9 of ``U1`` through a via, with a stub on ``In1.Cu`` and one on ``B.Cu``;
- ``GND`` has a via in pin 10 of ``U1`` and one zone on ``In1.Cu`` and ``B.Cu``, 1 mm inside the outline.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from _altium import BLINK, blink_resolver, blink_tree

from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput, build_design
from fenolite.model.board import Arc, Track, Via, Zone
from fenolite.model.design import Design as ModelDesign

NAME = "routed"
MM = 1_000_000
FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
SIGNAL_WIDTH = 250_000
POWER_WIDTH = 500_000
VIA_DIAMETER, VIA_DRILL = 600_000, 300_000
TRACKS: tuple[tuple[str, str, str, tuple[float, float], tuple[float, float], int], ...] = (
    ("t1", "F.Cu", "LED_DRV", (9.85, 12.2), (9.85, 10.0), SIGNAL_WIDTH),
    ("t2", "F.Cu", "LED_DRV", (10.85, 9.0), (31.2, 9.0), SIGNAL_WIDTH),
    ("t3", "B.Cu", "VIN", (11.2, 18.75), (5.0, 18.75), POWER_WIDTH),
    ("t4", "In1.Cu", "VIN", (11.2, 18.75), (11.2, 26.0), POWER_WIDTH),
    ("t5", "In2.Cu", "LED_A", (32.8, 9.0), (40.54, 20.0), SIGNAL_WIDTH),
)
"""(key, layer, net, start, end, width in nm)."""
ARC = ("a1", "F.Cu", "LED_DRV", (9.85, 10.0), (10.142893, 9.292893), (10.85, 9.0), SIGNAL_WIDTH)
"""A quarter circle of 1 mm radius around (10.85, 10.0): start, mid, end."""
VIAS: tuple[tuple[str, str, tuple[float, float]], ...] = (
    ("v1", "LED_A", (32.8, 9.0)),
    ("v2", "VIN", (11.2, 18.75)),
    ("v3", "GND", (12.0, 19.55)),
)
ZONE = ("z1", "GND", ("In1.Cu", "B.Cu"), ((1.0, 1.0), (49.0, 1.0), (49.0, 29.0), (1.0, 29.0)))
INNER = ("In1.Cu", "In2.Cu")
FEATURES = ("tracks", "arc", "vias", "inner", "zones", "class")
"""What ``routed_model`` holds, in the order the variants add it."""
BOARD_LINE = "design.board(mm(50), mm(30))"


def at(x: float, y: float) -> Point:
    """A point given in millimetres from the outline's corner, in the frame of the placements."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


def routed_script(board: str = "design.board(mm(50), mm(30), copper=4)") -> str:
    """The sample's script: the blink example renamed, with the board line ``board``."""
    source = BLINK.read_text(encoding="utf-8")
    for old, new in (('Design("blink")', f'Design("{NAME}")'), (BOARD_LINE, board)):
        assert old in source, old
        source = source.replace(old, new)
    return source


def routed_design(board: str = "design.board(mm(50), mm(30), copper=4)") -> Design:
    namespace: dict[str, object] = {}
    exec(compile(routed_script(board), str(BLINK), "exec"), namespace)  # noqa: S102
    design = namespace["design"]
    assert isinstance(design, Design)
    return design


def _id(prefix: str, key: str) -> str:
    return derived_id(prefix, "dsl", f"copper:{key}")


def copper(
    nets: Mapping[str, str], features: tuple[str, ...] = FEATURES
) -> tuple[tuple[Track, ...], tuple[Arc, ...], tuple[Via, ...], tuple[Zone, ...]]:
    """The sample's copper as model entities; ``nets`` maps a net name to the net id to put on them."""
    tracks: tuple[Track, ...] = ()
    if "tracks" in features:
        tracks = tuple(
            Track(id=_id("trk", key), start=at(*a), end=at(*b), width=width, layer=layer, net_id=nets[net])
            for key, layer, net, a, b, width in TRACKS
            if "inner" in features or layer not in INNER
        )
    arcs: tuple[Arc, ...] = ()
    if "arc" in features:
        key, layer, net, start, mid, end, width = ARC
        arcs = (
            Arc(
                id=_id("arc", key),
                start=at(*start),
                mid=at(*mid),
                end=at(*end),
                width=width,
                layer=layer,
                net_id=nets[net],
            ),
        )
    vias: tuple[Via, ...] = ()
    if "vias" in features:
        vias = tuple(
            Via(
                id=_id("via", key),
                position=at(*xy),
                diameter=VIA_DIAMETER,
                drill=VIA_DRILL,
                layers=("F.Cu", "B.Cu"),
                net_id=nets[net],
            )
            for key, net, xy in VIAS
        )
    zones: tuple[Zone, ...] = ()
    if "zones" in features:
        key, net, layers, outline = ZONE
        zones = (
            Zone(id=_id("zon", key), outline=tuple(at(*p) for p in outline), layers=layers, net_id=nets[net]),
        )
    return tracks, arcs, vias, zones


def with_copper(model: ModelDesign, features: tuple[str, ...] = FEATURES) -> ModelDesign:
    """``model`` with the sample's copper on its board, the nets looked up by name."""
    assert model.board is not None
    nets = {net.name: net.id for net in model.circuit.nets}
    tracks, arcs, vias, zones = copper(nets, features)
    board = dataclasses.replace(model.board, tracks=tracks, arcs=arcs, vias=vias, zones=zones)
    return dataclasses.replace(model, board=board)


def without_class(model: ModelDesign) -> ModelDesign:
    nets = tuple(dataclasses.replace(net, netclass_id=None) for net in model.circuit.nets)
    return dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, nets=nets, netclasses=()))


def routed_model(features: tuple[str, ...] = FEATURES) -> ModelDesign:
    """The sample's model: the script's model with the copper of ``features`` (all of it by default)."""
    model = with_copper(to_model(routed_design()), features)
    return model if "class" in features else without_class(model)


PLANE = {"In1.Cu": "GND"}
"""The plane of the variant ``p0``."""


def plane_model() -> ModelDesign:
    """The sample without its track on ``In1.Cu``, which the plane of ``p0`` replaces."""
    model = routed_model()
    assert model.board is not None
    tracks = tuple(track for track in model.board.tracks if track.layer != "In1.Cu")
    return dataclasses.replace(model, board=dataclasses.replace(model.board, tracks=tracks))


def routed_kicad_build(board: str = "design.board(mm(50), mm(30), copper=4)") -> BuildOutput:
    """The KiCad build of the sample's script in memory (no file is written to disk)."""
    design = routed_design(board)
    with tempfile.TemporaryDirectory() as folder:
        built = build_design(
            to_model(design),
            placements(design),
            name=NAME,
            copper=design.copper,  # type: ignore[arg-type]
            resolver=blink_resolver(Path(folder)),
        )
    assert built.files and not [found for found in built.issues if found.severity == "error"]
    return built


def routed_kicad_design(features: tuple[str, ...] = FEATURES) -> ModelDesign:
    """The sample as the KiCad build of its script holds it in memory, with the sample's copper put into
    its model: what change c0028 hands over as script copper (a ``CopperSource`` of origin ``script``)."""
    return with_copper(routed_kicad_build().design, features)


def routed_board_text(edit: Callable[[ModelDesign], ModelDesign] | None = None) -> str:
    """The text of the sample's routed KiCad board: the KiCad build of the script with the sample's copper,
    as a ``.kicad_pcb``; ``edit`` changes the model first (a moved part, a mismatch)."""
    design = routed_kicad_design()
    written = write_board(design if edit is None else edit(design))
    return written.text


def routed_placements() -> Mapping[str, object]:
    return placements(routed_design())


@dataclass(frozen=True)
class Variant:
    """One document handed to the maintainer: its model and the build arguments."""

    model: ModelDesign
    copper: int = 4
    build: Mapping[str, object] = dataclasses.field(default_factory=lambda: {})
    """Further keyword arguments of ``build_altium`` (the planes of ``p0``)."""


def variants() -> dict[str, Variant]:
    """The bisection variants: ``c0`` two layers with tracks and an arc, ``c1`` adds the vias, ``c2`` the
    stack of four signal layers with the inner tracks, ``c3`` adds the polygons; ``p0`` is the
    sample with ``In1.Cu`` as a plane on ``GND`` and without its track on ``In1.Cu``."""
    return {
        "c0": Variant(routed_model(("tracks", "arc")), copper=2),
        "c1": Variant(routed_model(("tracks", "arc", "vias")), copper=2),
        "c2": Variant(routed_model(("tracks", "arc", "vias", "inner"))),
        "c3": Variant(routed_model(("tracks", "arc", "vias", "inner", "zones"))),
        "p0": Variant(plane_model(), build={"planes": PLANE}),
    }


def routed_build(root: Path, model: ModelDesign | None = None, **kwargs: object) -> BuildOutput:
    """The Altium build of ``model`` (the sample by default) in a blink tree under ``root``."""
    project = root / "examples" / "blink_2layer"
    if not project.is_dir():
        project = blink_tree(root)
    requested = routed_placements()
    kwargs.setdefault("copper", 4)
    kwargs.setdefault("placed", tuple(requested))
    kwargs.setdefault("placements", requested)
    return build_altium(
        routed_model() if model is None else model,
        name=NAME,
        resolver=blink_resolver(root, project),
        **kwargs,  # type: ignore[arg-type]
    )
