# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route the nets of a board that still have open connections through a registered Fenolite router
(capability cli-contract, "Route command"; ``docs/cli-contract.md``, "route").

The nets are selected by the open connections of the board (``analysis.connectivity``), so script copper
and earlier routes stay and a second run completes what the first left open. The verdict is taken from
the board after the merge, not from the router's lists; copper returned for a net that stays open is kept.

Change c0107: the command reads the project's rules, takes the board's plane layers (copper layers of type
``power``) and track layer rules into its job, joins the SMD pads of plane nets to their planes before the
router runs (``backends.kicad.fanout``), and never gives a plane net to a router (capability cli-contract,
"Plane nets in the route command").

``--timeout`` is the one time budget of the routing step, whatever the router, and ``--order`` puts nets
in tiers that are routed one after the other (capability cli-contract, "Route command budget and tiers";
change c0109). When the budget ends, the copper of the router runs that finished is written and the rest is
reported: run ``route`` again to continue with the nets that are still open.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import math
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

from fenolite import __version__
from fenolite.analysis.connectivity import connectivity
from fenolite.backends.base import DesignRules, ProjectSet
from fenolite.backends.kicad import fanout, pro
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import plane_layers as board_plane_layers
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.clearance import ClearanceResolver
from fenolite.cli import plans
from fenolite.cli._boardview import to_json
from fenolite.cli._examples import EXAMPLE_UNROUTED
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.jobs import JobRecord, route_job_key
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, RuleSubject, Selector
from fenolite.routing.layers import allowed_layers, routing_layers
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import FinishedRun, JobNet, JobPad, Router, RoutingJob, RoutingResult
from fenolite.routing.registry import routers
from fenolite.routing.select import rip, unrouted

HELP = "route selected KiCad board nets with a registered Fenolite routing plugin"
DEFAULTS = (200_000, 200_000, 600_000, 300_000)


def _safe_log(lines: tuple[str, ...], cwd: Path) -> list[str]:
    """Keep diagnostic lines useful without exposing temporary or home paths."""
    home = str(Path.home())
    temp = os.getenv("TMPDIR") or tempfile.gettempdir()
    # the longer prefix first: on Windows the temporary folder lies inside the home folder
    prefixes = sorted(((home, "<home>"), (temp, "<tmp>")), key=lambda pair: -len(pair[0]))
    result: list[str] = []
    for line in lines[:20]:
        safe = line
        for prefix, label in prefixes:
            safe = safe.replace(prefix, label)
        safe = re.sub(r"/(?:private/)?tmp/[^\s:'\"]+", "<tmp>", safe)
        safe = safe.replace(str(cwd), "<workdir>")
        result.append(safe)
    return result


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'route'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, .kicad_pro or project folder")
    parser.add_argument("--router", required=True, metavar="NAME", help="registered routing plugin")
    parser.add_argument(
        "--nets", action="append", default=None, metavar="GLOB", help="net-name pattern (repeatable)"
    )
    parser.add_argument(
        "--rip",
        action="store_true",
        help="remove the copper of the matching nets before routing; locked and script copper stay",
    )
    parser.add_argument(
        "--include-zone-nets", action="store_true", help="route nets that also have copper zones"
    )
    parser.add_argument(
        "--no-plane-fanout",
        action="store_true",
        help="do not join the SMD pads of plane nets to their planes with fan-out vias before routing",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 5 and write nothing when a selected net still has an open connection",
    )
    parser.add_argument(
        "--router-path",
        metavar="PATH",
        help="KiCadRoutingTools checkout, or the Freerouting jar (docker:<image> runs a container)",
    )
    parser.add_argument("--router-python", metavar="PATH", help="Python interpreter for the external router")
    parser.add_argument(
        "--router-option", action="append", default=[], metavar="KEY=VALUE", help="router-specific option"
    )
    parser.add_argument(
        "--order",
        action="append",
        default=[],
        metavar="GLOB",
        help="route the matching nets first (repeatable: one tier per glob, the other nets last)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="time budget of the whole routing step (default: the router's own, 900 s for the "
        "external routers); the copper of the router runs that finished in time is kept",
    )
    parser.add_argument(
        "--allow-offsite", action="store_true", help="allow a router that sends design data off this machine"
    )
    parser.add_argument("-o", "--out", metavar="FILE", help="write the routed board to this file")


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    includes = tuple(pattern for pattern in patterns if not pattern.startswith("!"))
    excludes = tuple(pattern[1:] for pattern in patterns if pattern.startswith("!"))
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in includes) and not any(
        fnmatch.fnmatchcase(name, pattern) for pattern in excludes
    )


