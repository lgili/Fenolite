# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route selected board nets through a registered Fenolite router."""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import os
import re
from pathlib import Path

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli._examples import EXAMPLE_UNROUTED
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import JobNet, JobPad, Router, RoutingJob
from fenolite.routing.registry import routers
from fenolite.routing.select import rip, unrouted

HELP = "route selected KiCad board nets with a registered Fenolite routing plugin"
DEFAULTS = (200_000, 200_000, 600_000, 300_000)


def _safe_log(lines: tuple[str, ...], cwd: Path) -> list[str]:
    """Keep diagnostic lines useful without exposing temporary or home paths."""
    home = str(Path.home())
    temp = os.getenv("TMPDIR", "/tmp")
    result: list[str] = []
    for line in lines[:20]:
        safe = line.replace(home, "<home>").replace(temp, "<tmp>")
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
        "--rip", action="store_true", help="remove unlocked copper of selected nets before routing"
    )
    parser.add_argument(
        "--include-zone-nets", action="store_true", help="route nets that also have copper zones"
    )
    parser.add_argument("--router-path", metavar="DIR", help="KiCadRoutingTools checkout")
    parser.add_argument("--router-python", metavar="PATH", help="Python interpreter for the external router")
    parser.add_argument(
        "--router-option", action="append", default=[], metavar="KEY=VALUE", help="router-specific option"
    )
    parser.add_argument("--timeout", type=float, default=600, metavar="SECONDS")
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
    if name == "kicadroutingtools" and (args.router_path or args.router_python or args.timeout != 600):
        from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter

        return KicadRoutingToolsRouter(args.router_path, args.router_python, args.timeout)
    return selected


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    if args.router_path and args.router != "kicadroutingtools":
        raise CliError("FEN-2001", "--router-path is only supported by kicadroutingtools")
    if args.router_python and args.router != "kicadroutingtools":
        raise CliError("FEN-2001", "--router-python is only supported by kicadroutingtools")
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
    status = router.available()
    if not status.available:
        raise CliError("FEN-6001", status.reason or f"router {router.name!r} is unavailable")
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    read_issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=read_issues)
    source = source_info(design)
    input_ref = InputRef(
        board_path.name,
        hashlib.sha256(data).hexdigest(),
        "kicad_pcb",
        str(source.version) if source is not None else None,
    )
    patterns = tuple(args.nets or ("*",))
    candidates = unrouted(design, patterns=patterns, include_zone_nets=args.include_zone_nets)
    zone_skipped: tuple[str, ...] = ()
    if not args.include_zone_nets and design.board is not None:
        zone_net_ids = {zone.net_id for zone in design.board.zones}
        copper_net_ids = {
            item.net_id
            for item in (*design.board.tracks, *design.board.arcs, *design.board.vias)
            if item.net_id is not None
        }
        zone_skipped = tuple(
            sorted(
                net.name
                for net in design.circuit.nets
                if net.id in zone_net_ids
                and (args.rip or net.id not in copper_net_ids)
                and len(design.by_net.get(net.name, ())) >= 2
                and _matches(net.name, patterns)
            )
        )
    ripped = 0
    if args.rip and design.board is not None:
        zone_ids = {zone.net_id for zone in design.board.zones}
        candidates = tuple(
            sorted(
                net.name
                for net in design.circuit.nets
                if len(design.by_net.get(net.name, ())) >= 2
                and (args.include_zone_nets or net.id not in zone_ids)
                and _matches(net.name, patterns)
            )
        )
        design, ripped = rip(design, candidates)
        candidates = unrouted(design, patterns=patterns, include_zone_nets=args.include_zone_nets)
    pads_by_net: dict[str, list[JobPad]] = {}
    net_ids = {net.name: net.id for net in design.circuit.nets}
    for pad in board_pads(design, issues=read_issues):
        if pad.net and pad.net_id and pad.net in candidates:
            pads_by_net.setdefault(pad.net, []).append(
                JobPad(pad.ref, pad.number, pad.net, pad.position, pad.layers, pad.drill)
            )
    classes = {item.id: item for item in design.circuit.netclasses}
    default_class = next(
        (item for item in design.circuit.netclasses if item.name.casefold() == "default"), None
    )
    jobs: list[JobNet] = []
    for name in candidates:
        net = next(item for item in design.circuit.nets if item.name == name)
        netclass = classes.get(net.netclass_id or "")
        values = tuple(
            getattr(netclass, key, None) or getattr(default_class, key, None) or fallback
            for key, fallback in zip(
                ("track_width", "clearance", "via_diameter", "via_drill"), DEFAULTS, strict=True
            )
        )
        jobs.append(
            JobNet(
                name,
                net_ids[name],
                tuple(pads_by_net.get(name, ())),
                values[0],
                values[1],
                values[2],
                values[3],
            )
        )
    if not jobs:
        empty_issues = [*read_issues]
        empty_issues.extend(
            Issue("route.zone-net-skipped", "info", f"zone net {name} was skipped", name)
            for name in zone_skipped
        )
        return Result(
            result={
                "board": board_path.name,
                "router": router.name,
                "tool_version": None,
                "selected": [],
                "routed": [],
                "unrouted": [],
                "tracks": 0,
                "vias": 0,
                "ripped": ripped,
                "log": [],
                "fills_stale": False,
            },
            issues=tuple(empty_issues),
            evidence=Evidence(Level.UNVERIFIED, router.name),
            input=input_ref,
        )
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    outcome = router.route(RoutingJob(design, tuple(jobs), layers, options))
    issues = [*read_issues, *outcome.issues]
    issues.extend(
        Issue("route.zone-net-skipped", "info", f"zone net {name} was skipped", name) for name in zone_skipped
    )
    issues.extend(
        Issue("route.unrouted", "warning", f"net {name} was not routed", name) for name in outcome.unrouted
    )
    merged_ok = True
    try:
        merged = apply(design, outcome)
    except RoutingError as exc:
        issues.extend(exc.issues)
        merged = design
        merged_ok = False
    zones_stale = bool(design.board and any(zone.filled or zone.fills for zone in design.board.zones))
    if zones_stale and outcome.routed:
        issues.append(
            Issue("route.fill-stale", "info", "routing changed copper; run fenolite fill before check")
        )
    target = source_info(design)
    major = target.major if target is not None and target.major is not None else ctx.kicad_target
    board_text = write_board(merged, target=major, allow_lossy=ctx.allow_lossy).text
    output = args.out or os.path.relpath(board_path, ctx.cwd)
    writes = (
        (PlannedWrite(output, board_text.encode("utf-8"), "kicad_pcb"),)
        if merged_ok and outcome.routed and (args.out is not None or board_text != text)
        else ()
    )
    evidence = dataclasses.replace(
        outcome.evidence,
        level=Level.UNVERIFIED,
        oracle=f"{outcome.tool} {outcome.tool_version}".strip(),
    )
    return Result(
        result={
            "board": board_path.name,
            "router": router.name,
            "tool_version": outcome.tool_version or None,
            "selected": list(candidates),
            "routed": list(outcome.routed),
            "unrouted": list(outcome.unrouted),
            "tracks": len(outcome.tracks),
            "vias": len(outcome.vias),
            "ripped": ripped,
            "log": _safe_log(outcome.log, ctx.cwd),
            "fills_stale": zones_stale and bool(outcome.routed),
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
    )


_EXAMPLE = (EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb")
COMMAND = Command(
    name="route",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)
