# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field precedence across rebuilds at the function level (capability layout-lens, "Footprint fields
across rebuilds"; change c0030)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from _buildhelp import blink, build

from fenolite.backends.kicad.fields import place_outside, set_field
from fenolite.backends.kicad.pcb import field_value, read_board, write_board
from fenolite.core.coords import Point
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import fields, moves, placements, to_model
from fenolite.lens.fields import FIELD_VALUES, FieldMerge, merge_fields
from fenolite.lens.preserve import ExistingProject, Merged, Prepared, merge_layout, prepare
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design

MM = 1_000_000


def script(change: Callable[[DslDesign], None] | None = None) -> DslDesign:
    design = blink()
    design.parts["R1"].field("Reference", outside="top")
    if change is not None:
        change(design)
    return design


def board_text(design: DslDesign, target: int = 10) -> str:
    return build(design, target, fields=fields(design)).files["blink.kicad_pcb"].decode("utf-8")


def footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def field(fp: FootprintInstance, name: str) -> FootprintField:
    return next(f for f in fp.fields if f.name == name)


def values(f: FootprintField) -> tuple[object, ...]:
    return tuple(getattr(f, name) for name in FIELD_VALUES)


def edited(text: str, ref: str, change: Callable[[FootprintInstance], FootprintInstance]) -> str:
    """The board text with footprint ``ref`` changed through the model and written again (a GUI edit)."""
    design = read_board(text)
    return write_board(design.replace_entity(change(footprint(design, ref))), target=10).text


def moved_reference(fp: FootprintInstance) -> FootprintInstance:
    """``fp`` with its Reference moved 1 mm along the footprint's X axis, as a drag in KiCad does."""
    reference = field(fp, "Reference")
    moved = dataclasses.replace(reference, position=Point(reference.position.x + MM, reference.position.y))
    return dataclasses.replace(fp, fields=tuple(moved if f is reference else f for f in fp.fields))


def run(design: DslDesign, text: str) -> tuple[FieldMerge, Merged, Prepared]:
    """``merge_fields`` over ``merge_layout`` of the build of ``design`` and the board read from ``text``."""
    ready = prepare(
        to_model(design), placements(design), ExistingProject(board=text), name="blink", moves=moves(design)
    )
    output = build(design, 10, placements_override=ready.placements, fields=fields(design))
    assert ready.board is not None and ready.match is not None
    merged = merge_layout(output.design, ready.board, ready.match)
    return merge_fields(merged, ready.board, ready.match, fields(design)), merged, ready


def test_unedited_board_is_quiet() -> None:
    design = script()
    result, merged, _ = run(design, board_text(design))
    assert (result.kept, result.forced, result.carried) == ((), (), ())
    assert result.design is merged.design
    assert result.summary == {"kept": [], "forced": [], "carried": []}


def test_board_wins_over_an_unlocked_request() -> None:
    design = script()
    text = edited(board_text(design), "R1", moved_reference)
    result, merged, ready = run(design, text)
    assert ready.board is not None
    assert result.kept == ("R1:Reference",) and result.forced == () and result.carried == ()
    assert result.design == merged.design
    assert values(field(footprint(result.design, "R1"), "Reference")) == values(
        field(footprint(ready.board, "R1"), "Reference")
    )


def test_locked_request_wins() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)
    design = blink()
    design.parts["R1"].field("Reference", outside="top", locked=True)
    result, merged, ready = run(design, text)
    assert result.forced == ("R1:Reference",) and result.kept == () and result.carried == ()
    r1 = footprint(result.design, "R1")
    assert place_outside(r1, "Reference", side="top") == r1
    assert ready.board is not None
    board_r1 = footprint(ready.board, "R1")
    # the kept node stays: id, uuid and slots of the board's field
    forced, old = field(r1, "Reference"), field(board_r1, "Reference")
    assert (forced.id, forced.native_ids, forced.ext) == (old.id, old.native_ids, old.ext)
    assert [values(f) for f in r1.fields if f.name != "Reference"] == [
        values(f) for f in board_r1.fields if f.name != "Reference"
    ]
    # nothing but fields changes
    without = dataclasses.replace(r1, fields=footprint(merged.design, "R1").fields)
    assert result.design.replace_entity(without) == merged.design


def test_locked_request_is_applied_on_top_of_the_board_field() -> None:
    """A locked request that only hides the field keeps the position edited in KiCad."""
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)
    design = blink()
    design.parts["R1"].field("Reference", visible=False, locked=True)
    result, _, ready = run(design, text)
    assert ready.board is not None
    new = field(footprint(result.design, "R1"), "Reference")
    old = field(footprint(ready.board, "R1"), "Reference")
    assert result.forced == ("R1:Reference",)
    assert not new.visible and new.position == old.position and new.rotation == old.rotation


def test_unlocked_request_that_agrees_with_the_board_is_not_listed() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)
    design = blink()
    design.parts["R1"].field("Reference", visible=True)  # the board's field is visible already
    result, _, _ = run(design, text)
    assert (result.kept, result.forced, result.carried) == ((), (), ())


def test_fields_follow_a_forced_move() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)

    def forced_place(design: DslDesign) -> None:
        request = design.parts["R1"].request
        assert request is not None
        design.parts["R1"].request = dataclasses.replace(request, x=request.x + 2 * MM, locked=True)

    result, merged, ready = run(script(forced_place), text)
    assert merged.summary["replaced"] == ["R1"]
    assert ready.board is not None
    r1, board_r1 = footprint(result.design, "R1"), footprint(ready.board, "R1")
    assert r1.position == Point(board_r1.position.x + 2 * MM, board_r1.position.y)
    new, old = field(r1, "Reference"), field(board_r1, "Reference")
    assert values(new) == values(old)
    assert result.carried == ("R1:Reference",) and result.kept == ("R1:Reference",) and result.forced == ()
    built = field(footprint(merged.design, "R1"), "Reference")
    assert (new.id, new.native_ids, new.ext) == (built.id, built.native_ids, built.ext)
    write_board(result.design, target=10)


