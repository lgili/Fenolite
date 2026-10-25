# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite view PATH``: show the boards and sheets of a project without the tool that made them
(capability cli-contract, "View command"; user guide ``docs/viewer.md``).

``PATH`` is an Altium or KiCad project file, a folder, a board or a sheet (changes c0177 and c0178). Without
``--serve`` and ``--export`` the reply holds the project tree and a summary of one document's scene, and
nothing is written. ``--export FILE`` plans one standalone HTML page with every viewable document embedded;
``--serve`` serves the page on the loopback address until it is interrupted, reloading a document when its
file is saved. Each document takes the colours of its tool (change c0178): ``--theme`` names a KiCad colour
theme for the KiCad documents.
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
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.base import BoardFrame
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.view import export, server, themes
from fenolite.view.kicad_schematic import build_kicad_schematic_scene
from fenolite.view.library import library_scene
from fenolite.view.library import summary as library_summary
from fenolite.view.project import VIEWABLE_LIBRARIES, ProjectTree, load_tree
from fenolite.view.scene import build_scene, summary
from fenolite.view.schematic import build_schematic_scene
from fenolite.view.schematic import summary as schematic_summary
from fenolite.view.themes import Palette

HELP = "show the boards and sheets of a project in a web page, without their tool (writes FILE with --export)"
KIND = "view"
DEFAULT_PORT = 8765


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/viewer.md."
    parser.add_argument(
        "path",
        metavar="PATH",
        help="a .PrjPcb or .kicad_pro, a project folder, a board, a sheet or a library",
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
    parser.add_argument(
        "--theme",
        metavar="THEME",
        help="a KiCad colour theme: a .json file, or a name in KiCad's colors folder",
    )


def scene_of(path: Path, kicad: Palette | None = None) -> dict[str, Any]:
    """The scene of the board or the sheet at ``path``, read by the backend that reads it, in the colours of
    its tool; ``kicad`` replaces the ``kicad`` palette (a user's theme)."""
    suffix = path.suffix.lower()
    if suffix in VIEWABLE_LIBRARIES:
        return library_scene(path, kicad=kicad)
    if suffix == ".schdoc":
        return _sheet_scene(path)
    if suffix == ".kicad_sch":
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CliError("FEN-3004", f"{path.name} is not UTF-8 text", where=path.name) from exc
        return build_kicad_schematic_scene(
            text, name=path.name, data=data, palette=kicad or themes.palette("kicad")
        )
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {path.name}", where=path.name)
    data = path.read_bytes()
    read = backend.read(path)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{path.name} is not a board", where=path.name)
    frame = backend if isinstance(backend, BoardFrame) else None
    scene = build_scene(
        design, frame, name=path.name, data=data, backend=backend.name, evidence=read.evidence.level.value
    )
    name = themes.theme_for(backend.name)
    chosen = kicad if name == "kicad" and kicad is not None else themes.palette(name)
    return themes.apply_board_theme(scene, chosen)


def theme_of(argument: str | None, ctx: Context) -> Palette | None:
    """The user's KiCad theme named by ``--theme``, or ``None``."""
    if not argument:
        return None
    found = themes.find_kicad_theme(argument, ctx.cwd)
    if found is None:
        raise CliError(
            "FEN-3001",
            f"--theme: no theme file or KiCad theme named {argument!r}",
            where="--theme",
            hint="pass a .json theme file, or a theme name of the colors folder of your KiCad settings",
        )
    try:
        return themes.read_kicad_theme(found)
    except FormatError as exc:
        raise CliError("FEN-3004", f"--theme: {exc}", where="--theme") from exc


def _sheet_scene(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    document = read_schematic(data, file=path.name)  # a FormatError is FEN-3004
    return build_schematic_scene(document, name=path.name, data=data, evidence=Level.INFERRED.value)


def _theme_name(scene: dict[str, Any]) -> str:
    """The palette a scene is drawn in: a board's theme, a KiCad sheet's palette, or ``altium``."""
    if scene.get("kind") == "library":
        drawn = [item["scene"] for item in scene["items"] if item.get("scene")]
        return _theme_name(drawn[0]) if drawn else ""
    board: Any = scene.get("theme")
    if isinstance(board, dict):
        return str(cast("dict[str, Any]", board).get("name", ""))
    return str(scene["meta"].get("theme") or "altium")


def _summary(scene: dict[str, Any]) -> dict[str, Any]:
    if scene.get("kind") == "library":
        return library_summary(scene)
    return schematic_summary(scene) if scene.get("kind") == "schematic" else summary(scene)


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
    kicad = theme_of(args.theme, ctx)
    doc = tree.document(args.doc) if args.doc else tree.first_viewable()
    if args.doc and doc is None:
        raise CliError("FEN-2001", f"--doc: the project holds no document {args.doc!r}", where="--doc")
    result: dict[str, Any] = {
        "project": tree.to_json(),
        "document": doc.id if doc else None,
        "summary": None,
        "notes": [],
        "theme": None,
    }
    evidence = Evidence(Level.INFERRED)
    ref: InputRef | None = None
    scenes: dict[str, dict[str, Any]] = {}
    if doc is not None and doc.viewable and doc.file is not None and doc.present:
        scene = scene_of(doc.file, kicad)
        scene["overlays"] = overlays
        scenes[doc.id] = scene
        result["summary"] = _summary(scene)
        result["notes"] = list(scene["meta"]["notes"])
        result["theme"] = _theme_name(scene)
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
                scenes[other.id] = scene_of(other.file, kicad) | {"overlays": []}
        html = export.page(tree.to_json(), scenes, open_id=doc.id if doc else None).encode("utf-8")
        writes = (PlannedWrite(path=str(args.export), data=html, kind=KIND),)
        result["export"] = {
            "documents": sorted(scenes),
            "bytes": len(html),
            "sha256": hashlib.sha256(html).hexdigest(),
        }

    if args.serve:

        def build(path: Path) -> dict[str, Any]:
            return scene_of(path, kicad)

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
