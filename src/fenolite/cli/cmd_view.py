# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite view PATH``: show the boards of a project without the tool that made them (capability
cli-contract, "View command"; user guide ``docs/viewer.md``).

``PATH`` is an Altium or KiCad project file, a folder or a board. Without ``--serve`` and ``--export`` the
reply holds the project tree and a summary of one board's scene, and nothing is written. ``--export FILE``
plans one standalone HTML page with every viewable board embedded; ``--serve`` serves the page on the
loopback address until it is interrupted, reloading a board when its file is saved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, cast

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.view import export, server
from fenolite.view.project import ProjectTree, load_tree
from fenolite.view.scene import build_scene, summary

HELP = "show the boards of a project in a web page, without their tool (writes FILE with --export)"
KIND = "view"
DEFAULT_PORT = 8765


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/viewer.md."
    parser.add_argument(
        "path", metavar="PATH", help="an Altium .PrjPcb or KiCad .kicad_pro, a project folder, or a board"
    )
    parser.add_argument(
        "--doc", metavar="ID", help="the document to show: its id, path or name (default: the first board)"
    )
    parser.add_argument(
        "--overlay",
        metavar="FILE",
        action="append",
        default=[],
        help="draw the distances of a fenolite analyze reply (JSON) on the board (repeatable)",
    )
    parser.add_argument("--serve", action="store_true", help="serve the page on 127.0.0.1 until interrupted")
    parser.add_argument(
        "--port",
        metavar="N",
        default=str(DEFAULT_PORT),
        help=f"with --serve: the port (default {DEFAULT_PORT}; 0 = any free port)",
    )
    parser.add_argument("--no-browser", action="store_true", help="with --serve: do not open a browser")
    parser.add_argument("--export", metavar="FILE", help="also write one standalone HTML page")


def scene_of(path: Path) -> dict[str, Any]:
    """The scene of the board at ``path``, read by the backend that reads it."""
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {path.name}", where=path.name)
    data = path.read_bytes()
    read = backend.read(path)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{path.name} is not a board", where=path.name)
    frame = backend if isinstance(backend, BoardFrame) else None
    return build_scene(
        design, frame, name=path.name, data=data, backend=backend.name, evidence=read.evidence.level.value
    )


def overlays_of(files: list[str], ctx: Context) -> list[dict[str, Any]]:
    """The overlay items of ``fenolite analyze`` replies: per distance row, its clearance path (red) and its
    creepage path (blue), in micrometres, marked as a finding when an error or a warning names its nets."""
    out: list[dict[str, Any]] = []
    for name in files:
        path = Path(name) if Path(name).is_absolute() else ctx.cwd / name
        try:
            envelope: Any = json.loads(path.read_text(encoding="utf-8"))
            rows: list[Any] = list(envelope["result"]["distances"])
            issues: list[Any] = list(envelope.get("issues", []))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CliError(
                "FEN-3004",
                f"{name} is not a fenolite analyze reply: {type(exc).__name__}",
                where=name,
                hint="pass the JSON reply of `fenolite analyze ... --json`",
            ) from exc
        flagged = {str(i.get("where", "")) for i in issues if i.get("severity") in ("error", "warning")}
        for row in rows:
            out += _row_overlays(row, flagged)
    return out


def _row_overlays(row: Any, flagged: set[str]) -> list[dict[str, Any]]:
    """The clearance and creepage paths of one distance row of an ``analyze`` reply, in micrometres."""
    pair = f"{row.get('net_a')}, {row.get('net_b')}"
    finding = pair in flagged
    out: list[dict[str, Any]] = []
    for kind, color in (("clearance", "#ff3030"), ("creepage", "#30a0ff")):
        measure: Any = row.get(kind)
        if not isinstance(measure, dict):
            continue
        points: list[Any] = list(cast("dict[str, Any]", measure).get("points") or [])
        if not points:
            continue
        pts: list[list[int]] = [[round(int(q["x"]) / 1000), round(int(q["y"]) / 1000)] for q in points]
        if len(pts) == 1:
            pts.append(pts[0])
        low: Any = cast("dict[str, Any]", measure).get("low")
        name = f"{row.get('net_a')} × {row.get('net_b')}"
        text = f"{name}: {kind} {int(low) / 1e6:.3f} mm" if low is not None else name
        out.append(
            {
                "kind": kind,
                "pts": pts,
                "color": color,
                "finding": finding,
                "label": text + (" (finding)" if finding else ""),
                "layer": cast("dict[str, Any]", measure).get("layer"),
            }
        )
    return out


