# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The versions of the shipped library records (change c0259; capability library-records, "Record versions"
and "Interface changes make new ids")."""

from __future__ import annotations

from dataclasses import replace

from fenolite.catalog import CATALOG_VERSION
from fenolite.catalog.records import (
    PackageRecord,
    PinsRecord,
    VersionEntry,
    Versions,
    entries_sha256,
    parse_record,
    record_text,
    shipped_tree,
    shipped_versions,
    updated_versions,
    version_problems,
)


def test_shipped_records_follow_the_version_rules() -> None:
    assert version_problems(shipped_tree().records, shipped_versions()) == []
    assert CATALOG_VERSION == shipped_versions().catalog_version


def _chip() -> PackageRecord:
    record = shipped_tree().get("package", "Fenolite:Chip_0603")
    assert isinstance(record, PackageRecord)
    return record


def _with(record: PackageRecord | PinsRecord, versions: Versions) -> list[str]:
    others = [
        r for r in shipped_tree().records if r.header.id != record.header.id or type(r) is not type(record)
    ]
    return version_problems([*others, record], versions)


def test_changed_land_without_a_new_version() -> None:
    chip = _chip()
    pad = replace(chip.pads[0], size=replace(chip.pads[0].size, w=chip.pads[0].size.w + 10_000))
    changed = replace(chip, pads=(pad, *chip.pads[1:]))
    problems = _with(changed, shipped_versions())
    assert problems == ["Fenolite:Chip_0603: its definition changed; give it a MINOR version above 1.0.1"]
    bumped = replace(changed, header=replace(changed.header, version="1.1.0"))
    assert [p for p in _with(bumped, shipped_versions()) if "Chip_0603" in p] == [
        "Fenolite:Chip_0603: VERSIONS.toml is stale; run `uv run python tools/catalog/versions.py --update` "
        "after the review"
    ]


def test_metadata_change_is_a_patch() -> None:
    record = shipped_tree().get("pins", "Fenolite:Resistor")
    assert isinstance(record, PinsRecord)
    changed = replace(record, header=replace(record.header, sources=(*record.header.sources, "S-0315")))
    assert any("PATCH version above 1.0.1" in p for p in _with(changed, shipped_versions()))
    patched = replace(changed, header=replace(changed.header, version="1.0.2"))
    records = [
        r
        for r in shipped_tree().records
        if r.header.id != "Fenolite:Resistor" or not isinstance(r, PinsRecord)
    ]
    updated = updated_versions([*records, patched], shipped_versions())
    assert version_problems([*records, patched], updated) == []
    assert updated.catalog_version != shipped_versions().catalog_version
    assert parse_record(record_text(patched)) == patched


def test_pad_renumbered_under_an_id() -> None:
    chip = _chip()
    renumbered = replace(chip, pads=(chip.pads[0], replace(chip.pads[1], number="3")))
    renumbered = replace(renumbered, header=replace(renumbered.header, version="1.1.0"))
    problems = _with(renumbered, shipped_versions())
    assert any("interface changed" in p and "new id" in p and "deprecation" in p for p in problems), problems


def test_removed_id_reused() -> None:
    versions = shipped_versions()
    entries = (*versions.entries, VersionEntry("package", "Fenolite:Old", removed=True))
    marked = Versions(versions.catalog_version, entries_sha256(entries), entries)
    old = replace(_chip(), header=replace(_chip().header, id="Fenolite:Old"))
    problems = version_problems([*shipped_tree().records, old], marked)
    assert any(p.startswith("Fenolite:Old: the id was removed") for p in problems)


def test_missing_and_extra_entries() -> None:
    versions = shipped_versions()
    records = [r for r in shipped_tree().records if r.header.id != "Fenolite:Chip_0603"]
    assert any(
        "Fenolite:Chip_0603: in VERSIONS.toml but not shipped" in p
        for p in version_problems(records, versions)
    )
    updated = updated_versions(records, versions)
    assert any(e.id == "Fenolite:Chip_0603" and e.removed for e in updated.entries)
    assert version_problems(records, updated) == []


def test_major_stays_one() -> None:
    chip = _chip()
    major = replace(chip, header=replace(chip.header, version="2.0.0"))
    assert any("MAJOR stays 1" in p for p in _with(major, shipped_versions()))
