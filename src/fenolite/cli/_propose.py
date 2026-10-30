# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proposal mode of ``fenolite route``: ``--propose``, ``--accept``, ``--reject``, ``--replay`` and
``--forget`` (change c0280; capability cli-contract, "Route proposal mode" and the requirements after it;
``docs/cli-contract.md``, "route"; ``docs/routing.md``, "Proposals").

``--propose`` finds the subjects of the board (``fenolite.roles.proposals.subjects``: each open connection
after phases 1 and 2, and each critical group that phase 2 leaves open, from c0244's planner and router run in
memory), asks a router with the feature ``propose`` for candidates, and measures the facts of each candidate
alone, its items added locked: the connections it closes, the open connections of the board before and
after, the copper check's findings near it, the role findings within role reach, vias, length, layers, bends,
the loop of a role loop, its clashes with the candidates of other subjects, the board's fill state, and what
was not measured and why. It writes nothing. No score, rank or recommendation is given.

``--accept ID`` computes the proposals again, checks the ids, and plans in one reviewed plan the board with
each accepted candidate's items locked (a group candidate with its corridors) and the decision record
(``fenolite.routing.decisions``); ``--reject ID`` plans the record only. ``--replay`` plans the locked
decisions whose copper the board lacks; ``--forget ID`` plans dropping a decision and, for a locked one, its
copper.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.pour import DEFAULT_GRID_NM, PourCopper, pour_copper, rejoin
from fenolite.backends.base import BoardPad, DesignRules
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import plane_layers as board_plane_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import _gate, _roleroute
from fenolite.cli._documents import built_cache
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, format_length
from fenolite.geometry import Thick, thick_closer_than
from fenolite.model.board import Keepout, Track, Via
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles import profile
from fenolite.roles.judge import Judged
from fenolite.roles.measure import RoleBoard, power_pads
from fenolite.roles.proposals import Attach, OpenGroup, Subject, SubjectPlan, ZoneCopper, subjects
from fenolite.roles.routes import plan_critical
from fenolite.routing import decisions as record_io
from fenolite.routing.decisions import (
    Decisions,
    Locked,
    RecordCorridor,
    RecordEnd,
    RecordItem,
    RecordTrack,
    RecordVia,
    Rejected,
)
from fenolite.routing.layers import allowed_layers, routing_layers
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.octilinear import fresh
from fenolite.routing.protocol import (
    SUBJECT_KINDS,
    Candidate,
    JobAttach,
    JobNet,
    JobPad,
    JobRoleRoute,
    JobSubject,
    RoleOutcome,
    Router,
    RoutingJob,
    RoutingResult,
    router_features,
)
from fenolite.routing.registry import routers

MODES = ("propose", "accept", "replay", "forget")
REGION_MARGIN: Nm = 2_000_000
"""How far the ``render --region`` of a proposal reaches beyond its two ends (decision 6)."""
GROUP_REACH: Nm = 2_000_000
"""A candidate inside a group's pad box grown by this is within role reach (decision 5)."""
REASON_LIMIT = 300
"""The longest ``--reason`` (printable characters)."""
NOT_EVALUATED = (
    "no-gate",
    "no-role-loop",
    "outside-role-reach",
    "no-kicad-cli",
    "budget",
    "external-trial-failed",
)
"""The closed list of the reasons a fact was not measured."""
PROPOSAL_KEYS = ("id", "subject", "kind", "net", "ends", "region", "candidates", "reason", "alternatives")
CANDIDATE_KEYS = ("id", "source", "relaxed", "items", "geometry", "facts", "rejected")
REASONS = {
    "no-room": "every shape is refused by the clearance",
    "no-layer": "its ends share no allowed layer and no via fits",
    "too-long": "every shape is longer than max-length",
    "near-switching": "every shape of the group breaks its keep-away from switching copper",
    "isolation": "every shape of the group touches the power copper of its own net",
    "pads": "a pad of its group is missing from the board",
    "all-rejected": "every candidate was rejected",
    "budget": "--timeout ended before it",
}
NetValues = Callable[..., tuple[Nm, ...]]


def register(parser: argparse.ArgumentParser) -> None:
    """The options of the proposal mode of ``route``."""
    parser.add_argument(
        "--propose",
        action="store_true",
        help="list every open connection with candidate shapes and their facts, no score; writes nothing",
    )
    parser.add_argument(
        "--accept", action="append", default=[], metavar="ID", help="lock this candidate (repeatable; plan)"
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        metavar="ID",
        help="remember a rejected candidate or proposal (repeatable; plan)",
    )
    parser.add_argument("--reason", default=None, metavar="TEXT", help="with --reject: why, one line")
    parser.add_argument(
        "--replay", action="store_true", help="place again the locked decisions whose copper the board lacks"
    )
    parser.add_argument(
        "--forget",
        action="append",
        default=[],
        metavar="ID",
        help="drop a decision and its copper (repeatable)",
    )
    parser.add_argument(
        "--kind",
        action="append",
        default=[],
        choices=SUBJECT_KINDS,
        help="with --propose: subjects of this kind only (repeatable)",
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=None,
        metavar="N",
        help="with --propose: candidates per subject, 1 to 8 (default 4)",
    )
    parser.add_argument(
        "--show-rejected", action="store_true", help="with --propose: list rejected candidates too"
    )


def mode(args: argparse.Namespace) -> str | None:
    """The proposal mode of the arguments, or ``None``."""
    if args.propose:
        return "propose"
    if args.accept or args.reject:
        return "accept"
    if args.replay:
        return "replay"
    if args.forget:
        return "forget"
    return None


def check(args: argparse.Namespace, router: Router) -> None:
    """``FEN-2001`` for modes given together, an option that the proposal mode does not take, a proposal
    option without its mode, or a router without the feature ``propose``."""
    given = [
        name
        for name, on in (
            ("--propose", args.propose),
            ("--accept/--reject", bool(args.accept or args.reject)),
            ("--replay", args.replay),
            ("--forget", bool(args.forget)),
            ("--roles", args.roles is not None),
        )
        if on
    ]
    if len(given) > 1:
        raise CliError(
            "FEN-2001",
            f"{' and '.join(given)} do not go together",
            where=given[1].split("/")[0],
            hint="run one mode at a time; --accept and --reject may be combined",
        )
    current = mode(args)
    if current is None:
        for value, option in (
            (args.kind, "--kind"),
            (args.candidates is not None, "--candidates"),
            (args.show_rejected, "--show-rejected"),
            (args.reason is not None, "--reason"),
        ):
            if value:
                raise CliError(
                    "FEN-2001", f"{option} goes with --propose", where=option, hint="add --propose"
                )
        return
    for value, option in (
        (args.rip, "--rip"),
        (args.escape, "--escape"),
        (args.order, "--order"),
        (args.pairs_as_nets, "--pairs-as-nets"),
        (args.require_complete, "--require-complete"),
        (args.out, "--out"),
    ):
        if value:
            raise CliError(
                "FEN-2001",
                f"{option} does not go with the proposal mode",
                where=option,
                hint="proposals reach the board only through --accept and a reviewed plan",
            )
    if current != "propose":
        for value, option in (
            (args.kind, "--kind"),
            (args.candidates is not None, "--candidates"),
            (args.show_rejected, "--show-rejected"),
            (args.nets, "--nets"),
            (args.group, "--group"),
        ):
            if value:
                raise CliError(
                    "FEN-2001", f"{option} goes with --propose", where=option, hint="add --propose"
                )
    if args.reason is not None and not args.reject:
        raise CliError("FEN-2001", "--reason goes with --reject", where="--reason", hint="add --reject ID")
    if args.reason is not None and not (
        0 < len(args.reason) <= REASON_LIMIT and args.reason.isprintable() and args.reason.strip()
    ):
        raise CliError(
            "FEN-2001",
            f"--reason takes one line of 1 to {REASON_LIMIT} printable characters",
            where="--reason",
        )
    if args.candidates is not None and not 1 <= args.candidates <= 8:
        raise CliError("FEN-2001", "--candidates takes 1 to 8", where="--candidates", hint="--candidates 4")
    if "propose" not in router_features(router):
        able = sorted(name for name, item in routers().items() if "propose" in router_features(item))
        raise CliError(
            "FEN-2001",
            f"the router {router.name} gives no proposals",
            where="--router",
            hint=f"use a router with the feature propose: {', '.join(able) or 'none'}",
        )


