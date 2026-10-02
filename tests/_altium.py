# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the Altium writer tests (change c0032): the CC0 sample, models with generic pins, a plain
split of written records into dictionaries, and the layout bounds check."""

from __future__ import annotations

import dataclasses
import runpy
from collections.abc import Iterator
from pathlib import Path

from fenolite.backends.altium.layout import MARGIN, SheetPlan
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, to_model
from fenolite.model.circuit import Pin
from fenolite.model.design import Design as ModelDesign

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "altium_sample" / "design.py"
SAMPLE_PATHS = ("J1", "R2", "U2", "led/D1", "led/R1", "power/C1", "power/C2", "power/U1")


def sample() -> Design:
    design = runpy.run_path(str(SAMPLE))["design"]
    assert isinstance(design, Design)
    return design


def with_pins(model: ModelDesign) -> ModelDesign:
    """Each component with one passive pin per designator its nets name (name = designator), keyed as
    the DSL keys pins; the writer tests' stand-in for ``lens.altium.generic_pins``."""
    used: dict[str, set[str]] = {c.id: set() for c in model.circuit.components}
    for net in model.circuit.nets:
        for member in net.members:
            used[member.component_id].add(member.pin)
    components = tuple(
        dataclasses.replace(
            c,
            pins=tuple(
                Pin(id=derived_id("pin", "dsl", f"pin:{c.properties['fenolite.path']}:{d}"), number=d, name=d)
                for d in sorted(used[c.id])
            ),
        )
        for c in model.circuit.components
    )
    return dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))


def model_of(design: Design) -> ModelDesign:
    return with_pins(to_model(design))


def sample_model() -> ModelDesign:
    return model_of(sample())


def records(data: bytes) -> list[dict[str, str]]:
    """The records after the header line, each as ``{key: value}`` in written order."""
    lines = data.decode("ascii").split("\r\n")
    assert lines[-1] == "", "the last line ends with CR LF"
    found: list[dict[str, str]] = []
    for line in lines[1:-1]:
        assert line.startswith("|"), line
        fields = [field.partition("=") for field in line[1:].split("|")]
        found.append({key: value for key, _, value in fields})
    return found


def owned_by(found: list[dict[str, str]], owner: int) -> list[tuple[int, dict[str, str]]]:
    return [(i, r) for i, r in enumerate(found) if r.get("OWNERINDEX") == str(owner)]


def component_index(found: list[dict[str, str]], ref: str) -> int:
    """The record number of the component whose designator is ``ref``."""
    for record in found:
        if record["RECORD"] == "34" and record["TEXT"] == ref:
            return int(record["OWNERINDEX"])
    raise KeyError(ref)


def plan_points(plan: SheetPlan) -> Iterator[tuple[int, int]]:
    """Every point the writer writes for ``plan``: body corners, pin ends, texts, stub ends and marks."""
    for part in plan.parts:
        body = part.spec.body
        yield part.x, part.y
        yield part.x + body.width, part.y + body.height
        yield part.x, part.y - 100
        yield part.x, part.y + body.height + 200
        for pin in body.pins:
            for dx, dy in (pin.body_end(body.width), pin.hot_end(body.width)):
                yield part.x + dx, part.y + dy
    for stub in plan.stubs:
        yield stub.start
        yield stub.end
        yield stub.mark


def check_plan(plan: SheetPlan) -> None:
    """On the grid, inside the drawing area less the margins, and no two cells overlap."""
    size = plan.size
    for x, y in plan_points(plan):
        assert x % 100 == 0 and y % 100 == 0, (x, y)
        assert MARGIN <= x <= size.width - MARGIN and MARGIN <= y <= size.height - MARGIN, (x, y)
    cells = [p.cell for p in plan.parts]
    for i, (ax0, ay0, ax1, ay1) in enumerate(cells):
        assert MARGIN <= ax0 < ax1 <= size.width - MARGIN and MARGIN <= ay0 < ay1 <= size.height - MARGIN
        for bx0, by0, bx1, by1 in cells[i + 1 :]:
            assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, "cells overlap"
