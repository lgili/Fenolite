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

Change c0193 adds to a board, unless ``--no-review``, the review findings of ``fenolite.view.findings`` and
the open connections of ``analysis.connectivity`` (a line between the two anchors of each), and, unless
``--no-models``, the body models a backend gives (``BodyModelSource``), meshed by gmsh in a separate process
and placed by ``fenolite.view.models``: before the page is planned with ``--export``, in the background after
the first scene with ``--serve``. ``--overlay`` also reads a findings file (``fenolite.view_overlay.v0``).
"""

from __future__ import annotations

import argparse
import dataclasses
import errno
import hashlib
import json
import re
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from fenolite.analysis.connectivity import connectivity
from fenolite.backends import registry
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.variants import read_variants
from fenolite.backends.base import BoardFrame, BodyModel, BodyModelSource, PlacedExtent
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.explain import explain
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.placement import legality
from fenolite.view import export, keymap, layout, meshes, models, project_review, review, server, themes
from fenolite.view import roles as roles_view
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
from fenolite.view.findings import review as findings_of
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
OVERLAY_SCHEMA = "fenolite.view_overlay.v0"
GROUND = re.compile(r"GND|GROUND|VSS|EARTH", re.IGNORECASE)
GROUND_NAMES = frozenset({"PE", "FE", "COM"})
OPEN_GROUPS: dict[str, tuple[str, str]] = {
    "open_ground": ("Open connections: ground nets", "#3dff7a"),
    "open_net": ("Open connections: other nets", "#a6ff4d"),
}
ANALYZE_GROUPS: dict[str, tuple[str, str]] = {
    "analyze_clearance": ("analyze: clearance paths", "#ff3030"),
    "analyze_creepage": ("analyze: creepage paths", "#30a0ff"),
}


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
        help="draw an analyze reply or a findings file (JSON)",
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
    parser.add_argument(
        "--report",
        metavar="FILE",
        action="append",
        default=[],
        help="recorded convert/export JSON for project review; repeat for different commands",
    )
    parser.add_argument("--select", metavar="REF", help="open at this part or net")
    parser.add_argument(
        "--marks", metavar="FILE", help="review marks: list them; --serve saves new ones there"
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        help="a KiCad colour theme: a .json file or a theme name",
    )
    parser.add_argument(
        "--keymap",
        metavar="NAME|FILE",
        help="the keys of the workbench: fenolite, altium, kicad, or a fenolite.view_keymap.v0 file",
    )
    parser.add_argument(
        "--workspace",
        choices=("board", "roles"),
        default=None,
        help="the workspace to open: board, or roles (the Net Roles workspace of a board)",
    )
    parser.add_argument("--roles", metavar="FILE", help="the role document, as for fenolite roles --roles")
    parser.add_argument(
        "--layout", metavar="FILE", help="a fenolite.view_layout.v0 file: the docks and panels to open with"
    )
    parser.add_argument(
        "--edit", action="store_true", help="with --serve: allow the role writes of the Net Roles workspace"
    )
    parser.add_argument("--no-review", action="store_true", help="no review findings")
    parser.add_argument("--no-models", action="store_true", help="no 3D models (gmsh)")
    parser.add_argument("--silk-gap", metavar="MM", help="silkscreen gap (default: the rule)")
    parser.add_argument("--mask-expansion", metavar="MM", default="0", help="mask opening growth")


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


def keymap_of(argument: str | None, ctx: Context) -> dict[str, Any] | None:
    """The keymap named by ``--keymap`` for the page (change c0245, decision 5), or ``None``."""
    if not argument:
        return None
    if argument in keymap.BUILT_IN:
        return {"schema": keymap.SCHEMA, "base": argument, "bindings": {}}
    path = Path(argument) if Path(argument).is_absolute() else ctx.cwd / argument
    if not path.is_file():
        raise CliError(
            "FEN-3001",
            f"--keymap: no keymap {argument!r}",
            where="--keymap",
            hint=f"name one of {', '.join(keymap.BUILT_IN)}, or a fenolite.view_keymap.v0 file",
        )
    try:
        return keymap.read_keymap(path)
    except keymap.KeymapError as exc:
        raise CliError("FEN-3004", f"--keymap: {exc}", where="--keymap") from exc


def layout_of(argument: str | None, ctx: Context) -> dict[str, Any] | None:
    """The layout file named by ``--layout`` (change c0245, decision 4), or ``None``."""
    if not argument:
        return None
    path = Path(argument) if Path(argument).is_absolute() else ctx.cwd / argument
    if not path.is_file():
        raise CliError("FEN-3001", f"--layout: {argument} does not exist", where="--layout")
    try:
        return layout.read_layout(path)
    except layout.LayoutError as exc:
        raise CliError("FEN-3004", f"--layout: {exc}", where="--layout") from exc


def roles_reply(board: Path, roles_file: str | None, ctx: Context) -> dict[str, Any]:
    """The envelope of ``fenolite roles BOARD --check`` run here, read-only (change c0245): the Net Roles
    workspace shows its numbers as the command gives them."""
    from fenolite.cli import cmd_roles  # noqa: PLC0415  (only the Net Roles workspace needs the roles)

    parser = argparse.ArgumentParser(add_help=False)
    cmd_roles.COMMAND.register(parser)
    argv = [str(board), "--check"] + (["--roles", roles_file] if roles_file else [])
    found = cmd_roles.COMMAND.run(parser.parse_args(argv), ctx)
    return {
        "command": "roles",
        "result": found.result,
        "issues": [dataclasses.asdict(issue) for issue in found.issues],
        "evidence": {"level": found.evidence.level.value, "hypotheses": list(found.evidence.hypotheses)},
    }


def roles_write(
    board: Path, argv: list[str], plan_id: str | None, roles_file: str | None
) -> tuple[int, dict[str, Any]]:
    """``fenolite roles BOARD ARGV --check`` run in this process for a served page (change c0245, decision
    11): with ``--dry-run`` when ``plan_id`` is ``None``, else ``--confirm --plan PLAN_ID``, which writes the
    reviewed bytes. ``argv`` holds role options only (``fenolite.view.roles.write_argv``)."""
    from fenolite.cli.main import invoke  # noqa: PLC0415  (a command line, as the page's user would type it)

    line = ["roles", str(board), *argv, "--check", *(["--roles", roles_file] if roles_file else [])]
    line += ["--dry-run"] if plan_id is None else ["--confirm", "--plan", plan_id]
    code, envelope, error = invoke(line, cwd=board.parent)
    return code, (envelope or {}) | ({"error": error} if error else {})


def roles_payload(board: Path, roles_file: str | None, ctx: Context) -> dict[str, Any]:
    """The data of the Net Roles workspace for ``board``: the roles reply, its explanations and the board's
    locked copper (``fenolite.view.roles``)."""
    reply = roles_reply(board, roles_file, ctx)
    found = read_board(board).design.board
    assert found is not None  # read_board refuses a design without a board
    locked: dict[str, list[int]] = {
        "tracks": [k + 1 for k, track in enumerate(found.tracks) if track.locked],
        "arcs": [k + 1 for k, arc in enumerate(found.arcs) if arc.locked],
        "vias": [k + 1 for k, via in enumerate(found.vias) if via.locked],
    }
    data = roles_view.payload(
        reply, document=board.name, sha256=hashlib.sha256(board.read_bytes()).hexdigest(), locked=locked
    )
    data["explain"] = _explanations(str(issue["code"]) for issue in data["issues"])
    return data


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


@dataclass(frozen=True)
class Board:
    """A board file as read: its design, its backend (a board frame when it is one), bytes and evidence."""

    path: Path
    design: Design
    backend: Any
    data: bytes
    evidence: str

    @property
    def frame(self) -> BoardFrame | None:
        return self.backend if isinstance(self.backend, BoardFrame) else None


def read_board(path: Path) -> Board:
    """The board at ``path``, read by the backend that reads it."""
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {path.name}", where=path.name)
    data = path.read_bytes()
    read = backend.read(path)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{path.name} is not a board", where=path.name)
    return Board(path, design, backend, data, read.evidence.level.value)


def _group(gid: str, title: str, color: str, items: list[dict[str, Any]], note: str = "") -> dict[str, Any]:
    return {
        "id": gid,
        "title": title,
        "color": color,
        "n": sum(1 for o in items if o.get("group") == gid),
        "note": note,
    }


def open_connection_overlays(board: Board) -> list[dict[str, Any]]:
    """The open connections of ``analysis.connectivity``: a line between the two anchors of each."""
    pads = board.frame.board_pads(board.design) if board.frame is not None else None
    out: list[dict[str, Any]] = []
    for net in connectivity(board.design, pads=pads).nets:
        group = "open_ground" if GROUND.search(net.name) or net.name.upper() in GROUND_NAMES else "open_net"
        for link in net.open:
            a, b = link.a, link.b
            out.append(
                {
                    "group": group,
                    "kind": "line",
                    "pts": [
                        [round(a.position.x / 1000), round(a.position.y / 1000)],
                        [round(b.position.x / 1000), round(b.position.y / 1000)],
                    ],
                    "label": f"{net.name}: open connection {a.where} → {b.where}, {link.length / 1e6:.3f} mm "
                    f"({net.islands} islands)",
                    "layer": None,
                    "color": OPEN_GROUPS[group][1],
                }
            )
    return out


def add_findings(board: Board, scene: dict[str, Any], *, silk_gap: int | None, mask_expansion: int) -> None:
    """Add the review findings and the open connections to ``scene`` (overlays and ``meta.findings``)."""
    found = findings_of(
        board.design,
        board.frame,
        silk_gap=silk_gap,
        mask_expansion=mask_expansion,
        backend=board.backend.name,
    )
    links = open_connection_overlays(board)
    scene["overlays"] = list(scene.get("overlays", [])) + found.items + links
    groups = list(scene["meta"].get("findings", [])) + found.groups
    notes = {
        "open_ground": "Nets named as grounds (GND, GROUND, VSS, EARTH, or PE, FE, COM) whose copper is in "
        "more than one island: a line joins the nearest anchors of two islands (analysis.connectivity, the "
        "minimum spanning tree).",
        "open_net": "Other nets whose copper is in more than one island (analysis.connectivity).",
    }
    for gid, (title, color) in OPEN_GROUPS.items():
        groups.append(_group(gid, title, color, links, notes[gid]))
    scene["meta"]["findings"] = groups


def add_models(board: Board, scene: dict[str, Any], *, log: Any = None) -> dict[str, int] | None:
    """Mesh and place the body models of ``board`` in ``scene``; ``None`` when its backend gives none."""
    if not isinstance(board.backend, BodyModelSource):
        scene["meta"]["notes"].append(
            "This backend gives no body model: bodies are extruded from their outline."
        )
        return None
    found: tuple[BodyModel, ...] = board.backend.body_models(board.path)
    if not found:
        return models.attach_models(scene, (), {})
    command = meshes.find_gmsh()
    if command is None:
        scene["meta"]["notes"].append(
            f"{len(found)} body model(s) are embedded, but gmsh is not installed "
            f"(or {meshes.GMSH_ENV} names none): bodies are extruded."
        )
        return models.attach_models(scene, (), {})
    unique = {meshes.mesh_key(m.data): m for m in found}
    started = time.monotonic()
    made = meshes.mesh_models(
        [(m.data, m.format) for m in unique.values()], gmsh=command, cache=meshes.cache_folder()
    )
    counts = models.attach_models(scene, found, dict(zip(unique, made, strict=True)))
    scene["meta"]["notes"].append(
        f"3D: {counts['model']} body model(s) placed as the file places them, {counts['fitted']} fitted to "
        f"the body's stored outline, {counts['outline']} bodies extruded ({counts['unmeshed']} model(s) gmsh "
        "could not mesh)."
    )
    if log is not None:
        log(f"view: {board.path.name}: {len(unique)} models meshed in {time.monotonic() - started:.1f} s")
    return counts


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
    """The overlay items of ``fenolite analyze`` replies (per distance row, its clearance path in red and its
    creepage path in blue, in micrometres, marked as a finding when an error or a warning names its nets) and
    of findings files (``fenolite.view_overlay.v0``)."""
    return overlay_files(files, ctx)[0]


def overlay_files(files: list[str], ctx: Context) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(items, groups)`` of the overlay files (``overlays_of``)."""
    out: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    for name in files:
        path = Path(name) if Path(name).is_absolute() else ctx.cwd / name
        try:
            envelope: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CliError("FEN-3004", f"{name} is not JSON: {type(exc).__name__}", where=name) from exc
        if isinstance(envelope, dict) and cast("dict[str, Any]", envelope).get("schema") == OVERLAY_SCHEMA:
            items, more = _findings_file(cast("dict[str, Any]", envelope), name)
            out += items
            for g in more:
                groups.setdefault(g["id"], g)
            continue
        try:
            reply = cast("dict[str, Any]", envelope)
            rows: list[Any] = list(reply["result"]["distances"])
            issues: list[Any] = list(reply.get("issues", []))
        except (KeyError, TypeError, AttributeError) as exc:
            raise CliError(
                "FEN-3004",
                f"{name} is not a fenolite analyze reply nor a findings file: {type(exc).__name__}",
                where=name,
                hint=f"pass the JSON reply of `fenolite analyze ... --json`, or a file of the schema "
                f"{OVERLAY_SCHEMA}",
            ) from exc
        flagged = {str(i.get("where", "")) for i in issues if i.get("severity") in ("error", "warning")}
        for row in rows:
            out += _row_overlays(row, flagged)
        for gid, (title, color) in ANALYZE_GROUPS.items():
            groups.setdefault(
                gid, {"id": gid, "title": title, "color": color, "n": 0, "note": f"Paths of {name}."}
            )
    for g in groups.values():
        g["n"] = sum(1 for o in out if o.get("group") == g["id"])
    return out, list(groups.values())


