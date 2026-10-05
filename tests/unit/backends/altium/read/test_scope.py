# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed scope grammar (capability altium-project-reader, "Closed scope grammar")."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.read.scope import parse_scope
from fenolite.model.rules import Selector

NET_A = Selector("net", "A")
NET_B = Selector("net", "B")
TRACK = Selector("item_kind", "track")
VIA = Selector("item_kind", "via")


def test_class_and_item_kind() -> None:
    """Scenario "Class and item kind"."""
    assert parse_scope("InNetClass('HV') And (Not IsVia)") == Selector(
        "and", items=(Selector("netclass", "HV"), Selector("not", items=(VIA,)))
    )


@pytest.mark.parametrize(
    ("text", "selector"),
    [
        ("All", Selector("all")),
        ("  All  ", Selector("all")),
        ("InNet('A')", NET_A),
        ("InNet ( 'A' ) ", NET_A),
        ("InNetClass('PWR')", Selector("netclass", "PWR")),
        ("InComponent('U1')", Selector("ref", "U1")),
        ("InNet('net with space')", Selector("net", "net with space")),
        ("IsTrack", TRACK),
        ("IsVia", VIA),
        ("IsPad", Selector("item_kind", "pad")),
        ("InNet('A') And InNet('B')", Selector("and", items=(NET_A, NET_B))),
        ("InNet('A') && InNet('B') And IsTrack", Selector("and", items=(NET_A, NET_B, TRACK))),
        ("InNet('A') Or InNet('B')", Selector("or", items=(NET_A, NET_B))),
        ("InNet('A')||InNet('B')", Selector("or", items=(NET_A, NET_B))),
        ("Not IsVia", Selector("not", items=(VIA,))),
        ("Not (InNet('A') Or IsVia)", Selector("not", items=(Selector("or", items=(NET_A, VIA)),))),
        ("(InNet('A'))", NET_A),
        (
            "(InNet('A') Or InNet('B')) And IsTrack",
            Selector("and", items=(Selector("or", items=(NET_A, NET_B)), TRACK)),
        ),
    ],
)
def test_accepted(text: str, selector: Selector) -> None:
    assert parse_scope(text) == selector


def test_mixed_operators_without_parentheses() -> None:
    """Scenario "Mixed operators without parentheses" (the rule side is in test_rule_map.py)."""
    reason = parse_scope("InNet('A') Or InNet('B') And IsTrack")
    assert isinstance(reason, str) and "mixes the operators And and Or" in reason


def test_layer_and_wildcard_refused() -> None:
    """Scenario "Layer and wildcard refused"."""
    layer = parse_scope("OnLayer('Top Layer')")
    wildcard = parse_scope("InNet('PWR*')")
    assert isinstance(layer, str) and "OnLayer" in layer
    assert isinstance(wildcard, str) and "character *" in wildcard


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("InNet('A') And All", "All stands below the top level"),
        ("(All)", "All stands below the top level"),
        ("OnTopLayer", "layer function OnTopLayer"),
        ("InNet('A') And OnLayer('Top Layer')", "OnLayer"),
        ("IsPolygon", "function IsPolygon"),
        ("InNet('A?')", "character ?"),
        ("InNet('[A]')", "character ["),
        ("InNet('A]')", "character ]"),
        ("InNet('')", "is empty"),
        ("InNet('A", "unclosed quote"),
        ("InNet('a'b')", "takes one quoted value"),
        ("InNet('a''b')", "quote '"),
        ("InNet(A)", "one quoted value"),
        ("InNet", "ends where"),
        ("Not IsVia And IsTrack", "Not must be the whole"),
        ("IsTrack And Not IsVia", "mixes Not with And"),
        ("Not Not IsVia", "operator Not stands where an operand"),
        ("IsTrack IsVia", "text left over"),
        ("InNet('A')) ", "text left over"),
        ("(IsTrack", "not closed"),
        ("IsTrack And", "ends where an operand"),
        ("", "empty"),
        ("   ", "empty"),
        ("Width > 10", "function Width"),
        ("'A'", "quoted value"),
        ("InNet('A') AND InNet('B')", "text left over"),
        ("all", "function all"),
    ],
)
def test_refused(text: str, words: str) -> None:
    reason = parse_scope(text)
    assert isinstance(reason, str) and words in reason, reason