def _router(name: str, args: argparse.Namespace) -> Router:
    available = routers()
    if name not in available:
        known = ", ".join((*available,)) or "none"
        raise CliError("FEN-2001", f"unknown router {name!r} (registered: {known})")
    selected = available[name]
    # The budget is the given value whatever it is: no value stands for "the default" (c0109).
    budget: float | None = args.timeout
    if name == "kicadroutingtools" and (args.router_path or args.router_python or budget is not None):
        from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter

        return KicadRoutingToolsRouter(args.router_path, args.router_python, budget)
    if name == "freerouting" and (args.router_path or budget is not None):
        from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter

        return FreeroutingRouter(args.router_path, budget=budget)
    return selected


def _tier(name: str, order: tuple[str, ...]) -> int:
    """The tier of a net: the index of the first ``--order`` glob it matches, else the count of globs."""
    return next(
        (index for index, pattern in enumerate(order) if fnmatch.fnmatchcase(name, pattern)), len(order)
    )


def _budget_json(seconds: float | None, spent: float, ended: bool) -> dict[str, object]:
    return {"seconds": seconds, "spent": round(spent, 1), "exhausted": ended}


def _missing_hint(router: Router) -> str | None:
    """The hint of an unavailable router: the command that installs the Freerouting jar when that jar is
    what is missing, else ``None`` (the registry's hint)."""
    from fenolite.routing.plugins.specctra.freerouting import FETCH_COMMAND, FreeroutingRouter

    if isinstance(router, FreeroutingRouter) and router.jar_missing:
        return f"run '{FETCH_COMMAND}'"
    return None


def _relative(path: Path, cwd: Path) -> str:
    """``path`` relative to ``cwd``, or as it is when the two are on different Windows drives."""
    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return str(path)


EDGE_MINIMUM = "min_copper_edge_clearance"
"""The board-setup minimum of the project that the command hands on as a board-wide edge clearance rule."""
_ALL = Selector("all")


def _project_rules(design: Design, board_path: Path, issues: list[Issue]) -> DesignRules:
    """``design`` with the net classes of the project file and the lifted rules of the rules file beside
    the board (``KicadBackend.design_rules``), so that a router gets each net's own track width, clearance
    and via size, and the rules of the design. A KiCad board holds neither: without the two files, every
    net would take the defaults. A file that cannot be read gives ``route.project-unread`` and leaves the
    design as the other file gives it."""
    files = {board_path.name: board_path}
    for suffix in (".kicad_pro", ".kicad_dru"):
        beside = board_path.with_suffix(suffix)
        if beside.is_file():
            files[beside.name] = beside
    project = ProjectSet(root=board_path.parent, board=board_path.name, files=files)
    found = KicadBackend().design_rules(design, project, issues=issues)
    for name, error in found.unread:
        lost = (
            "every net takes the default class values"
            if name.endswith(".kicad_pro")
            else "the rules of the design are not given to the router"
        )
        issues.append(
            Issue("route.project-unread", "warning", f"{name} could not be read, so {lost}: {error}", name)
        )
    return found


def _edge_minimum(board_path: Path) -> Nm:
    """The ``min_copper_edge_clearance`` of the project file beside the board, or 0."""
    project = board_path.with_suffix(".kicad_pro")
    if not project.is_file():
        return 0
    try:
        data = pro.read_project_text(project.read_text(encoding="utf-8"))
        return max(0, pro.project_minimums(data).get(EDGE_MINIMUM, 0))
    except (FormatError, UnicodeDecodeError, OSError):
        return 0  # the unread project is already reported


def _with_edge_rule(design: Design, minimum: Nm) -> Design:
    """``design`` with one board-wide ``edge_clearance`` rule of the project's minimum, so that the
    fan-out and the router keep it as KiCad's check does."""
    if minimum <= 0:
        return design
    rule = Rule(
        id=derived_id("rul", "kicad", f"rule:project:{EDGE_MINIMUM}"),
        name=EDGE_MINIMUM,
        kind="edge_clearance",
        selector_a=_ALL,
        min=minimum,
    )
    held = design.rules
    if held is None:
        rules = RuleSet(id=derived_id("rst", "kicad", "rules:route"), rules=(rule,))
    else:
        rules = dataclasses.replace(held, rules=(*held.rules, rule))
    return dataclasses.replace(design, rules=rules)


