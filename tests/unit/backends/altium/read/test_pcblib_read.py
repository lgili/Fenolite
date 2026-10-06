# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""PCB library reading (capability altium-pcb-reader, "PCB library reading", change c0041)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from _altium_long import library, long_pad, long_text, long_track

from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import PadRecord, TextRecord

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbLib"
LONG = "A/VERY-LONG-NAME-OF-MORE-THAN-31-CHARACTERS"
SHORT = "A_VERY-LONG-NAME-OF-MORE-THAN-3"


def test_fenolites_library() -> None:
    data = BLINK.read_bytes()
    lib = read_pcblib(data)
    assert lib.header_text == "PCB 6.0 Binary Library File"
    assert lib.version == 5.01
    assert lib.unique_id is not None and len(lib.unique_id) == 8
    assert [f.name for f in lib.footprints] == list(lib.names) and len(lib.names) == 3
    assert lib.board.kind == "Protel_Advanced_PCB_Library" and lib.board.origin is None
    assert len(lib.board.stack) == 9
    assert lib.issues == ()
    compound = open_compound(data)
    for footprint in lib.footprints:
        indexes = [i for i, p in enumerate(footprint.primitives) if isinstance(p, PadRecord)]
        assert indexes and all(i in footprint.unique_ids for i in indexes)
        assert footprint.rebuild() == compound.read(f"{footprint.storage}/Data")
        assert footprint.parameters.get("PATTERN") == footprint.name
        assert lib.footprint(footprint.name) is footprint
    assert lib.footprint("nothing") is None
    assert "Library" in lib.storages and "Data" in lib.storages["Library"]
    assert "FileHeader" in lib.storages[""]


def test_footprint_under_a_section_key() -> None:
    data = library(
        {LONG: [long_pad(114, 0)]},
        storage_names={LONG: SHORT},
        section_keys=True,
        patterns={LONG: "OTHER"},
    )
    lib = read_pcblib(data)
    (footprint,) = lib.footprints
    assert footprint.name == LONG and footprint.storage == SHORT
    assert lib.issues == ()


def test_footprint_found_by_pattern_and_by_name() -> None:
    by_pattern = read_pcblib(library({"R1": [long_track(49)]}, storage_names={"R1": "STORAGE"}))
    assert [(f.name, f.storage) for f in by_pattern.footprints] == [("R1", "STORAGE")]
    by_name = read_pcblib(library({"r1": [long_track(49)]}, names=["R1"], patterns={"r1": "X"}))
    assert [(f.name, f.storage) for f in by_name.footprints] == [("R1", "r1")]
    assert by_name.issues == ()


def test_listed_footprint_without_a_storage() -> None:
    lib = read_pcblib(library({"A": [long_track(36)]}, names=["A", "X"]))
    assert [f.name for f in lib.footprints] == ["A"]
    (problem,) = lib.issues
    assert problem.code == "altium.pcb-read.missing-stream" and problem.severity == "error"
    assert problem.where == "Library/Data"


def test_listed_footprint_without_a_storage_strict() -> None:
    from fenolite.backends.altium.read.pcbprims import PcbReadError

    with pytest.raises(PcbReadError) as raised:
        read_pcblib(library({"A": [long_track(36)]}, names=["A", "X"]), strict=True)
    assert raised.value.locator == "Library/Data"


def test_unlisted_footprint() -> None:
    lib = read_pcblib(library({"A": [long_track(36)], "B": [long_track(45)]}, names=["A"]))
    assert [f.name for f in lib.footprints] == ["A", "B"]
    (problem,) = lib.issues
    assert problem.code == "altium.pcb-read.unlisted-footprint" and problem.severity == "info"


def test_header_count_differs() -> None:
    lib = read_pcblib(library({"A": [long_track(36)]}, header_counts={"A": 2}))
    (problem,) = lib.issues
    assert problem.code == "altium.pcb-read.count-mismatch" and problem.where == "A/Header"


def test_footprint_fields_and_wide_strings() -> None:
    text = long_text(252, text="short", wide_index=1)
    data = library(
        {"F": [long_pad(194, 651), text]},
        unique_ids={"F": [(0, "Pad")]},
        wide={"F": "|ENCODEDTEXT0=65|ENCODEDTEXT1=937,49"},
    )
    (footprint,) = read_pcblib(data).footprints
    assert footprint.height == Fraction(100_000) and footprint.description == "d"
    assert dict(footprint.wide_strings) == {0: "A", 1: "Ω1"}
    pad, label = footprint.primitives
    assert isinstance(pad, PadRecord) and isinstance(label, TextRecord)
    assert label.text == "Ω1" and label.short_text == "short"
    assert dict(footprint.unique_ids) == {0: "ID000000"}
    assert footprint.pads == (pad,)
    assert set(footprint.streams) >= {"Header", "Parameters", "WideStrings", "Data"}
