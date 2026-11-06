# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed scope grammar (capability altium-project-reader, "Closed scope grammar"). Change c0462 reads
mixed operators by Altium's precedence and InNet's wildcards; ``test_scope_c0462.py`` holds its own cases."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.read.scope import LayerScope, parse_layer_scope, parse_scope
from fenolite.model.rules import NO_NET, Selector

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
        ("InNet('No Net')", NO_NET),
        ("IsTrack", TRACK),
        ("IsVia", VIA),
        ("IsPad", Selector("item_kind", "pad")),
        ("InPolygon", Selector("item_kind", "zone")),
        ("InPoly", Selector("item_kind", "zone")),
        (
            "InPolygon And (Not InNetClass('HV'))",
            Selector(
                "and",
                items=(Selector("item_kind", "zone"), Selector("not", items=(Selector("netclass", "HV"),))),
            ),
        ),
        ("InNet('A') And InNet('B')", Selector("and", items=(NET_A, NET_B))),
        ("InNet('A') && InNet('B') And IsTrack", Selector("and", items=(NET_A, NET_B, TRACK))),
        ("InNet('A') Or InNet('B')", Selector("or", items=(NET_A, NET_B))),
        ("InNet('A')||InNet('B')", Selector("or", items=(NET_A, NET_B))),
        ("Not IsVia", Selector("not", items=(VIA,))),
        ("Not (InNet('A') Or IsVia)", Selector("not", items=(Selector("or", items=(NET_A, VIA)),))),
        ("(InNet('A'))", NET_A),
        ("InNet('A') AND InNet('B')", Selector("and", items=(NET_A, NET_B))),
        ("IsVia or IsTrack", Selector("or", items=(VIA, TRACK))),
        ("not InNet('A')", Selector("not", items=(NET_A,))),
        (
            "(InNet('A') OR InNet('B')) and IsTrack",
            Selector("and", items=(Selector("or", items=(NET_A, NET_B)), TRACK)),
        ),
        (
            "(InNet('A') Or InNet('B')) And IsTrack",
            Selector("and", items=(Selector("or", items=(NET_A, NET_B)), TRACK)),
        ),
    ],
)
def test_accepted(text: str, selector: Selector) -> None:
    assert parse_scope(text) == selector


def test_mixed_operators_by_precedence() -> None:
    """Scenario "Mixed operators by Altium's precedence" (change c0462): And binds tighter than Or."""
    assert parse_scope("InNet('A') Or InNet('B') And IsTrack") == Selector(
        "or", items=(NET_A, Selector("and", items=(NET_B, TRACK)))
    )


def test_layer_refused_without_a_document() -> None:
    layer = parse_scope("OnLayer('Top Layer')")
    assert isinstance(layer, str) and "OnLayer" in layer


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("InNet('A') And All", "All stands below the top level"),
        ("(All)", "All stands below the top level"),
        ("OnTopLayer", "layer function OnTopLayer"),
        ("InNet('A') And OnLayer('Top Layer')", "OnLayer"),
        ("IsPolygon", "function IsPolygon"),
        ("InNet('')", "is empty"),
        ("InNet('A", "unclosed quote"),
        ("InNet('a'b')", "takes quoted values"),
        ("InNet('a''b')", "quote '"),
        ("InNet(A)", "takes quoted values"),
        ("InNet", "ends where"),
        ("IsTrack IsVia", "text left over"),
        ("InNet('A')) ", "text left over"),
        ("(IsTrack", "not closed"),
        ("IsTrack And", "ends where an operand"),
        ("", "empty"),
        ("   ", "empty"),
        ("Width > 10", "function Width"),
        ("'A'", "gives a string"),
        ("all", "function all"),
    ],
)
def test_refused(text: str, words: str) -> None:
    reason = parse_scope(text)
    assert isinstance(reason, str) and words in reason, reason


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("OnMid", LayerScope(inner=True)),
        (" ( OnMid ) ", LayerScope(inner=True)),
        ("ExistsOnLayer('Top Layer')", LayerScope(names=("Top Layer",))),
        (
            "(ExistsOnLayer('Top Layer') Or ExistsOnLayer('Bottom Layer'))",
            LayerScope(names=("Top Layer", "Bottom Layer")),
        ),
        ("ExistsOnLayer('A') || ExistsOnLayer('B') Or ExistsOnLayer('C')", LayerScope(names=("A", "B", "C"))),
    ],
)
def test_layer_conditions(text: str, found: LayerScope) -> None:
    """The two layer conditions of change c0125 ("Layer scopes of Clearance")."""
    assert parse_layer_scope(text) == found
    assert isinstance(parse_scope(text), str)  # the closed grammar itself holds no layer function


@pytest.mark.parametrize(
    "text",
    [
        "",
        "All",
        "()",
        "OnMid Or OnMid",
        "Not OnMid",
        "OnOutside",
        "OnLayer('Top Layer')",
        "ExistsOnLayer('')",
        "ExistsOnLayer(Top)",
        "ExistsOnLayer('A') And ExistsOnLayer('B')",
        "ExistsOnLayer('A') Or",
        "ExistsOnLayer('A') Or IsTrack",
        "ExistsOnLayer('A') ExistsOnLayer('B')",
        "((ExistsOnLayer('A')))",
        "(ExistsOnLayer('A')) Or (ExistsOnLayer('B'))",
        "InNet('A')",
    ],
)
def test_no_layer_condition(text: str) -> None:
    assert parse_layer_scope(text) is None


def test_named_polygon_stays_outside() -> None:
    """Scenario "Pour copper" (change c0412): ``InPolygon`` reads without an argument only."""
    assert isinstance(parse_scope("InPolygon('GND')"), str)
    assert isinstance(parse_scope("InNamedPolygon('GND')"), str)
