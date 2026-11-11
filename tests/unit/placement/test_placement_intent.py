# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

import pytest

from fenolite.model.canonical import dumps, loads
from fenolite.placement.intent import PlacementIntent, resolve_intents
from fenolite.placement.topology import PadIdentity

A, B, C = (PadIdentity("footprint", name) for name in ("a", "b", "c"))
SUGGESTION = PlacementIntent("bypass", "proximity", (A, B), "suggested", "circuit", "v0", "match")


def test_suggestion_is_inactive_and_declared_binding_takes_precedence():
    pads = frozenset({A, B, C})
    assert resolve_intents((SUGGESTION,), available_pads=pads)[0].effective is None
    confirmed = replace(SUGGESTION, origin="confirmed")
    declared = replace(confirmed, origin="declared", endpoints=(A, C), required=True)
    reviewed = loads(dumps(declared), PlacementIntent)
    (result,) = resolve_intents((confirmed, SUGGESTION, reviewed), available_pads=pads)
    assert result.effective == declared
    assert SUGGESTION in result.alternatives
    with pytest.raises(ValueError, match="suggested intent"):
        replace(SUGGESTION, required=True)


def test_conflict_and_missing_pads_do_not_fall_back_to_weaker_intent():
    declared = replace(SUGGESTION, origin="declared", required=True)
    conflict = replace(declared, endpoints=(A, C))
    (result,) = resolve_intents((declared, conflict), available_pads=frozenset({A, B, C}))
    assert result.problem == "conflict" and result.effective is None
    (result,) = resolve_intents((declared, SUGGESTION), available_pads=frozenset({A}))
    assert result.problem == "missing_endpoint" and result.effective is None
