# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit physical reservations and bounded placement inputs (c0096)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.polygon import Polygon
from fenolite.model.board import MechanicalIntent
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CONSTRAINED-PLACE",))


@dataclass(frozen=True)
class MechanicalVolume:
    """An explicitly supplied board-frame reservation volume, in integer nm."""

    name: str
    outline: tuple[Point, ...]
    z_min: int
    z_max: int
    status: Literal["exact", "conservative"] = "exact"

    def __post_init__(self) -> None:
        if type(self.z_min) is not int or type(self.z_max) is not int or self.z_min > self.z_max:
            raise ValueError("volume bounds must be ordered integer nm")
        Polygon(self.outline)


@dataclass(frozen=True)
class MechanicalConstraints:
    board_thickness: int | None = None
    allowed_penetrations: tuple[MechanicalVolume, ...] = ()
    obstacles: tuple[MechanicalVolume, ...] = ()
    missing_assembly: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.board_thickness is not None and (
            type(self.board_thickness) is not int or self.board_thickness <= 0
        ):
            raise ValueError("board thickness must be positive integer nm")


@dataclass(frozen=True)
class MechanicalReservation:
    """Use one existing drill; declared volumes are in the board frame and never create a Hole."""

    key: str
    footprint_id: str
    pad_id: str
    volumes: tuple[MechanicalVolume, ...] = ()
    fixed: bool = True
    intent: MechanicalIntent | None = None


@dataclass(frozen=True)
class GroupRegion:
    key: str
    footprint_ids: tuple[str, ...]
    outline: tuple[Point, ...]

    def __post_init__(self) -> None:
        Polygon(self.outline)
        if not self.key or not self.footprint_ids or len(set(self.footprint_ids)) != len(self.footprint_ids):
            raise ValueError("a group region needs a key and distinct footprint ids")


@dataclass(frozen=True)
class PlacementObjective:
    """A pad-centre distance surrogate; no routed electrical property is inferred."""

    key: str
    first_pad: str
    second_pad: str
    max_distance: int | None = None
    weight: int = 1
    require_connected: bool = True

    def __post_init__(self) -> None:
        if not self.key or not self.first_pad or not self.second_pad or self.first_pad == self.second_pad:
            raise ValueError("an objective needs a key and two distinct pad ids")
        if type(self.weight) is not int or self.weight <= 0:
            raise ValueError("objective weight must be positive integer")
        if self.max_distance is not None and (type(self.max_distance) is not int or self.max_distance < 0):
            raise ValueError("maximum distance must be nonnegative integer nm")


@dataclass(frozen=True)
class PlacementConstraints:
    pitch: int = 500_000
    edge_clearance: int = 0
    gap: int = 0
    max_candidates: int = 2048
    reservations: tuple[MechanicalReservation, ...] = ()
    regions: tuple[GroupRegion, ...] = ()
    volumes: MechanicalConstraints = MechanicalConstraints()
    source_frame: str = "board"
    source_hashes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name, value, positive in (
            ("pitch", self.pitch, True),
            ("max_candidates", self.max_candidates, True),
            ("edge_clearance", self.edge_clearance, False),
            ("gap", self.gap, False),
        ):
            if type(value) is not int or value < (1 if positive else 0):
                raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'} integer")
        if self.source_frame != "board":
            raise ValueError("placement constraints use the written board frame")
        for rows in (self.reservations, self.regions):
            keys = [row.key for row in rows]
            if any(not key for key in keys) or len(keys) != len(set(keys)):
                raise ValueError("constraint keys must be distinct and nonempty")


@dataclass(frozen=True)
class MechanicalReview:
    duplicate_drills: tuple[tuple[str, ...], ...]
    linked_drills: tuple[tuple[str, str], ...]
    missing_inputs: tuple[str, ...]
    evidence: Evidence = EVIDENCE


@dataclass(frozen=True)
class PlacementRequest:
    schema: Literal["fenolite.placement-request.v0"] = "fenolite.placement-request.v0"
    constraints: PlacementConstraints = PlacementConstraints()
    objectives: tuple[PlacementObjective, ...] = ()


def review_mechanics(
    design: Design, pads: tuple[BoardPad, ...], reservations: tuple[MechanicalReservation, ...] = ()
) -> MechanicalReview:
    """Locate duplicate drills and unresolved reservation inputs without changing any pad or net."""
    drills: dict[tuple[Point, ...], set[str]] = {}
    by_pad = {(pad.footprint_id, pad.pad_id): pad for pad in pads}
    for pad in pads:
        if pad.hole and pad.drill is not None:
            drills.setdefault(tuple(sorted(pad.hole)), set()).add(pad.pad_id)
    if design.board is not None:
        for hole in design.board.holes:
            drills.setdefault((hole.position,), set()).add(hole.id)
    missing: list[str] = []
    linked: list[tuple[str, str]] = []
    reserved: set[tuple[str, str]] = set()
    for reservation in reservations:
        identity = (reservation.footprint_id, reservation.pad_id)
        if identity in reserved:
            missing.append(f"reservation:{reservation.key}:duplicate_reference")
        reserved.add(identity)
        pad = by_pad.get(identity)
        if pad is None or not pad.hole or pad.drill is None:
            missing.append(f"reservation:{reservation.key}:existing_drill")
        else:
            linked.append((reservation.key, pad.pad_id))
        if not reservation.volumes:
            missing.append(f"reservation:{reservation.key}:reservation_geometry")
        if (
            reservation.intent is None
            or not reservation.intent.source
            or reservation.intent.status != "measured"
        ):
            missing.append(f"reservation:{reservation.key}:source_measurement")
    duplicates = tuple(sorted(tuple(sorted(ids)) for ids in drills.values() if len(ids) > 1))
    return MechanicalReview(duplicates, tuple(sorted(linked)), tuple(sorted(set(missing))))


__all__ = [
    "MechanicalVolume",
    "MechanicalConstraints",
    "PlacementRequest",
    "MechanicalReservation",
    "GroupRegion",
    "PlacementObjective",
    "PlacementConstraints",
    "MechanicalReview",
    "review_mechanics",
]
