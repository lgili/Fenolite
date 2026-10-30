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


RoleKind = Literal["gate-out", "gate-return", "kelvin"]
"""The kind of a role route (change c0244): a gate loop's drive or return, or a Kelvin branch."""


@dataclass(frozen=True, slots=True)
class JobRoleEnd:
    """One end of a role route (change c0244): the pad (reference, number, net, copper layers) and ``at``,
    the board-frame point where the track must end: the pad centre, or an entry point inside the pad."""

    ref: str
    number: str
    net: str
    at: Point
    layers: tuple[str, ...]

    @property
    def label(self) -> str:
        """``REF-NUMBER``."""
        return f"{self.ref}-{self.number}"


@dataclass(frozen=True, slots=True)
class JobRoleRoute:
    """One open connection of a role group that a router with the feature ``roles`` routes (capability
    routing, "Role routes in a routing job"; change c0244; ``docs/routing.md``, "Role mode").

    ``tier`` is 0 for a gate loop's routes and 1 for a Kelvin pair's; the routes of one ``group`` are
    routed whole or not at all. ``layers`` are the allowed copper layers in preference order; ``vias`` the
    vias the route may place. An ``isolated`` route may touch the copper of its own net only at its ends;
    a route keeps ``keep_away`` from the copper of the ``aggressors`` on its layer and does not overlap it
    on an adjacent layer. ``partner`` is the key of the route it pairs with, at ``gap``. ``loop`` is the
    rest of the role loop, from ``b`` back to ``a``, for the area cost; ``key`` names the route. ``plane``
    marks a gate return of a ``ground`` net, which a zone of its net under the whole drive may carry."""

    group: str
    kind: str
    tier: int
    net: str
    a: JobRoleEnd
    b: JobRoleEnd
    width: Nm
    layers: tuple[str, ...]
    vias: int = 0
    isolated: bool = False
    aggressors: tuple[str, ...] = ()
    keep_away: Nm = 0
    partner: str = ""
    gap: Nm = 0
    loop: tuple[Point, ...] = ()
    key: str = ""
    plane: bool = False


RoleStatus = Literal["routed", "plane-return", "unrouted", "refused"]


@dataclass(frozen=True, slots=True)
class RoleOutcome:
    """What a router in role mode did with one role route (capability routing, "Role outcomes in a routing
    result"; change c0244).

    ``status``: ``routed`` (its copper is in the result), ``plane-return`` (a gate return that a ground
    plane under the drive carries, with no copper), ``unrouted`` or ``refused`` (routed, then removed by the
    role check), with ``reason`` for the last two. ``form`` is ``single``, ``pair``, ``side-by-side``,
    ``stacked`` or ``plane-return``; ``runs`` the placed polylines as ``(layer, width, points)`` and
    ``via_points`` the vias, so that the command can fence them; ``blockers`` names what refused the
    shortest shape, and ``detail`` the finding of a refusal or the zone that blocked the route."""

    key: str
    group: str
    status: str
    reason: str = ""
    form: str = ""
    layer: str = ""
    length: Nm = 0
    vias: int = 0
    runs: tuple[tuple[str, Nm, tuple[Point, ...]], ...] = ()
    via_points: tuple[Point, ...] = ()
    blockers: tuple[str, ...] = ()
    detail: str = ""


SubjectKind = Literal["fanout", "join", "role-net", "group", "connection"]
"""The kind of a proposal subject (change c0280; ``docs/routing.md``, "Proposals"), in the order the command
sorts its proposals."""
SUBJECT_KINDS: tuple[str, ...] = ("fanout", "join", "role-net", "group", "connection")


@dataclass(frozen=True, slots=True)
class JobAttach:
    """One end of a proposal subject (change c0280): what the copper must reach (``pad``, ``track-end`` or
    ``zone``), its net, ``at`` (a pad centre, a track end, or a point inside the zone's copper), its copper
    layers and its name (``REF-N``, ``trk@x,y`` in nanometres, or the zone's name)."""

    kind: str
    net: str
    at: Point
    layers: tuple[str, ...]
    name: str = ""


