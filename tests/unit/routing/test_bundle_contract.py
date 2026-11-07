# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored bundle schema/identity and unchanged legacy decision cases (c0367)."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest
from _searchbench import point

from fenolite.core.errors import FormatError
from fenolite.model.board import Track
from fenolite.routing.bundles import data, make
from fenolite.routing.decisions import Decisions, dumps, loads
from fenolite.routing.protocol import Candidate, RoutingResult


def members():
    track = Track(id="trk_a", start=point(1, 1), end=point(4, 1), width=100_000, layer="F.Cu", net_id="a")
    a = Candidate("c-a", "connection:A", "search", tracks=(track,))
    b = replace(a, id="c-b", subject="connection:B", tracks=(replace(track, id="trk_b", net_id="b"),))
    return a, b


def test_bundle_identity_is_order_independent_but_binds_every_geometry_and_input() -> None:
    a, b = members()
    bundle = make((a, b), "1" * 64)
    assert bundle == make((b, a), "1" * 64)
    assert bundle.id != make((a, b), "2" * 64).id
    changed = replace(b, tracks=(replace(b.tracks[0], width=200_000),))
    assert bundle.id != make((a, changed), "1" * 64).id
    assert data(bundle)["members"] == ["c-a", "c-b"]
    assert all(c.bundle == bundle.id for c in bundle.members)
    assert not RoutingResult(bundles=(bundle,)).tracks
    with pytest.raises(FrozenInstanceError):
        bundle.id = "changed"


@pytest.mark.parametrize("bad", ["", "f" * 63, "Z" * 64])
def test_input_identity_is_a_real_digest(bad) -> None:
    with pytest.raises(ValueError):
        make(members(), bad)


def test_single_duplicate_and_nested_members_are_refused() -> None:
    a, b = members()
    for held in ((a,), (a, a), (a, replace(b, id=a.id)), (a, replace(b, subject=a.subject))):
        with pytest.raises(ValueError):
            make(held, "1" * 64)
    bundle = make((a, b), "1" * 64)
    with pytest.raises(ValueError):
        make(bundle.members, "1" * 64)


def test_legacy_decision_bytes_and_independent_defaults_are_unchanged() -> None:
    raw = (
        b'{\n  "board": "authored.kicad_pcb",\n  "locked": [],\n'
        b'  "rejected": [],\n  "schema": "fenolite.route-decisions.v0"\n}\n'
    )
    assert dumps(loads(raw)) == raw
    assert loads(raw) == Decisions("authored.kicad_pcb")
    assert not members()[0].bundle and not RoutingResult().bundles
    future = json.loads(raw)
    future["schema"] = "fenolite.route-decisions.v999"
    with pytest.raises(FormatError):
        loads(json.dumps(future))