def test_locked_request_is_not_carried() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)

    def change(design: DslDesign) -> None:
        request = design.parts["R1"].request
        assert request is not None
        design.parts["R1"].request = dataclasses.replace(request, x=request.x + 2 * MM, locked=True)
        design.parts["R1"].field_requests["Reference"] = dataclasses.replace(
            design.parts["R1"].field_requests["Reference"], locked=True
        )

    result, merged, _ = run(script(change), text)
    r1 = footprint(result.design, "R1")
    assert place_outside(r1, "Reference", side="top") == r1
    assert result.forced == ("R1:Reference",) and result.carried == () and result.kept == ()
    assert result.design == merged.design


def test_side_change_takes_the_built_fields() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)

    def change(design: DslDesign) -> None:
        request = design.parts["R1"].request
        assert request is not None
        design.parts["R1"].request = dataclasses.replace(request, side="bottom", locked=True)

    result, merged, _ = run(script(change), text)
    reference = field(footprint(result.design, "R1"), "Reference")
    assert reference.layer == "B.SilkS" and reference.mirrored
    assert (result.kept, result.forced, result.carried) == ((), (), ())
    assert result.design is merged.design


def test_alias_carries_the_fields() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)
    design = blink()
    part = design.parts.pop("R1")
    part.ref = "R7"
    design.parts["R7"] = part
    design.moved("R1", "R7")
    result, merged, ready = run(design, text)
    assert merged.summary["replaced"] == ["R7"]
    assert ready.board is not None
    new = field(footprint(result.design, "R7"), "Reference")
    assert values(new) == values(field(footprint(ready.board, "R1"), "Reference"))
    assert result.carried == ("R7:Reference",)


def test_user_properties_are_carried_but_never_listed() -> None:
    def with_property(design: DslDesign) -> None:
        design.parts["R1"].properties = {"Part number": "PN-330"}

    first = script(with_property)

    def shown(fp: FootprintInstance) -> FootprintInstance:
        return set_field(fp, "Part number", visible=True, anchor=Point(fp.position.x + MM, fp.position.y))

    text = edited(board_text(first), "R1", shown)

    def change(design: DslDesign) -> None:
        design.parts["R1"].properties = {"Part number": "PN-470"}
        request = design.parts["R1"].request
        assert request is not None
        design.parts["R1"].request = dataclasses.replace(request, x=request.x + 2 * MM, locked=True)

    result, _, _ = run(script(change), text)
    part_number = field(footprint(result.design, "R1"), "Part number")
    assert part_number.visible and part_number.position == Point(MM, 0)
    assert field_value(part_number) == "PN-470"
    assert result.carried == () and result.forced == ()
    write_board(result.design, target=10)


def test_merge_is_pure_and_idempotent() -> None:
    plain = script()
    text = edited(board_text(plain), "R1", moved_reference)
    cases: list[Callable[[DslDesign], None] | None] = [None]

    def locked(design: DslDesign) -> None:
        design.parts["R1"].field_requests["Reference"] = dataclasses.replace(
            design.parts["R1"].field_requests["Reference"], locked=True
        )

    def moved(design: DslDesign) -> None:
        request = design.parts["R1"].request
        assert request is not None
        design.parts["R1"].request = dataclasses.replace(request, x=request.x + 2 * MM, locked=True)

    cases += [locked, moved]
    for change in cases:
        design = script(change)
        result, merged, ready = run(design, text)
        assert ready.board is not None and ready.match is not None
        before = merged.design
        again = merge_fields(
            dataclasses.replace(merged, design=result.design), ready.board, ready.match, fields(design)
        )
        assert again.design == result.design
        assert merged.design is before and merged.design == before
        third = merge_fields(merged, ready.board, ready.match, fields(design))
        assert third == result


def test_request_for_a_field_the_footprint_lost() -> None:
    """A kept footprint whose field was deleted is left alone: the request has nothing to apply to."""
    design = script()
    text = board_text(design)
    ready = prepare(
        to_model(design), placements(design), ExistingProject(board=text), name="blink", moves=moves(design)
    )
    output = build(design, 10, placements_override=ready.placements, fields=fields(design))
    assert ready.board is not None and ready.match is not None
    merged = merge_layout(output.design, ready.board, ready.match)
    r1 = footprint(merged.design, "R1")
    stripped = merged.design.replace_entity(
        dataclasses.replace(r1, fields=tuple(f for f in r1.fields if f.name != "Reference"))
    )
    result = merge_fields(
        dataclasses.replace(merged, design=stripped), ready.board, ready.match, fields(design)
    )
    assert result.design == stripped and (result.kept, result.forced, result.carried) == ((), (), ())


def test_copper_mismatch_leaves_the_design_alone() -> None:
    design = script()
    text = board_text(design)
    four = script()
    four.copper = 4
    ready = prepare(
        to_model(four), placements(four), ExistingProject(board=text), name="blink", moves=moves(four)
    )
    output = build(design, 10, fields=fields(design))
    assert ready.board is not None and ready.match is not None
    merged = Merged(output.design, (), {})
    result = merge_fields(merged, ready.board, ready.match, fields(design))
    assert result.design is merged.design and result.summary == {"kept": [], "forced": [], "carried": []}
