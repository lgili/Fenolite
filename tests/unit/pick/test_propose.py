# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Supplier proposals (change c0254; part-selection, "Supplier proposals", "Unverified rows")."""

from __future__ import annotations

import pytest

from fenolite.catalog.devices import parse_device
from fenolite.core.errors import FormatError
from fenolite.pick.match import match
from fenolite.pick.propose import file_name, proposals, read_rows
from fenolite.pick.query import parse_query
from fenolite.pick.rows import PROJECT, device_row

CSV = (
    "id,kind,value,footprint,case,tolerance,dielectric,voltage\n"
    "Vendor:C1,capacitor,10uF,Fenolite:Chip_0805,0805,10%,X7R,25V\n"
    "Vendor:C2,capacitor,10uF,Fenolite:Chip_0805,0805,10%,X7R,10V\n"
    "Vendor:R1,resistor,1k,Fenolite:Chip_0603,0603,1%,,\n"
)


def test_proposals_from_a_file() -> None:
    query = parse_query("capacitor(10uF, rating>=25V)")
    found, skipped = proposals(query, read_rows(CSV, file="rows.csv"), source="rows.csv")
    assert [item.device.id for item in found] == ["Vendor:C1"] and len(skipped) == 2
    record = parse_device(found[0].text, file="vendor_c1.toml")
    assert (
        record.evidence == "UNVERIFIED"
        and record.kind == "capacitor"
        and file_name(record.id) == "vendor_c1.toml"
    )
    assert "rows.csv, line 2" in found[0].text


def test_json_rows() -> None:
    rows = read_rows(
        '[{"id": "Vendor:C9", "kind": "capacitor", "value": "1uF", "footprint": "Fenolite:Chip_0603"}]',
        file="r.json",
    )
    found, _ = proposals(parse_query("capacitor(1uF)"), rows, source="r.json")
    assert [item.file for item in found] == ["vendor_c9.toml"]


def test_a_proposal_is_not_picked_by_itself() -> None:
    query = parse_query("capacitor(10uF, rating>=25V)")
    found, _ = proposals(query, read_rows(CSV, file="rows.csv"), source="rows.csv")
    row = device_row(
        parse_device(found[0].text), origin=PROJECT, catalog="project:devices/proposed/vendor_c1.toml"
    )
    assert row is not None and row.unverified
    result = match(query, (row,))
    assert result.matches == () and result.excluded[0].reason == "unverified"
    named = parse_query("capacitor(10uF, rating>=25V, row=Vendor:C1)")
    assert match(named, (row,)).best is row


@pytest.mark.parametrize(
    "line",
    [
        "Fenolite:C1,capacitor,10uF,Fenolite:Chip_0805",
        "Vendor:C1,diode,10uF,Fenolite:Chip_0805",
        "Vendor:C1,capacitor,ten,Fenolite:Chip_0805",
    ],
)
def test_bad_rows(line: str) -> None:
    with pytest.raises(FormatError):
        proposals(
            parse_query("capacitor(10uF)"),
            read_rows(f"id,kind,value,footprint\n{line}\n", file="r.csv"),
            source="r.csv",
        )