def _edge_clearance(design: Design) -> Nm:
    """The largest ``min`` of the board-wide ``edge_clearance`` rules of ``design``, or 0."""
    rules = design.rules.rules if design.rules is not None else ()
    return max(
        (
            rule.min
            for rule in rules
            if rule.kind == "edge_clearance"
            and rule.severity != "ignore"
            and rule.min is not None
            and rule.selector_a == _ALL
            and rule.selector_b is None
        ),
        default=0,
    )


def _net_values(net: Net, classes: dict[str, NetClass], default_class: NetClass | None) -> tuple[Nm, ...]:
    """Track width, clearance, via diameter and via drill of ``net``: its class, else the project's
    ``Default`` class, else the command's constants."""
    netclass = classes.get(net.netclass_id or "")
    return tuple(
        getattr(netclass, key, None) or getattr(default_class, key, None) or fallback
        for key, fallback in zip(
            ("track_width", "clearance", "via_diameter", "via_drill"), DEFAULTS, strict=True
        )
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    if args.router_path and args.router not in ("kicadroutingtools", "freerouting"):
        raise CliError("FEN-2001", "--router-path is only supported by kicadroutingtools and freerouting")
    if args.router_python and args.router != "kicadroutingtools":
        raise CliError("FEN-2001", "--router-python is only supported by kicadroutingtools")
    if args.timeout is not None and not (math.isfinite(args.timeout) and args.timeout > 0):
        raise CliError(
            "FEN-2001",
            f"--timeout must be a positive number of seconds, got {args.timeout:g}",
            hint="--timeout is the time budget of the whole routing step",
        )
    order = tuple(args.order)
    options: dict[str, str] = {}
    for option in args.router_option:
        key, separator, value = option.partition("=")
        if not separator or not key or not value:
            raise CliError("FEN-2001", f"invalid --router-option {option!r}; expected KEY=VALUE")
        options[key] = value
    router = _router(args.router, args)
    if router.sends_data_offsite and not args.allow_offsite:
        raise CliError(
            "FEN-2001", "this router sends design data offsite", hint="pass --allow-offsite to continue"
        )
    # the budget the step runs with: the caller's, else the router's own; a router without one (the
    # built-in direct router) starts no process and is not bounded
    default_budget: float | None = getattr(router, "default_budget", None)
    budget_seconds: float | None = args.timeout if args.timeout is not None else default_budget
    status = router.available()
    if not status.available:
        raise CliError(
            "FEN-6001", status.reason or f"router {router.name!r} is unavailable", hint=_missing_hint(router)
        )
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    read_issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=read_issues)
    source = source_info(design)
    project_rules = _project_rules(design, board_path, read_issues)
    design = _with_edge_rule(project_rules.design, _edge_minimum(board_path))
    input_ref = InputRef(
        board_path.name,
        hashlib.sha256(data).hexdigest(),
        "kicad_pcb",
        str(source.version) if source is not None else None,
    )
    patterns = tuple(args.nets or ("*",))
    board = design.board
    zone_ids: set[str | None] = {zone.net_id for zone in board.zones} if board is not None else set()
    matching = tuple(
        sorted(
            net.name
            for net in design.circuit.nets
            if len(design.by_net.get(net.name, ())) >= 2 and _matches(net.name, patterns)
        )
    )
    net_ids = {net.name: net.id for net in design.circuit.nets}
    nets_by_name = {net.name: net for net in design.circuit.nets}
    classes = {item.id: item for item in design.circuit.netclasses}
    default_class = next(
        (item for item in design.circuit.netclasses if item.name.casefold() == "default"), None
    )
    # plane layers and plane nets: a plane net is never a job net, whatever the selection gives
    planes = board_plane_layers(design)
    plane_names = set(fanout.plane_nets(design, planes))
    plane_selected = tuple(name for name in matching if name in plane_names)
    wanted = tuple(
        name
        for name in matching
        if name not in plane_names and (args.include_zone_nets or net_ids[name] not in zone_ids)
    )
    zone_skipped = tuple(name for name in matching if name not in wanted and name not in plane_names)
    ripped = 0
    rip_kept = {"locked": 0, "script": 0}
    if args.rip and board is not None:
        design, ripped, rip_kept = _rip(design, (*wanted, *plane_selected))
    frame_pads = board_pads(design, issues=read_issues)
    outline_rings = board_outline(design).rings
    # the plane fan-out: its copper is merged before the job is built, so the router sees it as existing
    fanned = fanout.FanoutPlan()
    fanout_issues: list[Issue] = []
    if plane_selected and not args.no_plane_fanout:
        resolver = ClearanceResolver(
            design,
            min_clearance=project_rules.min_clearance,
            rules_over_classes=project_rules.rules_over_classes,
            floor_over_rules=project_rules.floor_over_rules,
        )

        def in_force(a: RuleSubject, b: RuleSubject) -> Nm:
            return resolver.resolve(a, b).value or 0

        sizes: dict[str, fanout.FanoutSizes] = {}
        for name in plane_selected:
            width, clearance, diameter, drill = _net_values(nets_by_name[name], classes, default_class)
            sizes[name] = fanout.FanoutSizes(width, diameter, drill, clearance)
        fanned = fanout.plan_fanout(
            design,
            frame_pads,
            nets=sizes,
            plane_layers=planes,
            outline=outline_rings,
            edge_clearance=_edge_clearance(design),
            clearance=in_force,
        )
        fanout_issues += fanned.issues
        try:
            design = apply(design, RoutingResult(tracks=fanned.tracks, vias=fanned.vias))
        except RoutingError as exc:
            fanout_issues += exc.issues
            fanned = dataclasses.replace(fanned, tracks=(), vias=())
    fanout_made = bool(fanned.tracks or fanned.vias)
    plane_issues = [
        Issue(
            "route.plane-net",
            "info",
            f"plane net {name} is not routed: its pads reach the plane through fan-out vias",
            name,
        )
        for name in plane_selected
    ]
    plane_result: dict[str, object] = {
        "nets": sorted(plane_selected) if not args.no_plane_fanout else [],
        "pads": len(fanned.pads),
        "joined": len(fanned.joined),
        "tracks": len(fanned.tracks),
        "vias": len(fanned.vias),
        "failed": list(fanned.failed),
    }
    # the copper of the router runs that finished in an earlier call of this job, merged before the nets
    # are selected, so that those nets are not routed again. It is merged after the plane fan-out, as the
    # router of that call saw the board: the fan-out is planned on the same board and gives the same copper
    project_file = board_path.with_suffix(".kicad_pro")
    rules_file = board_path.with_suffix(".kicad_dru")  # read with the project by ``_project_rules``
    record = JobRecord(
        ctx.state,
        route_job_key(
            fenolite_version=__version__,
            router=router.name,
            router_version=status.version,
            board_sha256=input_ref.sha256 or "",
            project_sha256=plans.digest_of(project_file),
            rules_sha256=plans.digest_of(rules_file),
            arguments=plans.arguments(vars(args)),
        ),
    )
    reused = record.runs()
    if reused:
        try:
            design = apply(design, _copper_of(reused))
        except RoutingError:  # a record that does not fit this board is not one of this job
            record.remove()
            reused = ()
    resumed = _copper_of(reused)
    resumed_nets = sorted({name for run in reused for name in run.nets})
    depends = depends_on(
        ctx.cwd,
        board_path,
        project_file if project_file.is_file() else None,
        rules_file if rules_file.is_file() else None,
    )
    # the open connections of the board as it is given to the router: after the rip, and after any copper
    # that a step of this command adds before the router
    before = connectivity(design, pads=frame_pads, nets=wanted)
    candidates = tuple(
        name
        for name in unrouted(
            design, before.open_nets(), patterns=patterns, include_zone_nets=args.include_zone_nets
        )
        if name not in plane_names
    )
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    routable = routing_layers(layers, planes)
    net_layers: dict[str, tuple[str, ...] | None] = {}
    layer_issues: list[Issue] = []
    for name in candidates:
        allowed = allowed_layers(design, nets_by_name[name], routable)
        if not allowed:
            layer_issues.append(
                Issue(
                    "route.no-layer",
                    "warning",
                    f"net {name} may use no routing layer: track layer rules forbid every one of "
                    f"{', '.join(routable) or 'none'}; it is not routed",
                    name,
                    hint="free a layer for the net in its no_tracks rules",
                )
            )
        else:
            net_layers[name] = None if allowed == routable else allowed
    candidates = tuple(name for name in candidates if name in net_layers)
    pads_by_net: dict[str, list[JobPad]] = {}
    for pad in frame_pads:
        if pad.net and pad.net_id and pad.net in candidates:
            pads_by_net.setdefault(pad.net, []).append(
                JobPad(pad.ref, pad.number, pad.net, pad.position, pad.layers, pad.drill)
            )
    jobs: list[JobNet] = []
    for name in candidates:
        values = _net_values(nets_by_name[name], classes, default_class)
        jobs.append(
            JobNet(
                name,
                net_ids[name],
                tuple(pads_by_net.get(name, ())),
                values[0],
                values[1],
                values[2],
                values[3],
                net_layers[name],
                tier=_tier(name, order),
            )
        )
    jobs.sort(key=lambda item: (item.tier, item.name))
    skipped = [
        *(
            Issue("route.zone-net-skipped", "info", f"zone net {name} was skipped", name)
            for name in zone_skipped
        ),
        *plane_issues,
        *layer_issues,
    ]
    target = source_info(design)
    major = target.major if target is not None and target.major is not None else ctx.kicad_target
    output = args.out or _relative(board_path, ctx.cwd)
    zones_stale = bool(design.board and any(zone.filled or zone.fills for zone in design.board.zones))
    if not jobs and not reused:
        # no net for a router: the fan-out copper alone is still written
        fan_text = (
            write_board(design, target=major, allow_lossy=ctx.allow_lossy).text if fanout_made else text
        )
        fan_issues = list(fanout_issues)
        if fanout_made and zones_stale:
            fan_issues.append(
                Issue("route.fill-stale", "info", "routing changed copper; run fenolite fill before check")
            )
        return Result(
            result={
                "board": board_path.name,
                "router": router.name,
                "tool_version": None,
                "selected": [],
                "routed": [],
                "unrouted": [],
                "open": [],
                "connections": {"before": 0, "after": 0},
                "tracks": 0,
                "vias": 0,
                "ripped": ripped,
                "rip_kept": rip_kept,
                "log": [],
                "fills_stale": fanout_made and zones_stale,
                "budget": _budget_json(budget_seconds, 0.0, False),
                "runs": [],
                "not_attempted": [],
                "resumed": None,
                "plane_layers": list(planes),
                "plane_fanout": plane_result,
            },
            issues=(*read_issues, *before.issues, *fan_issues, *skipped),
            evidence=Evidence(Level.UNVERIFIED, router.name),
            input=input_ref,
            writes=(
                (PlannedWrite(output, fan_text.encode("utf-8"), "kicad_pcb"),)
                if fanout_made and (args.out is not None or fan_text != text)
                else ()
            ),
            depends=depends,
        )
    extra = {"board_pads": frame_pads, "outline": outline_rings}
    started = time.monotonic()
    if jobs:
        outcome = router.route(
            RoutingJob(
                design,
                tuple(jobs),
                layers,
                options,
                extra,
                plane_layers=planes,
                budget=args.timeout,
                on_run=record.add,
                progress=ctx.progress,
            )
        )
    else:  # every open net was routed by the runs of the record: no process starts
        outcome = RoutingResult(tool=router.name, tool_version=status.version)
    # only a router that has a budget is timed: the result of the built-in router stays the same bytes
    spent = time.monotonic() - started if default_budget is not None else 0.0
    budget_ended = bool(outcome.not_attempted) or any(
        found.code == "route.budget-exhausted" for found in outcome.issues
    )
    issues = [*read_issues, *before.issues, *fanout_issues, *outcome.issues, *skipped]
    if reused:
        issues.append(
            Issue(
                "route.resumed",
                "info",
                f"{len(reused)} router run(s) of an earlier call were reused: the copper of "
                f"{len(resumed_nets)} net(s) was not routed again",
                resumed_nets[0] if resumed_nets else "",
                hint="copper made in two calls need not equal the copper of one",
            )
        )
    merged_ok = True
    try:
        merged = apply(design, outcome)
    except RoutingError as exc:
        issues.extend(exc.issues)
        merged = design
        merged_ok = False
    # the verdict: the open connections of the selected nets on the merged board, whatever the router listed
    after = connectivity(merged, pads=frame_pads, nets=candidates)
    still_open = {row.name: row for row in after.nets if row.open}
    routed = [name for name in candidates if name not in still_open]
    open_names = [name for name in candidates if name in still_open]
    new_items = (*outcome.tracks, *outcome.arcs, *outcome.vias) if merged_ok else ()
    kept_items = (*resumed.tracks, *resumed.arcs, *resumed.vias)
    got = Counter(item.net_id for item in new_items)
    claimed = set(outcome.routed)
    for name in open_names:
        row = still_open[name]
        shortest = min(row.open, key=lambda found: found.length)
        said = "; the router listed the net as routed" if name in claimed else ""
        issues.append(
            Issue(
                "route.unrouted",
                "warning",
                f"net {name} has {len(row.open)} open connection(s); the shortest is "
                f"{format_length(shortest.length)} between {shortest.a.where} and {shortest.b.where}{said}",
                name,
            )
        )
        kept = got.get(net_ids[name], 0)
        if kept:
            issues.append(
                Issue(
                    "route.partial",
                    "info",
                    f"net {name} stays open; {kept} item(s) that the router returned for it are kept",
                    name,
                    hint=f"run route again to complete it, or with --rip --nets {name} to start it again",
                )
            )
    if args.require_complete and open_names:
        first = ", ".join(open_names[:5])
        more = f" and {len(open_names) - 5} more" if len(open_names) > 5 else ""
        issues.append(
            Issue(
                "route.incomplete",
                "error",
                f"{len(open_names)} selected net(s) stay open: {first}{more}; nothing is written",
                open_names[0],
                hint="run without --require-complete to keep the partial copper, then route again",
            )
        )
    added = bool(new_items) or bool(kept_items) or fanout_made
    fills_stale = zones_stale and added
    if fills_stale:
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
    evidence = dataclasses.replace(
        outcome.evidence,
        level=Level.UNVERIFIED,
        oracle=f"{outcome.tool} {outcome.tool_version}".strip(),
    )
    selected = set(candidates)
    if getattr(args, "dry_run", False) and not budget_ended and not failed:
        # every selected net was attempted, and a staged plan holds the board. A run that the budget cut
        # keeps its record: the same dry run made again goes on with the nets that were not attempted.
        # So does a run with an error, which plans no write: its finished runs are not routed again
        record.remove()
    return Result(
        result={
            "board": board_path.name,
            "router": router.name,
            "tool_version": outcome.tool_version or None,
            "selected": list(candidates),
            "routed": routed,
            "unrouted": open_names,
            "open": [
                {
                    "net": name,
                    "islands": still_open[name].islands,
                    "connections": to_json(still_open[name].open),
                }
                for name in open_names
            ],
            "connections": {
                "before": sum(len(row.open) for row in before.nets if row.name in selected),
                "after": sum(len(row.open) for row in still_open.values()),
            },
            "tracks": len(outcome.tracks) + len(resumed.tracks),
            "vias": len(outcome.vias) + len(resumed.vias),
            "ripped": ripped,
            "rip_kept": rip_kept,
            "log": _safe_log(outcome.log, ctx.cwd),
            "fills_stale": fills_stale,
            "budget": _budget_json(budget_seconds, spent, budget_ended),
            "runs": [
                {
                    "tier": run.tier,
                    "nets": len(run.nets),
                    "seconds": round(run.seconds, 1),
                    "outcome": run.outcome,
                }
                for run in outcome.runs
            ],
            "not_attempted": list(outcome.not_attempted),
            "resumed": {"runs": len(reused), "nets": len(resumed_nets)} if reused else None,
            "plane_layers": list(planes),
            "plane_fanout": plane_result,
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
        depends=depends,
        written=record.remove,  # the board then holds the copper, and its digest names another job
    )


def _copper_of(runs: tuple[FinishedRun, ...]) -> RoutingResult:
    """The copper of ``runs`` as one result, for the merge."""
    return RoutingResult(
        tracks=tuple(item for run in runs for item in run.tracks),
        arcs=tuple(item for run in runs for item in run.arcs),
        vias=tuple(item for run in runs for item in run.vias),
    )


def _rip(design: Design, nets: tuple[str, ...]) -> tuple[Design, int, dict[str, int]]:
    """``design`` without the copper of ``nets`` that a rip may remove, the number of items removed, and
    how many items of those nets were kept because they are locked or script copper (an item that is both
    counts as locked)."""
    board = design.board
    assert board is not None
    names = set(nets)
    ids = {net.id for net in design.circuit.nets if net.name in names}
    held = [item for item in (*board.tracks, *board.arcs, *board.vias) if item.net_id in ids]
    script = frozenset(item.id for item in held if is_copper_uuid(item.native_ids.get("kicad", "")))
    locked = sum(1 for item in held if item.locked)
    ripped_design, count = rip(design, nets, keep=script)
    kept = {"locked": locked, "script": sum(1 for item in held if item.id in script and not item.locked)}
    return ripped_design, count, kept


_EXAMPLE = (EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb")
COMMAND = Command(
    name="route",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="open",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)
