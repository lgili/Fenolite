# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data contract shared by routing engines and the Fenolite routing command."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

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
    """One selected net and the physical constraints a router must use (all lengths in nm).

    ``tier`` orders a job: a plugin routes the tiers one after the other, lowest first, and the copper of
    earlier tiers is fixed input of later ones (capability routing, "Routing tiers"; change c0109).
    """

    name: str
    net_id: str
    pads: tuple[JobPad, ...]
    width: Nm
    clearance: Nm
    via_diameter: Nm
    via_drill: Nm
    # builds on c0107 (not on this base): ``tier`` comes after the fields c0107 adds to a job net.
    tier: int = 0


@dataclass(frozen=True, slots=True)
class RoutingJob:
    """A model-only routing request; no backend file paths cross the plugin boundary.

    ``extra`` carries data the routing package cannot type because it may not import ``backends.base``:
    the command fills ``board_pads`` (the pads of ``BoardFrame.board_pads``) and ``outline`` (the rings of
    the board outline, the board first). A router that needs neither ignores it.

    ``budget`` is the wall-clock time, in seconds, of the plugin's whole ``route()``; ``None`` gives the
    plugin's ``DEFAULT_BUDGET`` (capability routing, "Routing time budget"; change c0109). A router that
    starts no process ignores it. ``nets`` is sorted by tier, then by name.
    """

    design: Design
    nets: tuple[JobNet, ...]
    layers: tuple[str, ...]
    options: Mapping[str, str] = field(default_factory=lambda: {})
    extra: Mapping[str, object] = field(default_factory=lambda: {})
    # builds on c0107 (not on this base): ``budget`` comes after the fields c0107 adds to a job.
    budget: float | None = None


RunOutcomeName = Literal["done", "failed", "cut"]


@dataclass(frozen=True, slots=True)
class RouterRun:
    """One process a plugin started: its nets, their tier, its wall-clock seconds and how it ended.

    ``done``: the process ended inside the budget and its output was read; ``failed``: it exited with an
    error or left no readable output; ``cut``: the budget ended first, it was killed and gave no copper.
    """

    nets: tuple[str, ...]
    tier: int
    seconds: float
    outcome: RunOutcomeName


@dataclass(frozen=True, slots=True)
class RoutingResult:
    """Proposed copper and per-net outcome. Every route remains UNVERIFIED until KiCad checks it.

    ``runs`` lists one ``RouterRun`` per process the plugin started, in the order it started them, and
    ``not_attempted`` the nets of the runs it never started because the budget was spent; those nets are
    in ``unrouted`` too.
    """

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
    runs: tuple[RouterRun, ...] = ()
    not_attempted: tuple[str, ...] = ()


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
    "RouterRun",
    "RouterStatus",
    "RoutingJob",
    "RoutingResult",
]
