# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable role-field interchange, independent of the roles/check packages (c0366).

Distances are declared constraints. Influence costs are software preferences, never rules.
Ground geometry in this packet is validated saved copper, never a zone outline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash
from fenolite.geometry import Thick
from fenolite.model.canonical import to_data
from fenolite.model.design import Design

if TYPE_CHECKING:
    from fenolite.routing.protocol import Candidate, RoutingJob


FIELD_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SEARCH-ROLE-FIELDS", "H-G-SEARCH-ROLE-COSTS"))


def board_fingerprint(design: Design) -> str:
    """Hash the actual circuit, geometry and rules, without process-local geometry caches."""
    return content_hash(to_data(design.circuit), to_data(design.board), to_data(design.rules))


@dataclass(frozen=True, slots=True)
class Provenance:
    board: str
    roles: str
    profile: str
    fill: str

    def __post_init__(self) -> None:
        if any(
            re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in (self.board, self.roles, self.profile, self.fill)
        ):
            raise ValueError("field provenance requires four SHA-256 fingerprints")


@dataclass(frozen=True, slots=True)
class Spacing:
    victim: str
    aggressor: str
    distance: int
    kind: Literal["high-voltage", "switching", "declared-distance"]
    origin: str

    def __post_init__(self) -> None:
        if type(self.distance) is not int or self.distance < 0:
            raise ValueError("field distances must be nonnegative integer nanometres")
        if self.kind not in ("high-voltage", "switching", "declared-distance") or not self.origin:
            raise ValueError("field spacing needs its kind and provenance")


@dataclass(frozen=True, slots=True)
class Influence:
    victim: str
    aggressor: str
    distance: int

    def __post_init__(self) -> None:
        if type(self.distance) is not int or self.distance < 0:
            raise ValueError("field influences must be nonnegative integer nanometres")


@dataclass(frozen=True, slots=True)
class Copper:
    net: str
    layer: str
    shape: Thick
    source: str


@dataclass(frozen=True, slots=True)
class Ground:
    net: str
    layer: str
    polygon: tuple[Point, ...]

    def __post_init__(self) -> None:
        if type(self.polygon) is not tuple or len(self.polygon) < 3:
            raise ValueError("a reference field needs an immutable saved-fill ring")


@dataclass(frozen=True, slots=True)
class Fields:
    provenance: Provenance
    layers: tuple[str, ...]
    spacings: tuple[Spacing, ...] = ()
    influences: tuple[Influence, ...] = ()
    copper: tuple[Copper, ...] = ()
    ground: tuple[Ground, ...] = ()
    missing: tuple[tuple[str, str], ...] = ()
    unknowns: tuple[str, ...] = ()
    confirmed_groups: tuple[str, ...] = ()
    reference_expected: bool = False

    def __post_init__(self) -> None:
        if any(
            type(value) is not tuple
            for value in (
                self.layers,
                self.spacings,
                self.influences,
                self.copper,
                self.ground,
                self.missing,
                self.unknowns,
                self.confirmed_groups,
            )
        ):
            raise ValueError("field collections must be immutable tuples")

    @property
    def fingerprint(self) -> str:
        """Include payload data, but not Thick's mutable acceleration caches."""
        shapes = [
            [s.net, s.layer, [[p.x, p.y] for p in s.shape.core], s.shape.width, s.shape.filled, s.source]
            for s in self.copper
        ]
        return content_hash(
            to_data(self.provenance),
            self.layers,
            to_data(self.spacings),
            to_data(self.influences),
            shapes,
            to_data(self.ground),
            self.missing,
            self.unknowns,
            self.confirmed_groups,
            self.reference_expected,
        )


@dataclass(frozen=True, slots=True)
class Measurement:
    length: int
    reference_lower_bound: int
    switching_upper_bound: int
    penalty: int