def _findings_file(data: dict[str, Any], name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The items and groups of a findings file: points in nanometres of the board frame become micrometres."""
    try:
        groups = [
            {
                "id": str(g["id"]),
                "title": str(g.get("title", g["id"])),
                "color": str(g.get("color", "#ffd84d")),
                "n": 0,
                "note": str(g.get("note", "")),
            }
            for g in data.get("groups", [])
        ]
        colors = {g["id"]: g["color"] for g in groups}
        items: list[dict[str, Any]] = []
        for item in data.get("items", []):
            kind = str(item.get("kind", "line"))
            if kind not in ("line", "path", "point"):
                raise ValueError(f"item kind {kind!r}")
            pts = [
                [round(Fraction(int(p[0]), 1000)), round(Fraction(int(p[1]), 1000))]
                for p in item["points_nm"]
            ]
            if not pts:
                raise ValueError("an item without points")
            group = str(item["group"])
            if group not in colors:
                groups.append({"id": group, "title": group, "color": "#ffd84d", "n": 0, "note": ""})
                colors[group] = "#ffd84d"
            items.append(
                {
                    "group": group,
                    "kind": kind,
                    "pts": pts,
                    "label": str(item.get("label", "")),
                    "layer": item.get("layer"),
                    "color": colors[group],
                }
            )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise CliError("FEN-3004", f"{name} is not a valid {OVERLAY_SCHEMA} file: {exc}", where=name) from exc
    return items, groups


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
                "group": f"analyze_{kind}",
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
            "input": dataclasses.asdict(found.input) if found.input is not None else None,
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


def reports_of(arguments: list[str], ctx: Context) -> list[dict[str, Any]]:
    """Load recorded operation replies for review without running or writing anything."""
    reports: list[dict[str, Any]] = []
    for argument in arguments:
        path = Path(argument) if Path(argument).is_absolute() else ctx.cwd / argument
        if not path.is_file():
            raise CliError("FEN-3001", f"--report: {argument} does not exist", where="--report")
        try:
            report = project_review.read_report(json.loads(path.read_text(encoding="utf-8")), name=path.name)
        except (ValueError, FormatError) as exc:
            raise CliError(
                "FEN-3004",
                f"--report: {exc}",
                where=argument,
                hint="pass a complete convert or export JSON reply; use --check for check results",
            ) from exc
        if any(item["command"] == report["command"] for item in reports):
            raise CliError(
                "FEN-2001", f"--report: more than one {report['command']} report", where="--report"
            )
        reports.append(report)
    return reports


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
    check = check_overlay(reply, scene, root_sheet=root)
    check["explain"] = _explanations(str(f["code"]) for f in check["findings"])
    return scene | {"check": check}


def _explanations(codes: Iterable[str]) -> dict[str, dict[str, str]]:
    """The ``fenolite explain`` text of each code, for the Messages panel (change c0245, M11)."""
    out: dict[str, dict[str, str]] = {}
    for code in sorted(set(codes)):
        entry = explain(code)
        if entry is not None:
            out[code] = {"meaning": entry.meaning, "fix": entry.fix, "see": entry.see}
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


def _mm_option(text: str | None, name: str) -> int | None:
    """A length option in millimetres as nanometres; ``None`` when not given."""
    if text is None:
        return None
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        value = Fraction(-1)
    if value < 0:
        raise CliError("FEN-2001", f"{name}: expected millimetres of at least 0, got {text!r}", where=name)
    return round(value * 1_000_000)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.serve and ctx.in_process:
        raise CliError(
            "FEN-2001",
            "--serve runs until stopped, and fenolite.api.run does not block",
            where="--serve",
            hint="run 'fenolite view --serve' as a process, or export the page with --export",
        )
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
    silk_gap = _mm_option(args.silk_gap, "--silk-gap")
    mask_expansion = _mm_option(args.mask_expansion, "--mask-expansion") or 0
    tree = _tree(args.path, ctx)
    file_items, file_groups = overlay_files(args.overlay, ctx)
    kicad = theme_of(args.theme, ctx)
    if args.edit and not args.serve:
        raise CliError(
            "FEN-2001",
            "--edit allows the role writes of a served page; pass --serve",
            where="--edit",
            hint="fenolite view PATH --serve --edit",
        )
    settings: dict[str, Any] = {}
    if (keys := keymap_of(args.keymap, ctx)) is not None:
        settings["keymap"] = keys
    if (given_layout := layout_of(args.layout, ctx)) is not None:
        settings["layout"] = given_layout
    if args.workspace is not None:
        settings["workspace"] = args.workspace
    if args.edit:
        settings["edit"] = True
    store = SceneCache.at(args.cache, tree.root)
    theme_key = json.dumps(kicad, sort_keys=True) if kicad is not None else ""

    def plain(path: Path) -> dict[str, Any]:
        return store.scene(path, theme_key, lambda: scene_of(path, kicad))

    nets_of = _ProjectNets(tree, plain)

    def make(path: Path, *, with_files: bool) -> dict[str, Any]:
        """The cached scene of ``path`` with the overlay files (the document shown) and, for a board, the
        review findings (change c0193); the cached scene itself is not changed."""
        scene = cached(path)
        items = list(file_items) if with_files else []
        if scene.get("kind") is not None:  # a sheet, a library or a drawing
            return scene | {"overlays": items}
        groups = [dict(g) for g in file_groups] if with_files else []
        meta = scene["meta"] | {"notes": list(scene["meta"].get("notes", [])), "findings": groups}
        scene = scene | {"overlays": items, "meta": meta}
        if not args.no_review:
            add_findings(read_board(path), scene, silk_gap=silk_gap, mask_expansion=mask_expansion)
        return scene

    doc = tree.document(args.doc) if args.doc else tree.first_viewable()
    if args.doc and doc is None:
        raise CliError("FEN-2001", f"--doc: the project holds no document {args.doc!r}", where="--doc")
    reply = check_reply(args.check, ctx, tree, doc.file if doc is not None else None)
    reports = reports_of(args.report, ctx)
    marks_file, marks = marks_of(args.marks, ctx, serving=bool(args.serve))

    def cached(path: Path) -> dict[str, Any]:
        scene = _with_check(reply, tree, path, nets_of.annotate(path, plain(path)))
        review_status = project_review.status(scene, reply, reports)
        if "check" in scene and review_status["binding"] and not review_status["binding"]["matched"]:
            scene["check"]["notes"].append(review_status["binding"]["note"])
        return scene | {"project_review": review_status}

    result: dict[str, Any] = {
        "project": tree.to_json(),
        "document": doc.id if doc else None,
        "summary": None,
        "notes": [],
        "theme": None,
    }
    evidence = Evidence(Level.INFERRED, hypotheses=("H-G-VIEW-SCENE",))
    ref: InputRef | None = None
    scenes: dict[str, dict[str, Any]] = {}
    if doc is not None and doc.viewable and doc.file is not None and doc.present:
        scene: dict[str, Any] = make(doc.file, with_files=True)
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
        result["review"] = scene["project_review"]
        if scene.get("kind") is None:  # a board: its findings by group, and no model meshed in this form
            result["summary"] |= {
                "findings": {g["id"]: g["n"] for g in scene["meta"]["findings"]},
                "models": None,
            }
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
    roles_data: dict[str, dict[str, Any]] = {}
    if args.workspace == "roles":
        if doc is None or doc.file is None or doc.id not in scenes or scenes[doc.id].get("kind") is not None:
            raise CliError(
                "FEN-2001",
                "--workspace roles opens the Net Roles workspace of a board",
                where="--workspace",
                hint="pass a board, or --doc with a board of the project",
            )
        roles_data[doc.id] = roles_payload(doc.file, args.roles, ctx)
        result["roles"] = roles_view.summary(roles_data[doc.id])
        evidence = Evidence(Level.INFERRED, hypotheses=tuple(roles_data[doc.id]["evidence"]["hypotheses"]))
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
                scenes[other.id] = make(other.file, with_files=False)
        if not args.no_models:
            for other in tree.documents:
                if other.id in scenes and other.file is not None and scenes[other.id].get("kind") is None:
                    counts = add_models(read_board(other.file), scenes[other.id])
                    if doc is not None and other.id == doc.id and result["summary"] is not None:
                        result["summary"]["models"] = counts
        if args.workspace == "roles":  # every board of the page, in its Net Roles workspace
            for other in tree.documents:
                if other.id in scenes and other.id not in roles_data and other.file is not None:
                    if scenes[other.id].get("kind") is None:
                        roles_data[other.id] = roles_payload(other.file, args.roles, ctx)
        html = export.page(
            tree.to_json(),
            scenes,
            open_id=doc.id if doc else None,
            select=args.select,
            marks=marks,
            settings=settings,
            roles=roles_data,
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
            built = make(path, with_files=doc is not None and path == doc.file)
            if args.compare and doc is not None and path == doc.file:  # rebuilt on save: compared again
                built = built | {"diff": _compare(built, args.compare, ctx, cached)}
            return built

        def refine(path: Path, scene: dict[str, Any]) -> dict[str, Any] | None:
            """The body models of a board, placed after its first scene was served (change c0193)."""
            if scene.get("kind") is not None:
                return None
            refined = json.loads(json.dumps(scene))
            return refined if add_models(read_board(path), refined, log=_log) is not None else None

        roles_abs = (
            str(Path(args.roles) if Path(args.roles).is_absolute() else ctx.cwd / args.roles)
            if args.roles
            else None
        )
        live = server.Live(
            tree,
            build,
            open_id=doc.id if doc else None,
            log=_log,
            marks_file=marks_file,
            select=args.select,
            refine=None if args.no_models else refine,
            settings=settings,
            roles=lambda path: roles_payload(path, args.roles, ctx),
            roles_writer=lambda path, argv, plan_id: roles_write(path, argv, plan_id, roles_abs),
        )
        try:
            httpd = server.serve(live, port)
        except OSError as exc:
            if exc.errno in (errno.EADDRINUSE, errno.EACCES):
                raise CliError(
                    "FEN-2001",
                    f"--port: port {port} of {server.HOST} is in use",
                    where="--port",
                    hint="pass --port 0 to take a free port, or stop the program that holds it",
                ) from exc
            raise
        url = f"http://{server.HOST}:{httpd.server_address[1]}/"
        _progress(ctx, url)
        if not args.no_browser:
            webbrowser.open(url)
        started = time.monotonic()
        server.run(live, httpd, until=SERVE_STOP)
        result["serve"] = {"url": url, "seconds": round(time.monotonic() - started, 1)}
        if marks_file is not None:
            result["serve"]["marks_written"] = live.written
    dependencies = [*args.report, *([args.check] if args.check and args.check != "run" else [])]
    return Result(
        result=result,
        evidence=evidence,
        input=ref,
        writes=writes,
        depends=depends_on(ctx.cwd, *dependencies),
    )


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

__all__ = [
    "COMMAND",
    "Board",
    "add_findings",
    "add_models",
    "overlay_files",
    "overlays_of",
    "read_board",
    "scene_of",
]
