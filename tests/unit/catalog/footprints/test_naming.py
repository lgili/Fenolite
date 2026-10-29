# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Names of Fenolite-authored packages and the generator stamp (change c0260, scenarios "Name checked against
numbers", "Stamp in the description")."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.naming import mm
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]
NAMING_PAGE = Path(__file__).resolve().parents[4] / "docs" / "formats" / "library" / "naming.md"


def test_name_checked_against_numbers(record: Record) -> None:
    def wrong_pitch(raw: dict[str, Any]) -> None:
        raw["pitch"] = "0.65mm"
        raw["land"]["pad"] = {"length": "1.52mm", "width": "0.4mm"}

    result = generate(record("soic8", wrong_pitch))
    assert result.footprint is None
    assert [i.code for i in result.issues] == ["package.name-mismatch"] and "P1.27" in result.issues[
        0
    ].message


@pytest.mark.parametrize(
    ("stem", "name", "field"),
    [
        ("soic8", "SOIC8_B5x3.9_P1.27", "B5x3.9"),
        ("soic8", "SOIC14_B4.9x3.9_P1.27", "SOIC14"),
        ("qfn16", "QFN16_B3x3_P0.5_EP2x2", "EP2x2"),
        ("header1x2", "HDR1x3_P2.54", "HDR1x3"),
    ],
)
def test_each_field_is_checked(record: Record, stem: str, name: str, field: str) -> None:
    result = generate(record(stem, lambda raw: raw.update(name=name)))
    assert result.footprint is None and field in result.issues[0].message


def test_other_names_are_not_checked(record: Record) -> None:
    assert generate(record("soic8", lambda raw: raw.update(name="SOIC8_onsemi_751_07"))).footprint is not None


def test_stamp_in_the_description(record: Record) -> None:
    result = generate(record("soic8", lambda raw: raw.pop("land")))
    assert result.stamp == "gullwing/1 lands/1 drawing/1 nominal"
    assert (
        result.footprint is not None
        and "gullwing/1 lands/1 drawing/1 nominal" in result.footprint.description
    )


def test_millimetres_without_trailing_zeros() -> None:
    assert (mm(4_900_000), mm(3_000_000), mm(1_270_000), mm(605_000)) == ("4.9", "3", "1.27", "0.605")


def test_naming_page() -> None:
    page = NAMING_PAGE.read_text(encoding="utf-8")
    assert "<FAMILY><pins>_B<L>x<W>" in page and "package.name-mismatch" in page and "S-0862" in page
