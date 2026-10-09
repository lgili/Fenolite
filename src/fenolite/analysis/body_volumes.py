# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mounted-face signed extrusions and explicit conservative/unknown mechanical checks (c0099)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.boolean import select_backend
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.model.board import ComponentBody, FootprintInstance
from fenolite.model.design import Design

Status = Literal["exact", "conservative", "unknown"]
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BODY-VOLUME", "H-A-IMP-BODY-Z"))


@dataclass(frozen=True)
class BodyVolume:
    name: str
    outline: tuple[Point, ...]
    z_min: int
    z_max: int
    status: Status = "exact"

    def __post_init__(self) -> None:
        if type(self.z_min) is not int or type(self.z_max) is not int or self.z_min > self.z_max:
            raise ValueError("volume bounds must be ordered integer nm")
        Polygon(self.outline)


@dataclass(frozen=True)
class VolumeProjection:
    body_id: str
    footprint_id: str
    volume: BodyVolume | None
    status: Status
    reason: str = ""


@dataclass(frozen=True)
class VolumeConstraints:
    board_thickness: int | None = None
    allowed_penetrations: tuple[BodyVolume, ...] = ()
    obstacles: tuple[BodyVolume, ...] = ()
    missing_assembly: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.board_thickness is not None and (
            type(self.board_thickness) is not int or self.board_thickness <= 0
        ):
            raise ValueError("board thickness must be positive integer nm")


@dataclass(frozen=True)
class VolumeFinding:
    code: str
    first: str
    second: str
    status: Status
    reason: str


@dataclass(frozen=True)
class VolumeReport:
    projections: tuple[VolumeProjection, ...]
    findings: tuple[VolumeFinding, ...]
    missing_inputs: tuple[str, ...]
    evidence: Evidence = EVIDENCE

    @property
    def qualified_clear(self) -> bool:
        return (
            not self.findings
            and not self.missing_inputs
            and all(p.status == "exact" for p in self.projections)
        )


def body_volume(
    body: ComponentBody, footprint: FootprintInstance, *, board_thickness: int | None = None
) -> VolumeProjection:
    """Global Z=0 is the top face; the bottom face is -thickness. XY follows the stored pad frame."""

    def unknown(reason: str) -> VolumeProjection:
        return VolumeProjection(body.id, footprint.id, None, "unknown", reason)

    if body.projection_unknown:
        return unknown("unproved source projection")
    lo, hi = body.z_min, body.z_max
    if lo is None and hi is None:
        lo, hi = body.standoff, body.height
        if lo < 0:
            return unknown("invalid legacy standoff without signed bounds")
    if lo is None or hi is None or lo > hi:
        return unknown("incomplete/reversed body bounds")
    if len(body.outline) < 3:
        return unknown("missing body outline")
    status: Status = "conservative" if body.kind == "model" else "exact"
    if footprint.side == "bottom":
        if board_thickness is None:
            return unknown("board thickness required for bottom-face Z")
        lo, hi = -board_thickness - hi, -board_thickness - lo
    frame = Transform.placement(footprint.position, footprint.rotation)
    outline = tuple(frame.apply(p) for p in body.outline)
    if footprint.rotation % 90_000_000:
        status = "conservative"  # transform rounds each XY coordinate within 0.5 nm
    try:
        volume = BodyVolume(body.id, outline, lo, hi, status)
    except GeometryError:
        return unknown("invalid body polygon")
    return VolumeProjection(body.id, footprint.id, volume, status)


def _intersection(a: BodyVolume, b: BodyVolume) -> tuple[tuple[Polygon, ...], int, int] | None:
    lo, hi = max(a.z_min, b.z_min), min(a.z_max, b.z_max)
    if lo >= hi or not BBox.of_points(a.outline).intersects(BBox.of_points(b.outline)):
        return None
    shapes = select_backend().intersection(Polygon(a.outline), Polygon(b.outline))
    return (shapes, lo, hi) if shapes else None


