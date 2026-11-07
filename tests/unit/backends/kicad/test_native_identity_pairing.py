# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refusals of the test-only feature-keyed identity pairing (c0384 1.1)."""

from __future__ import annotations

import pytest
from _native_identity_pairing import apply_identities, pair_identities

from fenolite.backends.kicad.sexpr import parse

FP = (
    '(footprint "R" (at 10 10) (property "Reference" "R1") '
    '(pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "A") (uuid "{p1}")) '
    '(pad "2" smd circle (at 1 0) (size 1 1) (layers "F.Cu") (net 2 "B") (uuid "{p2}")))'
)
SEG = '(segment (start {x} 0) (end {x} 5) (width 0.2) (layer "F.Cu") (net {n}) (uuid "{u}"))'


def board(p1="p-1", p2="p-2", s1="s-1", s2="s-2", x1=0, x2=1, n2=2, extra=""):
    return parse(
        "(kicad_pcb "
        + FP.format(p1=p1, p2=p2)
        + SEG.format(x=x1, n=1, u=s1)
        + SEG.format(x=x2, n=n2, u=s2)
        + extra
        + ")"
    )


def test_complete_unique_bijection_pairs_and_rewrites_only_identities():
    source, target = board(), board("q-1", "q-2", "t-1", "t-2")
    mapping = pair_identities(source, target)
    assert mapping == {"q-1": "p-1", "q-2": "p-2", "t-1": "s-1", "t-2": "s-2"}
    assert apply_identities(target, mapping) == source


@pytest.mark.parametrize(
    "target",
    (
        board(x2=2),  # changed geometry
        board(n2=1),  # changed net
        board(extra=SEG.format(x=3, n=1, u="s-3")),  # extra object
    ),
)
def test_changed_or_extra_objects_refuse(target):
    with pytest.raises(ValueError, match="differ"):
        pair_identities(board(), target)


def test_duplicate_signatures_refuse_without_a_first_match():
    twin = board(x2=0, n2=1)
    with pytest.raises(ValueError, match="duplicate"):
        pair_identities(twin, twin)


def test_aliased_identities_refuse():
    with pytest.raises(ValueError, match="aliases"):
        pair_identities(board(s2="s-1"), board())
    with pytest.raises(ValueError, match="aliases"):
        pair_identities(board(), board(s2="s-1"))


def test_missing_identity_refuses():
    bare = parse("(kicad_pcb " + '(segment (start 0 0) (end 0 5) (width 0.2) (layer "F.Cu") (net 1))' + ")")
    with pytest.raises(ValueError, match="identity"):
        pair_identities(bare, bare)


def _declared(code_a: int, code_b: int, segment_code: int, extra: str = "") -> object:
    return parse(
        f'(kicad_pcb (net 0 "") (net {code_a} "A") (net {code_b} "B") {extra}'
        f'(segment (start 0 0) (end 0 5) (width 0.2) (layer "F.Cu") (net {segment_code}) '
        f'(uuid "s-{segment_code}")))'
    )


def test_net_names_replace_codes_only_when_declared_one_to_one():
    source, target = _declared(1, 2, 1), _declared(7, 9, 7)
    with pytest.raises(ValueError, match="differ"):
        pair_identities(source, target)  # raw codes differ
    assert pair_identities(source, target, by_net_name=True) == {"s-7": "s-1"}
    with pytest.raises(ValueError, match="differ"):
        pair_identities(source, _declared(7, 9, 9), by_net_name=True)  # the object moved to net B
    with pytest.raises(ValueError, match="declared"):
        pair_identities(source, _declared(7, 9, 5), by_net_name=True)
    with pytest.raises(ValueError, match="declaration"):
        pair_identities(source, _declared(7, 9, 7, '(net 7 "C") '), by_net_name=True)
    with pytest.raises(ValueError, match="one net name"):
        pair_identities(source, _declared(7, 9, 7, '(net 11 "A") '), by_net_name=True)


def test_unique_net_position_and_quarter_angle_spelling_pair_but_a_real_rotation_refuses():
    moved = parse(
        "(kicad_pcb "
        + FP.format(p1="q-1", p2="q-2").replace(
            '(size 1 1) (layers "F.Cu") (net 1 "A")', '(net 1 "A") (size 1 1) (layers "F.Cu")'
        )
        + SEG.format(x=0, n=1, u="t-1")
        + SEG.format(x=1, n=2, u="t-2")
        + ")"
    )
    assert pair_identities(board(), moved)["q-1"] == "p-1"

    def turned(angle: int):
        footprint = FP.format(p1="p-1", p2="p-2").replace("(at 10 10)", f"(at 10 10 {angle})")
        return parse("(kicad_pcb " + footprint + ")")

    assert pair_identities(turned(-90), turned(270))
    with pytest.raises(ValueError, match="differ"):
        pair_identities(turned(90), turned(270))
