# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated bodies (change c0260, requirement "Generated bodies"; component-body-volumes, "Generated
bodies are known volumes")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from _package_records import every_record

from fenolite.catalog.footprints import generate, model_path, positions_of
from fenolite.catalog.footprints.record import Package
from fenolite.core.ids import derived_id
from fenolite.model.board import ComponentBody
from fenolite.model.library import FootprintDef

Record = Callable[..., Package]


def _footprint(package: Package, **kwargs: Any) -> FootprintDef:
    footprint = generate(package, **kwargs).footprint
    assert footprint is not None
    return footprint


def _extent(body: ComponentBody) -> tuple[int, int]:
    xs, ys = [p.x for p in body.outline], [p.y for p in body.outline]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_soic_bodies(record: Record) -> None:
    fp = _footprint(record("soic8"))
    body, *leads = fp.bodies
    assert body.name == "body" and (body.z_min, body.z_max) == (100_000, 1_750_000)
    assert _extent(body) == (3_900_000, 4_900_000)
    assert len(leads) == 16 and [b.name for b in leads[:2]] == ["lead:1:foot", "lead:1:shoulder"]
    assert all(b.kind == "extruded" and not b.projection_unknown for b in fp.bodies)
    foot = leads[0]
    assert (foot.z_min, foot.z_max) == (0, 220_000)  # lead thickness nominal
    assert _extent(foot) == (835_000, 420_000)  # nominal lead length and width
    xs = [p.x for p in foot.outline]
    assert min(xs) == -3_000_000  # the lead tip at half the nominal span
    assert body.id == derived_id("bdy", "fenolite.catalog", "Local:SOIC8_B4.9x3.9_P1.27:body")
    assert fp.models == (model_path("Local", "SOIC8_B4.9x3.9_P1.27"),)
    assert fp.models[0] == "${KIPRJMOD}/lib/Local.3dshapes/SOIC8_B4.9x3.9_P1.27.step"


def test_no_height_no_body(record: Record) -> None:
    def no_height(raw: dict[str, Any]) -> None:
        raw["body"] = {"length": raw["body"]["length"], "width": raw["body"]["width"]}

    fp = _footprint(record("soic8", no_height))
    assert fp.bodies == () and fp.models == ()


def test_through_hole_pins_reach_below_the_board(record: Record) -> None:
    fp = _footprint(record("dip8"))
    pins = [b for b in fp.bodies if b.name.startswith("pin:")]
    assert len(pins) == 8 and all(b.z_min == -3_365_000 and b.z_max == 0 for b in pins)
    header = _footprint(record("header1x2"))
    tops = {b.z_max for b in header.bodies if b.name.startswith("pin:")}
    assert tops == {2_690_000 + 6_000_000}  # above the insulator by the pin's length above


def test_drawing_0_has_bodies_but_no_model(record: Record) -> None:
    fp = _footprint(record("soic8", lambda raw: raw["generate"].update(drawing=0)))
    assert fp.bodies and fp.models == ()


@pytest.mark.parametrize("package", every_record(), ids=lambda p: p.file)
def test_bodies_are_known_volumes(package: Package) -> None:
    for count in positions_of(package)[:1] or (None,):
        fp = _footprint(package, positions=count)
        names = [b.name for b in fp.bodies]
        assert len(names) == len(set(names))
        for body in fp.bodies:
            assert body.z_min is not None and body.z_max is not None and body.z_min <= body.z_max
            assert len(body.outline) == 4 and not body.projection_unknown
