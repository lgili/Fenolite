# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded position sampling from projected footprint envelopes."""

from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.geometry.shapes import BBox
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.optimization_contract import ProposedPose


@dataclass(frozen=True, slots=True)
class PoseDomain:
    poses: tuple[ProposedPose, ...]
    attempts: int
    exhausted: bool


def _positions(box: BBox, pitch: int, anchors: tuple[Point, ...], initial: Point | None) -> Iterator[Point]:
    if initial is not None:
        yield initial
    yield from anchors
    yield Point((box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2)
    for y in (box.y0, box.y1):
        for x in (box.x0, box.x1):
            yield Point(x, y)
    for y in range(box.y0, box.y1 + 1, pitch):
        for x in range(box.x0, box.x1 + 1, pitch):
            yield Point(x, y)


def pads_near_anchor(
    anchor_pad: Point, anchor: BBox, moving_pad_offset: Point, envelope: BBox, gap: int
) -> tuple[Point, ...]:
    """Seed all four sides of an anchor, aligning the reviewed pads on the free axis."""
    x = anchor_pad.x - moving_pad_offset.x
    y = anchor_pad.y - moving_pad_offset.y
    spacing = max(1, gap)
    return tuple(
        sorted(
            (
                Point(anchor.x0 - envelope.x1 - spacing, y),
                Point(anchor.x1 - envelope.x0 + spacing, y),
                Point(x, anchor.y0 - envelope.y1 - spacing),
                Point(x, anchor.y1 - envelope.y0 + spacing),
            ),
            key=lambda point: (abs(point.x - x) + abs(point.y - y), point),
        )
    )


def sample_domain(
    current: ProposedPose,
    board: BBox,
    envelopes: Mapping[int, BBox],
    constraints: PlacementConstraints,
    *,
    anchors: tuple[Point, ...] = (),
    oriented_anchors: Mapping[int, tuple[Point, ...]] | None = None,
    max_attempts: int,
) -> PoseDomain:
    """Sample same-side poses. Envelopes are offsets from the origin for each allowed rotation.

    Bounds are a necessary condition only. Each sampled pose still needs the full geometry,
    electrical and mechanical checks before it is usable.
    """
    if type(max_attempts) is not int or max_attempts < 0:
        raise ValueError("pose sampling needs a nonnegative integer work limit")
    if any(type(angle) is not int or not 0 <= angle < 360_000_000 for angle in envelopes):
        raise ValueError("domain rotations must be normalized integer microdegrees")

    region_boxes = [
        BBox.of_points(region.outline)
        for region in constraints.regions
        if current.footprint_id in region.footprint_ids
    ]
    streams: deque[tuple[int, BBox, Iterator[Point]]] = deque()
    rotations = sorted(envelopes, key=lambda angle: (angle != current.rotation, angle))
    for angle in rotations:
        extent = envelopes[angle]
        margin = constraints.edge_clearance
        x0 = max([board.x0 + margin, *(box.x0 for box in region_boxes)]) - extent.x0
        y0 = max([board.y0 + margin, *(box.y0 for box in region_boxes)]) - extent.y0
        x1 = min([board.x1 - margin, *(box.x1 for box in region_boxes)]) - extent.x1
        y1 = min([board.y1 - margin, *(box.y1 for box in region_boxes)]) - extent.y1
        if x0 <= x1 and y0 <= y1:
            bounds = BBox(x0, y0, x1, y1)
            start = current.position if angle == current.rotation else None
            seeds = (*anchors, *(oriented_anchors.get(angle, ()) if oriented_anchors is not None else ()))
            streams.append((angle, bounds, _positions(bounds, constraints.pitch, seeds, start)))

    poses: list[ProposedPose] = []
    seen: set[tuple[int, Point]] = set()
    attempts = 0
    while streams and attempts < max_attempts:
        angle, bounds, positions = streams.popleft()
        at = next(positions, None)
        if at is None:
            continue
        attempts += 1
        streams.append((angle, bounds, positions))
        key = (angle, at)
        if bounds.contains_point(at) and key not in seen:
            seen.add(key)
            poses.append(ProposedPose(current.footprint_id, at, angle, current.side))
    exhausted = any(next(positions, None) is not None for _, _, positions in streams)
    return PoseDomain(tuple(poses), attempts, exhausted)
