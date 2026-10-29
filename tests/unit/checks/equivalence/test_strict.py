# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strict level 5: the copper item by item (capability design-equivalence, "Level 5 strict compares copper
items" and "Level 5 strict matching"; change c0278)."""

from __future__ import annotations

import dataclasses

from _cases import reversed_order, two_layer
from _routes import board, mm, routed, track, with_board, with_track, without

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.checks.equivalence import LevelResult, Tolerances, compare_designs, difference_issues
from fenolite.checks.equivalence.model import EXACT
from fenolite.checks.equivalence.strict import STRICT_RULE, items
from fenolite.model.design import Design


def strict5(a: Design, b: Design, tolerances: Tolerances = EXACT) -> LevelResult:
    return compare_designs(a, b, level=5, tolerances=tolerances, strict=True).levels[-1]


def kinds(result: LevelResult) -> list[tuple[str, str]]:
    return [(d.kind, d.where) for d in result.differences]


def test_a_faithful_copy_is_strictly_equal() -> None:
    source = two_layer()
    copy = read_board(write_board(source, target=10).text, file="copy.kicad_pcb")
    result = strict5(source, copy)
    assert (result.differences, result.notices) == ((), ())
    assert result.summary["strict"] == {
        "tracks": {"matched": 3, "a": 0, "b": 0},
        "arcs": {"matched": 1, "a": 0, "b": 0},
        "vias": {"matched": 1, "a": 0, "b": 0},
    }
    assert result.compared == 3 + 5


def test_the_default_level_5_is_unchanged() -> None:
    plain = compare_designs(routed(), routed(), level=5).levels[-1]
    assert "strict" not in plain.summary and plain.compared == 4


def test_same_connectivity_other_segments() -> None:
    """One track replaced by two tracks through a new point of it, joining the same pads: the routing rule
    sees the same copper, the strict rule two new tracks and one gone."""
    source = routed()
    cut = without(source, "c-top")
    held = board(cut)
    tracks = (
        *held.tracks,
        track(cut, "c-1", "C", mm(9, 10), mm(9, 12)),
        track(cut, "c-2", "C", mm(9, 12), mm(9, 15)),
    )
    copy = with_board(cut, tracks=tracks)
    assert compare_designs(source, copy, level=5).equivalent
    result = strict5(source, copy)
    missing = [d for d in result.differences if d.kind == "track-missing"]
    assert len(missing) == 3 and len(result.differences) == 3
    assert sum(1 for d in missing if d.a and not d.b) == 1
    assert sum(1 for d in missing if d.b and not d.a) == 2
    assert missing[0].where.startswith("C:track:top:")


def test_planted_strict_edits() -> None:
    """Each edit alone gives its kind: a wider track, another via drill, a blind via, an unlocked arc."""
    source = routed()
    held = board(source)
    locked_arcs = tuple(dataclasses.replace(a, locked=True) for a in held.arcs)
    locked = with_board(source, arcs=locked_arcs)
    edits = (
        (source, with_track(source, "c-top", width=300_000)),
        (source, with_board(source, vias=(dataclasses.replace(held.vias[0], drill=350_000), *held.vias[1:]))),
        (
            source,
            with_board(
                source,
                vias=(
                    dataclasses.replace(held.vias[0], via_type="blind", layers=("Top", "Mid")),
                    *held.vias[1:],
                ),
            ),
        ),
        (locked, source),
    )
    found: list[str] = []
    for a, b in edits:
        result = strict5(a, b)
        strict_kinds = [
            d.kind for d in (*result.differences, *result.notices) if not d.kind.startswith("route-")
        ]
        assert len(strict_kinds) == 1, strict_kinds
        found += strict_kinds
    assert found == ["track-width", "via-drill", "via-span", "copper-locked"]


def test_a_lock_is_a_notice() -> None:
    source = routed()
    held = board(source)
    unlocked = with_board(source, arcs=tuple(dataclasses.replace(a, locked=True) for a in held.arcs))
    report = compare_designs(unlocked, source, level=5, strict=True)
    assert report.equivalent
    (issue,) = [i for i in difference_issues(report) if i.code == "equiv.copper-locked"]
    assert issue.severity == "warning" and issue.where.startswith("D:arc:top:")


def test_reversed_track_is_equal() -> None:
    source = routed()
    flipped = with_track(source, "c-top", start=mm(9, 15), end=mm(9, 10))
    assert strict5(source, flipped).differences == ()


def test_tolerance() -> None:
    source = routed()
    held = board(source)
    first = held.vias[0]
    moved = dataclasses.replace(first, position=dataclasses.replace(first.position, x=first.position.x + 5))
    copy = with_board(source, vias=(moved, *held.vias[1:]))
    tight = strict5(source, copy, Tolerances(length_nm=4))
    vias = [d for d in tight.differences if d.kind == "via-missing"]
    assert [(bool(d.a), bool(d.b)) for d in vias] == [(True, False), (False, True)]
    assert vias[0].where == f"A:via:top-bottom:{first.position.x},{first.position.y}"
    assert vias[1].where == f"A:via:top-bottom:{first.position.x + 5},{first.position.y}"
    assert [
        d
        for d in strict5(source, copy, Tolerances(length_nm=5)).differences
        if not d.kind.startswith("route-")
    ] == []


def test_order_does_not_matter() -> None:
    source = two_layer()
    assert strict5(source, reversed_order(source)).differences == ()


def test_items_are_keyed_by_span() -> None:
    found = items(routed())
    assert {item.span for item in found["track"]} == {"top", "bottom"}
    assert {item.span for item in found["via"]} == {"top-bottom"}
    assert set(STRICT_RULE) == {"track", "arc", "via"}
