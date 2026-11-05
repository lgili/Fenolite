# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The level-7 proof's private identity and order preparation receipt (c0384 2.1): applied, unneeded or
refused, labelled by what was prepared; source aliases listed as not rewritten."""

from __future__ import annotations

from fenolite.backends.kicad.sexpr import dumps
from fenolite.cli._derived_cache import CacheInput, identities
from tests.unit.backends.kicad.test_identity_pairing import SEG, SOURCE, TARGET, board


def _input(text: str) -> CacheInput:
    return CacheInput("x.kicad_pcb", {"x.kicad_pcb": text.encode()}, {}, {})


def test_rewritten_identities_are_receipted_and_labelled() -> None:
    receipt, prepared = identities(_input(dumps(board(SOURCE))), _input(dumps(board(TARGET))))
    assert receipt["status"] == "applied" and receipt["label"] == "L7 after identity preparation"
    assert receipt["scope"] == "private-native-input-copy" and receipt["side"] == "b"
    assert len(receipt["rewritten"]) == 6 and receipt["reason"] is None  # type: ignore[arg-type]
    assert prepared == board(SOURCE)


def test_equal_identities_stay_plain_level_seven() -> None:
    receipt, prepared = identities(_input(dumps(board(SOURCE))), _input(dumps(board(SOURCE))))
    assert (receipt["status"], receipt["label"], receipt["rewritten"], prepared) == (
        "unneeded",
        "L7",
        [],
        None,
    )


def test_a_refused_pairing_leaves_side_b_unprepared_and_says_why() -> None:
    extra = SEG.format(x=4, code=1, u="11111111-0000-4000-8000-0000000000ee")
    receipt, prepared = identities(_input(dumps(board(SOURCE))), _input(dumps(board(TARGET, extra=extra))))
    assert (receipt["status"], receipt["label"], prepared) == ("refused", "L7", None)
    assert "differ" in str(receipt["reason"])


def test_reordered_copper_is_moved_and_labelled_identity_and_order() -> None:
    target = board(TARGET)
    segments = [c for c in target.children if getattr(c, "name", None) == "segment"]
    swapped = target.with_children(
        tuple(
            segments[1] if c is segments[0] else segments[0] if c is segments[1] else c
            for c in target.children
        )
    )
    receipt, prepared = identities(_input(dumps(board(SOURCE))), _input(dumps(swapped)))
    assert receipt["label"] == "L7 after identity and order preparation"
    assert receipt["moved"] == [["segment", TARGET["s2"], 0, 1], ["segment", TARGET["s1"], 1, 0]]
    assert prepared == board(SOURCE)


def test_source_aliases_are_counted_and_noted() -> None:
    aliased = dict(SOURCE, p2=SOURCE["p1"])
    receipt, _ = identities(_input(dumps(board(aliased))), _input(dumps(board(TARGET))))
    assert receipt["source_aliases"] == {
        "note": "source alias, not rewritten",
        "count": 2,
        "identities": sorted((TARGET["p1"], TARGET["p2"])),
    }
