# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite path``: search one connection, or measure the free channel of a net, on an existing
``.kicad_pcb`` or ``.PcbDoc`` with the board's own rules (capability cli-contract, "Path command"; change
c0501, design D7).

With ``--width`` the command searches one connection (``fenolite.api.find_route``) and plans the found
copper through the mutation protocol: a ``.kicad_pcb`` is written by the KiCad writer, a ``.PcbDoc`` as an
edit session commit, which needs ``--gate clone``. With ``--widest`` it measures the channel
(``fenolite.api.free_channel``) and never writes. Lengths are integer nanometres.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any

from fenolite.api.route import (
    MAX_STATES,
    POURS,
    Channel,
    EndpointError,
    RouteFound,
    RouteSearch,
    find_route,
    free_channel,
)
from fenolite.api.sides import SideError
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import parse_length
from fenolite.routing.channel import RESOLUTION
from fenolite.routing.octilinear import Blocker
from fenolite.routing.search import Gap, WallItem

HELP = "search one connection or the widest free channel of a net on an existing board"
GATE_HINT = "add --gate clone: the clone operation of an Altium edit session is not confirmed by the kit"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb or a .PcbDoc")
    parser.add_argument("--net", required=True, metavar="NET", help="the net to route")
    parser.add_argument("--from", dest="start", required=True, metavar="A", help="REF-PIN or X,Y@LAYER (mm)")
    parser.add_argument("--to", dest="end", required=True, metavar="B", help="REF-PIN or X,Y@LAYER (mm)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--width", metavar="W", help="search one connection of this track width (mm)")
    mode.add_argument(
        "--widest", action="store_true", help="measure the widest track that fits; never writes"
    )
    parser.add_argument("--layers", metavar="L1,L2", help="the copper layers a track may use")
    parser.add_argument("--grid", default="0.1mm", metavar="G", help="the search grid (default 0.1mm)")
    parser.add_argument("--max-states", type=int, default=MAX_STATES, metavar="N", help="search state bound")
    parser.add_argument("--max-vias", type=int, default=None, metavar="N", help="default 2, 0 with --widest")
    parser.add_argument("--resolution", default=None, metavar="R", help="channel bracket (default 10um)")
    parser.add_argument(
        "--pours", choices=POURS, default=None, help="kept (.PcbDoc) or refilled (.kicad_pcb)"
    )
    parser.add_argument("--timeout", type=float, default=None, metavar="S", help="seconds for the command")
    parser.add_argument("--gate", choices=("clone",), default=None, help="open the clone gate of a .PcbDoc")
    parser.add_argument("-o", "--out", metavar="FILE", help="write to this file instead of replacing PATH")


def _length(text: str, option: str) -> int:
    try:
        value = parse_length(text, default_unit="mm")
    except ValueError as error:
        raise CliError("FEN-2001", f"{option}: {error}", where=option) from None
    if value <= 0:
        raise CliError("FEN-2001", f"{option} must be positive, got {text!r}", where=option)
    return value


def _blocker(item: Blocker) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "net": item.net,
        "layer": item.layer,
        "label": item.label,
        "at": [item.where.x, item.where.y],
        "clearance": item.clearance,
    }


def _wall(items: tuple[WallItem, ...]) -> list[dict[str, Any]]:
    return [{**_blocker(item.blocker), "refused": item.refused} for item in items]


def _gap(gap: Gap | None) -> dict[str, Any] | None:
    return None if gap is None else {"a": _blocker(gap.a), "b": _blocker(gap.b), "free": gap.free}


def _path(found: RouteFound) -> dict[str, Any]:
    return {
        "width": found.width,
        "runs": [{"layer": layer, "points": [[p.x, p.y] for p in points]} for layer, points in found.runs],
        "vias": [[p.x, p.y] for p in found.vias],
        "length": found.length,
    }


def _search(reply: RouteSearch) -> dict[str, Any]:
    if reply.found is not None:
        return {"path": _path(reply.found), "refusal": None}
    refusal = reply.refusal
    assert refusal is not None
    return {
        "path": None,
        "refusal": {
            "reason": refusal.reason,
            "proven": refusal.proven,
            "wall": _wall(refusal.wall),
            "widest_gap": _gap(refusal.widest),
        },
    }


def _channel(reply: Channel) -> dict[str, Any]:
    return {
        "channel": {
            "low": reply.low,
            "high": reply.high,
            "grid_limited": reply.grid_limited,
            "undecided": reply.undecided,
            "pinch": _gap(reply.pinch),
            "path": None if reply.path is None else _path(reply.path),
        }
    }


def _altium_write(path: Path, found: RouteFound) -> tuple[bytes | None, list[Issue], Evidence]:
    """The bytes an edit session commit of the found copper would write (design D6): the clones queued on
    a session whose ``clone`` gate is open, run and checked as ``Session.commit`` checks them."""
    from fenolite.backends.altium import edit
    from fenolite.backends.altium.edit.session import EVIDENCE, verify

    session = edit.open(path, gates={"clone": True})
    assert isinstance(session, edit.Session)
    issues = list(found.queue_on(session))
    if issues:
        return None, issues, EVIDENCE
    state, refused = session.apply()
    if state is None:
        return None, refused, EVIDENCE
    data, found_issues = verify(session.data, state, declared_nets=session.declared_nets, file=path.name)
    unconfirmed = Issue(
        "route.altium-edit-unconfirmed",
        "warning",
        "the copper is written by clone operations of an Altium edit session, whose gate the kit has not "
        "confirmed (H-A-EDIT-CLONE)",
        path.name,
        hint="open the written document in Altium and run its DRC",
    )
    return data, [*found_issues, unconfirmed], EVIDENCE


