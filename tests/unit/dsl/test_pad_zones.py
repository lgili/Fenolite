# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad zone connection requests of the DSL (capability design-dsl, "Pad zone connections in the DSL";
change c0068)."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, Module, PadZoneRequest, Part, pad_zones


def design_with(*refs: str) -> tuple[Design, dict[str, Part]]:
    design = Design("pad-zones")
    parts = {ref: Part(ref, "Mini:Mini_R", "Mini:Mini_R_0603", "1k") for ref in refs}
    design.add(*parts.values())
    return design, parts


def test_requests_recorded() -> None:
    """Scenario "Requests recorded"."""
    design, parts = design_with("U1")
    u1 = parts["U1"]
    u1.zone_connection(9, "solid")
    u1.zone_connection("1", "none", locked=True)
    assert pad_zones(design)["U1"] == (
        PadZoneRequest("1", None, "none", True),
        PadZoneRequest("9", None, "solid", False),
    )


def test_one_of_several_pads() -> None:
    """Scenario "One of several pads"."""
    design, parts = design_with("J1")
    j1 = parts["J1"]
    j1.zone_connection(1, "solid", index=1)
    j1.zone_connection(1, "thermal", index=0)
    assert pad_zones(design)["J1"] == (
        PadZoneRequest("1", 0, "thermal", False),
        PadZoneRequest("1", 1, "solid", False),
    )


def test_numbers_sort_as_text_and_none_comes_first() -> None:
    design, parts = design_with("U1")
    u1 = parts["U1"]
    u1.zone_connection("B", "none", index=3)
    u1.zone_connection("B", "none", index=0)
    u1.zone_connection("A", "thru_hole_only")
    u1.zone_connection(10, "thermal")
    assert [(r.number, r.index) for r in pad_zones(design)["U1"]] == [
        ("10", None),
        ("A", None),
        ("B", 0),
        ("B", 3),
    ]


@pytest.mark.parametrize("connection", ["solid", "thermal", "none", "thru_hole_only"])
def test_the_four_values(connection: str) -> None:
    design, parts = design_with("U1")
    parts["U1"].zone_connection(1, connection)
    (request,) = pad_zones(design)["U1"]
    assert request.connection == connection
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.connection = "solid"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((9, "direct"), {}),
        ((9, None), {}),
        (("", "solid"), {}),
        ((None, "solid"), {}),
        ((True, "solid"), {}),
        ((1.5, "solid"), {}),
        ((9, "solid"), {"index": -1}),
        ((9, "solid"), {"index": True}),
        ((9, "solid"), {"index": "0"}),
        ((9, "solid"), {"locked": 1}),
    ],
)
def test_refused_values(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    design, parts = design_with("U1")
    with pytest.raises(DslError, match="U1"):
        parts["U1"].zone_connection(*args, **kwargs)
    assert "U1" not in pad_zones(design)


def test_refused_calls() -> None:
    """Scenario "Refused calls": a second request for the pad, and an index beside a request without."""
    _, parts = design_with("U1")
    u1 = parts["U1"]
    u1.zone_connection(9, "solid")
    with pytest.raises(DslError, match=r"U1.*9"):
        u1.zone_connection(9, "thermal")
    with pytest.raises(DslError, match=r"U1.*9"):
        u1.zone_connection(9, "thermal", index=0)
    u1.zone_connection(4, "solid", index=0)
    with pytest.raises(DslError, match=r"U1.*4"):
        u1.zone_connection(4, "thermal")
    with pytest.raises(DslError, match=r"U1.*4"):
        u1.zone_connection(4, "thermal", index=0)
    u1.zone_connection(4, "thermal", index=1)
    assert sorted(u1.pad_zone_requests) == [("4", 0), ("4", 1), ("9", None)]


def test_paths_in_order_and_parts_without_requests_left_out() -> None:
    design = Design("pad-zones")
    power = Module("power")
    r1, r2 = (Part(ref, "Mini:Mini_R", "Mini:Mini_R_0603") for ref in ("R1", "R2"))
    power.add(r2)
    design.add(power, r1, Part("R3", "Mini:Mini_R", "Mini:Mini_R_0603"))
    r2.zone_connection(1, "solid")
    r1.zone_connection(1, "none")
    found = pad_zones(design)
    assert list(found) == ["R1", "power/R2"]
    with pytest.raises(TypeError):
        found["R9"] = ()  # type: ignore[index]


def test_requests_do_not_change_the_model() -> None:
    plain, _ = design_with("R1")
    design, parts = design_with("R1")
    parts["R1"].zone_connection(1, "solid", locked=True)
    assert dsl.to_model(design) == dsl.to_model(plain)
    assert dsl.fields(design) == dsl.fields(plain) and dsl.placements(design) == dsl.placements(plain)


def test_re_exports() -> None:
    assert dsl.PadZoneRequest is PadZoneRequest and dsl.pad_zones is pad_zones
    assert {"PadZoneRequest", "pad_zones"} <= set(dsl.__all__)