# --- the board ----------------------------------------------------------------------------------------------


@dataclass
class Board:
    """What the proposal mode reads of a board."""

    path: Path
    text: str
    design: Design
    as_read: Design
    rules: DesignRules
    input: InputRef
    checks: Mapping[str, object]
    pads: tuple[BoardPad, ...]
    layers: tuple[str, ...]
    planes: tuple[str, ...]
    routable: tuple[str, ...]
    major: int
    output: str
    built: bool
    net_values: NetValues
    defaults: Sequence[Nm]
    judge: _roleroute.Judge
    roles_file: Path | None
    issues: list[Issue] = field(default_factory=lambda: [])

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def record_path(self) -> Path:
        return record_io.record_path(self.path, built=self.built)

    def record(self) -> Decisions:
        try:
            return record_io.read(self.record_path, board=self.name)
        except FormatError as error:
            raise CliError("FEN-3004", str(error), where=error.locator or error.file) from None

    def values(self, net: str) -> tuple[Nm, ...]:
        found = next((n for n in self.design.circuit.nets if n.name == net), None)
        if found is None:
            return tuple(self.defaults)
        classes = {item.id: item for item in self.design.circuit.netclasses}
        default = next((c for c in self.design.circuit.netclasses if c.name.casefold() == "default"), None)
        return self.net_values(found, classes, default)


def _board(
    args: argparse.Namespace,
    ctx: Context,
    *,
    board_path: Path,
    text: str,
    design: Design,
    as_read: Design,
    rules: DesignRules,
    input_ref: InputRef,
    checks: Mapping[str, object],
    major: int,
    output: str,
    read_issues: Sequence[Issue],
    net_values: NetValues,
    defaults: Sequence[Nm],
) -> Board:
    declared, confirmed, circuit, roles_file = _roleroute.roles_of(args, ctx, board_path)
    pads = tuple(board_pads(design, issues=[]))
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    planes = tuple(board_plane_layers(design))
    built, _, _ = built_cache(board_path.parent)
    return Board(
        board_path,
        text,
        design,
        as_read,
        rules,
        input_ref,
        checks,
        pads,
        layers,
        planes,
        tuple(routing_layers(layers, planes)),
        major,
        output,
        built,
        net_values,
        defaults,
        _roleroute.Judge(pads, circuit, confirmed, declared),
        roles_file,
        list(read_issues),
    )


# --- subjects and candidates --------------------------------------------------------------------------------


@dataclass
class Proposal:
    """A subject with its candidates (generation order), the reason and blockers of a subject without one,
    and the facts measured of each candidate by id."""

    subject: Subject
    candidates: list[Candidate] = field(default_factory=lambda: [])
    reason: str = ""
    blockers: tuple[str, ...] = ()
    facts: dict[str, dict[str, Any]] = field(default_factory=lambda: {})


@dataclass
class Found:
    """The proposals of a board and what was measured to make them."""

    plan: SubjectPlan
    proposals: list[Proposal]
    pour: PourCopper
    routes: dict[str, JobRoleRoute]
    nets: dict[str, JobNet]
    issues: list[Issue]
    cut: int = 0


def _job_attach(attach: Attach) -> JobAttach:
    return JobAttach(attach.kind, attach.net, attach.at, attach.layers, attach.name)


def _open_groups(
    board: Board, router: Router
) -> tuple[list[OpenGroup], dict[str, JobRoleRoute], dict[str, JobNet]]:
    """The critical groups that phase 2 leaves open, from c0244's planner and router run in memory, with the
    role routes and job nets of each."""
    judged = board.judge.judged(board.design)
    roles = judged.resolved.roles
    clearance = _roleroute.pair_clearance(board.checks["clearance"], board.design)  # type: ignore[arg-type]
    held: dict[str, list[str]] = {}
    for code, group, _severity, _measure in board.judge.findings(board.design):
        if code != "roles.loop-open":
            held.setdefault(group, []).append(code)
    plan = plan_critical(
        board.design, roles, board.pads, layers=board.routable, clearance=clearance,
        default_width=board.defaults[0], findings=held,
    )  # fmt: skip
    routes = {route.key: _roleroute.job_route(route) for route in plan.routes}
    nets = {
        net.name: net for net in _roleroute.job_nets(board.design, board.pads, plan.routes, board.defaults)
    }
    outcomes: dict[str, RoleOutcome] = {}
    if routes:
        extra = {
            "board_pads": board.pads,
            "outline": board_outline(board.design).rings,
            **board.checks,
            "role_check": board.judge.findings,
        }
        result = router.route(
            RoutingJob(
                board.design,
                tuple(nets.values()),
                board.layers,
                {},
                extra,
                plane_layers=board.planes,
                roles=tuple(routes.values()),
            )
        )
        outcomes = {item.key: item for item in result.roles}
    records = {f"{p.ref}-{p.number}": p for p in board.pads}
    found: list[OpenGroup] = []
    for group in plan.groups:
        mine = [routes[key] for key in group.routes if key in routes]
        bad = [
            outcomes[r.key]
            for r in mine
            if r.key in outcomes and outcomes[r.key].status in ("unrouted", "refused")
        ]
        status, reason = "", ""
        if group.status == "unrouted":
            status, reason = "unrouted", group.reason
        elif bad:
            status, reason = bad[0].status, bad[0].reason
        if not status:
            continue
        ends: list[tuple[str, str, Attach, Attach]] = []
        for route in mine:
            a = Attach("pad", route.net, route.a.at, route.a.layers, route.a.label)
            b = Attach("pad", route.net, route.b.at, route.b.layers, route.b.label)
            ends.append((route.key, route.net, a, b))
        if not ends:
            pads = [records[name] for name in group.pads if name in records][:2]
            if pads:
                first, last = pads[0], pads[-1]
                a = Attach(
                    "pad", first.net or "", first.position, tuple(first.layers), f"{first.ref}-{first.number}"
                )
                b = Attach(
                    "pad", last.net or "", last.position, tuple(last.layers), f"{last.ref}-{last.number}"
                )
                ends.append((f"{group.name}:pads", first.net or "", a, b))
        if ends:
            found.append(OpenGroup(group.name, status, reason, tuple(ends)))
    return found, routes, nets


def _selected(subject: Subject, args: argparse.Namespace) -> bool:
    import fnmatch

    if args.kind and subject.kind not in args.kind:
        return False
    if args.nets and not any(fnmatch.fnmatchcase(subject.net, glob) for glob in args.nets):
        return False
    return not (args.group and (subject.kind != "group" or subject.group not in args.group))


