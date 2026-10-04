# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field placements in a build (capability design-dsl, "Field placements in a build"; change c0030)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.fields import DEFAULT_GAP, field_anchor, field_angle, place_outside
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.dsl import Design, fields, mm
from fenolite.lens.build import BuildOutput
from fenolite.lens.fields import FieldRequestLike, apply_requests
from fenolite.model.board import FootprintField, FootprintInstance
from fenolite.model.design import Design as ModelDesign

MM = 1_000_000


def variant(change: Callable[[Design], None]) -> Design:
    design = blink()
    change(design)
    return design


def built(design: Design, target: int = 10) -> BuildOutput:
    output = build(design, target, fields=fields(design))
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return output


def board_of(output: BuildOutput) -> ModelDesign:
    return read_board(output.files["blink.kicad_pcb"].decode("utf-8"))


def footprint(design: ModelDesign, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def field(fp: FootprintInstance, name: str) -> FootprintField:
    return next(f for f in fp.fields if f.name == name)


def values(f: FootprintField) -> tuple[object, ...]:
    return (
        f.position,
        f.rotation,
        f.layer,
        f.size,
        f.thickness,
        f.visible,
        f.h_justify,
        f.v_justify,
        f.mirrored,
    )


def test_reference_above_a_part() -> None:
    output = built(variant(lambda d: d.parts["R1"].field("Reference", outside="top")))
    r1 = footprint(board_of(output), "R1")
    reference = field(r1, "Reference")
    assert field_angle(r1, reference) == 0
    assert (reference.h_justify, reference.v_justify) == ("center", "bottom")
    assert place_outside(r1, "Reference", side="top") == r1
    plain = footprint(board_of(built(blink())), "R1")
    assert values(field(place_outside(plain, "Reference", side="top"), "Reference")) == values(reference)
    assert values(field(plain, "Reference")) != values(reference)
    # the other fields and footprints are the plain build's
    assert values(field(r1, "Value")) == values(field(plain, "Value"))


def test_hidden_value_of_a_bottom_part() -> None:
    output = built(variant(lambda d: d.parts["D1"].field("Value", visible=False, layer="silk")), 9)
    d1 = footprint(board_of(output), "D1")
    value = field(d1, "Value")
    assert d1.side == "bottom"
    assert (value.visible, value.layer, value.mirrored) == (False, "B.SilkS", True)


def test_offset_of_a_rotated_part() -> None:
    def change(design: Design) -> None:
        u1 = design.parts["U1"]
        u1.request = dataclasses.replace(u1.request, rotation=90 * MM)  # type: ignore[type-var]
        u1.field("Reference", dx=mm(0), dy=mm(-5), rot=0)

    u1 = footprint(board_of(built(variant(change))), "U1")
    assert u1.rotation == 90 * MM
    reference = field(u1, "Reference")
    assert field_anchor(u1, reference) == Point(u1.position.x, u1.position.y - 5 * MM)
    assert field_angle(u1, reference) == 0


def test_every_value_of_a_request() -> None:
    def change(design: Design) -> None:
        design.parts["R1"].field(
            "Value", dx=mm(1), dy=mm(2), rot=90, layer="silk", visible=True, size=mm(0.8), thickness=mm(0.12),
            justify="right top",
        )  # fmt: skip

    r1 = footprint(board_of(built(variant(change))), "R1")
    value = field(r1, "Value")
    assert field_anchor(r1, value) == Point(r1.position.x + MM, r1.position.y + 2 * MM)
    assert field_angle(r1, value) == 90 * MM
    assert (value.layer, value.visible, value.size, value.thickness) == (
        "F.SilkS",
        True,
        Size(800_000, 800_000),
        120_000,
    )
    assert (value.h_justify, value.v_justify, value.mirrored) == ("right", "top", False)


def test_outside_with_a_gap_on_a_bottom_part() -> None:
    output = built(variant(lambda d: d.parts["D1"].field("Reference", outside="left", gap=mm(1))))
    d1 = footprint(board_of(output), "D1")
    reference = field(d1, "Reference")
    assert reference.mirrored and reference.h_justify == "left"
    assert place_outside(d1, "Reference", side="left", gap=1_000_000) == d1
    assert place_outside(d1, "Reference", side="left", gap=DEFAULT_GAP) != d1


def test_staged_part_takes_its_request() -> None:
    def change(design: Design) -> None:
        design.parts["R1"].request = None
        design.parts["R1"].field("Reference", outside="bottom")

    output = built(variant(change))
    assert "R1" in output.summary["staged"]  # type: ignore[operator]
    r1 = footprint(board_of(output), "R1")
    assert place_outside(r1, "Reference", side="bottom") == r1
    assert field(r1, "Reference").v_justify == "top"


def test_requests_add_no_issue_and_keep_other_files() -> None:
    plain = built(blink())
    output = built(variant(lambda d: d.parts["R1"].field("Reference", outside="top")))
    assert [i.code for i in output.issues] == [i.code for i in plain.issues]
    assert output.evidence == plain.evidence
    changed = sorted(k for k in output.files if output.files[k] != plain.files.get(k))
    assert changed == [".fenolite/board.json", ".fenolite/build.json", "blink.kicad_pcb"]


def test_without_requests_the_build_is_unchanged() -> None:
    design = blink()
    assert fields(design) == {}
    assert build(design, 10, fields=fields(design)).files == build(blink(), 10).files


def test_built_model_holds_the_applied_fields() -> None:
    output = built(variant(lambda d: d.parts["R1"].field("Value", visible=False)))
    r1 = footprint(output.design, "R1")
    assert not field(r1, "Value").visible
    assert output.layout is not None and not field(footprint(output.layout, "R1"), "Value").visible


def test_library_without_the_field() -> None:
    design = variant(lambda d: d.parts["R1"].field("Value", visible=False))
    r1 = footprint(built(blink()).design, "R1")
    bare = dataclasses.replace(r1, fields=tuple(f for f in r1.fields if f.name != "Value"))
    (request,) = fields(design)["R1"]
    with pytest.raises(FormatError) as info:
        apply_requests(bare, [request])
    assert "Mini:Mini_R_0603" in str(info.value) and "Value" in str(info.value)
    assert getattr(type(info.value), "cli_code", "FEN-3004") == "FEN-3004"


def test_requests_apply_in_name_order() -> None:
    @dataclasses.dataclass(frozen=True)
    class Request:
        name: str
        dx: int | None = None
        dy: int | None = None
        rotation: int | None = None
        layer: str | None = None
        visible: bool | None = None
        size: int | None = None
        thickness: int | None = None
        justify: str | None = None
        outside: str | None = None
        gap: int | None = None
        locked: bool = False

    requests: list[FieldRequestLike] = [Request("Value", visible=False), Request("Reference", outside="top")]
    r1 = footprint(built(blink()).design, "R1")
    done = apply_requests(r1, requests)
    assert done == apply_requests(r1, list(reversed(requests)))
    assert not field(done, "Value").visible and field(done, "Reference").v_justify == "bottom"
    assert apply_requests(r1, []) is r1


def test_reproducible_field_placement(tmp_path: Path) -> None:
    def change(design: Design) -> None:
        design.parts["R1"].field("Reference", outside="top")

    first, second = built(variant(change), 9), built(variant(change), 9)
    assert first.files == second.files
