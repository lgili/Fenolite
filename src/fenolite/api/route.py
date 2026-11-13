# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route search and free channel on an existing board (capability python-api, "Route search and free channel
in the API"; change c0501, designs D2 and D6; ``docs/api.md``).

``find_route`` and ``free_channel`` take a ``Board``, the path of a board, or an Altium edit ``Session`` (its
pending edits), build the routing job with the board's own rules (``design_rules`` of its backend and
``ClearanceResolver`` as the clearance in force) and its rule areas, and run ``routing.search`` or
``routing.channel.widest``. Nothing is written and no process is started. ``RouteFound.queue_on`` queues the
found copper on an edit session as ``clone`` operations; ``RouteFound.result`` gives it as a
``RoutingResult`` for ``routing.merge.apply``."""

from __future__ import annotations

import dataclasses
import difflib
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fenolite.api.board import Board, read_board
from fenolite.api.sides import SideUsageError
from fenolite.backends.base import DesignRules, ProjectSet
from fenolite.backends.kicad.layers import plane_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.clearance import ClearanceResolver
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, format_length, parse_length
from fenolite.model.board import Keepout, Track, Via, rule_areas
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject
from fenolite.routing import octilinear
from fenolite.routing.channel import RESOLUTION, widest
from fenolite.routing.octilinear import World
from fenolite.routing.protocol import JobAttach, JobNet, RoutingJob, RoutingResult
from fenolite.routing.search import Gap, Limits, WallItem, search
from fenolite.routing.search_grid import StopReason

if TYPE_CHECKING:
    from fenolite.backends.altium.edit.session import Session

DEFAULTS = (200_000, 200_000, 600_000, 300_000)
"""Track width, clearance, via diameter and via drill of a net whose class and ``Default`` class give none."""
GRID = 100_000
MAX_STATES = 200_000
VIA_TOLERANCE = 10
"""A via of the document is the job's via size when its diameter and drill are within this many nanometres:
the document's unit (1/10 000 mil) rounds each by up to a few nanometres in the model."""
POURS = ("kept", "refilled")
_END = re.compile(r"^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)@(.+)$")
Endpoint = str | tuple[Point, str]
"""``REF-PIN``, ``X,Y@LAYER`` in millimetres, or a point and a layer."""


class EndpointError(SideUsageError):
    """An end names no pad or layer of the board (``FEN-2001``); the hint holds the closest names."""


def net_values(net: Net, classes: dict[str, NetClass], default_class: NetClass | None) -> tuple[Nm, ...]:
    """Track width, clearance, via diameter and via drill of ``net``: its class, else the project's
    ``Default`` class, else ``DEFAULTS``."""
    netclass = classes.get(net.netclass_id or "")
    return tuple(
        getattr(netclass, key, None) or getattr(default_class, key, None) or fallback
        for key, fallback in zip(
            ("track_width", "clearance", "via_diameter", "via_drill"), DEFAULTS, strict=True
        )
    )