def find(
    args: argparse.Namespace,
    ctx: Context,
    board: Board,
    router: Router,
    options: Mapping[str, str],
    *,
    facts_of: Sequence[str] | None = None,
    started: float | None = None,
) -> Found:
    """The proposals of ``board``: subjects, the router's candidates and, for every candidate (or only those
    of ``facts_of``), its facts."""
    design = board.design
    assert design.board is not None
    pour = pour_copper(design, pads=board.pads, boundary=board_boundary(design.board), grid=DEFAULT_GRID_NM)
    groups, routes, nets = _open_groups(board, router)
    roles = board.judge.judged(design).resolved.roles
    widths = {net.name: board.values(net.name)[0] for net in design.circuit.nets}
    judged = board.judge.judged(design)
    power = power_pads(RoleBoard(design, board.pads, roles, judged.resolved.classes))
    plan = subjects(design, board.pads, roles=roles, groups=groups, widths=widths, pour=pour, power=power)
    chosen = [s for s in plan.subjects if _selected(s, args)]
    by_name = {net.name: net for net in design.circuit.nets}
    job_subjects: list[JobSubject] = []
    job_nets: dict[str, JobNet] = {}
    group_routes: list[JobRoleRoute] = []
    proposals = [Proposal(s) for s in chosen]
    for proposal in proposals:
        subject = proposal.subject
        if subject.reason:
            proposal.reason = subject.reason
            continue
        net = by_name.get(subject.net)
        if net is None:
            proposal.reason = "pads"
            continue
        width, clear, diameter, drill = board.values(subject.net)
        layers = allowed_layers(design, net, board.routable)
        if subject.kind == "group":
            mine = [routes[key] for key in subject.routes if key in routes]
            group_routes += mine
            for route in mine:
                if route.net in nets:
                    job_nets[route.net] = nets[route.net]
        if subject.net not in job_nets:
            held = tuple(
                JobPad(p.ref, p.number, p.net or "", p.position, p.layers, p.drill)
                for p in board.pads
                if p.net == subject.net
            )
            job_nets[subject.net] = JobNet(subject.net, net.id, held, width, clear, diameter, drill)
        job_subjects.append(
            JobSubject(
                subject.key,
                subject.kind,
                subject.net,
                _job_attach(subject.a),
                _job_attach(subject.b),
                width,
                tuple(layers),
                diameter,
                drill,
                subject.group,
            )
        )
    issues: list[Issue] = []
    if job_subjects:
        copper = ZoneCopper(design, pour)
        extra = {
            "board_pads": board.pads,
            "outline": board_outline(design).rings,
            **board.checks,
            "role_check": board.judge.findings,
            "zone_copper": copper.covers,
        }
        given = dict(options)
        if args.candidates is not None:
            given["candidates"] = str(args.candidates)
        result = router.route(
            RoutingJob(
                design,
                tuple(job_nets.values()),
                board.layers,
                given,
                extra,
                plane_layers=board.planes,
                progress=ctx.progress,
                roles=tuple(group_routes),
                subjects=tuple(job_subjects),
            )
        )
        issues += [i for i in result.issues if i.code != "route.proposal-open"]
        by_subject: dict[str, list[Candidate]] = {}
        for candidate in result.candidates:
            by_subject.setdefault(candidate.subject, []).append(candidate)
        refused = {key: (reason, blockers) for key, reason, blockers in result.refusals}
        for proposal in proposals:
            key = proposal.subject.key
            proposal.candidates = by_subject.get(key, [])
            if key in refused and not proposal.reason:
                proposal.reason, proposal.blockers = refused[key]
    found = Found(plan, proposals, pour, routes, nets, issues)
    _measure(args, board, found, facts_of=facts_of, started=started)
    return found


# --- facts --------------------------------------------------------------------------------------------------


def _locked_items(candidate: Candidate) -> RoutingResult:
    return RoutingResult(
        tracks=tuple(dataclasses.replace(t, locked=True) for t in candidate.tracks),
        arcs=tuple(dataclasses.replace(a, locked=True) for a in candidate.arcs),
        vias=tuple(dataclasses.replace(v, locked=True) for v in candidate.vias),
    )


def _box(candidate: Candidate, grow: int) -> tuple[int, int, int, int]:
    xs = [p.x for t in candidate.tracks for p in (t.start, t.end)] + [v.position.x for v in candidate.vias]
    ys = [p.y for t in candidate.tracks for p in (t.start, t.end)] + [v.position.y for v in candidate.vias]
    width = max([t.width for t in candidate.tracks] + [v.diameter for v in candidate.vias] + [0])
    reach = grow + width
    return min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach


def _meets(box: tuple[int, int, int, int], points: Sequence[Point]) -> bool:
    if not points:
        return False
    return not (
        max(p.x for p in points) < box[0]
        or min(p.x for p in points) > box[2]
        or max(p.y for p in points) < box[1]
        or min(p.y for p in points) > box[3]
    )


def _needs_full_pour(design: Design, candidate: Candidate, net_id: str | None, grow: int) -> bool:
    """Whether the candidate comes near a zone of another net, so that the pour must be simulated again."""
    board = design.board
    if board is None:
        return False
    box = _box(candidate, grow)
    for zone in board.zones:
        if zone.net_id != net_id and zone.net_id is not None and _meets(box, zone.outline):
            return True
    return False


def _box_items(design: Design, pads: Sequence[BoardPad], box: tuple[int, int, int, int]) -> set[str]:
    board = design.board
    found: set[str] = set()
    if board is None:
        return found
    for track in (*board.tracks, *board.arcs):
        if _meets(box, (track.start, track.end)):
            found.add(track.id)
    for via in board.vias:
        if _meets(box, (via.position,)):
            found.add(via.id)
    for zone in board.zones:
        if _meets(box, zone.outline):
            found.add(zone.id)
    for pad in pads:
        if _meets(box, (pad.position,)):
            found.add(pad.pad_id)
    return found


def _role_rows(judged: Judged) -> dict[tuple[str, str, str], int | None]:
    """The role findings of warning or above as ``(code, where, severity)`` with the loop ratio of a loop
    finding."""
    ratios = {m.subject: m.values.get("ratio_permille") for m in judged.measured.measures if m.kind == "loop"}
    found: dict[tuple[str, str, str], int | None] = {}
    for item in judged.issues:
        if not item.code.startswith("roles.") or item.severity == "info":
            continue
        measure = ratios.get(item.where.split(":")[0])
        found[(item.code, item.where, item.severity)] = measure if isinstance(measure, int) else None
    return found


