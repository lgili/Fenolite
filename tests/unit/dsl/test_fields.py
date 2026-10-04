# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field placement requests of DSL parts (capability design-dsl, "Field placements in the DSL"; c0030)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import Any

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, FieldRequest, Module, Part, fields, mm

SRC = Path(__file__).resolve().parents[3] / "src" / "fenolite" / "dsl"
NOTHING = {
    "dx": None,
    "dy": None,
    "rotation": None,
    "layer": None,
    "visible": None,
    "size": None,
    "thickness": None,
    "justify": None,
    "outside": None,
    "gap": None,
}


def design_with(*refs: str) -> tuple[Design, dict[str, Part]]:
    design = Design("fields")
    parts = {ref: Part(ref, "Mini:Mini_R", "Mini:Mini_R_0603", "1k") for ref in refs}
    design.add(*parts.values())
    return design, parts


def given(request: FieldRequest) -> dict[str, Any]:
    data = dataclasses.asdict(request)
    return {k: v for k, v in data.items() if k not in ("name", "locked") and v is not None}


def test_requests_recorded() -> None:
    design, parts = design_with("R1")
    r1 = parts["R1"]
    r1.field("Value", visible=False)
    r1.field("Reference", outside="top", gap=mm(0.3))
    reference, value = fields(design)["R1"]
    assert (reference.name, value.name) == ("Reference", "Value")
    assert given(reference) == {"outside": "top", "gap": 300_000}
    assert given(value) == {"visible": False}
    assert reference.locked is False and value.locked is False
    assert dataclasses.asdict(value) == {**NOTHING, "name": "Value", "visible": False, "locked": False}


def test_offset_in_the_board_frame() -> None:
    design, parts = design_with("U1")
    parts["U1"].field("Reference", dx=mm(0), dy="-2.5mm", rot=-90, justify="left bottom", locked=True)
    (request,) = fields(design)["U1"]
    assert (request.dx, request.dy, request.rotation) == (0, -2_500_000, 270_000_000)
    assert request.justify == "left bottom" and request.locked is True


def test_every_value() -> None:
    design, parts = design_with("R1")
    parts["R1"].field(
        "Value", dx="1mm", dy=mm(2), rot="45", layer="fab", visible=True, size=mm(0.8), thickness="0.12mm",
        justify="  right   top ",
    )  # fmt: skip
    (request,) = fields(design)["R1"]
    assert dataclasses.asdict(request) == {
        "name": "Value",
        "dx": 1_000_000,
        "dy": 2_000_000,
        "rotation": 45_000_000,
        "layer": "fab",
        "visible": True,
        "size": 800_000,
        "thickness": 120_000,
        "justify": "right top",
        "outside": None,
        "gap": None,
        "locked": False,
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.visible = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "MPN", "visible": True},
        {"name": "reference", "visible": True},
        {"name": "Reference", "dx": mm(1)},
        {"name": "Reference", "dy": mm(1)},
        {"name": "Reference", "outside": "top", "dx": mm(1), "dy": mm(0)},
        {"name": "Reference", "outside": "top", "rot": 0},
        {"name": "Reference", "outside": "top", "justify": "left"},
        {"name": "Reference", "outside": "north"},
        {"name": "Reference", "justify": "middle"},
        {"name": "Reference", "justify": "top left"},
        {"name": "Reference", "justify": "left right"},
        {"name": "Reference", "justify": ""},
        {"name": "Reference"},
        {"name": "Reference", "locked": True},
        {"name": "Reference", "dx": 1, "dy": 2},
        {"name": "Reference", "dx": 1.5, "dy": mm(2)},
        {"name": "Reference", "layer": "F.SilkS"},
        {"name": "Reference", "layer": "copper"},
        {"name": "Reference", "visible": 1},
        {"name": "Reference", "visible": False, "locked": "yes"},
        {"name": "Reference", "size": mm(0)},
        {"name": "Reference", "size": mm(-1)},
        {"name": "Reference", "size": 1},
        {"name": "Reference", "thickness": mm(0)},
        {"name": "Reference", "gap": mm(0.3)},
        {"name": "Reference", "outside": "top", "gap": mm(-0.1)},
        {"name": "Reference", "outside": "top", "gap": 0.3},
        {"name": "Reference", "rot": "ninety", "dx": mm(0), "dy": mm(0)},
        {"name": "Reference", "rot": True},
    ],
)
def test_refused_calls(kwargs: dict[str, Any]) -> None:
    design, parts = design_with("R1")
    name = kwargs.pop("name")
    with pytest.raises(DslError):
        parts["R1"].field(name, **kwargs)
    assert "R1" not in fields(design)


def test_second_request_for_one_field() -> None:
    _, parts = design_with("R1")
    parts["R1"].field("Value", visible=False)
    with pytest.raises(DslError, match=r"R1.*Value"):
        parts["R1"].field("Value", visible=False)
    parts["R1"].field("Reference", visible=False)  # another field of the same part is fine


def test_zero_gap_and_single_words() -> None:
    design, parts = design_with("R1")
    parts["R1"].field("Reference", outside="left", gap=mm(0))
    parts["R1"].field("Value", justify="top")
    reference, value = fields(design)["R1"]
    assert (reference.outside, reference.gap) == ("left", 0)
    assert value.justify == "top"


def test_paths_in_order_and_parts_without_requests_left_out() -> None:
    design = Design("fields")
    power = Module("power")
    r1, r2 = (Part(ref, "Mini:Mini_R", "Mini:Mini_R_0603") for ref in ("R1", "R2"))
    power.add(r2)
    design.add(power, r1, Part("R3", "Mini:Mini_R", "Mini:Mini_R_0603"))
    r2.field("Value", visible=False)
    r1.field("Value", visible=False)
    found = fields(design)
    assert list(found) == ["R1", "power/R2"]
    with pytest.raises(TypeError):
        found["R9"] = ()  # type: ignore[index]


def test_requests_do_not_change_the_model() -> None:
    plain, _ = design_with("R1")
    design, parts = design_with("R1")
    parts["R1"].field("Reference", outside="top")
    assert dsl.to_model(design) == dsl.to_model(plain)
    assert dsl.placements(design) == dsl.placements(plain)


def test_re_exports_and_import_edges() -> None:
    assert dsl.FieldRequest is FieldRequest and dsl.fields is fields
    assert {"FieldRequest", "fields"} <= set(dsl.__all__)
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("fenolite."):
                assert node.module.split(".")[1] in ("core", "model", "dsl"), (path.name, node.module)