class Evaluator:
    """Per-job geometry caches over immutable fields; no import from roles or checks."""

    def __init__(self, fields: Fields) -> None:
        self.fields = fields
        self._allowed: dict[tuple[str, str, tuple[Point, ...], int], bool] = {}
        self._measured: dict[tuple[str, str, tuple[Point, ...], int], Measurement] = {}

    def adjacent(self, layer: str) -> tuple[str, ...]:
        if layer not in self.fields.layers:
            return ()
        index = self.fields.layers.index(layer)
        return tuple(
            self.fields.layers[i] for i in (index - 1, index + 1) if 0 <= i < len(self.fields.layers)
        )

    def allows(self, net: str, layer: str, points: tuple[Point, ...], width: int) -> bool:
        from fenolite.geometry import thick_closer_than

        key = (net, layer, points, width)
        if key in self._allowed:
            return self._allowed[key]
        shape = Thick(points, width)
        allowed = not any(victim == net for victim, _ in self.fields.missing)
        for spacing in self.fields.spacings:
            if spacing.victim != net:
                continue
            for other in self.fields.copper:
                if other.net != spacing.aggressor:
                    continue
                if spacing.kind != "switching":
                    # Conservative projection on every copper layer; never infer laminate insulation.
                    limit = spacing.distance
                elif other.layer == layer:
                    limit = spacing.distance
                elif other.layer in self.adjacent(layer):
                    limit = 1  # overlap test, not a new electrical distance
                else:
                    continue
                if thick_closer_than(shape, other.shape, limit):
                    allowed = False
                    break
        self._allowed[key] = allowed
        return allowed

    def measure(self, net: str, layer: str, points: tuple[Point, ...], width: int) -> Measurement:
        from math import isqrt

        from fenolite.geometry import Location, point_in_ring, thick_closer_than

        key = (net, layer, points, width)
        if key in self._measured:
            return self._measured[key]
        total, reference, exposure = 0, 0, 0
        adjacent = self.adjacent(layer)
        for a, b in zip(points, points[1:], strict=False):
            length = isqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
            total += length
            shape = Thick((a, b), width)
            covered = False
            for ground in self.fields.ground:
                if ground.layer not in adjacent:
                    continue
                boundary = Thick((*ground.polygon, ground.polygon[0]), 0)
                if (
                    point_in_ring(a, ground.polygon) is Location.INSIDE
                    and point_in_ring(b, ground.polygon) is Location.INSIDE
                    and not thick_closer_than(shape, boundary, 1)
                ):
                    covered = True
                    break
            reference += length if covered else 0
            near = False
            for influence in self.fields.influences:
                if influence.victim != net:
                    continue
                for other in self.fields.copper:
                    if other.net != influence.aggressor:
                        continue
                    reach = (
                        influence.distance if other.layer == layer else (1 if other.layer in adjacent else 0)
                    )
                    if reach > 0 and thick_closer_than(shape, other.shape, reach):
                        near = True
                        break
                if near:
                    break
            exposure += length if near else 0
        # Authored software heuristic: one extra length unit for an unconfirmed reference
        # when that policy is active, and one for switching exposure. No negative reward.
        penalty = (total - reference if self.fields.reference_expected else 0) + exposure
        result = Measurement(total, reference, exposure, penalty)
        self._measured[key] = result
        return result


def rejection(job: RoutingJob, candidate: Candidate, fields: Fields) -> str:
    """Both existing judges remain authoritative; inference never becomes a hard role."""
    from collections.abc import Callable, Sequence
    from typing import cast

    from fenolite.routing.merge import RoutingError, apply
    from fenolite.routing.octilinear import fresh
    from fenolite.routing.protocol import RoutingResult

    names = {net.id: net.name for net in job.design.circuit.nets}
    evaluator = Evaluator(fields)
    if candidate.arcs:
        return "search-role-refused"
    for track in candidate.tracks:
        net = names.get(track.net_id or "")
        if net is None or not evaluator.allows(net, track.layer, (track.start, track.end), track.width):
            return "search-role-refused"
    for via in candidate.vias:
        net = names.get(via.net_id or "")
        probe = (via.position, Point(via.position.x + 1, via.position.y))
        if net is None or not all(evaluator.allows(net, layer, probe, via.diameter) for layer in job.layers):
            return "search-role-refused"
    copper = job.extra.get("copper_check")
    roles = job.extra.get("role_check")
    if not callable(copper) or not callable(roles):
        return "search-role-refused"
    try:
        after = apply(job.design, RoutingResult(tracks=candidate.tracks, vias=candidate.vias))
    except RoutingError:
        return "search-role-refused"
    copper_judge = cast("Callable[[Design],Sequence[tuple[str,str,tuple[str,...],int]]]", copper)
    if fresh(copper_judge(job.design), copper_judge(after)):
        return "search-role-refused"
    role_judge = cast("Callable[[Design],Sequence[tuple[str,str,str,int|None]]]", roles)

    def known(rows: Sequence[tuple[str, str, str, int | None]]) -> dict[tuple[str, str, str], int | None]:
        return {
            (code, group, severity): measure
            for code, group, severity, measure in rows
            if group in fields.confirmed_groups
            and severity in ("warning", "error")
            and code != "roles.loop-open"
        }

    before, following = known(role_judge(job.design)), known(role_judge(after))
    for key, measure in following.items():
        old = before.get(key)
        if key not in before or (measure is not None and old is not None and measure > old):
            return "search-role-refused"
    return ""
