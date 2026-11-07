# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.reuse.bodies``: 3D bodies copied between boards by pad fit (change c0175, task 10.4).
Authored boards, hermetic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, ComponentBody, FootprintInstance, ModelRef, Pad
from fenolite.model.design import Design
from fenolite.reuse.bodies import copy_bodies, pad_fit

MM = 1_000_000
QUARTER = 90_000_000
SOIC = {"1": (-3 * MM, -MM), "2": (-3 * MM, MM), "3": (3 * MM, MM), "4": (3 * MM, -MM)}
"""Four pads of an authored package, in the footprint frame (Y down)."""
BODY = ComponentBody(
    id=derived_id("bdy", "bodies", "soic"),
    kind="model",
    height=1_750_000,
    outline=(Point(-2 * MM, -2 * MM), Point(2 * MM, -2 * MM), Point(2 * MM, 2 * MM), Point(-2 * MM, 2 * MM)),
    layer="F.Fab",
    model="parts/soic4.step",
)
MODEL = ModelRef("parts/soic4.step", offset=(MM, 0, 0))


def turned(pads: dict[str, tuple[int, int]], quarter: int) -> dict[str, tuple[int, int]]:
    """``pads`` turned counter-clockwise on screen (Y down) by ``quarter`` quarter turns."""
    out = dict(pads)
    for _ in range(quarter):
        out = {number: (y, -x) for number, (x, y) in out.items()}
    return out


def part(
    ref: str,
    pads: dict[str, tuple[int, int]],
    *,
    bodies: Sequence[ComponentBody] = (),
    models: Sequence[ModelRef] = (),
) -> FootprintInstance:
    return FootprintInstance(
        id=derived_id("fp", "bodies", ref),
        component_id=derived_id("cmp", "bodies", ref),
        lib_ref="kit:SOIC4",
        position=Point(10 * MM, 10 * MM),
        pads=tuple(
            Pad(
                id=derived_id("pad", "bodies", f"{ref}.{n}"),
                number=n,
                shape="rect",
                size=Size(MM, MM // 2),
                position=Point(*at),
            )
            for n, at in pads.items()
        ),
        bodies=tuple(bodies),
        models=tuple(models),
    )


def board(name: str, *parts: FootprintInstance) -> Design:
    design = Design.new(name, seed=1)
    return replace(design, board=Board(id=derived_id("brd", "bodies", name), footprints=parts))


REFERENCE = board("reference", part("U1", SOIC, bodies=(BODY,), models=(MODEL,)))


def test_same_pads_copy_unchanged() -> None:
    result = copy_bodies(REFERENCE, board("target", part("U9", SOIC)))
    (row,) = result.rows
    assert (row.status, row.turn, row.residual) == ("copied", 0, 0)
    assert row.source == REFERENCE.board.footprints[0].id  # type: ignore[union-attr]
    (copied,) = result.design.board.footprints  # type: ignore[union-attr]
    assert copied.bodies == (BODY,) and copied.models == (MODEL,)
    assert result.variants == (("parts/soic4.step", (0,)),)


def test_turned_footprint_turns_the_body_and_the_model() -> None:
    """A target footprint drawn a quarter turn from the reference takes the body turned with its pads."""
    result = copy_bodies(REFERENCE, board("target", part("U9", turned(SOIC, 1))))
    (row,) = result.rows
    assert (row.status, row.turn) == ("copied", 1)
    (copied,) = result.design.board.footprints  # type: ignore[union-attr]
    (model,) = copied.models
    assert model.offset == (0, -MM, 0) and model.rotation == (0, 0, QUARTER)
    (body,) = copied.bodies
    assert set(body.outline) == set(BODY.outline)  # a square turns onto itself
    assert body.outline[0] == Point(-2 * MM, 2 * MM)
    assert result.variants == (("parts/soic4.step", (1,)),)


def test_variants_list_every_rotation() -> None:
    target = board("target", part("U8", SOIC), part("U9", turned(SOIC, 2)), part("U7", turned(SOIC, 3)))
    result = copy_bodies(REFERENCE, target)
    assert [row.turn for row in result.rows] == [0, 2, 3]
    assert result.variants == (("parts/soic4.step", (0, 2, 3)),)


def test_no_fit_kept_and_mirror() -> None:
    other = {n: (x * 2, y) for n, (x, y) in SOIC.items()}  # another pitch
    mirrored = {n: (-x, y) for n, (x, y) in SOIC.items()}  # a mirror image is no fit
    owned = part("U5", SOIC, models=(ModelRef("parts/own.step"),))
    result = copy_bodies(REFERENCE, board("target", part("U1", other), part("U2", mirrored), owned))
    assert [row.status for row in result.rows] == ["no-fit", "no-fit", "kept"]
    assert result.design.board.footprints[2] == owned  # type: ignore[union-attr]
    assert result.variants == ()


def test_ambiguous_references_copy_nothing() -> None:
    second = part("U2", SOIC, bodies=(replace(BODY, height=900_000),))
    reference = board("reference", REFERENCE.board.footprints[0], second)  # type: ignore[union-attr]
    (row,) = copy_bodies(reference, board("target", part("U9", SOIC))).rows
    assert row.status == "ambiguous" and row.source is None


def test_tilted_model_is_not_turned() -> None:
    tilted = part("U1", SOIC, models=(ModelRef("parts/soic4.step", rotation=(QUARTER, 0, 0)),))
    result = copy_bodies(
        board("reference", tilted), board("target", part("U9", turned(SOIC, 1)), part("U8", SOIC))
    )
    assert [row.status for row in result.rows] == ["tilted", "copied"]


def test_pad_fit_needs_two_numbered_places() -> None:
    one = part("U1", {"1": (0, 0)}).pads
    assert pad_fit(one, one) is None
    same_place = part("U1", {"1": (0, 0), "2": (0, 0)}).pads
    assert pad_fit(same_place, same_place) is None
    renumbered = part("U1", {"A": (0, 0), "B": (MM, 0)}).pads
    assert pad_fit(part("U1", {"1": (0, 0), "2": (MM, 0)}).pads, renumbered) is None
    near = part("U1", {n: (x + 40_000, y) for n, (x, y) in SOIC.items()}).pads
    assert pad_fit(part("U1", SOIC).pads, near) is not None
    assert pad_fit(part("U1", SOIC).pads, near, tolerance=10_000) is not None  # a translation fits exactly
