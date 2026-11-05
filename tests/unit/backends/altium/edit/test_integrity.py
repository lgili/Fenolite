# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The integrity check of an Altium PCB document, on the kit board and on planted faults (c0241, task 2.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.edit import integrity
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import v7_layer
from fenolite.core.evidence import Level
from tests.unit.backends.altium.edit import faults

MECHANICAL_13, MECHANICAL_15 = 69, 71


def _codes(data: bytes) -> list[str]:
    return [i.code for i in integrity.check_pcbdoc(data, file="edit.PcbDoc")]


def test_the_kit_board_has_no_finding(board: Path) -> None:
    assert integrity.check_pcbdoc(board.read_bytes(), file=board.name) == ()
    assert integrity.EVIDENCE.level is Level.INFERRED
    assert not integrity.CONFIRMED


def test_a_gap_in_the_pieces_of_a_polygon_is_named(board: Path) -> None:
    [finding] = integrity.check_pcbdoc(faults.subpoly_gap(board.read_bytes()))
    assert finding.code == "altium.integrity.subpoly-gap" and finding.severity == "warning"
    assert "SUBPOLYINDEX 0, 1, 3, without 2" in finding.message and "'GND'" in finding.message
    assert finding.where == "Regions6/Data#1" and "H-A-INTEG-SUBPOLY" in finding.hint


@pytest.mark.parametrize("name", sorted(faults.FAULTS))
def test_each_planted_fault_gives_its_one_finding(board: Path, name: str) -> None:
    plant, code = faults.FAULTS[name]
    assert _codes(plant(board.read_bytes())) == [code]


def test_two_pads_with_one_unique_id_are_named(board: Path) -> None:
    state = State.of(board.read_bytes())
    entries = state.properties("UniqueIDPrimitiveInformation")
    first = dict(entries[0].fields)["UNIQUEID"]
    state.replace(
        "UniqueIDPrimitiveInformation",
        1,
        rec.set_property(state.get("UniqueIDPrimitiveInformation")[1], {"UNIQUEID": first}),
    )
    [finding] = integrity.check_pcbdoc(state.data())
    assert finding.code == "altium.integrity.unique-id-twice" and finding.severity == "warning"
    assert finding.message.count("pad ") == 2 and "UniqueIDPrimitiveInformation" in finding.message
    assert first in finding.message


def test_an_entry_that_names_no_pad(board: Path) -> None:
    state = State.of(board.read_bytes())
    raw = state.get("UniqueIDPrimitiveInformation")[0]
    state.replace("UniqueIDPrimitiveInformation", 0, rec.set_property(raw, {"PRIMITIVEINDEX": "99"}))
    assert "altium.integrity.unique-id-index" in _codes(state.data())


def test_two_polygons_with_one_pour_index(board: Path) -> None:
    state = State.of(board.read_bytes())
    state.replace("Polygons6", 1, rec.set_property(state.get("Polygons6")[1], {"POURINDEX": "0"}))
    [finding] = integrity.check_pcbdoc(state.data())
    assert finding.code == "altium.integrity.pour-index-twice"
    assert "'GND'" in finding.message and "'VIN'" in finding.message and "POURINDEX 0" in finding.message


def test_a_region_whose_layer_byte_and_v7_layer_differ(board: Path) -> None:
    state = State.of(board.read_bytes())
    raw = state.get("Regions6")[0]
    assert rec.prefix_of(raw)[0] == MECHANICAL_13
    state.replace("Regions6", 0, rec.set_region_keys(raw, {"V7_LAYER": v7_layer(MECHANICAL_15)}))
    [finding] = integrity.check_pcbdoc(state.data())
    assert finding.code == "altium.integrity.layer-fields" and finding.where == "Regions6/Data#0"
    assert "Mechanical 13" in finding.message and "Mechanical 15" in finding.message


def test_every_code_cites_a_row_and_has_its_severities() -> None:
    assert set(integrity.INTEGRITY_ISSUE_CODES) == set(integrity.RULES)
    assert integrity.INTEGRITY_ISSUE_CODES["altium.integrity.parameters-unjudged"] == "info"
    assert all(row.startswith("H-A-") for row in integrity.RULES.values())