def _allowed(shapes: tuple[Polygon, ...], lo: int, hi: int, allowed: tuple[BodyVolume, ...]) -> bool:
    for permit in allowed:
        if permit.z_min > lo or permit.z_max < hi:
            continue
        ring = Polygon(permit.outline)
        if ring.is_convex() and all(
            ring.locate(p).value != "outside" for shape in shapes for p in shape.outer
        ):
            return True
    return False


def check_body_volumes(design: Design, constraints: VolumeConstraints | None = None) -> VolumeReport:
    """Check known bodies against each other, board material and declared obstacles; unknowns never pass."""
    constraints = constraints or VolumeConstraints()
    board = design.board
    if board is None:
        return VolumeReport((), (), ("board",))
    thickness = constraints.board_thickness
    if (
        thickness is None
        and board.stackup
        and board.stackup.layers
        and all(layer.thickness > 0 for layer in board.stackup.layers)
    ):
        thickness = sum(layer.thickness for layer in board.stackup.layers)
    projections = tuple(
        body_volume(b, fp, board_thickness=thickness) for fp in board.footprints for b in fp.bodies
    )
    missing = list(constraints.missing_assembly)
    if thickness is None:
        missing.append("board_thickness")
    for fp in board.footprints:
        if not fp.bodies:
            missing.append(f"body:{fp.id}")
    for p in projections:
        if p.status != "exact":
            missing.append(f"volume:{p.body_id}:{p.reason or p.status}")
    known = [p for p in projections if p.volume is not None]
    findings: list[VolumeFinding] = []

    def check(a: BodyVolume, b: BodyVolume, *, code: str) -> None:
        try:
            hit = _intersection(a, b)
        except (GeometryError, BackendUnavailable) as exc:
            findings.append(VolumeFinding(code, a.name, b.name, "unknown", str(exc)))
            return
        if hit is not None and not _allowed(*hit, constraints.allowed_penetrations):
            state: Status = "exact" if a.status == b.status == "exact" else "conservative"
            findings.append(VolumeFinding(code, a.name, b.name, state, "intersecting extrusions"))

    for a, b in combinations(known, 2):
        if a.footprint_id != b.footprint_id:
            assert a.volume is not None and b.volume is not None
            check(a.volume, b.volume, code="body.intersection")
    for p in known:
        assert p.volume is not None
        for obstacle in constraints.obstacles:
            check(p.volume, obstacle, code="body.assembly-intersection")
        if thickness is None or p.volume.z_min >= 0 or p.volume.z_max <= -thickness:
            continue
        if board.outline is None:
            missing.append("board_outline")
            continue
        # Entire projection inside a cutout or physical drill contains no board material.
        shape = Polygon(p.volume.outline)
        free = any(
            Polygon(c).is_convex() and all(Polygon(c).locate(v).value != "outside" for v in shape.outer)
            for c in board.outline.cutouts
        )
        circles = [(h.position, h.drill) for h in board.holes]
        for fp in board.footprints:
            frame = Transform.placement(fp.position, fp.rotation)
            circles.extend(
                (frame.apply(pad.position), pad.drill)
                for pad in fp.pads
                if pad.drill is not None and (pad.padstack is None or pad.padstack.hole_shape == "round")
            )
        free |= any(
            all(4 * ((v.x - at.x) ** 2 + (v.y - at.y) ** 2) <= drill**2 for v in shape.outer)
            for at, drill in circles
        )
        if not free:
            check(
                p.volume,
                BodyVolume(
                    "board",
                    board.outline.points,
                    -thickness,
                    0,
                    "conservative" if board.outline.cutouts or circles else "exact",
                ),
                code="body.board-penetration",
            )
    return VolumeReport(projections, tuple(findings), tuple(sorted(set(missing))))


__all__ = [
    "BodyVolume",
    "VolumeProjection",
    "VolumeConstraints",
    "VolumeFinding",
    "VolumeReport",
    "body_volume",
    "check_body_volumes",
]