def _kicad_write(path: Path, found: RouteFound, ctx: Context) -> bytes:
    """The board with the found copper merged (``routing.merge.apply``), as ``fenolite route`` writes it."""
    from fenolite.backends.kicad.pcb import read_board, source_info, write_board
    from fenolite.routing.merge import apply

    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    merged = apply(design, found.result(design))
    target = source_info(design)
    major = target.major if target is not None and target.major is not None else ctx.kicad_target
    return write_board(merged, target=major, allow_lossy=ctx.allow_lossy).text.encode("utf-8")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    path = (ctx.cwd / args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)
    if not path.is_file():
        raise CliError("FEN-3001", f"no board at {args.path}", where=args.path)
    altium = path.suffix.lower() == ".pcbdoc"
    if not altium and path.suffix != ".kicad_pcb":
        raise CliError("FEN-2001", f"{path.name} is not a .kicad_pcb or a .PcbDoc", where=args.path)
    if args.width is not None and altium and args.gate != "clone":
        raise CliError(
            "FEN-2001", "a .PcbDoc is written by an edit session's clones", where="--gate", hint=GATE_HINT
        )
    if args.out and (Path(args.out).is_absolute() or args.widest):
        raise CliError(
            "FEN-2001", "--out is a path relative to the working directory, with --width", where="--out"
        )
    if args.timeout is not None and args.timeout <= 0:
        raise CliError("FEN-2001", "--timeout must be a positive number of seconds", where="--timeout")
    if args.resolution is not None and not args.widest:
        raise CliError(
            "FEN-2001", "--resolution measures a channel: use it with --widest", where="--resolution"
        )
    grid = _length(args.grid, "--grid")
    layers = tuple(args.layers.split(",")) if args.layers else None
    data = path.read_bytes()
    given = InputRef(path.name, hashlib.sha256(data).hexdigest(), "pcbdoc" if altium else "kicad_pcb", None)
    depends = depends_on(ctx.cwd, path)
    common: dict[str, Any] = {
        "net": args.net,
        "start": args.start,
        "end": args.end,
        "layers": layers,
        "grid": grid,
        "max_states": args.max_states,
        "pours": args.pours,
        "timeout": args.timeout,
    }
    try:
        if args.widest:
            resolution = RESOLUTION if args.resolution is None else _length(args.resolution, "--resolution")
            vias = 0 if args.max_vias is None else args.max_vias
            channel = free_channel(path, max_vias=vias, resolution=resolution, **common)
            fails = ("route.no-path", "route.path-limit") if channel.low is None else ()
            result = {"board": path.name, "net": args.net, **_channel(channel)}
            return Result(
                result, channel.issues, channel.evidence, given, depends=depends, fail_on_codes=fails
            )
        vias = 2 if args.max_vias is None else args.max_vias
        reply = find_route(path, width=_length(str(args.width), "--width"), max_vias=vias, **common)
    except EndpointError as error:
        raise CliError("FEN-2001", str(error), where=error.where or args.path, hint=error.hint) from None
    except (SideError, FormatError) as error:
        raise CliError("FEN-3001", str(error), where=path.name) from None
    except ValueError as error:
        raise CliError("FEN-2001", str(error), where=args.path) from None
    result = {"board": path.name, "net": args.net, **_search(reply)}
    issues = list(reply.issues)
    if reply.found is None:
        fails = ("route.no-path", "route.path-limit")
        return Result(result, tuple(issues), reply.evidence, given, depends=depends, fail_on_codes=fails)
    evidence = reply.evidence
    if args.out:
        output = args.out
    else:
        output = os.path.relpath(path, ctx.cwd) if path.is_relative_to(ctx.cwd) else str(path)
    if altium:
        written, found_issues, session_evidence = _altium_write(path, reply.found)
        issues.extend(found_issues)
        evidence = Evidence.combine(evidence, session_evidence)
        writes = () if written is None else (PlannedWrite(output, written, "pcbdoc"),)
    else:
        writes = (PlannedWrite(output, _kicad_write(path, reply.found, ctx), "kicad_pcb"),)
    # the board written in place is the target, not an input
    return Result(result, tuple(issues), evidence, given, writes, depends=depends if args.out else ())


COMMAND = Command(
    name="path",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(
        EXAMPLE_BOARD,
        "--net",
        "GND",
        "--from",
        "D1-1",
        "--to",
        "30,15@F.Cu",
        "--widest",
        "--grid",
        "0.5mm",
        "--resolution",
        "0.5mm",
        "--max-states",
        "3000",
    ),
    mutation_example_args=(
        EXAMPLE_BOARD,
        "--net",
        "GND",
        "--from",
        "D1-1",
        "--to",
        "30,15@F.Cu",
        "--width",
        "0.5mm",
        "--grid",
        "0.5mm",
        "--max-states",
        "3000",
        "--out",
        "fenolite-path.kicad_pcb",
    ),
)
