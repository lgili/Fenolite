# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``altium-pcbx-<kind>`` probes: the six-layer sample's PCB document imported by ``kicad-cli pcb
import`` and compared with the model, kind by kind (change c0085; hypothesis ``H-A-PCBX-KICAD``).

KiCad moves the board on its sheet, so positions are compared relative to the outline's corner, within
10 nm (KiCad rounds a length to 10 nm, ``pcb-read.md``). ``pcb import`` exists from 10.0 only. A probe
says ``equal`` when every item of its kind in the model is in the imported board as the model holds it.
What KiCad's importer does not read is not compared and is listed in ``NOT_COMPARED``.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _altium_board6 import LAYERS, NAME, PLANES, board6_build, board6_model
from _kicad import oracle_env
from _resources import kicad_cli

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

TOLERANCE = 10
MAJORS = (10,)
KICAD_LAYERS = {"F.Fab": "User.13", "B.Fab": "User.14", "F.CrtYd": "User.15", "B.CrtYd": "User.16"}
"""Layer of the writer's map → the layer KiCad's import gives its mechanical layer (``pcb-records.md``,
"Layers": Mechanical n becomes ``User.n``)."""
LAYER_ROW = re.compile(r'\((\d+) "([^"]+\.Cu)" (\w+)')
NOT_COMPARED = (
    "the restriction no_footprints of a keep-out, which the record does not hold",
    "the anchor of a text: KiCad places a stroke text by its lower-left corner and shifts the baseline",
    "the drill pairs of the board record: KiCad reads no LAYERPAIR key",
    "the net of an internal plane, net classes and rules (see test_pcbdoc_copper_oracle.py)",
    "dielectric thicknesses and materials: the import writes KiCad's default stack-up values",
)
"""What ``kicad-cli pcb import`` does not carry of the kinds this change writes."""


@dataclass(frozen=True)
class Imported:
    code: int
    output: str
    board: Design
    text: str


def import_document(data: bytes, name: str = f"{NAME}.PcbDoc") -> Imported:
    """The bytes of a PCB document as ``kicad-cli pcb import`` reads them."""
    cli = kicad_cli()
    assert cli is not None
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target = root / name, root / "b.kicad_pcb"
        source.write_bytes(data)
        env = oracle_env(root / "config")
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "-o", str(target), str(source)],
            capture_output=True, text=True, timeout=300, env=env, check=False,
        )  # fmt: skip
        assert target.is_file(), proc.stdout + proc.stderr
        text = target.read_text(encoding="utf-8")
        return Imported(proc.returncode, proc.stdout + proc.stderr, read_board(target), text)


@cache
def imported() -> tuple[Imported, Design]:
    """The sample's PCB document as ``kicad-cli pcb import`` reads it, and the sample's model."""
    model = board6_model()
    with tempfile.TemporaryDirectory() as folder:
        output = board6_build(Path(folder) / "build", model)
    assert not [found for found in output.issues if found.severity == "error"]
    return import_document(output.files[f"{NAME}.PcbDoc"]), model


def _corner(points: list[Point]) -> Point:
    return Point(min(p.x for p in points), min(p.y for p in points))


