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
import dataclasses
import hashlib
import json
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fenolite.backends import registry
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.variants import read_variants
from fenolite.backends.base import BoardFrame, PlacedExtent
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.placement import legality
from fenolite.view import export, review, server, themes
from fenolite.view.altium_layers import native_view
from fenolite.view.bom import bom_scene
from fenolite.view.bom import with_parts as bom_with_parts
from fenolite.view.cache import WHERE, SceneCache
from fenolite.view.check_overlay import overlay as check_overlay
from fenolite.view.check_overlay import read_reply
from fenolite.view.check_overlay import summary as check_summary
from fenolite.view.compare import compare
from fenolite.view.compare import summary as compare_summary
from fenolite.view.drawing import PANEL_NOTE, drawing_scene, holds_panel
from fenolite.view.drawing import summary as drawing_summary
from fenolite.view.kicad_schematic import build_kicad_schematic_scene
from fenolite.view.library import library_scene
from fenolite.view.library import summary as library_summary
from fenolite.view.outjob import outjob_scene
from fenolite.view.project import VIEWABLE_LIBRARIES, ProjectTree, load_tree
from fenolite.view.project_nets import annotate as annotate_nets
from fenolite.view.project_nets import project_index, sheet_params
from fenolite.view.scene import build_scene, summary
from fenolite.view.schematic import build_schematic_scene
from fenolite.view.schematic import summary as schematic_summary
from fenolite.view.themes import Palette
from fenolite.view.variants import counts as variant_counts
from fenolite.view.variants import variant_states

