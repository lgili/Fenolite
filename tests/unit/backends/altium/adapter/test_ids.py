# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identifiers, provenance and bags of the Altium import (capability altium-import, "Identifiers and
provenance" and "Extension bags"; change c0043)."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import EVIDENCE, EXT_KEYS, import_board
from fenolite.backends.altium.adapter.codes import Census
from fenolite.backends.altium.adapter.ids import Exact, Ids, bag
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.design import Design

BLINK = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


def _blink() -> Design:
    data = BLINK.read_bytes()
    return import_board(read_pcbdoc(data), file=BLINK.name, sha256=hashlib.sha256(data).hexdigest())


def test_stable_ids_across_imports() -> None:
    first, second = _blink(), _blink()
    ids = [entity.id for entity in first.entities()]
    assert ids == [entity.id for entity in second.entities()]
    assert len(ids) == len(set(ids))
    assert first.nets_by_name["GND"].id == derived_id("net", "altium", "net:GND")
    assert first.nets_by_name["GND"].native_ids == {"altium": "net:GND"}
    assert first.header.native_ids == {"altium": "altium_pcbdoc"}
    assert first.board is not None and first.board.native_ids == {"altium": "altium_pcbdoc"}
    assert first.rules is not None and first.rules.native_ids == {"altium": "altium_pcbdoc"}


def test_provenance_names_the_file_and_the_record() -> None:
    design = _blink()
    digest = hashlib.sha256(BLINK.read_bytes()).hexdigest()
    assert design.board is not None
    for entity in design.entities():
        assert entity.provenance is not None, entity.id
        assert (entity.provenance.backend, entity.provenance.file) == ("altium", "blink.PcbDoc")
        assert entity.provenance.file_sha256 == digest and entity.provenance.evidence == EVIDENCE
    footprint = design.board.footprints[0]
    assert footprint.provenance is not None and footprint.provenance.locator == "Components6/Data#0"
    assert footprint.native_ids["altium"].startswith("fp:")
    assert footprint.pads[0].provenance is not None
    assert footprint.pads[0].provenance.locator.startswith("Pads6/Data#")
    assert footprint.pads[0].native_ids["altium"].startswith("pad:")


def test_editing_another_track_keeps_the_id() -> None:
    first = rec.track((0, 0), (1000, 0))
    second = rec.track((0, 500), (1000, 500))
    moved = dataclasses.replace(second, y2=700)
    one = import_board(rec.document(tracks=[first, second]), file="a.PcbDoc", sha256=rec.SHA)
    two = import_board(rec.document(tracks=[first, moved]), file="a.PcbDoc", sha256=rec.SHA)
    assert one.board is not None and two.board is not None
    assert one.board.tracks[0].id == two.board.tracks[0].id
    assert one.board.tracks[1].id != two.board.tracks[1].id


def test_equal_content_gets_an_occurrence_counter() -> None:
    same = rec.track((0, 0), (1000, 0))
    design = import_board(rec.document(tracks=[same, same]), file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    assert design.board.tracks[0].id != design.board.tracks[1].id
    assert [i.code for i in design.validate() if i.code == "model.duplicate-id"] == []


def test_a_file_hash_never_enters_an_id() -> None:
    document = rec.document(tracks=[rec.track((0, 0), (1000, 0))], nets=["A"])
    one = import_board(document, file="a.PcbDoc", sha256="1" * 64)
    two = import_board(document, file="b.PcbDoc", sha256="2" * 64)
    assert [e.id for e in one.entities()] == [e.id for e in two.entities()]


def test_original_integers_kept() -> None:
    document = rec.document(tracks=[rec.track((25, 0), (125, 0), width=75)])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    track = design.board.tracks[0]
    assert track.ext["altium"] == ExtBag(None, (("u", "start.x=25,end.x=125,width=75"),))
    assert (track.start, track.end, track.width) == (Point(64, 0), Point(318, 0), 190)


def test_exact_values_leave_the_bag_empty() -> None:
    design = import_board(rec.document(tracks=[rec.track((0, 0), (1000, 0))]), file="a", sha256=rec.SHA)
    assert design.board is not None and design.board.tracks[0].ext == {}


def test_bag_orders_pairs_and_refuses_unknown_keys() -> None:
    found = bag([("net", "GND"), ("u", "a=1"), ("alias", "B"), ("alias", "A")])
    assert found["altium"].payload == (("u", "a=1"), ("net", "GND"), ("alias", "B"), ("alias", "A"))
    assert found["altium"].min_version is None and bag([]) == {}
    with pytest.raises(KeyError):
        bag([("nope", "1")])
    assert len(set(EXT_KEYS)) == len(EXT_KEYS)


def test_exact_records_angles_as_hex() -> None:
    census = Census()
    exact = Exact(census)
    assert exact.angle("rotation", 1e-7) == 0 and exact.length("width", 25) == 64
    assert exact.pairs() == [("u", "width=25"), ("deg", f"rotation={(1e-7).hex()}")]
    assert (census.inexact_lengths, census.inexact_angles) == (1, 1)


def test_a_repeated_native_id_gets_a_suffix() -> None:
    ids = Ids("altium_pcbdoc", EVIDENCE)
    first, second = ids.native("net", "net:A"), ids.native("net", "net:A")
    assert first[1] == {"altium": "net:A"} and second[1] == {"altium": "net:A#2"} and first[0] != second[0]
