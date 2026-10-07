# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route the nets of a board that still have open connections through a registered Fenolite router
(capability cli-contract, "Route command"; ``docs/cli-contract.md``, "route").

The nets are selected by the open connections of the board (``analysis.connectivity``), so script copper
and earlier routes stay and a second run completes what the first left open. The verdict is taken from
the board after the merge, not from the router's lists; copper returned for a net that stays open is kept.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

from fenolite.analysis.connectivity import connectivity
from fenolite.backends.kicad import pro
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli._boardview import to_json
from fenolite.cli._examples import EXAMPLE_UNROUTED
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import format_length
from fenolite.model.design import Design
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import JobNet, JobPad, Router, RoutingJob
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
    if name == "freerouting" and (args.router_path or args.timeout != 600):
        from fenolite.routing.plugins.specctra.freerouting import DEFAULT_TIMEOUT, FreeroutingRouter

        timeout = args.timeout if args.timeout != 600 else DEFAULT_TIMEOUT
        return FreeroutingRouter(args.router_path, timeout=timeout)
    return selected


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


def _with_project_classes(design: Design, board_path: Path, issues: list[Issue]) -> Design:
    """``design`` with the net classes of the project file beside the board, so that a router gets each
    net's own track width, clearance and via size. A KiCad board holds no net class: without the project,
    every net would take the defaults. A project that is missing or unreadable leaves the design as read."""
    project = board_path.with_suffix(".kicad_pro")
    if not project.is_file():
        return design
    try:
        info = pro.read_project(project.read_text(encoding="utf-8"), file=project.name, issues=issues)
        return pro.apply_project(design, info, issues=issues)
    except (FormatError, UnicodeDecodeError) as error:
        issues.append(
            Issue(
                "route.project-unread",
                "warning",
                f"{project.name} could not be read, so every net takes the default class values: {error}",
                project.name,
            )
        )
        return design


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    if args.router_path and args.router not in ("kicadroutingtools", "freerouting"):
        raise CliError("FEN-2001", "--router-path is only supported by kicadroutingtools and freerouting")
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
        raise CliError(
            "FEN-6001", status.reason or f"router {router.name!r} is unavailable", hint=_missing_hint(router)
        )
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    read_issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=read_issues)
    source = source_info(design)
    design = _with_project_classes(design, board_path, read_issues)
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
    wanted = tuple(name for name in matching if args.include_zone_nets or net_ids[name] not in zone_ids)
    zone_skipped = tuple(name for name in matching if name not in wanted)
    ripped = 0
    rip_kept = {"locked": 0, "script": 0}
    if args.rip and board is not None:
        design, ripped, rip_kept = _rip(design, wanted)
    frame_pads = board_pads(design, issues=read_issues)
    # the open connections of the board as it is given to the router: after the rip, and after any copper
    # that a step of this command adds before the router
    before = connectivity(design, pads=frame_pads, nets=wanted)
    candidates = unrouted(
        design, before.open_nets(), patterns=patterns, include_zone_nets=args.include_zone_nets
    )
    pads_by_net: dict[str, list[JobPad]] = {}
    for pad in frame_pads:
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
    skipped = [
        Issue("route.zone-net-skipped", "info", f"zone net {name} was skipped", name) for name in zone_skipped
    ]
    if not jobs:
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
                "fills_stale": False,
            },
            issues=(*read_issues, *before.issues, *skipped),
            evidence=Evidence(Level.UNVERIFIED, router.name),
            input=input_ref,
        )
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    extra = {"board_pads": frame_pads, "outline": board_outline(design).rings}
    outcome = router.route(RoutingJob(design, tuple(jobs), layers, options, extra))
    issues = [*read_issues, *before.issues, *outcome.issues, *skipped]
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
    added = bool(new_items)
    zones_stale = bool(design.board and any(zone.filled or zone.fills for zone in design.board.zones))
    fills_stale = zones_stale and added
    if fills_stale:
        issues.append(
            Issue("route.fill-stale", "info", "routing changed copper; run fenolite fill before check")
        )
    target = source_info(design)
    major = target.major if target is not None and target.major is not None else ctx.kicad_target
    board_text = write_board(merged, target=major, allow_lossy=ctx.allow_lossy).text
    output = args.out or _relative(board_path, ctx.cwd)
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
            "tracks": len(outcome.tracks),
            "vias": len(outcome.vias),
            "ripped": ripped,
            "rip_kept": rip_kept,
            "log": _safe_log(outcome.log, ctx.cwd),
            "fills_stale": fills_stale,
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
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
