# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The search for designator places (change c0212; capability silkscreen-layout, "Designator placement";
``fenolite.silk.layout``), on parts and obstacles written out as rectangles: no board is read."""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.core.coords import Point
from fenolite.silk.layout import (
    ANGLE_COST,
    Choice,
    Field,
    Look,
    Obstacle,
    Part,
    Rect,
    arrange,
    candidates,
    gap2,
    gap_floor,
)

MM = 1_000_000
DEG = 1_000_000
INK = Rect(-1_000_000, -500_000, 1_000_000, 500_000)
"""A text 2 mm long and 1 mm high at angle 0."""
TURNED = Rect(-500_000, -1_000_000, 500_000, 1_000_000)
LOOKS = (Look(0, MM, MM, 150_000, INK), Look(90 * DEG, MM, MM, 150_000, TURNED))
GAP = 100_000
CLEARANCE = 150_000


def _part(key: str, x: int, y: int, *, looks: Sequence[Look] = LOOKS, current: Choice | None = None) -> Part:
    """A part with a box of 3 mm x 1.5 mm centred at (x, y) mm, its axis at 0 degrees."""
    box = Rect(x * MM - 1_500_000, y * MM - 750_000, x * MM + 1_500_000, y * MM + 750_000)
    held = ("top", current.rect) if current is not None else None
    return Part(key, key, "top", box, 0, tuple(looks), current, held)


BOARD = Rect(0, 0, 100 * MM, 100 * MM)


def _field(*obstacles: Rect, board: Rect = BOARD) -> Field:
    found = [Obstacle.of(rect.thick(), f"obstacle {n}") for n, rect in enumerate(obstacles)]

    def inside(rect: Rect) -> bool:
        return board.x0 <= rect.x0 and rect.x1 <= board.x1 and board.y0 <= rect.y0 and rect.y1 <= board.y1

    return Field(found, CLEARANCE, inside)


def test_rectangles() -> None:
    a, b = Rect(0, 0, 3, 4), Rect(6, 8, 9, 9)
    assert gap2(a, b) == 25 and gap_floor(a, b) == 5 and gap2(a, a) == 0
    assert Rect(0, 0, 0, 5).thick().core == (Point(0, 0), Point(0, 5))
    assert Rect(1, 1, 1, 1).thick().core == (Point(1, 1),)
    assert Rect(0, 0, 2, 2).thick().filled


def test_the_first_candidate_is_centred_above() -> None:
    """Alone, a part's cheapest candidate is centred above it at the part's angle, ``gap`` away."""
    part = _part("R1", 10, 10)
    first = candidates(part, [], gap=GAP)[0]
    assert first.slot == (0, 0, 0) and first.look.angle == 0
    assert first.rect == Rect(9 * MM, 9_250_000 - GAP - MM, 11 * MM, 9_250_000 - GAP)
    turned = next(c for c in candidates(part, [], gap=GAP) if c.look.angle == 90 * DEG)
    assert turned.cost >= first.cost + ANGLE_COST


def test_a_foreign_part_nearer_than_the_own_one_costs_much() -> None:
    """A candidate nearer to another part than to its own part costs more than any other candidate."""
    part = _part("R1", 10, 10)
    other = Rect(9 * MM, 7 * MM, 11 * MM, 8_900_000)  # just above R1's box
    found = candidates(part, [other], gap=GAP)
    above = next(c for c in found if c.slot == (0, 0, 0))
    assert found[0].slot != (0, 0, 0) and above.cost > found[-12].cost


def test_an_obstacle_moves_the_text() -> None:
    """With something above the part, its text goes below."""
    part = _part("R1", 10, 10)
    plan = arrange([part], {"top": _field(Rect(9 * MM, 7 * MM, 11 * MM, 8_500_000))}, gap=GAP)
    assert plan.placed["R1"].slot[0] == 1 and not plan.blocked


def test_a_row_shares_one_slot() -> None:
    """Three identical parts 4 mm apart, grouped: one slot for all, and the group is reported."""
    parts = [_part(f"R{n}", 10 + 4 * n, 10) for n in range(3)]
    plan = arrange(parts, {"top": _field()}, gap=GAP, groups=[["R0", "R1", "R2"]])
    assert len({choice.slot for choice in plan.placed.values()}) == 1
    assert plan.aligned == [["R0", "R1", "R2"]]
    assert len({choice.rect.y1 for choice in plan.placed.values()}) == 1


def test_a_group_without_a_common_free_slot_is_placed_part_by_part() -> None:
    """When an obstacle blocks the slot above one member, the group still lines up below."""
    parts = [_part(f"R{n}", 10 + 4 * n, 10) for n in range(2)]
    plan = arrange(
        parts, {"top": _field(Rect(9 * MM, 7 * MM, 11 * MM, 8_500_000))}, gap=GAP, groups=[["R0", "R1"]]
    )
    assert {choice.slot[0] for choice in plan.placed.values()} == {1}


def test_a_part_without_room_is_blocked_by_what_it_meets() -> None:
    part = _part("R1", 10, 10)
    plan = arrange([part], {"top": _field(board=Rect(8 * MM, 8_500_000, 12 * MM, 11_500_000))}, gap=GAP)
    assert plan.blocked == {"R1": "the board edge"} and not plan.placed


def test_repair_pushes_one_text_aside() -> None:
    """``A`` may write above or below itself, and goes first (fewer free places); ``B``, just above ``A``,
    may only write below itself, where ``A``'s text went. A repair moves ``A``'s text below ``A``."""
    a = _part("A", 10, 10, looks=(LOOKS[0],))
    b = Part("B", "B", "top", Rect(9 * MM, 6 * MM, 11 * MM, 7 * MM), 0, (LOOKS[0],))
    walls = (
        Rect(0, 8 * MM, 8_840_000, 12 * MM),  # beside the places of A's text
        Rect(11_160_000, 8 * MM, 20 * MM, 12 * MM),
        Rect(0, 5_500_000, 8_840_000, 7_500_000),  # beside the places of B's text
        Rect(11_160_000, 5_500_000, 20 * MM, 7_500_000),
        Rect(8 * MM, 5 * MM, 12 * MM, 5_300_000),  # above B
    )
    plan = arrange([a, b], {"top": _field(*walls)}, gap=GAP)
    assert set(plan.placed) == {"A", "B"} and not plan.blocked
    assert plan.placed["A"].slot[0] == 1 and plan.placed["B"].slot[0] == 1


def test_keep_holds_free_texts() -> None:
    """``keep``: a free text stays; one on an obstacle is placed again."""
    free = Choice(Point(10 * MM, 8 * MM), LOOKS[0], INK.moved(10 * MM, 8 * MM), 0, (-1, -1, -1))
    stuck = Choice(Point(20 * MM, 10 * MM), LOOKS[0], INK.moved(20 * MM, 10 * MM), 0, (-1, -1, -1))
    parts = [_part("A", 10, 10, current=free), _part("B", 20, 10, current=stuck)]
    plan = arrange(parts, {"top": _field(Rect(19 * MM, 10 * MM, 21 * MM, 10_200_000))}, gap=GAP, keep=True)
    assert plan.kept == ["A"] and set(plan.placed) == {"B"}


def test_a_text_that_stays_is_kept_clear() -> None:
    """``B`` has no room and keeps its text, which stands where ``A``'s first choice would go: ``A`` takes
    another place."""
    a = _part("A", 10, 10)
    stuck_rect = INK.moved(10 * MM, 8_650_000)
    b = Part(
        "B",
        "B",
        "top",
        Rect(30 * MM, 30 * MM, 31 * MM, 31 * MM),
        0,
        (),
        None,
        ("top", stuck_rect),
    )
    plan = arrange([a, b], {"top": _field()}, gap=GAP)
    assert "B" in plan.blocked and plan.placed["A"].slot != (0, 0, 0)
    assert gap2(plan.placed["A"].rect, stuck_rect) >= CLEARANCE * CLEARANCE
