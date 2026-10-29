# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Device records of version 1 and their orderable parts (change c0259; capability library-records,
"Orderable parts inherit from their device" and "Parts never change the interface"). The records are
authored for Fenolite as test data and illustrative."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.catalog.devices import parse_device
from fenolite.catalog.records import (
    DeviceRecord,
    effective_part,
    load_tree,
    parse_record,
    record_text,
    resolved_part,
)
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "tests" / "data" / "library"
DEVICE = (LIBRARY / "devices" / "example_reg.toml").read_text(encoding="utf-8")


def _refused(text: str) -> FormatError:
    with pytest.raises(FormatError) as caught:
        parse_record(text, file="devices/x.toml")
    assert getattr(caught.value, "code", None) == "FEN-3004", caught.value
    return caught.value


def test_a_grade_variant_inherits_the_packing() -> None:
    tree = load_tree(LIBRARY)
    record = tree.get("device", "Example:REG_TWO")
    assert isinstance(record, DeviceRecord)
    parts = tree.parts["Example:REG_TWO"]
    part = resolved_part(parts, "EXR100QDR")
    assert (part.packing, part.grade, part.lifecycle) == ("reel 2500", "automotive", "active")
    device = effective_part(record.device, parts, "EXR100QDR")
    assert device.pins == record.device.pins and device.footprint == "Proj:Two_Pad"
    assert device.id == "Example:REG_TWO@EXR100QDR" and device.mpn == "EXR100QDR"
    assert device.manufacturer == "Example Semi"


def test_cycle_refused() -> None:
    text = DEVICE + '\n[[part]]\nmpn = "A"\nextends = "B"\n\n[[part]]\nmpn = "B"\nextends = "A"\n'
    error = _refused(text)
    assert "A" in str(error) and "B" in str(error) and "extend each other" in str(error)
    assert "extends" in str(_refused(DEVICE + '\n[[part]]\nmpn = "C"\nextends = "NONE"\n'))
    assert "twice" in str(_refused(DEVICE + '\n[[part]]\nmpn = "EXR100DR"\n'))


def test_footprint_in_a_part() -> None:
    error = _refused(DEVICE + '\n[[part]]\nmpn = "D"\nfootprint = "Fenolite:Chip_0805"\n')
    assert "footprint" in str(error) and "a different interface is a different device" in str(error)


def test_wider_temperature() -> None:
    wider = (
        DEVICE
        + '\n[[part]]\nmpn = "W"\n'
        + 'ratings = { temperature = { operating = { min = "-40degC", max = "125degC" } } }\n'
    )
    assert "ratings.temperature" in str(_refused(wider))
    narrower = (
        DEVICE
        + '\n[[part]]\nmpn = "N"\n'
        + 'ratings = { temperature = { operating = { min = "0degC", max = "70degC" } } }\n'
    )
    assert isinstance(parse_record(narrower), DeviceRecord)


def test_device_record_round_trip() -> None:
    record = parse_record(DEVICE)
    assert isinstance(record, DeviceRecord) and record.header.version == "1.1.0"
    assert parse_record(record_text(record)) == record


def test_version_0_files_are_still_read() -> None:
    text = (ROOT / "tests" / "data" / "devices" / "example_buck.toml").read_text(encoding="utf-8")
    record = parse_record(text)
    assert isinstance(record, DeviceRecord)
    assert record.device == parse_device(text) and record.header.version == "0.0.0"
    assert record.header.licence == "" and parse_record(record_text(record)) == record


def test_part_record_names_its_id() -> None:
    text = (LIBRARY / "parts" / "example_reg_grade.toml").read_text(encoding="utf-8")
    assert "id" in str(
        _refused(text.replace('id = "Example:REG_TWO@EXR100QDR"', 'id = "Example:REG_TWO@OTHER"'))
    )
