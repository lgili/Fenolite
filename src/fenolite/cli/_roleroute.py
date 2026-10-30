# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role mode of ``fenolite route``: ``--roles critical`` (change c0244; capability cli-contract, "Route
command role mode" and "Role route result"; capability net-roles, "Critical route plan" and the requirements
after it; ``docs/cli-contract.md``, "route"; ``docs/roles.md``, "Critical routes").

The command reads the board's roles (``.fenolite/rules.json`` of a built project, the role document, or
``--roles-file``), plans the open connections of the confirmed and declared gate loops and Kelvin pairs
(``fenolite.roles.routes.plan_critical``), and gives them as ``RoutingJob.roles`` to a router with the
feature ``roles``, with ``extra["role_check"]`` (the c0222 judge, which ``routing`` may not import). It
fences each routed branch with a corridor ``role.corridor.<group>.<net>`` (a rule area that forbids pours),
replacing one of that name, and answers with ``result.roles``: one entry per group with its status, its
connections, the role findings before and after, its copper and corridors, and the reason and proposal of a
group that is not routed. Writes follow the mutation protocol, as every ``route`` does.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.base import BoardPad, DesignRules
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import plane_layers as board_plane_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import _gate
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
from fenolite.model.board import Keepout
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet, RuleSubject
from fenolite.roles.judge import Judged, run, split_roles
from fenolite.roles.routes import (
    CriticalPlan,
    CriticalRoute,
    GroupPlan,
    RouteEnd,
    corridor_name,
    plan_critical,
)
from fenolite.roles.store import stored_roles
from fenolite.routing.layers import routing_layers
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import (
    JobNet,
    JobPad,
    JobRoleEnd,
    JobRoleRoute,
    RoleOutcome,
    Router,
    RoutingJob,
    RoutingResult,
    router_features,
)
from fenolite.routing.registry import routers
from fenolite.routing.roleroute import corridor_rings, via_ring

ROLE_MODES = ("critical",)
"""The values of ``--roles``: ``critical`` (this change); phase 4 adds ``propose``."""
REGION_MARGIN: Nm = 2_000_000
"""How far the ``render --region`` of a proposal reaches beyond the group's pads (design decision 14)."""
KINDS = {"gate_loop": "gate loop", "kelvin_pair": "Kelvin pair", "hot_loop": "hot loop"}
REASONS = {
    "no-room": "every shape on every layer is refused by the clearance",
    "too-long": "every shape is longer than max-length",
    "no-layer": "its pads share no allowed layer and the route may place no via",
    "near-switching": "every shape that keeps the clearance runs near or over switching copper",
    "isolation": "every shape that keeps the clearance touches the power copper of its own net",
    "role-check": "a role finding got worse once it was routed",
    "drc": "KiCad's DRC found something new on its copper",
    "pads": "a pad of the group is missing from the board",
    "unconfirmed": "it is inferred and not confirmed",
    "phase-1": "a hot loop is power copper, placed as pours by the power-copper phase",
}
"""The reasons of design decision 14."""


def register(parser: argparse.ArgumentParser) -> None:
    """The role-mode options of ``route``."""
    parser.add_argument(
        "--roles",
        choices=ROLE_MODES,
        default=None,
        help="route the critical connections of the confirmed gate loops and Kelvin pairs (role mode)",
    )
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        metavar="NAME",
        help="with --roles: route this role group only (repeatable)",
    )
    parser.add_argument(
        "--roles-file", default=None, metavar="FILE", help="with --roles: the role document to read"
    )


def check(args: argparse.Namespace, router: Router) -> None:
    """``FEN-2001`` for an option that role mode does not take, a role option without ``--roles``, or a
    router without the feature ``roles``."""
    if args.roles is None:
        if getattr(args, "propose", False) or getattr(args, "accept", None) or getattr(args, "reject", None):
            return  # the proposal mode takes --group and --roles-file (change c0280)
        if getattr(args, "replay", False) or getattr(args, "forget", None):
            return
        for given, option in ((args.group, "--group"), (args.roles_file, "--roles-file")):
            if given:
                raise CliError(
                    "FEN-2001", f"{option} goes with --roles", where=option, hint="add --roles critical"
                )
        return
    for given, option in (
        (args.nets, "--nets"),
        (args.escape, "--escape"),
        (args.order, "--order"),
        (args.pairs_as_nets, "--pairs-as-nets"),
    ):
        if given:
            raise CliError(
                "FEN-2001",
                f"{option} does not go with --roles: the role groups choose the nets and their order",
                where=option,
                hint="name role groups with --group",
            )
    if "roles" not in router_features(router):
        able = sorted(name for name, item in routers().items() if "roles" in router_features(item))
        raise CliError(
            "FEN-2001",
            f"the router {router.name} does not route role groups",
            where="--router",
            hint=f"use a router with the feature roles: {', '.join(able) or 'none'}",
        )