def job_checks(design: Design, rules: DesignRules) -> dict[str, object]:
    """The job extras ``clearance`` and ``copper_check`` (capability routing, "Clearance and copper check in
    job extras"; change c0228, moved here from ``cmd_route`` by change c0501): the clearance in force between
    two rule subjects under the project's rules, and the copper check of a design with those rules, the
    board edge and the board-frame pads, its zone fills left out (routing makes them stale; ``fill`` pours
    them again)."""
    from fenolite.backends.kicad.backend import KicadBackend
    from fenolite.checks.copper import check_copper, frame_edges

    resolver = ClearanceResolver(
        design,
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    backend = KicadBackend()

    def clearance(a: RuleSubject, b: RuleSubject) -> Nm:
        return resolver.resolve(a, b).value or 0

    def copper_check(checked: Design) -> list[tuple[str, str, tuple[str, ...], int]]:
        board = checked.board
        if board is not None:
            zones = tuple(dataclasses.replace(zone, fills=(), filled=False) for zone in board.zones)
            checked = dataclasses.replace(checked, board=dataclasses.replace(board, zones=zones))
        edges, _ = frame_edges(backend, checked)
        report = check_copper(
            checked,
            pads=backend.board_pads(checked),
            min_clearance=rules.min_clearance,
            rules_over_classes=rules.rules_over_classes,
            floor_over_rules=rules.floor_over_rules,
            edges=edges,
            min_edge_clearance=rules.min_edge_clearance,
            edge_floor_over_rules=rules.edge_floor_over_rules,
        )
        return [
            (found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
            for found in report.findings
        ]

    return {"clearance": clearance, "copper_check": copper_check}


@dataclass(frozen=True, slots=True)
class _Source:
    board: Board
    rules: DesignRules
    areas: tuple[Keepout, ...]
    altium: bool


def _source(given: Any) -> _Source:
    """The board, its rules and its rule areas (design D2): an Altium document's from its bytes (a session's
    pending ones), a KiCad board's from the project and rules files beside it, a ``Board`` record's from its
    own design."""
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.altium.edit.session import Session

    if isinstance(given, Board):
        design = given.design
        assert design.board is not None
        return _Source(given, DesignRules(design), rule_areas(design.board), given.backend == "altium")
    data: bytes | None = None
    path: Path | None = None
    if isinstance(given, Session):
        data, _ = given.pending()
        board = read_board(given)
    else:
        path = Path(os.fspath(cast("str | os.PathLike[str]", given)))
        board = read_board(path)
        if path.is_dir() or path.suffix == ".kicad_pro":
            path = resolve_board(path)
        if board.backend == "altium":
            data = path.read_bytes()
    design = board.design
    if board.backend == "altium" and data is not None:
        backend = AltiumBackend()
        rules = backend.rules_from_bytes(design, data, file=board.name)
        return _Source(board, rules, backend.rule_areas(design, data), True)
    assert design.board is not None
    if path is None:
        return _Source(board, DesignRules(design), rule_areas(design.board), False)
    from fenolite.backends.kicad.backend import KicadBackend

    files = {path.name: path}
    for suffix in (".kicad_pro", ".kicad_dru"):
        beside = path.with_suffix(suffix)
        if beside.is_file():
            files[beside.name] = beside
    rules = KicadBackend().design_rules(design, ProjectSet(root=path.parent, board=path.name, files=files))
    return _Source(board, rules, rule_areas(design.board), False)


def _copper(design: Design) -> tuple[str, ...]:
    layers = design.board.layers if design.board is not None else ()
    return tuple(layer.name for layer in sorted(layers, key=lambda x: x.ordinal) if layer.kind == "copper")


def _job(source: _Source, net: str, pours: str) -> RoutingJob:
    """The routing job of one net under the board's rules (design D2)."""
    design = source.rules.design
    nets = {item.name: item for item in design.circuit.nets}
    if net not in nets:
        close = difflib.get_close_matches(net, sorted(nets), n=3)
        raise EndpointError(f"the board holds no net {net!r}", where=net, hint=", ".join(close) or None)
    classes = {item.id: item for item in design.circuit.netclasses}
    default = next((item for item in design.circuit.netclasses if item.name.casefold() == "default"), None)
    width, clearance, diameter, drill = net_values(nets[net], classes, default)
    held = JobNet(net, nets[net].id, (), width, clearance, diameter, drill)
    extra: dict[str, object] = {
        "board_pads": source.board.pads or (),
        "outline": board_outline(design).rings,
        "rule_areas": source.areas,
        "pours": pours,
        **job_checks(design, source.rules),
    }
    return RoutingJob(design, (held,), _copper(design), extra=extra, plane_layers=plane_layers(design))


def _closest(name: str, names: Sequence[str]) -> str | None:
    return ", ".join(difflib.get_close_matches(name, names, n=3)) or None


def _end(source: _Source, job: RoutingJob, net: str, given: Endpoint) -> JobAttach:
    """``given`` as an end of the connection: a pad of the net, or a point on a copper layer."""
    if isinstance(given, tuple):
        at, layer = given
        name = f"{format_length(at.x)},{format_length(at.y)}@{layer}"
    else:
        found = _END.match(given)
        if found is None:
            pads = source.board.pads or ()
            labels = [f"{p.ref}-{p.number}" for p in pads]
            if given not in labels:
                raise EndpointError(f"no pad is named {given!r}", where=given, hint=_closest(given, labels))
            pad = next(p for p in pads if f"{p.ref}-{p.number}" == given)
            if pad.net != net:
                raise EndpointError(f"the pad {given} is of net {pad.net!r}, not {net!r}", where=given)
            layers = tuple(layer for layer in job.layers if layer in pad.layers)
            return JobAttach("pad", net, pad.position, layers, given)
        x, y, layer = found.groups()
        at = Point(parse_length(x, default_unit="mm"), parse_length(y, default_unit="mm"))
        name = given
    if layer not in job.layers:
        raise EndpointError(
            f"no copper layer is named {layer!r}", where=layer, hint=_closest(layer, job.layers)
        )
    return JobAttach("point", net, at, (layer,), name)


def _layers(job: RoutingJob, a: JobAttach, b: JobAttach, given: Sequence[str] | None) -> tuple[str, ...]:
    """The layers a track may use: ``given``, else the ends' layers and the copper layers between."""
    if given is not None:
        unknown = [layer for layer in given if layer not in job.layers]
        if unknown:
            raise EndpointError(
                f"no copper layer is named {unknown[0]!r}",
                where=unknown[0],
                hint=_closest(unknown[0], job.layers),
            )
        return tuple(layer for layer in job.layers if layer in given)
    found = [job.layers.index(layer) for layer in (*a.layers, *b.layers) if layer in job.layers]
    span = job.layers[min(found) : max(found) + 1] if found else job.layers
    return tuple(layer for layer in span if layer not in job.plane_layers)


def _stop(timeout: float | None) -> Callable[[], StopReason | None]:
    if timeout is None:
        return lambda: None
    deadline = time.monotonic() + timeout
    return lambda: "budget" if time.monotonic() > deadline else None


def _altium_layer(name: str) -> str:
    """The Altium name of a model copper layer, for a clone onto another layer.
    shortcut: inner layers map to Mid-Layer n by their KiCad number, a stack whose signal layers skip a
    Mid-Layer id needs ``adapter.layers``; upgrade when a field board routes on an inner layer."""
    if name == "F.Cu":
        return "Top Layer"
    if name == "B.Cu":
        return "Bottom Layer"
    return f"Mid-Layer {name.removeprefix('In').removesuffix('.Cu')}"


@dataclass(frozen=True, slots=True)
class RouteFound:
    """A found path of ``net`` at ``width``: its runs (layer, points), its vias and the via size, every length
    in nanometres in the board frame of the model."""

    net: str
    width: Nm
    runs: tuple[tuple[str, tuple[Point, ...]], ...]
    vias: tuple[Point, ...]
    via_diameter: Nm
    via_drill: Nm

    @property
    def length(self) -> Nm:
        return sum(octilinear.length(points) for _, points in self.runs)

    def result(self, design: Design) -> RoutingResult:
        """The copper as a ``RoutingResult`` of ``design`` for ``routing.merge.apply`` (design D6)."""
        net_id = next(n.id for n in design.circuit.nets if n.name == self.net)
        tracks = tuple(
            Track(
                id=derived_id(
                    "trk", "routing", content_hash(self.net, (p.x, p.y, q.x, q.y, self.width, layer))
                ),
                start=p,
                end=q,
                width=self.width,
                layer=layer,
                net_id=net_id,
            )
            for layer, points in self.runs
            for p, q in zip(points, points[1:], strict=False)
        )
        copper = _copper(design)
        vias = tuple(
            Via(
                id=derived_id("via", "routing", content_hash(self.net, (at.x, at.y, self.via_diameter))),
                position=at,
                diameter=self.via_diameter,
                drill=self.via_drill,
                layers=(copper[0], copper[-1]),
                net_id=net_id,
            )
            for at in self.vias
        )
        return RoutingResult(tracks=tracks, vias=vias)

    def queue_on(self, session: Session) -> tuple[Issue, ...]:
        """Queue the copper on an Altium edit session (design D6): per segment one ``clone`` of the first
        track of the net on its layer (else the first track on the layer, else the first track of the
        document, moved to the layer), per via one ``clone`` of the first via of the net of the via size.
        Without such a via nothing is queued and ``route.via-template`` is returned. The session declares the
        connectivity of the net (decision of change c0501: the route joins its pieces); a short to another
        net is still refused by the commit."""
        from fenolite.backends.altium import edit
        from fenolite.backends.altium.frame import board_origin

        design = read_board(session).design
        board = design.board
        assert board is not None
        origin = board_origin(design)
        names = {n.id: n.name for n in design.circuit.nets}

        def at(p: Point) -> tuple[int, int]:
            return (p.x - origin.x, origin.y - p.y)

        template_via = next(
            (
                v
                for v in board.vias
                if names.get(v.net_id or "") == self.net
                and abs(v.diameter - self.via_diameter) <= VIA_TOLERANCE
                and abs(v.drill - self.via_drill) <= VIA_TOLERANCE
            ),
            None,
        )
        if self.vias and template_via is None:
            size = f"{format_length(self.via_diameter)}/{format_length(self.via_drill)}"
            message = f"no via of net {self.net} has the via size {size} to clone; nothing was queued"
            return (
                Issue("route.via-template", "error", message, self.net, hint="place one via of that size"),
            )
        if self.runs and not board.tracks:
            message = "the document holds no track to clone; nothing was queued"
            return (Issue("route.via-template", "error", message, self.net),)
        for layer, points in self.runs:
            track = next(
                (t for t in board.tracks if t.layer == layer and names.get(t.net_id or "") == self.net),
                next((t for t in board.tracks if t.layer == layer), board.tracks[0]),
            )
            item = edit.Track(at(track.start), at(track.end), names.get(track.net_id or ""))
            moved = {} if track.layer == layer else {"layer": _altium_layer(layer)}
            for p, q in zip(points, points[1:], strict=False):
                session.clone(item, start=at(p), end=at(q), width=self.width, net=self.net, **moved)
        if template_via is not None:
            via = edit.Via(at(template_via.position), self.net)
            for point in self.vias:
                session.clone(via, at=at(point), net=self.net)
        # joining pieces of the net is what the route is for; a short to another net stays refused
        session.declare_connectivity(self.net)
        return ()


@dataclass(frozen=True, slots=True)
class RouteRefusal:
    """Why no path was found: the reason (``no-room``, ``state-limit``, ``budget``, ...), whether a
    ``no-room`` refusal is ``proven``, its wall and its widest free gap (design D4)."""

    reason: str
    proven: bool
    wall: tuple[WallItem, ...]
    widest: Gap | None


@dataclass(frozen=True, slots=True)
class RouteSearch:
    """The answer of ``find_route``: ``found`` or ``refusal``, the issues and the evidence."""

    board: str
    found: RouteFound | None
    refusal: RouteRefusal | None
    issues: tuple[Issue, ...]
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class Channel:
    """The answer of ``free_channel`` (design D5): ``low`` the widest width with a path (``None``: none),
    ``high`` the narrowest width refused, ``grid_limited`` unless a proven refusal set ``high``, ``undecided``
    when a probe was cut by a bound, the ``pinch`` of the refusal and the path at ``low``."""

    board: str
    low: Nm | None
    high: Nm
    grid_limited: bool
    undecided: bool
    pinch: Gap | None
    path: RouteFound | None
    issues: tuple[Issue, ...]
    evidence: Evidence


def _prepare(
    board: Any, net: str, start: Endpoint, end: Endpoint, layers: Sequence[str] | None, pours: str | None
) -> tuple[_Source, RoutingJob, JobAttach, JobAttach, tuple[str, ...], list[Issue]]:
    source = _source(board)
    held = pours or ("kept" if source.altium else "refilled")
    if held not in POURS:
        raise SideUsageError(f"pours must be kept or refilled, not {held!r}", where="pours")
    job = _job(source, net, held)
    a, b = _end(source, job, net, start), _end(source, job, net, end)
    issues: list[Issue] = []
    if source.altium and held == "refilled":
        issues.append(
            Issue(
                "route.repour-needed",
                "warning",
                "the saved pours were left out of the search: repour the polygons in Altium before its check",
                source.board.name,
            )
        )
    return source, job, a, b, _layers(job, a, b, layers), issues


SEARCH_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-OCTI-CHECK",))
"""The search measures with the routing world's exact geometry; no tool confirmed the copper it finds."""


def _evidence(source: _Source) -> Evidence:
    return Evidence.combine(source.board.evidence, SEARCH_EVIDENCE)


def find_route(
    board: Any,
    *,
    net: str,
    start: Endpoint,
    end: Endpoint,
    width: Nm,
    layers: Sequence[str] | None = None,
    grid: Nm = GRID,
    max_states: int = MAX_STATES,
    max_vias: int = 2,
    pours: str | None = None,
    timeout: float | None = None,
) -> RouteSearch:
    """One connection of ``net`` from ``start`` to ``end`` at ``width`` on a ``Board``, a path or a
    ``Session``, with the board's rules: ``found`` or ``refusal`` (``route.no-path`` when a complete search
    found none, ``route.path-limit`` when it stopped at a bound). Nothing is written."""
    source, job, a, b, allowed, issues = _prepare(board, net, start, end, layers, pours)
    held = job.nets[0]
    subject = dataclasses.replace(
        _subject(job, net, a, b, width),
        layers=allowed,
        via_diameter=held.via_diameter,
        via_drill=held.via_drill,
    )
    world = World(job, cast("tuple[object, ...]", job.extra["board_pads"]), board_outline(job.design).rings)
    reach = 1_000 * (sum(abs(v) for v in (a.at.x - b.at.x, a.at.y - b.at.y)) + 1)
    out = search(
        job, subject, world, Limits(grid, max_states, max_vias), max_length=reach, stop=_stop(timeout)
    )
    if out.runs:
        found = RouteFound(net, width, out.runs, out.vias, held.via_diameter, held.via_drill)
        return RouteSearch(source.board.name, found, None, tuple(issues), _evidence(source))
    refusal = RouteRefusal(out.reason, out.proven, out.wall, out.widest)
    issues.append(_refusal_issue(net, out.reason, out.proven))
    return RouteSearch(source.board.name, None, refusal, tuple(issues), _evidence(source))


def _subject(job: RoutingJob, net: str, a: JobAttach, b: JobAttach, width: Nm) -> Any:
    from fenolite.routing.channel import subject_of

    return subject_of(job, net, a, b, width)


def _refusal_issue(net: str, reason: str, proven: bool) -> Issue:
    if reason == "no-room":
        word = (
            "proven: every gap of its wall is narrower"
            if proven
            else "grid-limited: a gap may pass off the grid"
        )
        return Issue("route.no-path", "warning", f"no path of net {net} was found ({word})", net)
    return Issue(
        "route.path-limit",
        "info",
        f"the search of net {net} stopped at a bound ({reason}); nothing is proven",
        net,
        hint="raise --max-states or --timeout, or use a coarser --grid",
    )


def free_channel(
    board: Any,
    *,
    net: str,
    start: Endpoint,
    end: Endpoint,
    layers: Sequence[str] | None = None,
    grid: Nm = GRID,
    max_states: int = MAX_STATES,
    max_vias: int = 0,
    resolution: Nm = RESOLUTION,
    pours: str | None = None,
    timeout: float | None = None,
) -> Channel:
    """The widest track of ``net`` from ``start`` to ``end`` on a ``Board``, a path or a ``Session``, with
    the board's rules, bracketed to ``resolution`` (``routing.channel.widest``). Nothing is written."""
    source, job, a, b, allowed, issues = _prepare(board, net, start, end, layers, pours)
    held = job.nets[0]
    job = dataclasses.replace(job, nets=(dataclasses.replace(held, layers=allowed),))
    out = widest(
        job, net, a, b, limits=Limits(grid, max_states, max_vias), resolution=resolution, stop=_stop(timeout)
    )
    path = (
        RouteFound(net, out.low, out.runs, out.vias, held.via_diameter, held.via_drill)
        if out.low is not None and out.runs
        else None
    )
    if out.low is None and out.refusal is not None:
        issues.append(_refusal_issue(net, out.refusal.reason, out.refusal.proven))
    elif out.undecided and out.refusal is not None:
        issues.append(_refusal_issue(net, out.refusal.reason, False))
    return Channel(
        source.board.name,
        out.low,
        out.high,
        out.grid_limited,
        out.undecided,
        out.pinch,
        path,
        tuple(issues),
        _evidence(source),
    )


__all__ = [
    "Channel",
    "Endpoint",
    "EndpointError",
    "RouteFound",
    "RouteRefusal",
    "RouteSearch",
    "find_route",
    "free_channel",
    "job_checks",
    "net_values",
]
