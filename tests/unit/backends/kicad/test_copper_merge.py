# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script copper beside existing copper (capability manual-copper, "Script copper is regenerated"; change
c0028): regenerated, stale and duplicate items, and what stays. Hermetic."""

from __future__ import annotations

import dataclasses

from _copper import arc, at, built_blink, end, routed_intents, stitch, track, via

from fenolite.backends.kicad.copper import CopperMerge, copper_uuid, merge_copper, resolve_copper
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design

A = track("a", end("R1", 2), at(36, 9), at(36, 14))
B = track("b", end("R1", 1), at(30, 9))


def _resolve(design: Design, *intents: object) -> tuple[Design, list[Issue]]:
    found: list[Issue] = []
    return resolve_copper(design, intents, issues=found), found  # type: ignore[arg-type]


def _board(design: Design, **items: object) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **items))  # type: ignore[arg-type]


def _tracks(design: Design) -> tuple[Track, ...]:
    assert design.board is not None
    return design.board.tracks


def _net(design: Design, name: str) -> str:
    return next(net.id for net in design.circuit.nets if net.name == name)


def _user(track: Track, n: int = 1, **changes: object) -> Track:
    native = f"00000000-0000-4000-8000-{n:012d}"
    return dataclasses.replace(
        track, id=derived_id("trk", "kicad", native), native_ids={"kicad": native}, **changes
    )  # type: ignore[arg-type]


def test_stale_script_copper() -> None:
    both, _ = _resolve(built_blink(), A, B)
    only_a, found = _resolve(both, A)
    assert [t.native_ids["kicad"] for t in _tracks(only_a)] == [
        copper_uuid("a", "seg[0]"),
        copper_uuid("a", "seg[1]"),
    ]
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.copper.stale", "warning")
    gone = copper_uuid("b", "seg[0]")
    assert gone in issue.message and issue.where == gone
    assert (
        "track on F.Cu" in issue.message and "LED_DRV" in issue.message and "(131.2, 109) mm" in issue.message
    )


def test_edited_script_copper_is_regenerated() -> None:
    resolved, _ = _resolve(built_blink(), A)
    first, second = _tracks(resolved)
    moved = dataclasses.replace(first, end=Point(first.end.x, first.end.y + 1_000_000))
    again, found = _resolve(_board(resolved, tracks=(moved, second)), A)
    assert again == resolved
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.copper.regenerated", "info")
    assert first.native_ids["kicad"] in issue.message


def test_every_modelled_field_counts_as_an_edit() -> None:
    resolved, _ = _resolve(built_blink(), A, via("v", at(20, 20)))
    assert resolved.board is not None
    first, second = _tracks(resolved)
    (only,) = resolved.board.vias
    gnd = _net(resolved, "GND")
    for edited in (
        dataclasses.replace(first, width=first.width + 1),
        dataclasses.replace(first, layer="B.Cu"),
        dataclasses.replace(first, net_id=gnd),
        dataclasses.replace(first, start=first.end, end=first.start),
    ):
        merge = merge_copper(_board(resolved, tracks=(edited, second)), resolved)
        assert (merge.regenerated, merge.stale, merge.duplicates) == (1, 0, 0) and merge.kept == frozenset()
    for edited_via in (
        dataclasses.replace(only, diameter=only.diameter + 2),
        dataclasses.replace(only, drill=only.drill - 2),
        dataclasses.replace(only, position=Point(1, 1)),
        dataclasses.replace(only, via_type="micro"),
    ):
        assert merge_copper(_board(resolved, vias=(edited_via,)), resolved).regenerated == 1
    assert merge_copper(resolved, resolved) == CopperMerge(frozenset())


def test_duplicates_and_user_copper() -> None:
    resolved, _ = _resolve(built_blink(), *routed_intents())
    script = _tracks(resolved)[0]
    copy = _user(script, 1)
    reversed_copy = _user(script, 2, start=script.end, end=script.start)
    own = _user(script, 3, start=at(1, 1), end=at(2, 1), net_id=_net(resolved, "GND"))
    with_user = _board(resolved, tracks=(copy, *_tracks(resolved), reversed_copy, own))
    again, found = _resolve(with_user, *routed_intents())
    assert [i.code for i in found] == ["kicad.copper.duplicate", "kicad.copper.duplicate"]
    assert all(i.severity == "info" for i in found)
    assert _tracks(again) == (own, *_tracks(resolved))  # user copper first, in its order, then the script's
    merge = merge_copper(with_user, resolved)
    assert (
        merge.kept == frozenset({own.id}) and merge.duplicates == 2 and merge.regenerated == merge.stale == 0
    )


def test_user_copper_that_differs_is_kept() -> None:
    resolved, _ = _resolve(built_blink(), A)
    script = _tracks(resolved)[0]
    assert resolved.board is not None
    users = (
        _user(script, 1, width=script.width + 1),
        _user(script, 2, layer="B.Cu"),
        _user(script, 3, net_id=_net(resolved, "GND")),
    )
    arc = Arc(id="arc_00000000-0000-4000-8000-000000000001", start=at(1, 1), mid=at(2, 0), end=at(3, 1),
              width=200_000, layer="F.Cu", net_id=_net(resolved, "GND"))  # fmt: skip
    user_via = Via(id="via_00000000-0000-4000-8000-000000000002", position=at(5, 5), diameter=600_000,
                   drill=300_000, layers=("F.Cu", "B.Cu"), net_id=None)  # fmt: skip
    design = _board(resolved, tracks=(*users, *_tracks(resolved)), arcs=(arc,), vias=(user_via,))
    again, found = _resolve(design, A)
    assert found == [] and again.board is not None
    assert again.board.tracks[:3] == users and again.board.arcs == (arc,) and again.board.vias == (user_via,)


def test_stale_arcs_and_vias() -> None:
    resolved, _ = _resolve(built_blink(), via("v", at(20, 20)))
    stale_arc_id = copper_uuid("old", "seg[0]")
    arc = Arc(id=derived_id("arc", "kicad", stale_arc_id), native_ids={"kicad": stale_arc_id}, start=at(1, 1),
              mid=at(2, 0), end=at(3, 1), width=200_000, layer="F.Cu")  # fmt: skip
    design = _board(resolved, arcs=(arc,))
    again, found = _resolve(design)
    assert again.board is not None and again.board.arcs == () and again.board.vias == ()
    assert sorted(i.code for i in found) == ["kicad.copper.stale", "kicad.copper.stale"]
    assert any("arc on F.Cu" in i.message and "no net" in i.message for i in found)
    assert any("via on F.Cu-B.Cu" in i.message for i in found)


def test_merge_is_pure_and_names_nets() -> None:
    resolved, _ = _resolve(built_blink(), A, B)
    before = canonical.dump_texts(resolved)
    built, _ = _resolve(built_blink(), A)
    merge = merge_copper(resolved, built)
    assert canonical.dump_texts(resolved) == before
    assert merge.stale == 1 and merge.kept == frozenset() and len(merge.issues) == 1
    # the comparison is by net name, so an existing board whose net ids differ still matches
    renumbered = dataclasses.replace(
        resolved,
        circuit=dataclasses.replace(
            resolved.circuit,
            nets=tuple(dataclasses.replace(n, id=n.id[:-1] + "f") for n in resolved.circuit.nets),
        ),
    )
    assert renumbered.board is not None
    tracks = tuple(dataclasses.replace(t, net_id=t.net_id[:-1] + "f") for t in renumbered.board.tracks)  # type: ignore[index]
    assert merge_copper(_board(renumbered, tracks=tracks), resolved).regenerated == 0


def test_design_without_a_board() -> None:
    bare = dataclasses.replace(built_blink(), board=None)
    assert merge_copper(bare, built_blink()) == CopperMerge(frozenset())


# --- script arcs (change c0068) ---------------------------------------------------------------------

BEND = track("bend", at(10, 10), arc(at(11, 11), at(10, 12)), at(10, 15), width=250_000, net="GND")


def _arcs(design: Design) -> tuple[Arc, ...]:
    assert design.board is not None
    return design.board.arcs


def test_arc_removed_from_the_script() -> None:
    """Scenario "Arc removed from the script"."""
    resolved, _ = _resolve(built_blink(), BEND)
    (made,) = _arcs(resolved)
    again, found = _resolve(resolved)
    assert _arcs(again) == () and _tracks(again) == ()
    assert [i.code for i in found] == ["kicad.copper.stale", "kicad.copper.stale"]
    assert all(i.severity == "warning" for i in found)
    (about_arc,) = [i for i in found if i.where == made.native_ids["kicad"]]
    assert made.native_ids["kicad"] == copper_uuid("bend", "arc[1]")
    for word in (made.native_ids["kicad"], "arc on F.Cu", "(110, 110) mm", "GND"):
        assert word in about_arc.message, word


def test_script_arc_is_regenerated_when_edited() -> None:
    resolved, _ = _resolve(built_blink(), BEND)
    (made,) = _arcs(resolved)
    for change in ({"mid": at(11.5, 11)}, {"width": 300_000}, {"layer": "B.Cu"}, {"end": at(10, 12.5)}):
        edited = dataclasses.replace(made, **change)  # type: ignore[arg-type]
        again, found = _resolve(_board(resolved, arcs=(edited,)), BEND)
        assert _arcs(again) == (made,), change
        assert [i.code for i in found] == ["kicad.copper.regenerated"] and "arc on F.Cu" in found[0].message
    quiet, found = _resolve(resolved, BEND)
    assert quiet == resolved and found == []


def test_user_arc_equal_to_a_script_arc_is_a_duplicate() -> None:
    resolved, _ = _resolve(built_blink(), BEND)
    (made,) = _arcs(resolved)
    native = "00000000-0000-4000-8000-0000000000a1"
    copy = dataclasses.replace(made, id=derived_id("arc", "kicad", native), native_ids={"kicad": native})
    reversed_copy = dataclasses.replace(
        copy, start=made.end, end=made.start
    )  # the ends are an unordered pair
    other = dataclasses.replace(copy, mid=at(9, 11))  # another mid point: another arc, kept
    for user, kept in ((copy, False), (reversed_copy, False), (other, True)):
        again, found = _resolve(_board(resolved, arcs=(user, made)), BEND)
        assert (user in _arcs(again)) is kept, user
        assert [i.code for i in found] == ([] if kept else ["kicad.copper.duplicate"])
        assert made in _arcs(again)


def test_merge_counts_arcs() -> None:
    blink = built_blink()
    resolved, _ = _resolve(blink, BEND)
    merge = merge_copper(resolved, resolved)
    assert isinstance(merge, CopperMerge)
    assert (merge.kept, merge.regenerated, merge.stale, merge.duplicates) == (frozenset(), 0, 0, 0)
    empty = merge_copper(resolved, blink)
    assert empty.stale == 2 and empty.kept == frozenset()


def test_created_items_follow_the_kept_ones_in_path_order() -> None:
    blink = built_blink()
    native = "00000000-0000-4000-8000-0000000000a2"
    user = Arc(id=derived_id("arc", "kicad", native), native_ids={"kicad": native}, start=at(1, 1),
               mid=at(2, 0), end=at(3, 1), width=200_000, layer="F.Cu")  # fmt: skip
    two = track(
        "two", at(20, 3), arc(at(21, 4), at(20, 5)), arc(at(19, 6), at(20, 7)), width=250_000, net="GND"
    )
    result, found = _resolve(_board(blink, arcs=(user,)), two, BEND)
    assert found == []
    assert [a.native_ids["kicad"] for a in _arcs(result)] == [
        native,
        copper_uuid("two", "arc[1]"),
        copper_uuid("two", "arc[2]"),
        copper_uuid("bend", "arc[1]"),
    ]


# --- locks (change c0108; capability manual-copper, "Locked script copper") -------------------------


def _locked(intent: object) -> object:
    return dataclasses.replace(intent, locked=True)  # type: ignore[type-var]


def test_locked_track_is_written_locked() -> None:
    """Scenario "Locked track written": every item of a locked intent is locked, in the model and in the
    text, after ``width``."""
    from fenolite.backends.kicad.pcb import write_board

    resolved, found = _resolve(built_blink(), _locked(A), B, _locked(via("v", at(20, 20))))
    assert not [i for i in found if i.severity == "error"]
    assert resolved.board is not None
    by_key = {copper_uuid("a", "seg[0]"), copper_uuid("a", "seg[1]")}
    for item in _tracks(resolved):
        assert item.locked is (item.native_ids["kicad"] in by_key)
    assert [v.locked for v in resolved.board.vias] == [True]
    text = write_board(resolved, target=10).text
    blocks = [part.split("\n\t)\n")[0] for part in text.split("\n\t(segment\n")[1:]]
    assert sum("(locked yes)" in block for block in blocks) == 2
    assert "(locked yes)" in text.split("\n\t(via\n")[1]
    for native in by_key:
        block = text[: text.index(native)].rsplit("(segment", 1)[1]
        assert block.index("(width") < block.index("(locked yes)") < block.index("(layer")
    # an intent without the attribute is read as unlocked
    plain, _ = _resolve(built_blink(), A, B)
    assert not any(item.locked for item in _tracks(plain))
    plain_text = write_board(plain, target=10).text
    assert not any("(locked" in part.split("\n\t)\n")[0] for part in plain_text.split("\n\t(segment\n")[1:])


def test_locked_stitch_and_bend_are_locked() -> None:
    resolved, _ = _resolve(built_blink(), _locked(BEND), _locked(stitch("st", along=(at(5, 5), at(15, 5)))))
    assert resolved.board is not None
    assert _arcs(resolved) and all(a.locked for a in _arcs(resolved))
    assert resolved.board.vias and all(v.locked for v in resolved.board.vias)
    assert all(t.locked for t in _tracks(resolved))


def test_lock_changed_in_kicad_is_regenerated() -> None:
    """Scenario "A lock changed in KiCad is regenerated"."""
    resolved, _ = _resolve(built_blink(), A)
    first, second = _tracks(resolved)
    assert first.native_ids["kicad"] == copper_uuid("a", "seg[0]")
    edited = _board(resolved, tracks=(dataclasses.replace(first, locked=True), second))
    again, found = _resolve(edited, A)
    assert again == resolved and not _tracks(again)[0].locked
    (issue,) = found
    assert (issue.code, issue.severity) == ("kicad.copper.regenerated", "info")
    assert first.native_ids["kicad"] in issue.message
    # the other way: a locked intent whose copper was unlocked in KiCad is locked again
    locked, _ = _resolve(built_blink(), _locked(A))
    one, two = _tracks(locked)
    back, found = _resolve(_board(locked, tracks=(dataclasses.replace(one, locked=False), two)), _locked(A))
    assert back == locked and [i.code for i in found] == ["kicad.copper.regenerated"]


def test_locked_copy_is_a_duplicate() -> None:
    """Scenario "A locked copy is a duplicate": the lock is not part of what makes two items the same."""
    resolved, _ = _resolve(built_blink(), A)
    script = _tracks(resolved)[0]
    copy = _user(script, 1, locked=True)
    again, found = _resolve(_board(resolved, tracks=(copy, *_tracks(resolved))), A)
    assert [i.code for i in found] == ["kicad.copper.duplicate"]
    assert again == resolved