# --- roles and their judge -------------------------------------------------------------------------------


class Judge:
    """The c0222 judge of a board's stored and declared roles, memoised per design (``role_check``)."""

    def __init__(
        self,
        pads: Sequence[BoardPad],
        circuit: object | None,
        stored: RoleSet | None,
        declared: RoleSet | None,
    ) -> None:
        self.pads = tuple(pads)
        self.circuit = circuit
        self.stored = stored
        self.declared = declared
        self._memo: dict[int, tuple[Design, Judged]] = {}

    def judged(self, design: Design) -> Judged:
        key = id(design)
        held = self._memo.get(key)
        if held is None or held[0] is not design:
            from fenolite.model.circuit import Circuit

            circuit = self.circuit if isinstance(self.circuit, Circuit) else None
            found = run(design, self.pads, circuit=circuit, stored=self.stored, declared=self.declared)
            held = (design, found)
            self._memo[key] = held
        return held[1]

    def findings(self, design: Design) -> tuple[tuple[str, str, str, int | None], ...]:
        """The role findings of ``design`` as ``(code, group, severity, measure)``: the group from the
        finding's subject (``group``, ``group:pad``, ``victim~node``; a gate net's victim is its loop), the
        measure the loop ratio of a loop finding."""
        judged = self.judged(design)
        roles = judged.resolved.roles
        names = {g.name for g in (*roles.loops, *roles.gates, *roles.kelvins)}
        by_net: dict[str, str] = {}
        records = {f"{p.ref}-{p.number}": p for p in self.pads}
        for gate in roles.gates:
            for pad in (gate.drive, gate.gate, *gate.resistor):
                record = records.get(pad)
                if record is not None and record.net:
                    by_net.setdefault(record.net, gate.name)
        ratios = {
            m.subject: m.values.get("ratio_permille") for m in judged.measured.measures if m.kind == "loop"
        }
        found: list[tuple[str, str, str, int | None]] = []
        for item in judged.issues:
            if not item.code.startswith("roles.") or item.severity == "info":
                continue
            head = item.where.split(":")[0].split("~")[0]
            group = head if head in names else by_net.get(head, "")
            if not group:
                continue
            measure = (
                ratios.get(group)
                if item.code in ("roles.loop-area", "roles.gate-loop", "roles.kelvin-apart")
                else None
            )
            found.append((item.code, group, item.severity, measure if isinstance(measure, int) else None))
        return tuple(sorted(set(found), key=lambda f: (f[1], f[0], f[2], -1 if f[3] is None else f[3])))


def roles_of(
    args: argparse.Namespace, ctx: Context, board_path: Path
) -> tuple[RoleSet | None, RoleSet | None, object | None, Path | None]:
    """``(declared, confirmed, circuit, file)``: the stored roles of the board, and the circuit to infer
    from."""
    root = board_path.parent
    built, model, cache_error = built_cache(root)
    if cache_error:
        raise CliError("FEN-3004", f".fenolite: {cache_error}", where=".fenolite")
    given = None
    if args.roles_file is not None:
        given = Path(args.roles_file) if Path(args.roles_file).is_absolute() else ctx.cwd / args.roles_file
    try:
        stored = stored_roles(
            board_path,
            model_roles=model.rules.roles if model is not None and model.rules is not None else None,
            built=built,
            root=root,
            given=given,
        )
    except FormatError as error:
        raise CliError("FEN-3004", str(error), where=error.locator or error.file) from None
    declared, confirmed = split_roles(stored.roles) if stored.built else (None, stored.roles)
    return declared, confirmed, model.circuit if model is not None else None, stored.source


