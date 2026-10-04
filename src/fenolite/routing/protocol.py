# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data contract shared by routing engines and the Fenolite routing command."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design


@dataclass(frozen=True, slots=True)
class JobPad:
    """A placed pad in board coordinates, with copper layers and optional drill size."""

    ref: str
    number: str
    net: str
    position: Point
    layers: tuple[str, ...]
    drill: Nm | None = None


@dataclass(frozen=True, slots=True)
class JobNet:
    """One selected net and the physical constraints a router must use (all lengths in nm)."""

    name: str
    net_id: str
    pads: tuple[JobPad, ...]
    width: Nm
    clearance: Nm
    via_diameter: Nm
    via_drill: Nm


@dataclass(frozen=True, slots=True)
class RoutingJob:
    """A model-only routing request; no backend file paths cross the plugin boundary."""

    design: Design
    nets: tuple[JobNet, ...]
    layers: tuple[str, ...]
    options: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class RoutingResult:
    """Proposed copper and per-net outcome. Every route remains UNVERIFIED until KiCad checks it."""

    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    routed: tuple[str, ...] = ()
    unrouted: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()
    tool: str = ""
    tool_version: str = ""
    log: tuple[str, ...] = ()
    evidence: Evidence = field(default_factory=Evidence)


@dataclass(frozen=True, slots=True)
class RouterStatus:
    """Whether a router can run in this environment and, when known, its installation details."""

    available: bool
    path: str = ""
    version: str = ""
    reason: str = ""


class Router(Protocol):
    """A pluggable engine that proposes routed copper for a model-only job."""

    name: str
    description: str
    sends_data_offsite: bool

    def available(self) -> RouterStatus:
        """Report readiness without routing a board."""
        ...

    def route(self, job: RoutingJob) -> RoutingResult:
        """Return proposed copper; the caller remains responsible for writing and verification."""
        ...


__all__ = [
    "JobNet",
    "JobPad",
    "Router",
    "RouterStatus",
    "RoutingJob",
    "RoutingResult",
]