@dataclass(frozen=True, slots=True)
class JobSubject:
    """An open connection, or a critical group that phase 2 left open, that a router with the feature
    ``propose`` answers with candidates (capability routing, "Proposal subjects in a routing job"; change
    c0280). ``key`` names it (``fanout:GND:C3-2``); ``kind`` is one of ``SUBJECT_KINDS``; ``width`` the track
    width, ``layers`` the allowed copper layers in preference order, ``via_diameter`` and ``via_drill`` the
    net's via. A ``group`` subject names its c0244 group, whose role routes are in ``RoutingJob.roles``."""

    key: str
    kind: str
    net: str
    a: JobAttach
    b: JobAttach
    width: Nm
    layers: tuple[str, ...]
    via_diameter: Nm = 0
    via_drill: Nm = 0
    group: str = ""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One candidate shape of a subject (capability routing, "Candidates in a routing result"; change
    c0280): ``id`` is ``c-`` and 16 hex digits of the SHA-256 of the subject key, the source, the relaxations
    and the items' geometry, never of the rest of the board. ``source`` is the family (``shape``, ``z-shape``,
    ``via-l``, ``fanout``, ``role`` or ``external:<router>``), ``relaxed`` the relaxations of a ``role``
    candidate; ``length`` the length of its tracks in nanometres and ``layers`` its copper layers in stack
    order. No score: candidates come in generation order."""

    id: str
    subject: str
    source: str
    relaxed: tuple[str, ...] = ()
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    length: Nm = 0
    layers: tuple[str, ...] = ()


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

    ``roles`` (change c0244) are the role routes of the critical connections; a job holds them only for a
    router whose ``router_features`` name ``roles``, which then routes them and nothing else.

    ``subjects`` (change c0280) are the subjects of a proposal run; a job holds them only for a router whose
    ``router_features`` name ``propose``, which then answers them with candidates and merges nothing.
    ``options["candidates"]`` is the number kept per subject. A ``group`` subject's role routes are in
    ``roles``.
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
    # ``roles`` (c0244) comes after the fields of c0110.
    roles: tuple[JobRoleRoute, ...] = ()
    # ``subjects`` (c0280) comes after ``roles``.
    subjects: tuple[JobSubject, ...] = ()


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
    in ``unrouted`` too. ``roles`` (change c0244) holds one ``RoleOutcome`` per role route of the job, in
    its order. ``candidates`` (change c0280) holds the candidates of a proposal run, in generation order, and
    ``refusals`` one ``(subject key, reason, blockers)`` per subject left without a candidate; a proposal run
    returns no track, arc or via.
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
    roles: tuple[RoleOutcome, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    refusals: tuple[tuple[str, str, tuple[str, ...]], ...] = ()


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


ROUTER_FEATURES: frozenset[str] = frozenset({"pairs", "escape", "short", "roles", "propose"})
"""What a router may take beyond single nets (change c0110), ``short``: the router routes short
connections, not whole boards (change c0228), ``roles``: it routes the role routes of
``RoutingJob.roles`` (change c0244), and ``propose``: it answers the subjects of ``RoutingJob.subjects``
with candidates (change c0280). A router lists those it has in an attribute ``features``,
which the ``Router`` protocol does not hold, so that a router written before stays valid."""


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
    "SUBJECT_KINDS",
    "Candidate",
    "EscapeKind",
    "FinishedRun",
    "JobAttach",
    "JobEscape",
    "JobNet",
    "JobPad",
    "JobPair",
    "JobRoleEnd",
    "JobRoleRoute",
    "JobSubject",
    "RoleKind",
    "RoleOutcome",
    "RoleStatus",
    "Router",
    "RouterRun",
    "RouterStatus",
    "RoutingJob",
    "RoutingResult",
    "SubjectKind",
    "router_features",
]
