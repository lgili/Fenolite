# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative, emitted-grid symbol and text envelopes; text metrics are INFERRED."""

from __future__ import annotations

from fenolite.schematic.composition import (
    CHAR_WIDTH,
    GRID,
    NM_PER_MIL,
    TEXT_HEIGHT,
    Box,
    Pin,
    Unit,
    Visible,
    rotate,
    union,
    up,
)

STEPS = ((1, 0), (0, -1), (-1, 0), (0, 1))


def rotated_box(box: Box, quarter: int) -> Box:
    points = tuple(
        rotate(p, quarter) for p in ((box.x0, box.y0), (box.x1, box.y0), (box.x0, box.y1), (box.x1, box.y1))
    )
    return Box(
        min(x for x, _ in points),
        min(y for _, y in points),
        max(x for x, _ in points),
        max(y for _, y in points),
    )


def field_boxes(unit: Unit, quarter: int) -> tuple[Box, Box]:
    body = rotated_box(unit.body, quarter)
    # Positions are hotspots matching horizontal left-justified native fields.
    return (
        Box(
            body.x0,
            body.y0 - 2 * TEXT_HEIGHT,
            body.x0 + max(1, len(unit.ref)) * CHAR_WIDTH,
            body.y0 - TEXT_HEIGHT,
        ),
        Box(
            body.x0,
            body.y1 + TEXT_HEIGHT,
            body.x0 + max(1, len(unit.value)) * CHAR_WIDTH,
            body.y1 + 2 * TEXT_HEIGHT,
        ),
    )


def pin_stub(pin: Pin, quarter: int) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    start = rotate(pin.at, quarter)
    side = (pin.direction + quarter) % 4
    dx, dy = STEPS[side]
    length = max(300 * NM_PER_MIL, up(CHAR_WIDTH * len(pin.net or "") + 150 * NM_PER_MIL))
    if pin.power:
        # Budget the longest possible staggered native power stub, not just its nominal 200 mil.
        length += 400 * NM_PER_MIL
    end = (start[0] + dx * length, start[1] + dy * length)
    mark = end if pin.power or side in (2, 3) else (start[0] + dx * GRID, start[1] + dy * GRID)
    return start, end, mark


def visible_envelopes(unit: Unit, quarter: int = 0) -> tuple[Visible, ...]:
    body = rotated_box(unit.body, quarter)
    ref, value = field_boxes(unit, quarter)
    found = [
        Visible(unit.key, "body", body),
        Visible(unit.key, "reference", ref),
        Visible(unit.key, "value", value),
    ]
    for pin in unit.pins:
        start, end = rotate(pin.body_at, quarter), rotate(pin.at, quarter)
        found.append(
            Visible(
                f"{unit.key}/{pin.number}",
                "pin",
                Box(
                    min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])
                ).expanded(NM_PER_MIL),
            )
        )
        if pin.name:
            # Pin names lie inside/near the body. A conservative envelope contributes to the cell
            # but is not treated as an obstacle to its own pin.
            width = max(TEXT_HEIGHT, len(pin.name) * CHAR_WIDTH)
            found.append(
                Visible(
                    f"{unit.key}/{pin.number}",
                    "pin-text",
                    Box(start[0] - width, start[1] - TEXT_HEIGHT, start[0] + width, start[1] + TEXT_HEIGHT),
                )
            )
        if pin.net is None:
            continue
        p0, p1, mark = pin_stub(pin, quarter)
        found.append(
            Visible(
                f"{unit.key}/{pin.number}",
                "stub",
                Box(min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])).expanded(
                    NM_PER_MIL
                ),
            )
        )
        width = max(TEXT_HEIGHT, len(pin.net) * CHAR_WIDTH)
        if pin.power:
            label = Box(
                mark[0] - width - GRID, mark[1] - width - GRID, mark[0] + width + GRID, mark[1] + width + GRID
            )
        elif (pin.direction + quarter) % 2:
            label = Box(mark[0] - TEXT_HEIGHT, mark[1] - width, mark[0] + TEXT_HEIGHT, mark[1])
        else:
            label = Box(mark[0], mark[1] - TEXT_HEIGHT, mark[0] + width, mark[1] + TEXT_HEIGHT)
        found.append(Visible(f"{unit.key}/{pin.number}", "net-label", label))
    return tuple(found)


def unit_bounds(unit: Unit, quarter: int = 0) -> Box:
    envelope = union(tuple(v.box for v in visible_envelopes(unit, quarter))).expanded(2 * GRID)
    return Box((envelope.x0 // GRID) * GRID, (envelope.y0 // GRID) * GRID, up(envelope.x1), up(envelope.y1))


def content_region(paper: Box, margins: tuple[int, int, int, int]) -> Box:
    left, right, top, bottom = margins
    return Box(paper.x0 + left, paper.y0 + top, paper.x1 - right, paper.y1 - bottom)
