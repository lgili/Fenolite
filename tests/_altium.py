# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the Altium writer tests (change c0032): the CC0 sample and its script text, models with
generic pins, a plain split of written records into dictionaries, and the layout bounds check."""

from __future__ import annotations

import runpy
from collections.abc import Iterator
from pathlib import Path

from fenolite.backends.altium.layout import MARGIN, SheetPlan
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, to_model
from fenolite.lens.altium import generic_pins
from fenolite.model.circuit import PinType
from fenolite.model.design import Design as ModelDesign
from fenolite.model.library import SymbolDef, SymbolPin, SymbolUnit

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "altium_sample" / "design.py"
EXAMPLE_DIR = ROOT / "examples" / "altium_kicad"
EXAMPLE = EXAMPLE_DIR / "design.py"
EXAMPLE_NETS: dict[str, set[tuple[str, str]]] = {
    "VIN": {("J1", "1"), ("U1", "8"), ("U2", "1"), ("U2", "6"), ("R1", "1")},
    "GND": {("J1", "2"), ("U1", "4"), ("U2", "7"), ("R2", "2")},
    "SIG": {("R1", "2"), ("U1", "3")},
    "FB_A": {("U1", "1"), ("U1", "2"), ("U1", "5")},
    "FB_B": {("U1", "6"), ("U1", "7"), ("U2", "3")},
    "OE_N": {("U2", "5"), ("R2", "1")},
}
"""The KiCad example's nets as (ref, pin) pairs, written out by hand from the script (change c0034)."""
SAMPLE_PATHS = ("J1", "R2", "U2", "led/D1", "led/R1", "power/C1", "power/C2", "power/U1")
SAMPLE_NETS: dict[str, set[tuple[str, str]]] = {
    "VIN": {("J1", "1"), ("U1", "1"), ("C1", "1")},
    "GND": {("J1", "2"), ("U1", "2"), ("C1", "2"), ("C2", "2"), ("D1", "1"), ("U2", "2")},
    "+5V": {("U1", "3"), ("C2", "1"), ("U2", "1"), ("R2", "1")},
    "EN": {("R2", "2"), ("U2", "4")},
    "LED_DRV": {("U2", "3"), ("R1", "1")},
    "LED_A": {("R1", "2"), ("D1", "2")},
}
"""The sample's nets as (ref, pin) pairs, written out by hand from the script."""


MIL = 25_400
"""Nanometres per mil."""


def symbol_pin(
    number: str, x: int, y: int, rot: int, unit: int, etype: PinType = "input", **more: object
) -> SymbolPin:
    """A KiCad symbol pin ``number`` named ``P<number>``, hot end (``x``, ``y``) mil, angle ``rot``
    degrees, 100 mil long."""
    fields: dict[str, object] = {
        "number": number,
        "name": f"P{number}",
        "etype": etype,
        "position": Point(x * MIL, y * MIL),
        "rotation": rot * 1_000_000,
        "length": 100 * MIL,
        "unit": unit,
        **more,
    }
    return SymbolPin(**fields)  # type: ignore[arg-type]


def dual_symbol() -> SymbolDef:
    """Two units of three pins each and two common power_in pins (``8`` up, ``4`` down)."""
    pins = (
        symbol_pin("1", -300, 100, 0, 1),
        symbol_pin("2", -300, -100, 0, 1),
        symbol_pin("3", 300, 0, 180, 1, "output"),
        symbol_pin("5", -300, 100, 0, 2),
        symbol_pin("6", -300, -100, 0, 2),
        symbol_pin("7", 300, 0, 180, 2, "output"),
        symbol_pin("8", 0, 300, 270, 0, "power_in"),
        symbol_pin("4", 0, -300, 90, 0, "power_in"),
    )
    return SymbolDef(
        id=derived_id("sym", "kicad", "Demo:DUAL"),
        name="DUAL",
        library="Demo",
        properties={"Reference": "U", "Value": "DUAL"},
        units=(SymbolUnit(1, 1), SymbolUnit(2, 1)),
        pins=pins,
    )


def example(text: str = "", new: str = "") -> Design:
    """The KiCad-sourced example (change c0034), with ``text`` replaced by ``new`` in its script."""
    if not text:
        design = runpy.run_path(str(EXAMPLE))["design"]
    else:
        source = EXAMPLE.read_text(encoding="utf-8")
        assert text in source, text
        namespace: dict[str, object] = {}
        exec(compile(source.replace(text, new), str(EXAMPLE), "exec"), namespace)  # noqa: S102
        design = namespace["design"]
    assert isinstance(design, Design)
    return design


def example_resolver(folder: Path, project_dir: Path = EXAMPLE_DIR) -> LibraryResolver:
    """A resolver that sees only the example's own ``sym-lib-table``: no global table, no install."""
    config = LibraryConfig(
        project_dir=project_dir,
        env={},
        config_home=folder / "config",
        install_dir=folder / "absent",
        use_global_table=False,
        home=folder,
    )
    return LibraryResolver(config)


def sample() -> Design:
    design = runpy.run_path(str(SAMPLE))["design"]
    assert isinstance(design, Design)
    return design


def variant_script(folder: Path, old: str = "", new: str = "", *, append: str = "") -> Path:
    """A copy of the sample script under ``folder`` with ``old`` replaced by ``new`` and ``append`` added."""
    text = SAMPLE.read_text(encoding="utf-8")
    if old:
        assert old in text, old
        text = text.replace(old, new)
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    script.write_text(text + append, encoding="utf-8")
    return script


def model_of(design: Design) -> ModelDesign:
    return generic_pins(to_model(design))


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