def _log(message: str) -> None:
    sys.stderr.write(message + "\n")


def _tree(argument: str, ctx: Context) -> ProjectTree:
    given = Path(argument)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.exists():
        raise CliError("FEN-3001", f"{argument} does not exist", where=given.name)
    try:
        return load_tree(path)
    except ValueError as exc:
        raise CliError(
            "FEN-2001",
            str(exc),
            where=given.name,
            hint="pass an Altium .PrjPcb, a KiCad .kicad_pro, a folder or a board",
        ) from exc


def _progress(ctx: Context, url: str) -> None:
    if ctx.mode == "json":
        record = {
            "command": KIND,
            "event": "step",
            "step": "serve",
            "index": None,
            "total": None,
            "detail": url,
            "elapsed_ms": 0,
        }
        line = json.dumps({"progress": record})
    else:
        line = f"progress: {KIND}: step serve: {url}"
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.serve and args.export:
        raise CliError(
            "FEN-2001",
            "--serve and --export cannot be combined",
            where="--export",
            hint="export the page, or serve it, in two runs",
        )
    try:
        port = int(args.port)
    except ValueError:
        port = -1
    if not 0 <= port <= 65535:
        raise CliError("FEN-2001", f"--port: expected a port number, got {args.port!r}", where="--port")
    tree = _tree(args.path, ctx)
    overlays = overlays_of(args.overlay, ctx)
    doc = tree.document(args.doc) if args.doc else tree.first_viewable()
    if args.doc and doc is None:
        raise CliError("FEN-2001", f"--doc: the project holds no document {args.doc!r}", where="--doc")
    result: dict[str, Any] = {
        "project": tree.to_json(),
        "document": doc.id if doc else None,
        "summary": None,
        "notes": [],
    }
    evidence = Evidence(Level.INFERRED)
    ref: InputRef | None = None
    scenes: dict[str, dict[str, Any]] = {}
    if doc is not None and doc.viewable and doc.file is not None and doc.present:
        scene = scene_of(doc.file)
        scene["overlays"] = overlays
        scenes[doc.id] = scene
        result["summary"] = summary(scene)
        result["notes"] = list(scene["meta"]["notes"])
        evidence = (
            Evidence(Level(scene["meta"]["evidence"]))
            if scene["meta"]["evidence"] in Level._value2member_map_
            else evidence
        )
        ref = InputRef(path=doc.file.name, sha256=scene["meta"]["sha256"], kind=doc.kind, format_version=None)
    elif doc is not None:
        result["notes"] = [f"{doc.name} ({doc.kind}) has no viewer in this version"]

    writes: tuple[PlannedWrite, ...] = ()
    if args.export:
        for other in tree.documents:
            if other.viewable and other.present and other.file is not None and other.id not in scenes:
                scenes[other.id] = scene_of(other.file) | {"overlays": []}
        html = export.page(tree.to_json(), scenes, open_id=doc.id if doc else None).encode("utf-8")
        writes = (PlannedWrite(path=str(args.export), data=html, kind=KIND),)
        result["export"] = {
            "documents": sorted(scenes),
            "bytes": len(html),
            "sha256": hashlib.sha256(html).hexdigest(),
        }

    if args.serve:

        def build(path: Path) -> dict[str, Any]:
            return scene_of(path)

        live = server.Live(
            tree,
            build,
            overlays=overlays,
            open_id=doc.id if doc else None,
            log=_log,
        )
        httpd = server.serve(live, port)
        url = f"http://{server.HOST}:{httpd.server_address[1]}/"
        _progress(ctx, url)
        if not args.no_browser:
            webbrowser.open(url)
        started = time.monotonic()
        server.run(live, httpd, until=SERVE_STOP)
        result["serve"] = {"url": url, "seconds": round(time.monotonic() - started, 1)}
    return Result(result=result, evidence=evidence, input=ref, writes=writes)


SERVE_STOP: threading.Event | None = None
"""When set by a caller (the tests), the event that ends ``--serve``; the command otherwise serves until it is
interrupted."""

COMMAND = Command(
    name="view",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--export", "view.html"),
)

__all__ = ["COMMAND", "overlays_of", "scene_of"]