def corners() -> tuple[Point, Point]:
    """The outline's corner in the model and in the imported board."""
    found, model = imported()
    assert model.board is not None and model.board.outline is not None and found.board.board is not None
    edge = [p for g in found.board.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    return _corner(list(model.board.outline.points)), _corner(edge)


def same(mine: Point, theirs: Point, tolerance: int = TOLERANCE) -> bool:
    """Whether a model point and an imported point are the same place relative to the outline."""
    a, b = corners()
    return (
        abs((mine.x - a.x) - (theirs.x - b.x)) <= tolerance
        and abs((mine.y - a.y) - (theirs.y - b.y)) <= tolerance
    )


def _all(points: tuple[Point, ...], others: tuple[Point, ...]) -> bool:
    return len(points) == len(others) and all(same(a, b) for a, b in zip(points, others, strict=True))


def stack() -> bool:
    found, _model = imported()
    rows = [(name, kind) for _number, name, kind in LAYER_ROW.findall(found.text)]
    wanted = [(name, "power" if name in PLANES else "signal") for name in LAYERS]
    return sorted(rows) == sorted(wanted) and found.code == 0


def vias() -> bool:
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    theirs = found.board.board.vias
    return len(theirs) == len(model.board.vias) and all(
        any(
            set(t.layers) == set(v.layers)
            and t.via_type == v.via_type
            and same(v.position, t.position)
            and abs(t.diameter - v.diameter) <= TOLERANCE
            and abs(t.drill - v.drill) <= TOLERANCE
            for t in theirs
        )
        for v in model.board.vias
    )


def texts() -> bool:
    """String, layer, height, stroke width and rotation; the place within the text's height."""
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    theirs = found.board.board.texts
    return len(theirs) == len(model.board.texts) and all(
        any(
            t.text == x.text
            and t.layer == KICAD_LAYERS.get(x.layer, x.layer)
            and abs(t.size.h - x.size.h) <= TOLERANCE
            and abs(t.thickness - x.thickness) <= TOLERANCE
            and t.rotation % 360_000_000 == x.rotation % 360_000_000
            and same(x.position, t.position, x.size.h)
            for t in theirs
        )
        for x in model.board.texts
    )


def graphics() -> bool:
    """Lines, arcs, circles and filled polygons on their layers; a drawn rectangle is four lines."""
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    theirs = [g for g in found.board.board.graphics if g.layer != "Edge.Cuts"]
    for graphic in model.board.graphics:
        on_layer = [g for g in theirs if g.layer == KICAD_LAYERS.get(graphic.layer, graphic.layer)]
        if graphic.kind == "rect":
            ok = sum(g.kind == "line" and abs(g.width - graphic.width) <= TOLERANCE for g in on_layer) >= 4
        elif graphic.kind == "circle":
            ok = any(g.kind == "circle" and same(graphic.points[0], g.points[0]) for g in on_layer)
        else:
            ok = any(
                g.kind == graphic.kind
                and g.filled == graphic.filled
                and (_all(graphic.points, g.points) or _all(graphic.points, g.points[::-1]))
                for g in on_layer
            )
        if not ok:
            return False
    return True


def keepouts() -> bool:
    """One rule area per keep-out with its outline, its copper layers and exactly the restrictions written
    (tracks, vias, pads, copper pour): KiCad reads them from the key ``KEEPOUTRESTRIC``, which the writer
    adds beside the key of the saved documents."""
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    theirs = found.board.board.keepouts
    return len(theirs) == len(model.board.keepouts) and all(
        any(
            set(t.layers) == set(k.layers)
            and _all(k.outline, t.outline)
            and (t.no_tracks, t.no_vias, t.no_pads, t.no_copper_pour)
            == (k.no_tracks, k.no_vias, k.no_pads, k.no_copper_pour)
            for t in theirs
        )
        for k in model.board.keepouts
    )


def holes() -> bool:
    """A footprint of KiCad's own with one non-plated through hole of the hole's drill at its place."""
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    pads = [
        (fp.position, pad)
        for fp in found.board.board.footprints
        for pad in fp.pads
        if pad.kind == "np_thru_hole" and len(fp.pads) == 1
    ]
    return all(
        any(
            same(h.position, at) and pad.drill is not None and abs(pad.drill - h.drill) <= TOLERANCE
            for at, pad in pads
        )
        for h in model.board.holes
    ) and len(pads) >= len(model.board.holes)


def zones() -> bool:
    """One zone per polygon with its layer and outline, without a fill: the polygons are unpoured."""
    found, model = imported()
    assert model.board is not None and found.board.board is not None
    theirs = found.board.board.zones
    return len(theirs) == len(model.board.zones) and all(
        any(t.layers == z.layers and _all(z.outline, t.outline) and not t.fills for t in theirs)
        for z in model.board.zones
    )


KINDS: dict[str, Callable[[], bool]] = {
    "stack": stack,
    "vias": vias,
    "texts": texts,
    "graphics": graphics,
    "keepouts": keepouts,
    "holes": holes,
    "zones": zones,
}


def pcbx_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """Probe id → (function, majors): ``equal`` when KiCad's import holds the kind as the model does."""

    def probe(check: Callable[[], bool]) -> Callable[[], str]:
        return lambda: "equal" if check() else "different"

    return {f"altium-pcbx-{kind}": (probe(check), MAJORS) for kind, check in KINDS.items()}
