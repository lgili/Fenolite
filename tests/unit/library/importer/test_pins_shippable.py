# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One pin template for both imports; local origins are never shippable (c0264)."""

from __future__ import annotations

import tomllib
from dataclasses import replace

import pytest
from _library_import import DATA

from fenolite.catalog import get_footprint, get_symbol
from fenolite.catalog.records import record_text
from fenolite.library.importer import shippable
from fenolite.library.importer.records import make_records
from fenolite.library.importer.sources import ImportUsageError, read_sources
from fenolite.library.importer.templates import pin_template


def test_pins_share_catalog_identity_names_and_override() -> None:
    symbol, footprint = get_symbol("Fenolite:Resistor"), get_footprint("Fenolite:Chip_0603")
    pins, issues = pin_template(symbol, footprint, [])
    assert not issues and [p.function for p in pins] == ["A", "B"]
    pins, issues = pin_template(symbol, footprint, ["X=1:2", "Y=2:1"])
    assert not issues and pins[0].pin_pads == (("1", "2"),)
    with pytest.raises(ImportUsageError):
        pin_template(symbol, footprint, ["invalid"])
    _, issues = pin_template(symbol, footprint, ["X=1:MISSING"])
    assert "catalog.pin-without-pad" in {i.code for i in issues}
    _, issues = pin_template(
        symbol, replace(footprint, pads=(*footprint.pads, replace(footprint.pads[0], number="EP"))), []
    )
    assert "catalog.pad-unmapped" in {i.code for i in issues}


def test_shippable_false_for_all_import_records() -> None:
    imported = make_records(read_sources([DATA / "exb6202.zip"]), device_id=None, date="2026-11-01")
    for record in imported.records:
        assert not shippable(record) and not shippable(record.header)
        assert not shippable(tomllib.loads(record_text(record)))
    assert not shippable({"licence": "see source terms"})
    assert not shippable({"origin": {"shippable": False}})
    assert shippable({"licence": "CC0-1.0"})


def test_shippable_check_in_a_library_item(demo) -> None:
    from fenolite.library.audit import audit

    imported = make_records(read_sources([DATA / "exb6202.zip"]), device_id=None, date="2026-11-01")
    folder = demo / "devices/cc0/Demo/EXB"
    (folder / "device.toml").write_bytes(imported.files["device.toml"])
    issues = [i for i in audit(demo).issues if i.code == "library.not-shippable"]
    assert len(issues) == 1 and "Imported:EXB6202" in issues[0].message


def test_legacy_import_stamp_is_not_shippable() -> None:
    assert not shippable({"provenance": {"tool": "fenolite catalog import"}})
