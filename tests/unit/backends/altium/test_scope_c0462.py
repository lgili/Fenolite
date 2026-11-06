# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scope grammar by Altium's order of precedence, typed (change c0462; capability altium-project-reader,
"Closed scope grammar"; S-2211, S-2212). Authored queries only."""

from __future__ import annotations

import fnmatch

import pytest

from fenolite.backends.altium.read import scope
from fenolite.backends.altium.read.scope import Refusal, ScopeDocument, parse_scope
from fenolite.model.rules import Selector

NET_A = Selector("net", "A")
NET_B = Selector("net", "B")
TRACK = Selector("item_kind", "track")
VIA = Selector("item_kind", "via")
PAD = Selector("item_kind", "pad")
AND_A_B = Selector("and", items=(NET_A, NET_B))
AND_B_TRACK = Selector("and", items=(NET_B, TRACK))
REFS = ("U1", "U2", "J1")


def _not(selector: Selector) -> Selector:
    return Selector("not", items=(selector,))


@pytest.mark.parametrize(
    ("text", "selector"),
    [
        ("InNet('A') Or InNet('B') And IsTrack", Selector("or", items=(NET_A, AND_B_TRACK))),
        ("InNet('A') And InNet('B') Or IsTrack", Selector("or", items=(AND_A_B, TRACK))),
        ("InNet('A') || InNet('B') Or IsTrack", Selector("or", items=(NET_A, NET_B, TRACK))),
        ("InNet('A') And InNet('B') && IsTrack", Selector("and", items=(NET_A, NET_B, TRACK))),
        ("InNet('A') && InNet('B') And IsTrack", Selector("and", items=(NET_A, NET_B, TRACK))),
        ("Not IsVia And IsTrack", Selector("and", items=(_not(VIA), TRACK))),
        ("IsTrack And Not IsVia", Selector("and", items=(TRACK, _not(VIA)))),
        ("Not Not IsVia", _not(_not(VIA))),
        ("not InNet('GND')     or IsVia", Selector("or", items=(_not(Selector("net", "GND")), VIA))),
        ("(InNet('A') And InNet('B')) And IsTrack", Selector("and", items=(AND_A_B, TRACK))),
        ("InNet('A') Xor IsVia", Selector("or", items=(
            Selector("and", items=(NET_A, _not(VIA))), Selector("and", items=(_not(NET_A), VIA))))),
    ],
)  # fmt: skip
def test_precedence(text: str, selector: Selector) -> None:
    """Scenario "Mixed operators by Altium's precedence": And over Or over && and ||, left to right; a
    bracketed group stays one operand."""
    assert parse_scope(text) == selector


@pytest.mark.parametrize(
    ("text", "selector"),
    [
        ("IsVia = True", VIA),
        ("IsVia = 'True'", VIA),
        ("True = IsVia", VIA),
        ("IsVia = False", _not(VIA)),
        ("IsVia = 'False'", _not(VIA)),
        ("IsVia <> True", _not(VIA)),
        ("IsVia <> 'False'", VIA),
        ("(IsVia = False) And IsTrack", Selector("and", items=(_not(VIA), TRACK))),
        ("InNet('A') = TRUE", NET_A),
    ],
)
def test_boolean_comparisons(text: str, selector: Selector) -> None:
    """A function of the form ``Boolean/Boolean_String`` compared with True or False (S-2212)."""
    assert parse_scope(text) == selector


@pytest.mark.parametrize(
    ("text", "selector"),
    [
        ("InNet('D0','D1')", Selector("or", items=(Selector("net", "D0"), Selector("net", "D1")))),
        ("InNet('V*')", Selector("net", "V*")),
        ("InNet('A?')", Selector("net", "A?")),
        ("InNet('[A]')", Selector("net", "[[]A[]]")),
        ("InComponent('U1', 'U2', 'J1')", Selector("or", items=tuple(Selector("ref", r) for r in REFS))),
        ("InComponent('U*')", Selector("ref", "U*")),
        ("InNetClass('A*')", Selector("netclass", "A[*]")),
        ("InNet('D0','D1') Or IsVia", Selector("or", items=(
            Selector("or", items=(Selector("net", "D0"), Selector("net", "D1"))), VIA))),
    ],
)  # fmt: skip
def test_membership_values(text: str, selector: Selector) -> None:
    """``InNet`` and ``InComponent`` take several names and Altium's wildcards ``*`` and ``?``; every other
    glob character matches itself, and ``InNetClass`` compares its one name as written (S-2212)."""
    assert parse_scope(text) == selector


def test_a_wildcard_in_a_net_name() -> None:
    """Scenario "A wildcard in a net name": Altium's ``*`` is a wildcard (S-2212), a bracket is not."""
    star = parse_scope("InNet('PWR*')")
    bracket = parse_scope("InNet('PWR[1]')")
    assert isinstance(star, Selector) and isinstance(bracket, Selector)
    assert fnmatch.fnmatchcase("PWR1", star.value) and fnmatch.fnmatchcase("PWR*", star.value)
    assert fnmatch.fnmatchcase("PWR[1]", bracket.value) and not fnmatch.fnmatchcase("PWR1", bracket.value)