# --- the job ----------------------------------------------------------------------------------------------


def _end(end: RouteEnd) -> JobRoleEnd:
    return JobRoleEnd(end.ref, end.number, end.net, end.at, end.layers)


def job_route(route: CriticalRoute) -> JobRoleRoute:
    """The routing-protocol form of a critical route."""
    return JobRoleRoute(
        group=route.group,
        kind=route.kind,
        tier=route.tier,
        net=route.net,
        a=_end(route.a),
        b=_end(route.b),
        width=route.width,
        layers=route.layers,
        vias=route.vias,
        isolated=route.isolated,
        aggressors=route.aggressors,
        keep_away=route.keep_away,
        partner=route.partner,
        gap=route.gap,
        loop=route.loop,
        key=route.key,
        plane=route.plane,
    )


def _classes(design: Design) -> tuple[dict[str, NetClass | None], NetClass | None]:
    classes = {item.id: item for item in design.circuit.netclasses}
    default = next((item for item in design.circuit.netclasses if item.name.casefold() == "default"), None)
    return {net.name: classes.get(net.netclass_id or "") for net in design.circuit.nets}, default


def job_nets(
    design: Design, pads: Sequence[BoardPad], routes: Sequence[CriticalRoute], defaults: Sequence[Nm]
) -> tuple[JobNet, ...]:
    """The job nets of ``routes``: each route's net with its pads, the route's width and its class values."""
    of, default = _classes(design)
    net_ids = {net.name: net.id for net in design.circuit.nets}
    widths: dict[str, Nm] = {}
    for route in routes:
        widths[route.net] = min(widths.get(route.net, route.width), route.width)
    found: list[JobNet] = []
    for name in sorted(widths):
        netclass = of.get(name)
        values = [
            getattr(netclass, key, None) or getattr(default, key, None) or fallback
            for key, fallback in zip(("clearance", "via_diameter", "via_drill"), defaults[1:], strict=True)
        ]
        held = tuple(
            JobPad(p.ref, p.number, name, p.position, p.layers, p.drill) for p in pads if p.net == name
        )
        found.append(JobNet(name, net_ids[name], held, widths[name], values[0], values[1], values[2]))
    return tuple(found)


def pair_clearance(
    clearance: Callable[[RuleSubject, RuleSubject], Nm], design: Design
) -> Callable[[str, str], Nm]:
    of, _ = _classes(design)

    def between(a: str, b: str) -> Nm:
        first = RuleSubject("track", a, getattr(of.get(a), "name", None))
        second = RuleSubject("track", b, getattr(of.get(b), "name", None))
        return clearance(first, second)

    return between


# --- rip of branches ------------------------------------------------------------------------------------


def rip_branches(
    design: Design, judged: Judged, plan: CriticalPlan, records: Mapping[str, BoardPad]
) -> tuple[Design, int, dict[str, int]]:
    """``design`` without the copper of the branches of the plan's gate loops and Kelvin pairs (design
    decision 9): each Kelvin branch and gate return as c0222's walk finds it from the receiver or the return
    pad, without entering power copper, and the copper of a gate out net that no pad outside its group
    lies on. Locked copper and script copper are kept and counted; pours are never touched."""
    board = design.board
    if board is None:
        return design, 0, {"locked": 0, "script": 0}
    wanted = {group.name for group in plan.groups if group.status in ("planned", "kept")}
    ids: set[str] = set()
    for pair, attachments in judged.measured.attachments:
        if pair.name in wanted:
            for attachment in attachments:
                ids.update(attachment.branch)
    for gate, attachment in judged.measured.returns:
        if gate.name in wanted:
            ids.update(attachment.branch)
    net_ids = {net.name: net.id for net in design.circuit.nets}
    for gate in judged.resolved.roles.gates:
        if gate.name not in wanted:
            continue
        group = set(gate.pads)
        for pad in (gate.drive, gate.gate, *gate.resistor):
            record = records.get(pad)
            if record is None or not record.net:
                continue
            on_net = {name for name, found in records.items() if found.net == record.net}
            if on_net <= group:
                net_id = net_ids.get(record.net)
                ids.update(
                    item.id for item in (*board.tracks, *board.arcs, *board.vias) if item.net_id == net_id
                )
    held = [item for item in (*board.tracks, *board.arcs, *board.vias) if item.id in ids]
    locked = {item.id for item in held if item.locked}
    script = {
        item.id for item in held if item.id not in locked and is_copper_uuid(item.native_ids.get("kicad", ""))
    }
    gone = ids - locked - script
    kept = {"locked": len(locked), "script": len(script)}
    if not gone:
        return design, 0, kept
    trimmed = dataclasses.replace(
        board,
        tracks=tuple(item for item in board.tracks if item.id not in gone),
        arcs=tuple(item for item in board.arcs if item.id not in gone),
        vias=tuple(item for item in board.vias if item.id not in gone),
    )
    count = len(board.tracks) + len(board.arcs) + len(board.vias)
    count -= len(trimmed.tracks) + len(trimmed.arcs) + len(trimmed.vias)
    return dataclasses.replace(design, board=trimmed), count, kept