def _role_json(
    rows: Mapping[tuple[str, str, str], int | None], keys: Sequence[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    return [{"code": k[0], "where": k[1], "severity": k[2], "measure": rows.get(k)} for k in sorted(keys)]


def _reach(board: Board, candidate: Candidate, net: str, roles: RoleSet) -> bool:
    """Whether a candidate is within role reach: on a role net, near switch-node copper, or inside a group's
    pad box grown by 2 mm (decision 5)."""
    kinds = {role.net: role.kind for role in roles.nets}
    if kinds.get(net, "signal") != "signal":
        return True
    records = {f"{p.ref}-{p.number}": p for p in board.pads}
    switching = profile.resolve("switching_distance_nm", roles.limits).value or 0
    nodes = {role.net for role in roles.nets if role.kind == "switch_node"}
    design = board.design
    names = {n.id: n.name for n in design.circuit.nets}
    box = _box(candidate, switching)
    if design.board is not None:
        for track in design.board.tracks:
            if names.get(track.net_id or "") in nodes and _meets(box, (track.start, track.end)):
                return True
        for zone in design.board.zones:
            if names.get(zone.net_id or "") in nodes and _meets(box, zone.outline):
                return True
    for pad in board.pads:
        if pad.net in nodes and _meets(box, (pad.position,)):
            return True
    near = _box(candidate, 0)
    for group in (*roles.gates, *roles.kelvins, *roles.loops):
        points = [records[name].position for name in _group_pads(group) if name in records]
        if not points:
            continue
        grown = (
            min(p.x for p in points) - GROUP_REACH,
            min(p.y for p in points) - GROUP_REACH,
            max(p.x for p in points) + GROUP_REACH,
            max(p.y for p in points) + GROUP_REACH,
        )
        corners = (Point(near[0], near[1]), Point(near[2], near[3]))
        if _meets(grown, corners):
            return True
    return False


def _group_pads(group: object) -> tuple[str, ...]:
    pads = getattr(group, "pads", None)
    if isinstance(pads, tuple):
        return cast("tuple[str, ...]", pads)
    names = [getattr(group, key, "") for key in ("drive", "gate", "source", "ret")]
    names += list(cast("tuple[str, ...]", getattr(group, "resistor", ())))
    names += list(cast("tuple[str, ...]", getattr(group, "element", ())))
    names += list(cast("tuple[str, ...]", getattr(group, "receiver", ())))
    return tuple(name for name in names if name)


def _bends(candidate: Candidate) -> int:
    """The joints between two tracks of the candidate whose directions differ."""
    count = 0
    tracks = candidate.tracks
    for one in tracks:
        for other in tracks:
            if one is other or one.layer != other.layer or one.end != other.start:
                continue
            u = (one.end.x - one.start.x, one.end.y - one.start.y)
            v = (other.end.x - other.start.x, other.end.y - other.start.y)
            if u[0] * v[1] - u[1] * v[0] != 0:
                count += 1
    return count


def _clash(
    one: Candidate, other: Candidate, clearance: Callable[[str, str], Nm], names: Mapping[str, str]
) -> bool:
    """Whether the copper of two candidates of other nets comes closer than the clearance in force."""
    for a in (*one.tracks, *one.vias):
        for b in (*other.tracks, *other.vias):
            net_a, net_b = names.get(a.net_id or "", ""), names.get(b.net_id or "", "")
            if net_a == net_b:
                continue
            layers_a = a.layers if isinstance(a, Via) else (a.layer,)
            layers_b = b.layers if isinstance(b, Via) else (b.layer,)
            if isinstance(a, Via) or isinstance(b, Via):
                shared = True
            else:
                shared = bool(set(layers_a) & set(layers_b))
            if not shared:
                continue
            shape_a = (
                Thick((a.position,), a.diameter) if isinstance(a, Via) else Thick((a.start, a.end), a.width)
            )
            shape_b = (
                Thick((b.position,), b.diameter) if isinstance(b, Via) else Thick((b.start, b.end), b.width)
            )
            if thick_closer_than(shape_a, shape_b, clearance(net_a, net_b)):
                return True
    return False


def _measure(
    args: argparse.Namespace,
    board: Board,
    found: Found,
    *,
    facts_of: Sequence[str] | None,
    started: float | None,
) -> None:
    design = board.design
    names = {net.id: net.name for net in design.circuit.nets}
    net_ids = {net.name: net.id for net in design.circuit.nets}
    copper_check = cast(
        "Callable[[Design], list[tuple[str, str, tuple[str, ...], int]]]", board.checks["copper_check"]
    )
    clearance = _roleroute.pair_clearance(board.checks["clearance"], design)  # type: ignore[arg-type]
    largest = max([clearance(n.name, n.name) for n in design.circuit.nets] + [0])
    before_copper = copper_check(design)
    before_open = found.plan.open
    judged = board.judge.judged(design)
    roles = judged.resolved.roles
    before_roles = _role_rows(judged)
    wanted = None if facts_of is None else set(facts_of)
    deadline = None if args.timeout is None else (started or time.monotonic()) + args.timeout
    all_candidates = [c for p in found.proposals for c in p.candidates]
    for proposal in found.proposals:
        subject = proposal.subject
        for candidate in proposal.candidates:
            if wanted is not None and candidate.id not in wanted:
                continue
            not_evaluated: list[dict[str, str]] = []
            facts: dict[str, Any] = {
                "vias": len(candidate.vias),
                "length": candidate.length,
                "layers": list(candidate.layers),
                "bends": _bends(candidate),
                "conflicts": sorted(
                    other.id
                    for other in all_candidates
                    if other.subject != candidate.subject and _clash(candidate, other, clearance, names)
                ),
                "fill": found.plan.fill,
            }
            if subject.kind == "role-net":
                facts["current"] = "not-declared"
            if candidate.relaxed:
                facts["relaxed"] = list(candidate.relaxed)
            if deadline is not None and time.monotonic() > deadline:
                found.cut += 1
                for fact in ("closes", "open", "copper_check", "roles", "loop"):
                    not_evaluated.append({"fact": fact, "why": "budget"})
                not_evaluated.append({"fact": "drc", "why": "no-gate" if args.gate != "drc" else "budget"})
                facts["not_evaluated"] = not_evaluated
                proposal.facts[candidate.id] = facts
                continue
            try:
                after = apply(design, _locked_items(candidate))
            except RoutingError:
                continue
            net_id = net_ids.get(subject.net)
            if _needs_full_pour(design, candidate, net_id, largest) or design.board is None:
                assert after.board is not None
                pour = pour_copper(
                    after, pads=board.pads, boundary=board_boundary(after.board), grid=found.pour.grid
                )
            else:
                pour = rejoin(found.pour, after, pads=board.pads)
            report = connectivity(after, pads=board.pads, pour=pour)
            row_before = sum(1 for s in found.plan.subjects if s.net == subject.net and s.kind != "group")
            row_after = len(report.net(subject.net).open) if report.net(subject.net) is not None else 0  # type: ignore[union-attr]
            closes: list[str] = []
            if subject.kind == "group":
                closes = list(subject.routes)
            elif row_after < row_before:
                closes = [subject.key.split(":", 1)[1]]
            facts["closes"] = closes
            facts["open"] = {"before": before_open, "after": report.total}
            box = _box(candidate, largest)
            near = (
                _box_items(design, board.pads, box)
                | {t.id for t in candidate.tracks}
                | {v.id for v in candidate.vias}
            )
            after_copper = copper_check(after)
            new = fresh(before_copper, after_copper)
            facts["copper_check"] = {
                "before": sum(1 for f in before_copper if set(f[2]) & near),
                "after": sum(1 for f in after_copper if set(f[2]) & near),
                "new": [{"code": f[0], "layer": f[1], "items": list(f[2]), "gap": f[3]} for f in new],
            }
            if _reach(board, candidate, subject.net, roles):
                judged_after = board.judge.judged(after)
                rows_after = _role_rows(judged_after)
                fresh_rows = [
                    k
                    for k, measure in rows_after.items()
                    if k not in before_roles or (measure is not None and (before_roles[k] or 0) < measure)
                ]
                facts["roles"] = {
                    "before": len(before_roles),
                    "after": len(rows_after),
                    "new": _role_json(rows_after, fresh_rows),
                    "cleared": _role_json(before_roles, [k for k in before_roles if k not in rows_after]),
                }
                loops = [
                    m
                    for m in judged_after.measured.measures
                    if m.kind == "loop" and (m.subject == subject.group or subject.net in _loop_nets(m))
                ]
                if loops:
                    first = loops[0]
                    facts["loop"] = {
                        "group": first.subject,
                        "area": first.values.get("area_nm2"),
                        "ratio_permille": first.values.get("ratio_permille"),
                        "bound": first.values.get("bound_nm2"),
                    }
                else:
                    not_evaluated.append({"fact": "loop", "why": "no-role-loop"})
            else:
                not_evaluated.append({"fact": "roles", "why": "outside-role-reach"})
                not_evaluated.append({"fact": "loop", "why": "no-role-loop"})
            if args.gate != "drc":
                not_evaluated.append({"fact": "drc", "why": "no-gate"})
            facts["not_evaluated"] = sorted(not_evaluated, key=lambda row: row["fact"])
            proposal.facts[candidate.id] = facts


def _loop_nets(measure: object) -> tuple[str, ...]:
    values = cast("Mapping[str, Any]", getattr(measure, "values", {}))
    nets = values.get("nets")
    if isinstance(nets, list):
        return tuple(str(n) for n in cast("list[Any]", nets))
    net = values.get("net")
    return (str(net),) if isinstance(net, str) else ()


# --- DRC batches --------------------------------------------------------------------------------------------


def drc_batches(board: Board, found: Found, kicad_cli: str | None) -> list[dict[str, Any]]:
    """With ``--gate drc``: the kept candidates packed, in reply order, into batches without two candidates of
    one subject or two that clash, each batch judged once by ``api.trial(..., gate=True)`` with each
    candidate's items as one ``together`` set; each candidate gets the new violations naming its items as
    ``drc.new`` (decision 12). Returns the findings that name no candidate item."""
    pending = [(p, c) for p in found.proposals for c in p.candidates if c.id in p.facts]
    batches: list[list[tuple[Proposal, Candidate]]] = []
    for proposal, candidate in pending:
        conflicts = set(proposal.facts[candidate.id].get("conflicts", []))
        for batch in batches:
            if all(c.subject != candidate.subject and c.id not in conflicts for _, c in batch):
                batch.append((proposal, candidate))
                break
        else:
            batches.append([(proposal, candidate)])
    unattributed: list[dict[str, Any]] = []
    for batch in batches:
        merged = board.design
        together: list[frozenset[str]] = []
        for _, candidate in batch:
            try:
                merged = apply(merged, _locked_items(candidate))
            except RoutingError:
                continue
            together.append(frozenset((*(t.id for t in candidate.tracks), *(v.id for v in candidate.vias))))
        gated = _gate.gate(
            board.path, board.design, merged, kicad_cli=kicad_cli, timeout=DEFAULT_TIMEOUT, together=together
        )
        version = gated.result.get("tool_version")
        level = f"KICAD-VERIFIED(kicad-cli {version})" if version else "KICAD-VERIFIED"
        dropped = {
            str(row["id"]): row for row in cast("list[dict[str, Any]]", gated.result.get("dropped", []))
        }
        for (proposal, candidate), items in zip(batch, together, strict=False):
            new = [
                {"type": str(finding.get("type", "")), "items": [item_id]}
                for item_id in sorted(items)
                if item_id in dropped
                for finding in cast("list[dict[str, Any]]", dropped[item_id].get("findings", []))
            ]
            facts = proposal.facts[candidate.id]
            facts["drc"] = {"new": new, "evidence": level}
            facts["not_evaluated"] = [row for row in facts.get("not_evaluated", []) if row["fact"] != "drc"]
        unattributed += cast("list[dict[str, Any]]", gated.result.get("findings", []))
    return unattributed


# --- the reply ----------------------------------------------------------------------------------------------


def _region(board: Board, subject: Subject) -> tuple[str, str]:
    """The region of a subject (its ends grown by 2 mm) as ``x0,y0,x1,y1`` text, and its render command."""
    points = (subject.a.at, subject.b.at)
    box = (
        min(p.x for p in points) - REGION_MARGIN,
        min(p.y for p in points) - REGION_MARGIN,
        max(p.x for p in points) + REGION_MARGIN,
        max(p.y for p in points) + REGION_MARGIN,
    )
    region = ",".join(format_length(v) for v in box)
    return region, f"fenolite render {board.name} --out fenolite-region --region {region} --nets --open"


def _alternatives(board: Board, proposal: Proposal) -> list[dict[str, str]]:
    subject = proposal.subject
    _, render = _region(board, subject)
    name = board.name
    group = f" --group {subject.group}" if subject.group else f" --nets {subject.net}"
    base = f"fenolite route {name} --router octilinear --propose{group}"

    def row(kind: str, text: str, command: str, **more: str) -> dict[str, str]:
        found = {"kind": kind, "text": text, "command": command, "region": render}
        found.update(more)
        return found

    move = row("move-part", "move a part to give the connection room (fenolite place --move)", render)
    reason = proposal.reason
    found: list[dict[str, str]] = []
    if subject.kind == "role-net":
        found.append(
            row(
                "confirm",
                f"confirm the role of {subject.net} with its current; the power-copper phase then sizes it",
                f"fenolite roles {name} --accept {subject.net} --dry-run",
                then=f"fenolite copper {name} --dry-run",
            )
        )
    if subject.hot and subject.kind == "join":
        found.append(
            row("power-copper", "place the hot loop's copper again", f"fenolite copper {name} --dry-run")
        )
    if proposal.candidates and reason != "all-rejected":
        return found
    if reason == "no-room":
        blockers = ", ".join(proposal.blockers) or "the copper between its ends"
        found += [
            row("free-corridor", f"free the corridor: {blockers}", render),
            move,
            row(
                "external-router",
                "route the net with an external router",
                f"fenolite route {name} --router freerouting --nets {subject.net} --dry-run",
            ),
        ]
    elif reason == "no-layer":
        option = "kelvin-vias=2" if subject.group.startswith("kelvin") else "gate-vias=2"
        found += [
            row(
                "allow-via", "allow a via, or give the net's class a via", f"{base} --router-option {option}"
            ),
            move,
        ]
    elif reason == "too-long":
        found += [row("raise-limit", "raise max-length", f"{base} --router-option max-length=40mm"), move]
    elif reason in ("near-switching", "isolation"):
        blockers = ", ".join(proposal.blockers) or "the switching copper"
        found += [
            row("free-corridor", f"free the corridor: {blockers}", render),
            move,
            row("power-copper", "shape the power copper again", f"fenolite copper {name} --dry-run"),
        ]
    elif reason == "pads":
        found += [
            row(
                "move-part",
                "place the group's parts, or edit the role with fenolite roles --set",
                f"fenolite roles {name} --dry-run",
            ),
            row("edit-script", "edit the script that places the parts", f"fenolite roles {name} --dry-run"),
        ]
    elif reason == "all-rejected":
        found += [
            row(
                "move-part",
                "list the rejected candidates with --show-rejected, or move a part",
                f"{base} --show-rejected",
            )
        ]
    elif reason == "budget":
        found += [row("raise-limit", "run again with a longer --timeout", f"{base} --timeout 600")]
    return found


def _ends_json(subject: Subject) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for end in (subject.a, subject.b):
        row: dict[str, Any] = {"kind": end.kind, "name": end.name, "layers": list(end.layers)}
        if end.kind != "zone":
            row["at"] = [end.at.x, end.at.y]
        found.append(row)
    return found


def _geometry(candidate: Candidate) -> list[dict[str, Any]]:
    return [record_io.item_data(item) for item in _record_items(candidate)]


def _record_items(candidate: Candidate) -> list[RecordItem]:
    items: list[RecordItem] = [RecordTrack(t.layer, t.width, (t.start, t.end)) for t in candidate.tracks]
    items += [RecordVia(v.position, v.diameter, v.drill, v.layers) for v in candidate.vias]
    return items


def _candidate_json(proposal: Proposal, candidate: Candidate, rejected: bool) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "source": candidate.source,
        "relaxed": list(candidate.relaxed),
        "items": {"tracks": len(candidate.tracks), "vias": len(candidate.vias)},
        "geometry": _geometry(candidate),
        "facts": proposal.facts.get(candidate.id, {}),
        "rejected": rejected,
    }


def _present(board: Design, entry: Locked) -> bool:
    if board.board is None:
        return False
    tracks = {(t.layer, t.width, t.start, t.end) for t in board.board.tracks}
    vias = {(v.position, v.diameter) for v in board.board.vias}
    for item in entry.items:
        if isinstance(item, RecordTrack):
            for p, q in zip(item.points, item.points[1:], strict=False):
                if (item.layer, item.width, p, q) not in tracks and (
                    item.layer,
                    item.width,
                    q,
                    p,
                ) not in tracks:
                    return False
        elif (item.at, item.diameter) not in vias:
            return False
    return True


def reply(
    args: argparse.Namespace, board: Board, found: Found, record: Decisions
) -> tuple[dict[str, Any], list[Issue]]:
    """``result`` of ``--propose`` and its issues (decisions 6 and 7)."""
    rejected_ids = {entry.id: entry for entry in record.rejected}
    issues: list[Issue] = []
    proposals: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    left_out = 0
    for proposal in found.proposals:
        subject = proposal.subject
        pid = subject.proposal
        if pid in rejected_ids:
            rejected_rows.append({"id": pid, "subject": subject.key, "reason": rejected_ids[pid].reason})
            left_out += 1
            continue
        rows: list[dict[str, Any]] = []
        for candidate in proposal.candidates:
            gone = candidate.id in rejected_ids
            if gone:
                left_out += 1
                if not args.show_rejected:
                    continue
            rows.append(_candidate_json(proposal, candidate, gone))
        if proposal.candidates and not [r for r in rows if not r["rejected"]] and not args.show_rejected:
            proposal.reason = "all-rejected"
        reason = proposal.reason if not rows or proposal.reason == "all-rejected" else ""
        if not rows:
            reason = reason or "no-room"
            proposal.reason = reason
        _, render = _region(board, subject)
        proposals.append(
            {
                "id": pid,
                "subject": subject.key,
                "kind": subject.kind,
                "net": subject.net,
                "ends": _ends_json(subject),
                "region": render,
                "candidates": rows,
                "reason": reason or None,
                "alternatives": _alternatives(board, proposal),
            }
        )
        if not rows:
            text = REASONS.get(reason, reason)
            blockers = f" ({', '.join(proposal.blockers)})" if proposal.blockers else ""
            issues.append(
                Issue(
                    "route.proposal-open",
                    "warning",
                    f"{subject.key} has no candidate: {text}{blockers}",
                    subject.key,
                    hint=proposals[-1]["alternatives"][0]["command"] if proposals[-1]["alternatives"] else "",
                )
            )
    if not proposals:
        issues.append(
            Issue(
                "route.proposal-none",
                "info",
                "the board has no open connection and no open critical group to propose for",
                board.name,
            )
        )
    if left_out:
        issues.append(
            Issue(
                "route.proposal-rejected",
                "info",
                f"{left_out} rejected candidate(s) or proposal(s) are left out",
                board.name,
                hint="pass --show-rejected to list the rejected candidates",
            )
        )
    if found.cut:
        issues.append(
            Issue(
                "route.proposal-limit",
                "info",
                f"--timeout ended before the facts of {found.cut} candidate(s) were measured",
                board.name,
                hint="run again with a longer --timeout, or narrow with --kind, --nets or --group",
            )
        )
    result = {
        "mode": "propose",
        "order": "generation",
        "open": {"before": found.plan.open},
        "proposals": proposals,
        "rejected": rejected_rows,
        "locked": [
            {"candidate": e.candidate, "subject": e.subject, "present": _present(board.design, e)}
            for e in record.locked
        ],
        "next": [
            f"fenolite route {board.name} --router octilinear --accept ID --dry-run",
            f"fenolite route {board.name} --router octilinear --reject ID --reason TEXT --dry-run",
        ],
    }
    return result, issues


# --- accept and reject --------------------------------------------------------------------------------------


def decision_id(board_sha256: str, ids: Sequence[str]) -> str:
    """The id of a decision: 16 hex digits of the SHA-256 of the board's SHA-256 and the accepted ids."""
    text = json.dumps([board_sha256, sorted(ids)], separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _corridors(board: Board, found: Found, candidate: Candidate, group: str) -> list[Keepout]:
    """The corridors ``role.corridor.<group>.<net>`` of a group candidate, along its tracks and around its
    vias, as c0244 fences a routed branch."""
    design = board.design
    names = {net.id: net.name for net in design.circuit.nets}
    clearance = _roleroute.pair_clearance(board.checks["clearance"], design)  # type: ignore[arg-type]
    routes: dict[str, JobRoleRoute] = {}
    outcomes: list[RoleOutcome] = []
    for key, route in found.routes.items():
        if route.group != group or route.net in {r.net for r in routes.values()}:
            continue
        routes[key] = route
        runs = tuple(
            (t.layer, t.width, (t.start, t.end))
            for t in candidate.tracks
            if names.get(t.net_id or "") == route.net
        )
        points = tuple(v.position for v in candidate.vias if names.get(v.net_id or "") == route.net)
        outcomes.append(RoleOutcome(key, group, "routed", runs=runs, via_points=points))
    made = _roleroute.corridors(design, outcomes, routes, found.nets, clearance)
    return [area for areas in made.values() for area in areas]


def _plan_write(
    board: Board,
    after: Design,
    record: Decisions,
    *,
    board_changed: bool,
    record_changed: bool,
    ctx: Context,
) -> tuple[PlannedWrite, ...]:
    writes: list[PlannedWrite] = []
    if board_changed:
        text = write_board(after, target=board.major, allow_lossy=ctx.allow_lossy).text
        if text != board.text:
            writes.append(PlannedWrite(board.output, text.encode("utf-8"), "kicad_pcb"))
    if record_changed:
        target = _relative(board.record_path, ctx.cwd)
        writes.append(PlannedWrite(target, record_io.dumps(record), "json"))
    return tuple(writes)


def _relative(path: Path, cwd: Path) -> str:
    import os

    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return str(path)


def _with_items(design: Design, items: RoutingResult, areas: Sequence[Keepout]) -> Design:
    merged = apply(design, items)
    if areas:
        merged = _roleroute.with_corridors(merged, {"proposal": list(areas)})
    return merged


def run_accept(
    args: argparse.Namespace, ctx: Context, board: Board, router: Router, options: Mapping[str, str]
) -> Result:
    """``--accept`` and ``--reject``: see the module."""
    record = board.record()
    issues: list[Issue] = list(board.issues)
    accepted_ids = list(dict.fromkeys(args.accept))
    rejected_ids = list(dict.fromkeys(args.reject))
    found = find(args, ctx, board, router, options, facts_of=accepted_ids)
    issues += found.issues
    candidates = {c.id: (p, c) for p in found.proposals for c in p.candidates}
    proposals = {p.subject.proposal: p for p in found.proposals}
    unknown = [i for i in accepted_ids if i not in candidates]
    unknown += [i for i in rejected_ids if i not in candidates and i not in proposals]
    if unknown:
        issues.append(
            Issue(
                "route.proposal-unknown",
                "error",
                f"no current candidate or proposal has the id(s) {', '.join(unknown)}; nothing is planned",
                unknown[0],
                hint=f"run fenolite route {board.name} --router octilinear --propose again and use its ids",
            )
        )
    chosen = [candidates[i] for i in accepted_ids if i in candidates]
    subjects_seen: dict[str, str] = {}
    names = {net.id: net.name for net in board.design.circuit.nets}
    clearance = _roleroute.pair_clearance(board.checks["clearance"], board.design)  # type: ignore[arg-type]
    for proposal, candidate in chosen:
        key = proposal.subject.key
        if key in subjects_seen:
            issues.append(
                Issue(
                    "route.proposal-conflict",
                    "error",
                    f"{subjects_seen[key]} and {candidate.id} answer one subject {key}; nothing is planned",
                    candidate.id,
                    hint="accept one candidate per subject",
                )
            )
        subjects_seen[key] = candidate.id
    for index, (_, one) in enumerate(chosen):
        for _, other in chosen[index + 1 :]:
            if one.subject != other.subject and _clash(one, other, clearance, names):
                issues.append(
                    Issue(
                        "route.proposal-conflict",
                        "error",
                        f"the copper of {one.id} and {other.id} clashes; nothing is planned",
                        one.id,
                        hint="accept candidates whose facts do not name each other under conflicts",
                    )
                )
    accepted_rows: list[dict[str, Any]] = []
    for proposal, candidate in chosen:
        facts = proposal.facts.get(candidate.id, {})
        accepted_rows.append({"candidate": candidate.id, "subject": proposal.subject.key, "facts": facts})
        named = [row["code"] for row in facts.get("copper_check", {}).get("new", [])]
        named += [row["code"] for row in facts.get("roles", {}).get("new", []) if row["severity"] != "info"]
        if named:
            issues.append(
                Issue(
                    "route.proposal-findings",
                    "warning",
                    f"{candidate.id} brings {', '.join(sorted(set(named)))}; accepted, as its facts showed",
                    candidate.id,
                    hint=f"fenolite route {board.name} --router octilinear --forget {candidate.id} --dry-run",
                )
            )
    failed = any(i.severity == "error" for i in issues)
    after = board.design
    gate_result: dict[str, Any] | None = None
    gate_evidence: Evidence | None = None
    kept: list[tuple[Proposal, Candidate, list[Keepout]]] = []
    if not failed and chosen:
        ordered = sorted(chosen, key=lambda pair: (pair[0].subject.key, pair[1].id))
        units: list[frozenset[str]] = []
        for proposal, candidate in ordered:
            areas = (
                _corridors(board, found, candidate, proposal.subject.group)
                if proposal.subject.kind == "group"
                else []
            )
            try:
                after = _with_items(after, _locked_items(candidate), areas)
            except RoutingError as exc:
                issues += exc.issues
                continue
            kept.append((proposal, candidate, areas))
            units.append(
                frozenset(
                    (
                        *(t.id for t in candidate.tracks),
                        *(v.id for v in candidate.vias),
                        *(a.id for a in areas),
                    )
                )
            )
        if args.gate == "drc" and kept:
            gated = _gate.gate(
                board.path,
                board.as_read,
                after,
                kicad_cli=args.kicad_cli,
                timeout=DEFAULT_TIMEOUT,
                together=units,
            )
            after, gate_result, gate_evidence = gated.design, gated.result, gated.evidence
            issues += gated.issues
            kept = [
                (p, c, a) for (p, c, a), unit in zip(kept, units, strict=True) if not (unit & gated.dropped)
            ]
    failed = any(i.severity == "error" for i in issues)
    decision = decision_id(board.input.sha256 or "", [c.id for _, c, _ in kept])
    locked = [
        Locked(
            candidate.id,
            proposal.subject.proposal,
            proposal.subject.key,
            proposal.subject.net,
            tuple(_record_end(end) for end in (proposal.subject.a, proposal.subject.b)),
            tuple(_record_items(candidate)),
            tuple(RecordCorridor(a.name, a.layers, a.outline) for a in areas),
            candidate.relaxed,
            decision,
        )
        for proposal, candidate, areas in kept
    ]
    reason = args.reason.strip() if args.reason else ""
    rejected = [
        Rejected(i, candidates[i][0].subject.key if i in candidates else proposals[i].subject.key, reason)
        for i in rejected_ids
        if i in candidates or i in proposals
    ]
    new_record = record_io.with_entries(record, locked=locked, rejected=rejected)
    writes: tuple[PlannedWrite, ...] = ()
    if not failed:
        writes = _plan_write(
            board, after, new_record, board_changed=bool(kept), record_changed=new_record != record, ctx=ctx
        )
        if kept and any(z.filled or z.fills for z in (after.board.zones if after.board else ())):
            issues.append(
                Issue("route.fill-stale", "info", "routing changed copper; run fenolite fill before check")
            )
    evidence = gate_evidence or Evidence(Level.UNVERIFIED, router.name, hypotheses=("H-G-PROP-FACTS",))
    return Result(
        result={
            "mode": "accept",
            "board": board.name,
            "accepted": accepted_rows if not failed else [],
            "rejected": [{"id": r.id, "subject": r.subject, "reason": r.reason} for r in rejected]
            if not failed
            else [],
            "record": _relative(board.record_path, ctx.cwd),
            "decision": decision if kept and not failed else None,
            "gate": gate_result,
        },
        issues=tuple(issues),
        evidence=evidence,
        input=board.input,
        writes=writes,
        depends=depends_on(
            ctx.cwd, board.path, board.roles_file, board.record_path if board.record_path.is_file() else None
        ),
    )


def _record_end(end: Attach) -> RecordEnd:
    return RecordEnd(end.kind, end.name, None if end.kind == "zone" else end.at, end.layers)


# --- replay and forget --------------------------------------------------------------------------------------


def _entry_items(entry: Locked, design: Design) -> tuple[RoutingResult, list[Keepout]]:
    """The tracks, vias and corridors of a locked entry with the ids its accept gave them."""
    net_id = next((n.id for n in design.circuit.nets if n.name == entry.net), None)
    tracks: list[Track] = []
    vias: list[Via] = []
    for item in entry.items:
        if isinstance(item, RecordTrack):
            for p, q in zip(item.points, item.points[1:], strict=False):
                geometry = (p.x, p.y, q.x, q.y, item.width, item.layer)
                tracks.append(
                    Track(
                        id=derived_id("trk", "proposal", content_hash(entry.candidate, geometry)),
                        start=p,
                        end=q,
                        width=item.width,
                        layer=item.layer,
                        net_id=net_id,
                        locked=True,
                    )
                )
        else:
            vias.append(
                Via(
                    id=derived_id("via", "proposal", content_hash(entry.candidate, item.at.x, item.at.y)),
                    position=item.at,
                    diameter=item.diameter,
                    drill=item.drill,
                    layers=item.layers,
                    net_id=net_id,
                    locked=True,
                )
            )
    areas = [
        Keepout(
            id=derived_id(
                "rul", "roles", content_hash(c.name, list(c.layers), [[p.x, p.y] for p in c.outline])
            ),
            outline=c.outline,
            layers=c.layers,
            no_copper_pour=True,
            name=c.name,
        )
        for c in entry.corridors
    ]
    return RoutingResult(tracks=tuple(tracks), vias=tuple(vias)), areas


def _stale(board: Board, entry: Locked) -> str:
    """Why a locked entry cannot be replayed (``moved``, ``net-gone``), or ``""``."""
    design = board.design
    if not any(n.name == entry.net for n in design.circuit.nets):
        return "net-gone"
    records = {f"{p.ref}-{p.number}": p for p in board.pads}
    zones = {z.name for z in (design.board.zones if design.board else ())}
    for end in entry.ends:
        if end.kind == "pad":
            pad = records.get(end.name)
            if pad is None or pad.net != entry.net or pad.position != end.at:
                return "moved"
        elif end.kind == "zone":
            if not end.name.startswith("zone@") and end.name not in zones:
                return "moved"
    return ""


def run_replay(args: argparse.Namespace, ctx: Context, board: Board, router: Router) -> Result:
    """``--replay``: see the module."""
    record = board.record()
    issues: list[Issue] = list(board.issues)
    after = board.design
    copper_check = cast(
        "Callable[[Design], list[tuple[str, str, tuple[str, ...], int]]]", board.checks["copper_check"]
    )
    replayed: list[str] = []
    stale: list[dict[str, str]] = []
    for entry in record.locked:
        if _present(after, entry):
            continue
        why = _stale(board, entry)
        items, areas = _entry_items(entry, after)
        trial = after
        if not why:
            try:
                trial = _with_items(after, items, areas)
            except RoutingError:
                why = "blocked"
        if not why and fresh(copper_check(after), copper_check(trial)):
            why = "blocked"
        if why:
            stale.append({"candidate": entry.candidate, "subject": entry.subject, "why": why})
            issues.append(
                Issue(
                    "route.proposal-stale",
                    "warning",
                    f"the decision {entry.candidate} of {entry.subject} cannot be replayed: {why}",
                    entry.candidate,
                    hint=f"fenolite route {board.name} --router octilinear --propose --nets {entry.net}",
                )
            )
            continue
        after = trial
        replayed.append(entry.candidate)
    writes = _plan_write(board, after, record, board_changed=bool(replayed), record_changed=False, ctx=ctx)
    return Result(
        result={
            "mode": "replay",
            "board": board.name,
            "replayed": replayed,
            "stale": stale,
            "record": _relative(board.record_path, ctx.cwd),
        },  # fmt: skip
        issues=tuple(issues),
        evidence=Evidence(Level.UNVERIFIED, router.name, hypotheses=("H-G-PROP-REPLAY",)),
        input=board.input,
        writes=writes,
        depends=depends_on(ctx.cwd, board.path, board.record_path if board.record_path.is_file() else None),
    )


def run_forget(args: argparse.Namespace, ctx: Context, board: Board, router: Router) -> Result:
    """``--forget``: see the module."""
    record = board.record()
    issues: list[Issue] = list(board.issues)
    ids = list(dict.fromkeys(args.forget))
    locked = {e.candidate: e for e in record.locked}
    rejected = {e.id for e in record.rejected}
    unknown = [i for i in ids if i not in locked and i not in rejected]
    if unknown:
        issues.append(
            Issue(
                "route.proposal-unknown",
                "error",
                f"the decision record holds no entry {', '.join(unknown)}; nothing is planned",
                unknown[0],
                hint=f"the record is {_relative(board.record_path, ctx.cwd)}",
            )
        )
    after = board.design
    removed = 0
    if not unknown and after.board is not None:
        drop_ids: set[str] = set()
        names: set[str] = set()
        for i in ids:
            entry = locked.get(i)
            if entry is None:
                continue
            items, areas = _entry_items(entry, after)
            drop_ids |= {t.id for t in items.tracks} | {v.id for v in items.vias}
            names |= {a.name for a in areas}
        held = after.board
        trimmed = dataclasses.replace(
            held,
            tracks=tuple(t for t in held.tracks if t.id not in drop_ids),
            vias=tuple(v for v in held.vias if v.id not in drop_ids),
            keepouts=tuple(k for k in held.keepouts if k.name not in names),
        )
        removed = (len(held.tracks) + len(held.vias) + len(held.keepouts)) - (
            len(trimmed.tracks) + len(trimmed.vias) + len(trimmed.keepouts)
        )
        after = dataclasses.replace(after, board=trimmed)
    new_record = record_io.with_entries(record, forget=ids) if not unknown else record
    failed = any(i.severity == "error" for i in issues)
    writes = (
        ()
        if failed
        else _plan_write(
            board, after, new_record, board_changed=removed > 0, record_changed=new_record != record, ctx=ctx
        )
    )
    return Result(
        result={
            "mode": "forget",
            "board": board.name,
            "forgotten": ids if not failed else [],
            "removed": removed,
            "record": _relative(board.record_path, ctx.cwd),
        },  # fmt: skip
        issues=tuple(issues),
        evidence=Evidence(Level.UNVERIFIED, router.name),
        input=board.input,
        writes=writes,
        depends=depends_on(ctx.cwd, board.path, board.record_path if board.record_path.is_file() else None),
    )


# --- propose ------------------------------------------------------------------------------------------------


def run_propose(
    args: argparse.Namespace, ctx: Context, board: Board, router: Router, options: Mapping[str, str]
) -> Result:
    """``--propose``: see the module."""
    started = time.monotonic()
    record = board.record()
    found = find(args, ctx, board, router, options, started=started)
    unattributed: list[dict[str, Any]] = []
    if args.gate == "drc":
        unattributed = drc_batches(board, found, args.kicad_cli)
    result, issues = reply(args, board, found, record)
    if args.gate == "drc":
        result["drc_unattributed"] = unattributed
    return Result(
        result=result,
        issues=(*board.issues, *found.issues, *issues),
        evidence=Evidence(Level.UNVERIFIED, router.name, hypotheses=("H-G-PROP-LEFTOVERS", "H-G-PROP-FACTS")),
        input=board.input,
        depends=depends_on(
            ctx.cwd, board.path, board.roles_file, board.record_path if board.record_path.is_file() else None
        ),
    )


def run(
    args: argparse.Namespace,
    ctx: Context,
    *,
    router: Router,
    board_path: Path,
    text: str,
    design: Design,
    as_read: Design,
    rules: DesignRules,
    input_ref: InputRef,
    checks: Mapping[str, object],
    options: Mapping[str, str],
    major: int,
    output: str,
    read_issues: Sequence[Issue],
    net_values: NetValues,
    defaults: Sequence[Nm],
) -> Result:
    """The proposal modes of ``route``."""
    board = _board(
        args, ctx, board_path=board_path, text=text, design=design, as_read=as_read, rules=rules,
        input_ref=input_ref, checks=checks, major=major, output=output, read_issues=read_issues,
        net_values=net_values, defaults=defaults,
    )  # fmt: skip
    current = mode(args)
    if current == "propose":
        return run_propose(args, ctx, board, router, options)
    if current == "accept":
        return run_accept(args, ctx, board, router, options)
    if current == "replay":
        return run_replay(args, ctx, board, router)
    return run_forget(args, ctx, board, router)


__all__ = [
    "CANDIDATE_KEYS",
    "MODES",
    "NOT_EVALUATED",
    "PROPOSAL_KEYS",
    "Board",
    "Found",
    "Proposal",
    "check",
    "decision_id",
    "drc_batches",
    "find",
    "mode",
    "register",
    "reply",
    "run",
]