HELP = "show a project's boards, sheets and drawings in a web page (writes FILE with --export)"
KIND = "view"
DEFAULT_PORT = 8765
APPROXIMATE_NOTE = (
    "{} overlap(s) of parts without a courtyard (their extent is taken from their pads) are not marked; "
    "fenolite place judges them"
)
LARGE_PAGE = 20_000_000
"""An exported page above this many bytes gets a warning in ``result.export``."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/viewer.md."
    parser.add_argument(
        "path",
        metavar="PATH",
        help="a project file or folder, a board, sheet, library or drawing",
    )
    parser.add_argument("--doc", metavar="ID", help="the document to show: id, path or name")
    parser.add_argument(
        "--overlay",
        metavar="FILE",
        action="append",
        default=[],
        help="draw a fenolite analyze reply on the board (repeatable)",
    )
    parser.add_argument("--serve", action="store_true", help="serve on 127.0.0.1 until stopped")
    parser.add_argument(
        "--port",
        metavar="N",
        default=str(DEFAULT_PORT),
        help=f"with --serve: port (default {DEFAULT_PORT}; 0 = any free)",
    )
    parser.add_argument("--no-browser", action="store_true", help="with --serve: no browser")
    parser.add_argument("--export", metavar="FILE", help="write one standalone page")
    parser.add_argument(
        "--cache",
        choices=WHERE,
        default="user",
        help="scene cache",
    )
    parser.add_argument("--docs", metavar="ID,...", help="--export only these")
    parser.add_argument("--variant", metavar="NAME", help="show an Altium project's variant")
    parser.add_argument("--compare", metavar="OLD", help="draw what changed since the board or sheet OLD")
    parser.add_argument("--check", metavar="FILE|run", help="draw a check reply's findings; run: check first")
    parser.add_argument("--select", metavar="REF", help="open at this part or net")
    parser.add_argument(
        "--marks", metavar="FILE", help="review marks: list them; --serve saves new ones there"
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        help="a KiCad colour theme: a .json file or a theme name",
    )


def scene_of(path: Path, kicad: Palette | None = None) -> dict[str, Any]:
    """The scene of the board or the sheet at ``path``, read by the backend that reads it, in the colours of
    its tool; ``kicad`` replaces the ``kicad`` palette (a user's theme)."""
    suffix = path.suffix.lower()
    if suffix in VIEWABLE_LIBRARIES:
        return library_scene(path, kicad=kicad)
    if suffix == ".pcbdwf":
        return drawing_scene(path)  # a DraftsmanError is a FormatError: FEN-3004
    if suffix == ".outjob":
        return outjob_scene(path)  # change c0190
    if suffix == ".bomdoc":
        return bom_scene(path)
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
    native = native_view(design, data, file=path.name) if path.suffix.lower() == ".pcbdoc" else None
    extents, checks = _placement(design, frame)
    scene = build_scene(
        design,
        frame,
        name=path.name,
        data=data,
        backend=backend.name,
        evidence=read.evidence.level.value,
        native=native,
        checks=checks,
        extents=extents,
    )
    if holds_panel(path):
        scene["meta"]["notes"] = [PANEL_NOTE, *scene["meta"].get("notes", [])]
    name = themes.theme_for(backend.name)
    chosen = kicad if name == "kicad" and kicad is not None else themes.palette(name)
    return themes.apply_board_theme(scene, chosen)


def _placement(
    design: Design, frame: BoardFrame | None
) -> tuple[tuple[PlacedExtent, ...] | None, list[tuple[str, tuple[str, ...]]]]:
    """The courtyards of the board and its placement findings that name parts (change c0183): overlapping
    courtyards and parts in keep-outs that forbid footprints, judged by ``placement.legality`` as
    ``fenolite place`` judges them."""
    if frame is None or design.board is None:
        return None, []
    try:
        extents = frame.placed_extents(design)
    except (ValueError, TypeError, KeyError):
        return None, []
    refs = {c.id: c.ref for c in design.circuit.components}
    names = {fp.id: refs.get(fp.component_id) or f"({fp.lib_ref})" for fp in design.board.footprints}
    found = legality.check(extents, (), names=names, keepouts=design.board.keepouts)
    marks: list[tuple[str, tuple[str, ...]]] = []
    approximate = 0
    for issue in found:
        if issue.code == "place.courtyard-overlap" and issue.message.endswith(legality.APPROXIMATE):
            approximate += 1  # courtyards made from pad copper: an overlap there is often no conflict
        elif issue.code == "place.courtyard-overlap" or issue.code.startswith("place.keepout"):
            marks.append((issue.message, tuple(issue.where.split(","))))
    if approximate:
        marks.append((APPROXIMATE_NOTE.format(approximate), ()))
    return extents, marks


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
    if scene.get("kind") == "table":
        return ""
    board: Any = scene.get("theme")
    if isinstance(board, dict):
        return str(cast("dict[str, Any]", board).get("name", ""))
    return str(scene["meta"].get("theme") or "altium")


def _summary(scene: dict[str, Any]) -> dict[str, Any]:
    if scene.get("kind") == "table":  # change c0190: a BOM document or an output job
        return {
            "kind": "table",
            "table": scene["table"],
            "counts": dict(scene["meta"]["counts"]),
            "columns": list(scene["columns"]),
        }
    if scene.get("lib") == "drawing":
        return drawing_summary(scene)
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


def _compare(
    scene: dict[str, Any], argument: str, ctx: Context, cached: Callable[[Path], dict[str, Any]]
) -> dict[str, Any]:
    """The overlay of the document shown against the revision ``--compare`` names (change c0184)."""
    given = Path(argument)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.exists():
        raise CliError("FEN-3001", f"--compare: {argument} does not exist", where="--compare")
    try:
        return compare(scene, cached(path))
    except ValueError as exc:
        raise CliError(
            "FEN-2001",
            f"--compare: {exc}",
            where="--compare",
            hint="compare two boards, or two sheets, of one tool",
        ) from exc


class _ProjectNets:
    """The project nets of an Altium project's sheets (change c0185), compiled once, when a sheet asks."""

    def __init__(self, tree: ProjectTree, scene: Callable[[Path], dict[str, Any]]) -> None:
        self.tree = tree
        self.scene = scene
        self.found: tuple[Design, dict[str, dict[str, Any]]] | None = None
        self.failed = ""
        self._sheets: dict[str, dict[str, Any]] | None = None
        self._variants: dict[str, dict[str, dict[str, Any]]] | None = None

    def sheets(self) -> dict[str, dict[str, Any]]:
        """The scenes of the project's Altium sheets, by document name."""
        if self._sheets is None:
            self._sheets = {
                doc.name: self.scene(doc.file)
                for doc in self.tree.documents
                if doc.kind == "schematic"
                and doc.present
                and doc.file is not None
                and doc.file.suffix.lower() == ".schdoc"
            }
        return self._sheets

    def variants(self) -> dict[str, dict[str, dict[str, Any]]]:
        """The project's variants resolved on its sheets (change c0186); empty without any."""
        if self._variants is None:
            self._variants = {}
            if self.tree.source == "altium" and self.tree.project_file:
                project = self.tree.root / self.tree.project_file
                try:
                    found = read_variants(project.read_bytes(), file=project.name)
                except (OSError, FormatError):
                    found = ()
                if found:
                    self._variants = variant_states(found, self.sheets())
        return self._variants

    def _compile(self) -> tuple[Design, dict[str, dict[str, Any]]] | None:
        if self.found is None and not self.failed:
            project = self.tree.root / self.tree.project_file
            try:
                backend = registry.for_path(project)
                design = backend.read(project).content if backend is not None else None
                if not isinstance(design, Design):
                    raise FormatError(f"{project.name} gives no design", file=project.name)
                self.found = (design, project_index(design, self.sheets()))
            except (FormatError, CliError, OSError, ValueError) as exc:
                self.failed = f"{type(exc).__name__}: {exc}"
        return self.found

    def annotate(self, path: Path, scene: dict[str, Any]) -> dict[str, Any]:
        """``scene`` with its project's variants (a sheet or a board), and its nets named as the project's (a
        sheet of an Altium project)."""
        if path.suffix.lower() in (".schdoc", ".pcbdoc") and self.variants():
            scene = scene | {"variants": self.variants()}
        if path.suffix.lower() == ".pcbdoc" and self.tree.source == "altium":
            scene = sheet_params(scene, self.sheets())
        if path.suffix.lower() == ".bomdoc":  # change c0190: the BOM of the project's parts
            scene = bom_with_parts(scene, self.sheets())
        if path.suffix.lower() != ".schdoc" or self.tree.source != "altium" or not self.tree.project_file:
            return scene
        found = self._compile()
        if found is None:
            meta = scene["meta"] | {
                "notes": [*scene["meta"]["notes"], f"Project nets not compiled ({self.failed})."]
            }
            return scene | {"meta": meta}
        return annotate_nets(scene, *found)


def _variant(name: str, project: _ProjectNets, scene: dict[str, Any], result: dict[str, Any]) -> str:
    """The variant ``--variant`` names, checked, with its counts on the document shown in ``result``."""
    known = project.variants()
    if name not in known:
        listed = ", ".join(sorted(known)) or "none"
        raise CliError(
            "FEN-2001", f"--variant: no variant {name!r} (the project has: {listed})", where="--variant"
        )
    refs = [
        str(c["ref"]) for c in cast("list[dict[str, Any]]", scene.get("comps", [])) if not c.get("hidden")
    ]
    result["variant"] = {"name": name, **variant_counts(known[name], refs)}
    return name


def _docs(argument: str | None, tree: ProjectTree) -> set[str] | None:
    """The ids that ``--docs`` names (ids, paths or names, comma-separated), or ``None`` without it."""
    if argument is None:
        return None
    chosen: set[str] = set()
    for name in (part.strip() for part in argument.split(",")):
        found = tree.document(name) if name else None
        if found is None:
            raise CliError("FEN-2001", f"--docs: the project holds no document {name!r}", where="--docs")
        chosen.add(found.id)
    return chosen


def check_reply(
    argument: str | None, ctx: Context, tree: ProjectTree, doc_file: Path | None
) -> dict[str, Any] | None:
    """The ``check`` reply that ``--check`` names (change c0188): a reply file, or with ``run`` the reply of
    ``check`` run here, read-only, on the project file, else on the document shown."""
    if argument is None:
        return None
    if argument == "run":
        from fenolite.cli import cmd_check  # noqa: PLC0415  (only --check run needs the stages)

        target = tree.root / tree.project_file if tree.project_file else doc_file
        if target is None:
            raise CliError("FEN-2001", "--check run: no document to check", where="--check")
        parser = argparse.ArgumentParser(add_help=False)
        cmd_check.COMMAND.register(parser)
        found = cmd_check.COMMAND.run(parser.parse_args([str(target)]), ctx)
        return {
            "command": "check",
            "result": found.result,
            "issues": [dataclasses.asdict(issue) for issue in found.issues],
            "evidence": {"level": found.evidence.level.value, "oracle": found.evidence.oracle},
        }
    path = Path(argument) if Path(argument).is_absolute() else ctx.cwd / argument
    if not path.is_file():
        raise CliError("FEN-3001", f"--check: {argument} does not exist", where="--check")
    try:
        return read_reply(json.loads(path.read_text(encoding="utf-8")), name=path.name)
    except (ValueError, FormatError) as exc:
        raise CliError(
            "FEN-3004",
            f"--check: {exc}",
            where=argument,
            hint="pass the JSON reply of `fenolite check ... --json`, or `--check run`",
        ) from exc


def marks_of(
    argument: str | None, ctx: Context, *, serving: bool
) -> tuple[Path | None, list[dict[str, Any]]]:
    """The review file ``--marks`` names and its marks (change c0189). A missing file is an empty list when
    the page is served (the server creates it with the first mark), else ``FEN-3001``; a malformed one is
    ``FEN-3004``."""
    if argument is None:
        return None, []
    path = Path(argument) if Path(argument).is_absolute() else ctx.cwd / argument
    if not path.is_file() and not serving:
        raise CliError("FEN-3001", f"--marks: {argument} does not exist", where="--marks")
    try:
        return path, review.to_json(review.load(path))
    except FormatError as exc:
        raise CliError(
            "FEN-3004", f"--marks: {exc}", where=argument, hint="pass a fenolite.review.v0 file"
        ) from exc


def _selected(name: str, scene: dict[str, Any]) -> bool:
    """Whether the scene holds the part or net ``name`` (``--select``), ignoring case."""
    want = name.removeprefix("net:").casefold()
    refs = [str(c.get("ref", "")) for c in cast("list[dict[str, Any]]", scene.get("comps", []))]
    nets = [
        str(cast("dict[str, Any]", n).get("name", "")) if isinstance(n, dict) else str(n)
        for n in cast("list[Any]", scene.get("nets", []))
    ]
    return any(item.casefold() == want for item in (*refs, *nets))


def _with_check(
    reply: dict[str, Any] | None, tree: ProjectTree, path: Path, scene: dict[str, Any]
) -> dict[str, Any]:
    """``scene`` with the findings of ``reply`` placed on it, when there is a reply and the scene is a board
    or a sheet."""
    if reply is None or scene.get("kind") not in (None, "schematic"):
        return scene
    root = not tree.project_file or path.stem.casefold() == Path(tree.project_file).stem.casefold()
    return scene | {"check": check_overlay(reply, scene, root_sheet=root)}


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
    store = SceneCache.at(args.cache, tree.root)
    theme_key = json.dumps(kicad, sort_keys=True) if kicad is not None else ""

    def plain(path: Path) -> dict[str, Any]:
        return store.scene(path, theme_key, lambda: scene_of(path, kicad))

    nets_of = _ProjectNets(tree, plain)

    doc = tree.document(args.doc) if args.doc else tree.first_viewable()
    if args.doc and doc is None:
        raise CliError("FEN-2001", f"--doc: the project holds no document {args.doc!r}", where="--doc")
    reply = check_reply(args.check, ctx, tree, doc.file if doc is not None else None)
    marks_file, marks = marks_of(args.marks, ctx, serving=bool(args.serve))

    def cached(path: Path) -> dict[str, Any]:
        return _with_check(reply, tree, path, nets_of.annotate(path, plain(path)))

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
        scene: dict[str, Any] = cached(doc.file)
        scene["overlays"] = overlays
        if args.variant is not None:
            scene = scene | {"variant": _variant(args.variant, nets_of, scene, result)}
        if args.compare:
            diff = _compare(scene, args.compare, ctx, cached)
            scene = scene | {"diff": diff}
            result["compare"] = compare_summary(diff)
        if "check" in scene:
            result["check"] = check_summary(scene["check"])
        scenes[doc.id] = scene
        result["summary"] = _summary(scene)
        result["notes"] = list(scene["meta"]["notes"])
        if args.select:
            result["select"] = {"name": args.select, "found": _selected(args.select, scene)}
            if not result["select"]["found"]:
                result["notes"].append(f"--select: {doc.name} holds no part or net {args.select!r}")
        result["theme"] = _theme_name(scene)
        evidence = (
            Evidence(Level(scene["meta"]["evidence"]))
            if scene["meta"]["evidence"] in Level._value2member_map_
            else evidence
        )
        ref = InputRef(path=doc.file.name, sha256=scene["meta"]["sha256"], kind=doc.kind, format_version=None)
    elif doc is not None:
        result["notes"] = [f"{doc.name} ({doc.kind}) has no viewer in this version"]
    if marks_file is not None:
        result["marks"] = marks

    writes: tuple[PlannedWrite, ...] = ()
    if args.export:
        chosen = _docs(args.docs, tree)
        if chosen is not None:
            scenes = {doc_id: scene for doc_id, scene in scenes.items() if doc_id in chosen}
        for other in tree.documents:
            if chosen is not None and other.id not in chosen:
                continue
            if other.viewable and other.present and other.file is not None and other.id not in scenes:
                scenes[other.id] = cached(other.file) | {"overlays": []}
        html = export.page(
            tree.to_json(), scenes, open_id=doc.id if doc else None, select=args.select, marks=marks
        ).encode("utf-8")
        writes = (PlannedWrite(path=str(args.export), data=html, kind=KIND),)
        result["export"] = {
            "documents": sorted(scenes),
            "bytes": len(html),
            "sha256": hashlib.sha256(html).hexdigest(),
        }
        if len(html) > LARGE_PAGE:
            result["export"]["warning"] = (
                f"the page holds {len(html) // 1_000_000} MB; --docs embeds fewer documents"
            )

    result["cache"] = {"where": args.cache, "hits": store.hits, "misses": store.misses}
    if args.serve:

        def build(path: Path) -> dict[str, Any]:
            built = cached(path)
            if args.compare and doc is not None and path == doc.file:  # rebuilt on save: compared again
                built = built | {"diff": _compare(built, args.compare, ctx, cached)}
            return built

        live = server.Live(
            tree,
            build,
            overlays=overlays,
            open_id=doc.id if doc else None,
            log=_log,
            marks_file=marks_file,
            select=args.select,
        )
        httpd = server.serve(live, port)
        url = f"http://{server.HOST}:{httpd.server_address[1]}/"
        _progress(ctx, url)
        if not args.no_browser:
            webbrowser.open(url)
        started = time.monotonic()
        server.run(live, httpd, until=SERVE_STOP)
        result["serve"] = {"url": url, "seconds": round(time.monotonic() - started, 1)}
        if marks_file is not None:
            result["serve"]["marks_written"] = live.written
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
