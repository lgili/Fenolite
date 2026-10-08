# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data contract shared by routing engines and the Fenolite routing command."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.progress import NULL_PROGRESS, Progress
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

    ``layers`` is ``None`` when the net may use every routing layer of the job, else the non-empty tuple,
    in stack order, of the routing layers its tracks may use (change c0107).

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
    layers: tuple[str, ...] | None = None
    # ``tier`` (c0109) stays the last field: it comes after the field c0107 adds to a job net.
    tier: int = 0


@dataclass(frozen=True, slots=True)
class JobPair:
    """Two nets of the job routed as one differential pair (capability routing, "Pairs and escape in a
    routing job"; change c0110).

    ``positive`` and ``negative`` name nets of ``RoutingJob.nets``, where a router finds their pads and
    class values. ``width``, ``gap`` and ``via_gap`` are the class pair values (change c0104); ``skew_max``
    is the ``max`` of the ``diff_pair_skew`` rule that governs the pair, ``None`` without one.
    """

    name: str
    positive: str
    negative: str
    width: Nm
    gap: Nm
    via_gap: Nm | None = None
    skew_max: Nm | None = None


EscapeKind = Literal["grid", "perimeter"]
"""``grid``: the pads of a part lie on a grid (a BGA); ``perimeter``: around its edge (QFN, QFP, SOIC)."""


@dataclass(frozen=True, slots=True)
class JobEscape:
    """A part whose pads the router escapes before it routes (change c0110): its reference, its kind,
    its pitch in nm and the job nets that have a pad on it, sorted."""

    ref: str
    kind: str
    pitch: Nm
    nets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinishedRun:
    """The copper that one tool process of a router added, and the nets it routed. ``tier`` is the tier
    of those nets (0 for a job without tiers); ``seconds`` is how long the process took."""

    nets: tuple[str, ...]
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    tier: int = 0
    seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class RoutingJob:
    """A model-only routing request; no backend file paths cross the plugin boundary.

    ``extra`` carries data the routing package cannot type because it may not import ``backends.base``:
    the command fills ``board_pads`` (the pads of ``BoardFrame.board_pads``) and ``outline`` (the rings of
    the board outline, the board first). A router that needs neither ignores it.

    ``plane_layers`` names the copper layers, in stack order, that hold planes and take no track (change
    c0107); a job built without it means what it meant before.

    ``budget`` is the wall-clock time, in seconds, of the plugin's whole ``route()``; ``None`` gives the
    plugin's ``DEFAULT_BUDGET`` (capability routing, "Routing time budget"; change c0109). A router that
    starts no process ignores it. ``nets`` is sorted by tier, then by name.

    A router that starts tool processes reports each one to ``progress`` as a unit (``step`` when it
    starts, ``done`` when it ends) and calls ``on_run`` once for each process that ended with copper,
    with that copper, before it starts the next one; a process that failed, was cut by the budget or
    gave no copper is not reported through ``on_run``. A router that ignores both fields stays valid.

    ``pairs`` and ``escape`` (change c0110) are the differential pairs and the parts to escape; a job holds
    them only for a router whose ``router_features`` name ``pairs`` and ``escape``.
    """

    design: Design
    nets: tuple[JobNet, ...]
    layers: tuple[str, ...]
    options: Mapping[str, str] = field(default_factory=lambda: {})
    extra: Mapping[str, object] = field(default_factory=lambda: {})
    plane_layers: tuple[str, ...] = ()
    # ``budget`` (c0109) stays the last field: it comes after the field c0107 adds to a job.
    budget: float | None = None
    on_run: Callable[[FinishedRun], None] | None = None
    progress: Progress = NULL_PROGRESS
    # ``pairs`` and ``escape`` (c0110) come after the fields of c0107 and c0109.
    pairs: tuple[JobPair, ...] = ()
    escape: tuple[JobEscape, ...] = ()


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


ROUTER_FEATURES: frozenset[str] = frozenset({"pairs", "escape"})
"""What a router may take beyond single nets (change c0110). A router lists those it takes in an attribute
``features``, which the ``Router`` protocol does not hold, so that a router written before stays valid."""


def router_features(router: object) -> frozenset[str]:
    """The router's ``features`` when it is a ``frozenset`` of members of ``ROUTER_FEATURES``, else an
    empty set (a missing attribute, a list, an unknown feature)."""
    found: object = getattr(router, "features", None)
    if not isinstance(found, frozenset):
        return frozenset()
    items = cast("frozenset[object]", found)
    if all(isinstance(item, str) and item in ROUTER_FEATURES for item in items):
        return frozenset(str(item) for item in items)
    return frozenset()


__all__ = [
    "ROUTER_FEATURES",
    "EscapeKind",
    "FinishedRun",
    "JobEscape",
    "JobNet",
    "JobPad",
    "JobPair",
    "Router",
    "RouterRun",
    "RouterStatus",
    "RoutingJob",
    "RoutingResult",
    "router_features",
]