def _hole(lo: int | None, hi: int | None) -> Selector:
    """A stand-in leaf for the field of the test (the ``hole`` leaf is task 3)."""
    return Selector("net", f"{'' if lo is None else lo}..{'' if hi is None else hi}")


@pytest.fixture
def field(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(parser: object, name: str) -> object:
        return scope._Field(name, _hole)  # pyright: ignore[reportPrivateUsage]

    monkeypatch.setitem(scope.FUNCTIONS, "Size", handler)  # pyright: ignore[reportArgumentType]


MM = ScopeDocument(unit="mm")
BETWEEN = _hole(200_000, 400_000)


@pytest.mark.parametrize(
    ("text", "document", "selector"),
    [
        ("Size > 0", None, _hole(1, None)),
        ("Size > 1", MM, _hole(1_000_001, None)),
        ("Size > 1 && IsPad", MM, Selector("and", items=(_hole(1_000_001, None), PAD))),
        ("Size >= 1", MM, _hole(1_000_000, None)),
        ("Size < 1", MM, _hole(None, 999_999)),
        ("Size <= 0.5", MM, _hole(None, 500_000)),
        ("Size = 0.3", MM, _hole(300_000, 300_000)),
        ("Size <> 0.3", MM, _not(_hole(300_000, 300_000))),
        ("1 < Size", MM, _hole(1_000_001, None)),
        ("AsMils(Size) > 10", None, _hole(254_001, None)),
        ("AsMM(Size) Between 0.2 And 0.4", None, _hole(200_000, 400_000)),
        ("AsMM(Size) Between 0.2 And 0.4 && IsPad", None, Selector("and", items=(BETWEEN, PAD))),
    ],
)  # fmt: skip
@pytest.mark.usefixtures("field")
def test_comparison(text: str, document: ScopeDocument | None, selector: Selector) -> None:
    """Scenario "A comparison under And", the reading side: ``&&`` sits below the comparisons, and a number
    takes the document's unit or the unit ``AsMils``/``AsMM`` gives."""
    assert parse_scope(text, document=document) == selector


@pytest.mark.parametrize(
    ("text", "document", "reason", "words"),
    [
        ("Size > 1 And IsPad", MM, "type", "operator And joins a number and a set of objects"),
        ("AsMM(Size) Between 0.2 And 0.4 And IsPad", None, "type", "operator And joins a number"),
        ("Size > 1", None, "unit", "has no unit"),
        ("Size > 1", ScopeDocument(), "unit", "has no unit"),
        ("AsMM(Size) = 0.0000001", None, "unit", "not a whole number of nanometres"),
        ("AsMils(IsVia) > 1", None, "type", "AsMils takes a length field"),
        ("Size", MM, "type", "gives the number Size"),
        ("Size + 1 > 2", MM, "grammar", "arithmetic operator +"),
        ("IsVia = IsTrack", None, "type", "comparison ="),
        ("Not 1", None, "type", "Not takes a set of objects"),
        ("IsVia Like 'V*'", None, "grammar", "operator Like"),
        ("InNet('A') Between 1 And 2", MM, "type", "Between compares"),
        ("InNet('A') And All", None, "grammar", "All stands below"),
        ("IsTrack IsVia", None, "syntax", "text left over"),
        ("Width > 10", MM, "grammar", "function Width"),
    ],
)
@pytest.mark.usefixtures("field")
def test_refusals_are_typed(text: str, document: ScopeDocument | None, reason: str, words: str) -> None:
    """A typed reading that is not a set of objects is refused, naming the operator, never re-bracketed."""
    found = parse_scope(text, document=document)
    assert isinstance(found, Refusal) and found.reason == reason and words in found, found


def test_document_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        parse_scope("IsVia", MM)  # type: ignore[misc]
