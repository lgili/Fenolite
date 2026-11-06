# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rooms and ``WithinRoom`` on the public rows (change c0462, task 2.3; capability imported-rules, "Altium
rooms are rule areas"). No public PCB document holds a room, so each ``WithinRoom`` names a room its board
does not hold (``undefined``); the public rule file holds nine rooms, each read with a straight outline on
the top side (S-0297)."""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rooms import read_rooms
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.scope import Refusal, for_kind, parse_scope
from fenolite.backends.altium.read.scopedoc import scope_document

pytestmark = pytest.mark.needs_corpus

ROWS = manifest_items("altium-pcbdoc")
WITHIN_ROOM = {"altium-third-party-pcbdoc-04": 2, "altium-third-party-pcbdoc-07": 2}
"""Row → its scopes that call ``WithinRoom``: both scopes of one Component Clearance record, naming the room
``BGA Decoupling`` (census of 2026-11-06)."""


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_within_room_names_a_room_the_board_does_not_hold(item: CorpusItem) -> None:
    document = read_pcbdoc(require(item).read_bytes(), file=item.path.name)
    rooms, issues = read_rooms([rule.fields for rule in document.rules])
    assert (rooms, issues) == ((), [])
    scopes = scope_document(document, LayerMap.from_board(document.board).copper_layers())
    assert scopes.rooms == ()
    reasons: Counter[str] = Counter()
    for rule in document.rules:
        for text in (rule.scope1, rule.scope2):
            if text and "WithinRoom" in text:
                found = parse_scope(text, document=for_kind(scopes, rule.rule_kind))
                assert isinstance(found, Refusal), text
                reasons[found.reason] += 1
    expected = WITHIN_ROOM.get(item.id, 0)
    assert reasons == (Counter({"undefined": expected}) if expected else Counter())


def test_the_rooms_of_the_public_rule_file() -> None:
    (item,) = [row for row in manifest_items("altium-text") if row.id == "altium-third-party-rules-01"]
    records = read_rule_file(require(item).read_bytes()).records
    rooms, issues = read_rooms([[(key, value or "") for key, value in record.fields] for record in records])
    assert not issues and len(rooms) == 9
    assert {(room.side, room.lines, room.confinement, len(room.vertices)) for room in rooms} == {
        ("F.Cu", True, "ConfineIn", 5)
    }
    assert all(room.vertices[0] == room.vertices[-1] for room in rooms)
