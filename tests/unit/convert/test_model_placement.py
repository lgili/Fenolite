# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Model placement of imported footprints (capability design-conversion, "Model placement of imported
footprints"; change c0223)."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest

from fenolite.backends.base import BodyModel
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.model.base import Provenance
from fenolite.model.board import ComponentBody
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
    """Scenario "A model on the bottom"."""
    conversion, _ = _convert(monkeypatch, side="bottom")
    assert not any(key.endswith(".step") for key in conversion.files)
    row = conversion.report.row("model")
    assert row is not None and row.lost == 1 and "bottom-side" in row.reasons[0].reason


def test_placement_in_the_frame_of_a_turned_footprint() -> None:
    """A model beside a footprint turned by 90°: the offset is in the footprint's own frame."""
    from fenolite.convert.models import TILTED, placement
    from fenolite.model.board import FootprintInstance

    fp = FootprintInstance(
        id="fp", component_id="c", lib_ref="L:A", position=Point(10_000_000, 0), rotation=90 * DEG
    )
    model = BodyModel(LOCATOR, "m", "step", STEP, Point(10_000_000, -1_000_000), 0, (0, 0, 90 * DEG))
    placed = placement(model, fp, "m.step")
    assert isinstance(placed, ModelPlacement)
    assert placed.rotation == (0, 0, 0) and abs(placed.offset[0]) + abs(placed.offset[1]) == 1_000_000
    assert placement(dataclasses.replace(model, rotation=(90 * DEG, 0, 0)), fp, "m.step") == TILTED
