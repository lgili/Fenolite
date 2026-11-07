# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored geometries and planted faults for c0264's import screening scenarios."""

from __future__ import annotations

from dataclasses import replace

import pytest
from _library_import import DATA, PACKAGE

from fenolite.catalog.footprints import generate, read_package
from fenolite.core.coords import Point, Size
from fenolite.library.importer import classify, crosscheck
from fenolite.library.importer.crosscheck import sources_disagree
from fenolite.library.importer.sources import read_sources


def source():
    return read_sources([DATA / "exb6202.zip"]).footprint


def test_matching_download_has_no_warning_or_error() -> None:
    got = crosscheck(source(), PACKAGE)
    assert got.family == "gullwing" and got.reference == "EXB6202"
    assert not got.issues and len(got.rows) == 8
    assert got.to_data()["tolerances"]["pitch_nm"] == 10_000


def test_clockwise_numbering_and_pin1_are_errors_with_explicit_package() -> None:
    footprint = source()
    renumbered = replace(
        footprint, pads=tuple(replace(p, number=str(9 - int(p.number))) for p in footprint.pads)
    )
    found = crosscheck(renumbered, PACKAGE)
    assert {i.code for i in found.issues if i.severity == "error"} >= {
        "library.import-numbering",
        "library.import-pin1",
    }
    assert not [i for i in crosscheck(renumbered).issues if i.severity == "error"]


def test_one_pad_moved_reports_its_measured_and_reference_nm() -> None:
    footprint = source()
    moved = replace(
        footprint,
        pads=tuple(
            replace(p, position=Point(p.position.x + 200_000, p.position.y)) if p.number == "3" else p
            for p in footprint.pads
        ),
    )
    got = crosscheck(moved)
    assert [(i.code, i.where) for i in got.issues] == [("library.import-land", "3")]
    assert (
        "measured" in got.issues[0].message
        and "reference" in got.issues[0].message
        and "nm" in got.issues[0].message
    )


def test_two_source_footprints_disagree_on_pad_width() -> None:
    footprint = source()
    wider = replace(
        footprint,
        pads=tuple(
            replace(p, size=Size(p.size.w + 500_000, p.size.h)) if p.number == "3" else p
            for p in footprint.pads
        ),
    )
    got = sources_disagree(footprint, wider)
    assert len(got) == 1 and got[0].code == "library.import-sources-disagree" and "pad 3" in got[0].message


@pytest.mark.parametrize(
    ("filename", "family"),
    [
        ("chip0603", "chip"),
        ("sod123", "molded"),
        ("soic8", "gullwing"),
        ("sot23_5", "gullwing"),
        ("qfn16", "nolead"),
        ("bga12", "grid"),
        ("to220", "to"),
        ("dip8", "dip"),
        ("header1x2", "header"),
    ],
)
def test_classifier_supports_the_generator_families(filename: str, family: str) -> None:
    package = read_package((DATA.parent / "packages" / f"{filename}.toml").read_text())
    footprint = generate(package).footprint
    assert footprint is not None
    match = classify(footprint)
    assert match is not None and match.family == family
    assert not crosscheck(footprint, package).issues


def test_unknown_family_and_package_mismatch() -> None:
    footprint = source()
    assert (
        crosscheck(replace(footprint, pads=footprint.pads[:1])).issues[0].code
        == "library.import-family-unknown"
    )
    chip = (DATA.parent / "packages/chip0603.toml").read_text()
    assert "library.import-package-mismatch" in {i.code for i in crosscheck(footprint, chip).issues}


def test_connector_is_only_selected_by_explicit_package() -> None:
    package = read_package((DATA.parent / "packages/connector_xh.toml").read_text())
    footprint = generate(package).footprint
    assert footprint is not None
    assert crosscheck(footprint, package).family == "connector"


def test_pad_count_and_pitch_are_reported() -> None:
    footprint = source()
    fewer = replace(footprint, pads=footprint.pads[:-1])
    assert "library.import-pad-count" in {i.code for i in crosscheck(fewer, PACKAGE).issues}
    stretched = replace(
        footprint,
        pads=tuple(replace(p, position=Point(p.position.x, p.position.y * 2)) for p in footprint.pads),
    )
    assert "library.import-pitch" in {i.code for i in crosscheck(stretched, PACKAGE).issues}
