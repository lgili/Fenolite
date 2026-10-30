# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The manufacturer's land and the evidence of generated lands (change c0260, requirements "Manufacturer land
override", "Evidence of generated lands")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def test_override_recorded(record: Record) -> None:
    result = generate(record("soic8"))
    fp = result.footprint
    assert fp is not None
    assert {(pad.size.w, pad.size.h) for pad in fp.pads} == {(1_520_000, 600_000)}
    assert {abs(pad.position.x) for pad in fp.pads} == {2_750_000}
    assert result.land.source == "manufacturer" and result.land.table is None
    assert (result.land.z, result.land.g, result.land.x) == (7_020_000, 3_980_000, 600_000)
    assert fp.description.endswith("land: manufacturer S-0961 soldering footprint")
    assert result.stamp == "gullwing/1 manufacturer drawing/1" and result.stamp in fp.description
    infos = [i for i in result.issues if i.code == "package.land-override"]
    assert len(infos) == 1 and infos[0].severity == "info"
    deltas = result.land.deltas
    assert set(deltas) == {"pad_length", "pad_width", "row_spacing"}
    largest = max(deltas, key=lambda key: abs(deltas[key]))
    assert f"{largest} {deltas[largest]:+d} nm" in infos[0].message


def test_override_without_goals_still_reports(record: Record) -> None:
    from fenolite.catalog.footprints.lands import LandTable

    result = generate(record("soic8"), table=LandTable(version=1))
    assert result.footprint is not None and result.land.deltas == {}
    override = next(i for i in result.issues if i.code == "package.land-override")
    assert "no calculated land to compare" in override.message


def test_calculated_land_stays_inferred(record: Record) -> None:
    def verified_without_land(raw: dict[str, Any]) -> None:
        raw["evidence"] = "CORPUS-VERIFIED"
        raw.pop("land")

    calculated = generate(record("soic8", verified_without_land))
    assert calculated.footprint is not None and calculated.land.evidence == "INFERRED"
    assert calculated.footprint.description.endswith("land: calculated lands/1 nominal (INFERRED)")
    given = generate(record("soic8", lambda raw: raw.update(evidence="CORPUS-VERIFIED")))
    assert given.land.evidence == "CORPUS-VERIFIED"
    lower = generate(record("soic8", lambda raw: raw.update(evidence="UNVERIFIED")))
    assert lower.land.evidence == "UNVERIFIED"  # no generation raises a label


def test_manufacturer_land_is_used_unchanged(record: Record) -> None:
    def tight(raw: dict[str, Any]) -> None:
        raw["land"]["pad"] = {"length": "1.52mm", "width": "1.20mm"}  # wider than pitch - pad_gap

    result = generate(record("soic8", tight))
    assert result.footprint is not None
    assert {pad.size.h for pad in result.footprint.pads} == {1_200_000}
    assert not [i for i in result.issues if i.code == "package.pads-clipped"]