# --- corridors ----------------------------------------------------------------------------------------------


def corridors(
    design: Design,
    outcomes: Sequence[RoleOutcome],
    routes: Mapping[str, JobRoleRoute],
    nets: Mapping[str, JobNet],
    clearance: Callable[[str, str], Nm],
) -> dict[str, list[Keepout]]:
    """The corridors of the routed branches, per group: for each net of a group, one rule area per layer of
    its runs (the polyline grown by half its width and the zone clearance in force) and one over a square
    around each via on every copper layer, each with only ``no_copper_pour`` (design decision 10)."""
    board = design.board
    zone_clear: dict[str, Nm] = {}
    for zone in board.zones if board is not None else ():
        for layer in zone.layers:
            zone_clear[layer] = max(zone_clear.get(layer, 0), zone.settings.clearance)
    copper = tuple(
        layer.name
        for layer in sorted(board.layers if board is not None else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    found: dict[str, list[Keepout]] = {}
    for outcome in outcomes:
        if outcome.status != "routed" or not outcome.runs:
            continue
        route = routes[outcome.key]
        name = corridor_name(route.group, route.net)
        own = clearance(route.net, route.net)
        areas = found.setdefault(route.group, [])
        for layer, width, points in outcome.runs:
            grow = (width + 1) // 2 + max(zone_clear.get(layer, 0), own)
            for ring in corridor_rings(points, grow):
                areas.append(_area(name, ring, (layer,)))
        net = nets.get(route.net)
        for point in outcome.via_points:
            grow = (net.via_diameter if net is not None else 0) // 2 + max(
                max(zone_clear.values(), default=0), own
            )
            areas.append(_area(name, via_ring(point, grow), copper))
    return found


def _area(name: str, ring: Sequence[Point], layers: Sequence[str]) -> Keepout:
    outline = tuple(ring)
    geometry = [[p.x, p.y] for p in outline]
    return Keepout(
        id=derived_id("rul", "roles", content_hash(name, list(layers), geometry)),
        outline=outline,
        layers=tuple(layers),
        no_copper_pour=True,
        name=name,
    )


def with_corridors(design: Design, made: Mapping[str, Sequence[Keepout]]) -> Design:
    """``design`` with the corridors of ``made``, each replacing every rule area of its name, and the further
    pieces ``<name>.<n>`` of a provisional corridor of phase 1 (``fenolite copper``, change c0243)."""
    board = design.board
    if board is None or not made:
        return design
    names = {area.name for areas in made.values() for area in areas}

    def replaced(name: str) -> bool:
        base, _, number = name.rpartition(".")
        return name in names or (number.isdigit() and base in names)

    kept = tuple(area for area in board.keepouts if not replaced(area.name))
    added = tuple(area for group in sorted(made) for area in made[group])
    return dataclasses.replace(design, board=dataclasses.replace(board, keepouts=(*kept, *added)))


# --- the reply ----------------------------------------------------------------------------------------------


def _region(plan: GroupPlan, records: Mapping[str, BoardPad]) -> str:
    points = [records[name].position for name in plan.pads if name in records]
    if not points:
        return ""
    x0 = min(p.x for p in points) - REGION_MARGIN
    y0 = min(p.y for p in points) - REGION_MARGIN
    x1 = max(p.x for p in points) + REGION_MARGIN
    y1 = max(p.y for p in points) + REGION_MARGIN
    return ",".join(format_length(v) for v in (x0, y0, x1, y1))


def _proposal(
    plan: GroupPlan,
    reason: str,
    detail: str,
    board: str,
    records: Mapping[str, BoardPad],
    blockers: Sequence[str],
) -> dict[str, str]:
    region = _region(plan, records)
    render = (
        f"fenolite render {board} --out fenolite-region --region {region} --nets --open" if region else ""
    )
    route = f"fenolite route {board} --router octilinear --roles critical --group {plan.name}"
    named = ", ".join(blockers) if blockers else ""
    if reason == "unconfirmed":
        return {
            "kind": "confirm",
            "text": f"confirm the group {plan.name}",
            "command": f"fenolite roles {board} --accept-group {plan.name} --dry-run",
            "region": region,
        }
    if reason == "phase-1":
        command = f"fenolite copper {board} --dry-run" if "copper" in _commands() else ""
        return {
            "kind": "power-copper",
            "text": "place the hot loop as power copper (pours) with the power-copper phase",
            "command": command,
            "region": region,
        }
    if reason == "kept":
        return {
            "kind": "rip",
            "text": "replace the group's branches",
            "command": f"{route} --rip --dry-run",
            "region": region,
        }
    if reason == "no-layer":
        option = "kelvin-vias=2" if plan.kind == "kelvin_pair" else "gate-vias=2"
        return {
            "kind": "allow-via",
            "text": f"allow a via per branch ({option}), or move a part",
            "command": f"{route} --router-option {option} --dry-run",
            "region": region,
        }
    if reason == "too-long":
        return {
            "kind": "raise-limit",
            "text": "raise max-length, or move a part closer",
            "command": f"{route} --router-option max-length=40mm --dry-run",
            "region": region,
        }
    if reason == "pads":
        return {
            "kind": "move-part",
            "text": "place the group's parts, or edit the role with fenolite roles --set",
            "command": f"fenolite roles {board} --dry-run",
            "region": region,
        }
    text = "free the corridor"
    if named:
        text += f": {named}"
    if detail:
        text += f" ({detail})"
    return {"kind": "free-corridor", "text": text, "command": render, "region": region}


def _commands() -> set[str]:
    from fenolite.cli.api import discover

    return set(discover())


def _finding_json(found: Sequence[tuple[str, str, str, int | None]], group: str) -> list[dict[str, Any]]:
    return [
        {"code": code, "severity": severity, "measure": measure}
        for code, held, severity, measure in found
        if held == group and code != "roles.loop-open"
    ]


def _connection(route: JobRoleRoute, outcome: RoleOutcome | None) -> dict[str, Any]:
    return {
        "key": route.key,
        "net": route.net,
        "a": route.a.label,
        "b": route.b.label,
        "layer": outcome.layer if outcome is not None and outcome.layer else None,
        "form": outcome.form if outcome is not None and outcome.form else None,
        "length": outcome.length if outcome is not None else 0,
        "vias": outcome.vias if outcome is not None else 0,
    }


# --- the run ------------------------------------------------------------------------------------------------


def run_roles(
    args: argparse.Namespace,
    ctx: Context,
    *,
    router: Router,
    tool_version: str,
    board_path: Path,
    text: str,
    design: Design,
    as_read: Design,
    rules: DesignRules,
    input_ref: InputRef,
    checks: Mapping[str, object],
    options: Mapping[str, str],
    defaults: Sequence[Nm],
    major: int,
    output: str,
    read_issues: Sequence[Issue],
) -> Result:
    """``route --roles critical``: see the module."""
    declared, confirmed, circuit, roles_file = roles_of(args, ctx, board_path)
    pads = board_pads(design, issues=[])
    records = {f"{p.ref}-{p.number}": p for p in pads}
    judge = Judge(pads, circuit, confirmed, declared)
    before = judge.findings(design)
    roles = judge.judged(design).resolved.roles
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    planes = board_plane_layers(design)
    routable = routing_layers(layers, planes)
    clearance = pair_clearance(checks["clearance"], design)  # type: ignore[arg-type]
    held: dict[str, list[str]] = {}
    for code, group, _severity, _measure in before:
        if code != "roles.loop-open":
            held.setdefault(group, []).append(code)
    plan = plan_critical(
        design, roles, pads, layers=routable, clearance=clearance, default_width=defaults[0],
        groups=tuple(args.group), findings=held,
    )  # fmt: skip
    ripped, rip_kept = 0, {"locked": 0, "script": 0}
    if args.rip:
        design, ripped, rip_kept = rip_branches(design, judge.judged(design), plan, records)
        if ripped:
            judge = Judge(pads, circuit, confirmed, declared)
            before = judge.findings(design)
            roles = judge.judged(design).resolved.roles
            held = {}
            for code, group, _severity, _measure in before:
                if code != "roles.loop-open":
                    held.setdefault(group, []).append(code)
            plan = plan_critical(
                design, roles, pads, layers=routable, clearance=clearance, default_width=defaults[0],
                groups=tuple(args.group), findings=held,
            )  # fmt: skip
    board_name = board_path.name
    depends = depends_on(ctx.cwd, board_path, roles_file, None)
    issues: list[Issue] = [*read_issues]
    if not plan.groups:
        named = f" among {', '.join(args.group)}" if args.group else ""
        issues.append(
            Issue(
                "route.role-none",
                "info",
                f"the board holds no confirmed or declared gate loop or Kelvin pair to route{named}",
                board_name,
                hint=f"run fenolite roles {board_name} to see and confirm the inferred groups",
            )
        )
    routes = {route.key: job_route(route) for route in plan.routes}
    nets = {net.name: net for net in job_nets(design, pads, plan.routes, defaults)}
    outcome = RoutingResult(tool=router.name, tool_version=tool_version)
    if routes:
        extra = {
            "board_pads": pads,
            "outline": board_outline(design).rings,
            **checks,
            "role_check": judge.findings,
        }
        outcome = router.route(
            RoutingJob(
                design,
                tuple(nets.values()),
                layers,
                options,
                extra,
                plane_layers=planes,
                progress=ctx.progress,
                roles=tuple(routes.values()),
            )
        )
    issues.extend(outcome.issues)
    by_key = {item.key: item for item in outcome.roles}
    merged = design
    try:
        merged = apply(design, RoutingResult(tracks=outcome.tracks, arcs=outcome.arcs, vias=outcome.vias))
    except RoutingError as exc:
        issues.extend(exc.issues)
        by_key = {key: RoleOutcome(key, route.group, "unrouted", "no-room") for key, route in routes.items()}
    made = corridors(merged, list(by_key.values()), routes, nets, clearance)
    merged = with_corridors(merged, made)
    copper_of = _group_items(outcome, routes, by_key)
    gate_result: dict[str, object] | None = None
    gate_evidence: Evidence | None = None
    dropped_groups: dict[str, str] = {}
    if args.gate == "drc":
        together = [
            frozenset((*copper_of.get(group, ()), *(a.id for a in made.get(group, ()))))
            for group in sorted(set(copper_of) | set(made))
        ]
        gated = _gate.gate(
            board_path, as_read, merged, kicad_cli=args.kicad_cli, timeout=DEFAULT_TIMEOUT, together=together
        )
        merged, gate_result, gate_evidence = gated.design, gated.result, gated.evidence
        issues.extend(gated.issues)
        for group, items in copper_of.items():
            if any(item in gated.dropped for item in items):
                first = (
                    next(i for i in gated.issues if i.where in items)
                    if any(i.where in items for i in gated.issues)
                    else None
                )
                dropped_groups[group] = (
                    first.message if first is not None else "KiCad's DRC found something new"
                )
    after = judge.findings(merged)
    entries: list[dict[str, Any]] = []
    unrouted_groups: list[str] = []
    for group_plan in plan.groups:
        entry, failed = _entry(
            group_plan,
            routes,
            by_key,
            before,
            after,
            made,
            copper_of,
            dropped_groups,
            board_name,
            records,
            issues,
        )
        entries.append(entry)
        if failed:
            unrouted_groups.append(group_plan.name)
    unconfirmed = [g.name for g in plan.groups if g.reason == "unconfirmed"]
    if unconfirmed:
        issues.append(
            Issue(
                "route.role-unconfirmed",
                "info",
                f"{len(unconfirmed)} inferred group(s) are not routed until confirmed: "
                f"{', '.join(unconfirmed)}",
                unconfirmed[0],
                hint=f"fenolite roles {board_name} --accept-group {unconfirmed[0]} --dry-run",
            )
        )
    _placement(plan, judge.judged(design), issues)
    if args.require_complete and unrouted_groups:
        issues.append(
            Issue(
                "route.incomplete",
                "error",
                f"{len(unrouted_groups)} role group(s) stay open: {', '.join(unrouted_groups[:5])}; "
                "nothing is written",
                unrouted_groups[0],
                hint="run without --require-complete to keep the routed groups, then follow the proposals",
            )
        )
    added = bool(_gate.edit_ids(as_read, merged))
    zones_stale = bool(design.board and any(zone.filled or zone.fills for zone in design.board.zones))
    if added and zones_stale:
        issues.append(
            Issue("route.fill-stale", "info", "routing changed copper; run fenolite fill before check")
        )
    board_text = write_board(merged, target=major, allow_lossy=ctx.allow_lossy).text
    failed = any(found.severity == "error" for found in issues)
    writes = (
        (PlannedWrite(output, board_text.encode("utf-8"), "kicad_pcb"),)
        if added and not failed and (args.out is not None or board_text != text)
        else ()
    )
    evidence = gate_evidence or Evidence(
        Level.UNVERIFIED,
        f"{outcome.tool} {outcome.tool_version}".strip(),
        hypotheses=outcome.evidence.hypotheses + (("H-G-CRIT-KELVIN", "H-G-CRIT-GATE") if routes else ()),
    )
    route_nets = sorted({route.net for route in routes.values()})
    open_nets = sorted({route.net for route in routes.values() if route.group in unrouted_groups})
    new_tracks = [item for item in outcome.tracks if item.id not in _dropped(gate_result)]
    new_vias = [item for item in outcome.vias if item.id not in _dropped(gate_result)]
    return Result(
        result={
            "board": board_name,
            "router": router.name,
            "tool_version": outcome.tool_version or None,
            "selected": route_nets,
            "routed": [name for name in route_nets if name not in open_nets],
            "unrouted": open_nets,
            "open": [],
            "connections": {
                "before": len(routes),
                "after": sum(1 for route in routes.values() if route.group in unrouted_groups),
            },
            "tracks": len(new_tracks),
            "vias": len(new_vias),
            "ripped": ripped,
            "rip_kept": rip_kept,
            "log": [],
            "fills_stale": added and zones_stale,
            "budget": {"seconds": None, "spent": 0.0, "exhausted": False},
            "runs": [],
            "not_attempted": [],
            "resumed": None,
            "plane_layers": list(planes),
            "plane_fanout": None,
            "pairs": [],
            "escape": [],
            "gate": gate_result,
            "roles": entries,
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
        depends=depends,
    )


def _dropped(gate: Mapping[str, object] | None) -> set[str]:
    if not gate:
        return set()
    items = gate.get("dropped", [])
    return {str(item["id"]) for item in items if isinstance(item, dict)} if isinstance(items, list) else set()  # type: ignore[misc]


def _group_items(
    outcome: RoutingResult, routes: Mapping[str, JobRoleRoute], by_key: Mapping[str, RoleOutcome]
) -> dict[str, list[str]]:
    """The ids of the tracks and vias of each group, matched by their runs and via points."""
    found: dict[str, list[str]] = {}
    for key, item in by_key.items():
        route = routes.get(key)
        if route is None or item.status != "routed":
            continue
        segments = {
            (layer, width, p, q)
            for layer, width, points in item.runs
            for p, q in zip(points, points[1:], strict=False)
        }
        for track in outcome.tracks:
            if (track.layer, track.width, track.start, track.end) in segments:
                found.setdefault(route.group, []).append(track.id)
        for via in outcome.vias:
            if via.position in item.via_points:
                found.setdefault(route.group, []).append(via.id)
    return {group: sorted(set(ids)) for group, ids in found.items()}


def _entry(
    plan: GroupPlan,
    routes: Mapping[str, JobRoleRoute],
    by_key: Mapping[str, RoleOutcome],
    before: Sequence[tuple[str, str, str, int | None]],
    after: Sequence[tuple[str, str, str, int | None]],
    made: Mapping[str, Sequence[Keepout]],
    copper_of: Mapping[str, Sequence[str]],
    dropped: Mapping[str, str],
    board: str,
    records: Mapping[str, BoardPad],
    issues: list[Issue],
) -> tuple[dict[str, Any], bool]:
    """The reply entry of one group and whether it stays open (unrouted or refused)."""
    mine = [routes[key] for key in plan.routes]
    outcomes = [by_key.get(route.key) for route in mine]
    status, reason, detail, blockers = plan.status, plan.reason, "", ()
    if plan.status == "planned":
        refused = next((o for o in outcomes if o is not None and o.status == "refused"), None)
        failures = [o for o in outcomes if o is None or o.status == "unrouted"]
        if plan.name in dropped:
            status, reason, detail = "unrouted", "drc", dropped[plan.name]
        elif refused is not None:
            status, reason, detail = "refused", "role-check", refused.detail
        elif failures:
            first = failures[0]
            status, reason = "unrouted", first.reason if first is not None else "no-room"
            blockers = first.blockers if first is not None else ()
        else:
            status = "routed"
    kind = KINDS[plan.kind]
    entry: dict[str, Any] = {
        "group": plan.name,
        "kind": plan.kind,
        "status": status,
        "connections": [_connection(route, by_key.get(route.key)) for route in mine],
        "findings_before": _finding_json(before, plan.name),
        "findings_after": _finding_json(after, plan.name),
        "reason": reason or None,
        "proposal": None,
        "copper": list(copper_of.get(plan.name, ())) if status == "routed" else [],
        "corridors": sorted(a.id for a in made.get(plan.name, ())) if status == "routed" else [],
    }
    if status in ("unrouted", "refused", "skipped", "kept"):
        proposal = _proposal(plan, reason if status != "kept" else "kept", detail, board, records, blockers)
        entry["proposal"] = proposal
        if status == "kept":
            codes = ", ".join(plan.findings)
            issues.append(
                Issue(
                    "route.role-kept",
                    "info",
                    f"the {kind} {plan.name} is joined by copper and still has {codes}; it is kept as it is",
                    plan.name,
                    hint=proposal["command"],
                )
            )
        elif status == "unrouted":
            named = f" ({', '.join(blockers)})" if blockers else ""
            extra = f": {detail}" if detail else ""
            issues.append(
                Issue(
                    "route.role-unrouted",
                    "warning",
                    f"the {kind} {plan.name} is not routed: {REASONS.get(reason, reason)}{named}{extra}; "
                    f"proposal: {proposal['text']}",
                    plan.name,
                    hint=proposal["command"],
                )
            )
        elif status == "refused":
            issues.append(
                Issue(
                    "route.role-refused",
                    "warning",
                    f"the copper of the {kind} {plan.name} was removed: {detail}",
                    plan.name,
                    hint=proposal["command"],
                )
            )
    return entry, status in ("unrouted", "refused")


def _placement(plan: CriticalPlan, judged: Judged, issues: list[Issue]) -> None:
    """One ``route.role-placement`` per gate loop whose placement bound is above the user's ``gate_max``."""
    from fenolite.roles import profile

    roles = judged.resolved.roles
    for measure in judged.measured.measures:
        if measure.kind != "loop" or measure.values.get("group") != "gate":
            continue
        if plan.group(measure.subject) is None:
            continue
        limit = profile.resolve("gate_max", roles.limits, net=measure.values.get("net"), kind="gate")
        bound = measure.values.get("bound_nm2")
        if limit.value is None or not isinstance(bound, int) or bound <= limit.value:
            continue
        issues.append(
            Issue(
                "route.role-placement",
                "info",
                f"the gate loop {measure.subject} has a placement bound of {bound} nm², above "
                f"{limit.text()}: no "
                "route brings its area under the limit",
                measure.subject,
                hint="place the driver closer to the switch with fenolite place --move",
            )
        )


__all__ = [
    "ROLE_MODES",
    "Judge",
    "check",
    "corridors",
    "job_nets",
    "job_route",
    "pair_clearance",
    "register",
    "roles_of",
    "run_roles",
    "with_corridors",
]
