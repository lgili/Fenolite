# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place PATH``: staged parts placed on the board in a deterministic grid, or named parts moved
(capability cli-contract, "Place command"; ``docs/placement.md``; ``docs/cli-contract.md``, "place").

The command reads the board, moves footprints with ``backends.kicad.replace.move_footprint``, judges the
resulting layout with ``placement.legality.check`` and plans one write: the board. It runs no tool. An
illegal placement is not written unless ``--force`` is given; KiCad's DRC stays the judge of the board.

The legality check gets the board's keep-outs, and the grid leaves the box of every rule area that forbids
footprints free. The placement rules of a built project (``.fenolite/``) are judged on the layout after
the moves and reported as warnings, which never refuse the write, and ``result.measures`` holds the wire
length and the congestion of that layout (``checks.placement``; change c0113).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad import pcb as kicad_pcb
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.backends.kicad.replace import PlacementError, footprint_ref, move_footprint
from fenolite.checks import placement as placement_rules
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import board_format
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, Udeg, parse_angle, parse_length
from fenolite.geometry import BBox
from fenolite.model import canonical
from fenolite.model.board import FootprintInstance, Side
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.placement import EVIDENCE, KEEPOUT_EVIDENCE, Box, check
from fenolite.placement import place as grid_place
from fenolite.placement.codes import issue
from fenolite.placement.grid import DEFAULT_GAP, DEFAULT_MARGIN, DEFAULT_PITCH
from fenolite.placement.legality import forbids_footprints

HELP = "place staged parts on the board in a grid, or move named parts (edits the board)"
STRATEGIES = ("grid", "manual")
SIDES: tuple[Side, ...] = ("top", "bottom")
CACHE_DIR = ".fenolite"
MOVE_HINT = "write --move REF=X,Y[,ROT[,SIDE]] with units, for example --move R1=12mm,8mm,90,top"


@dataclass(frozen=True, slots=True)
class Move:
    """One ``--move``: the reference, the position in the frame of ``place()`` and the optional rotation
    and side."""

    ref: str
    x: Nm
    y: Nm
    rotation: Udeg | None = None
    side: Side | None = None


def _length(text: str, option: str) -> Nm:
    try:
        return parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{option}: {error}", where=option, hint="lengths need a unit: 0.5mm"
        ) from None


def parse_move(text: str) -> Move:
    """``REF=X,Y[,ROT[,SIDE]]`` as a ``Move``; a malformed value is a usage error (``FEN-2001``)."""
    ref, eq, rest = text.partition("=")
    parts = [part.strip() for part in rest.split(",")]
    if not eq or not ref.strip() or not 2 <= len(parts) <= 4:
        raise CliError("FEN-2001", f"--move: cannot read {text!r}", where="--move", hint=MOVE_HINT)
    x, y = _length(parts[0], "--move"), _length(parts[1], "--move")
    rotation: Udeg | None = None
    side: Side | None = None
    if len(parts) >= 3:
        try:
            rotation = parse_angle(parts[2], default_unit="deg") % kicad_pcb.FULL_TURN
        except ValueError as error:
            raise CliError("FEN-2001", f"--move: {error}", where="--move", hint=MOVE_HINT) from None
    if len(parts) == 4:
        if parts[3] not in SIDES:
            raise CliError(
                "FEN-2001", f"--move: side {parts[3]!r} is not top or bottom", where="--move", hint=MOVE_HINT
            )
        side = "top" if parts[3] == "top" else "bottom"
    return Move(ref.strip(), x, y, rotation, side)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/placement.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=None,
        help="grid (default): place every part that is off the board; manual: only the --move parts",
    )
    parser.add_argument(
        "--move",
        action="append",
        default=[],
        metavar="REF=X,Y[,ROT[,SIDE]]",
        help="move one part (repeatable; implies --strategy manual): lengths with a unit, from the top-left "
        "corner of the outline, Y down; ROT in degrees; SIDE top or bottom",
    )
    parser.add_argument("--only", default=None, metavar="REF,REF", help="grid: place only these parts")
    parser.add_argument("--pitch", default=None, metavar="L", help="grid step (default 0.5mm)")
    parser.add_argument("--gap", default=None, metavar="L", help="space kept around a part (default 0.5mm)")
    parser.add_argument(
        "--margin", default=None, metavar="L", help="distance kept from the outline's box (default 1mm)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="write an illegal placement, and move parts that are locked on the board",
    )
    parser.add_argument(
        "-o", "--out", default=None, metavar="FILE", help="write the board here (default: PATH)"
    )


def _placement(fp: FootprintInstance) -> dict[str, object]:
    return {"x": fp.position.x, "y": fp.position.y, "rotation": fp.rotation, "side": fp.side}


def _paths(design: Design) -> dict[str, str]:
    """Footprint id → component path (``fenolite.path``, else the reference)."""
    components = {c.id: c for c in design.circuit.components}
    out: dict[str, str] = {}
    for fp in design.board.footprints if design.board is not None else ():
        component = components.get(fp.component_id)
        path = component.properties.get(PATH_PROPERTY) if component is not None else None
        out[fp.id] = path or footprint_ref(design, fp)
    return out


def _by_ref(design: Design) -> dict[str, FootprintInstance]:
    out: dict[str, FootprintInstance] = {}
    for fp in design.board.footprints if design.board is not None else ():
        out.setdefault(footprint_ref(design, fp), fp)
    return out


def _box(rings: Sequence[Sequence[Point]]) -> BBox | None:
    points = [point for ring in rings for point in ring]
    return BBox.of_points(points) if points else None


def _copper_left(design: Design, pads: Sequence[BoardPad], moved: set[str]) -> list[str]:
    """The ids of the moved footprints that had a track end or a via on a pad."""
    board = design.board
    assert board is not None
    ends = [(t.start, (t.layer,)) for t in board.tracks] + [(t.end, (t.layer,)) for t in board.tracks]
    ends += [(a.start, (a.layer,)) for a in board.arcs] + [(a.end, (a.layer,)) for a in board.arcs]
    ends += [(v.position, tuple(v.layers)) for v in board.vias]
    found: list[str] = []
    for pad in pads:
        if pad.footprint_id not in moved or pad.footprint_id in found:
            continue
        for entry in pad.copper:
            box = BBox.of_points(entry.core).inflate(-(-entry.width // 2))
            if any(entry.layer in layers and box.contains_point(point) for point, layers in ends):
                found.append(pad.footprint_id)
                break
    return found


def _cache(folder: Path) -> Design | None:
    """The ``.fenolite/`` model of a built project, loaded once: it holds the locked placements and the
    placement rules. ``None`` without a readable cache."""
    try:
        return canonical.load_dir(folder / CACHE_DIR)
    except (FenoliteError, OSError, ValueError):
        return None


def _wire_pitch(design: Design, board_path: Path) -> Nm | None:
    """The track width plus the clearance of the class ``Default`` in the project's own files, as the
    pitch of the congestion estimate; ``None`` without that class or without a readable project."""
    try:
        project = project_set(board_path)
    except (FenoliteError, OSError, ValueError):
        return None
    return placement_rules.default_pitch(KicadBackend().design_rules(design, project).design)


def _script_locked(cached: Design | None) -> set[str]:
    """The component paths whose placement is locked in ``.fenolite/`` (empty without a readable cache)."""
    if cached is None:
        return set()
    paths = _paths(cached)
    footprints = cached.board.footprints if cached.board is not None else ()
    return {paths[fp.id] for fp in footprints if fp.locked}


class _Definitions:
    """Library definitions by lib id, resolved through the project's tables when first asked."""

    def __init__(self, folder: Path, major: int) -> None:
        self._folder, self._major = folder, major
        self._resolver: LibraryResolver | None = None
        self.found: dict[str, FootprintDef] = {}

    def need(self, lib_ref: str) -> None:
        if not lib_ref or lib_ref in self.found:
            return
        if self._resolver is None:
            self._resolver = LibraryResolver(
                LibraryConfig(target_major=self._major, project_dir=self._folder)
            )
        try:
            self.found[lib_ref] = self._resolver.footprint(lib_ref)
        except LibraryError:
            pass  # ``move_footprint`` reports place.no-definition


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    moves = [parse_move(text) for text in args.move]
    strategy = args.strategy or ("manual" if moves else "grid")
    if moves and strategy != "manual":
        raise CliError("FEN-2001", "--move needs --strategy manual", where="--move", hint="drop --strategy")
    if args.only is not None and strategy != "grid":
        raise CliError("FEN-2001", "--only narrows the grid strategy", where="--only", hint="drop --only")
    pitch = DEFAULT_PITCH if args.pitch is None else _length(args.pitch, "--pitch")
    gap = DEFAULT_GAP if args.gap is None else _length(args.gap, "--gap")
    margin = DEFAULT_MARGIN if args.margin is None else _length(args.margin, "--margin")
    if pitch <= 0 or gap < 0 or margin < 0:
        raise CliError("FEN-2001", "--pitch must be positive, and --gap and --margin not negative")
    given = Path(args.path)
    board_path = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    data = board_path.read_bytes()
    reader_issues: list[Issue] = []
    design = kicad_pcb.read_board(board_path, issues=reader_issues)
    assert design.board is not None
    info = kicad_pcb.source_info(design)
    major = info.major if info is not None and info.major in versions.TARGET_MAJORS else ctx.kicad_target
    backend = KicadBackend()
    outline = board_outline(design)
    forbidding = forbids_footprints(design.board.keepouts)
    region = BBox.of_points(outline.rings[0]) if outline.rings else None
    origin = Point(region.x0, region.y0) if region is not None else Point(0, 0)
    before = _by_ref(design)
    paths = _paths(design)
    issues: list[Issue] = [found for found in reader_issues if found.severity != "info"]
    definitions = _Definitions(board_path.parent, major)
    moved_ids: list[str] = []

    def off_board(fp: FootprintInstance) -> bool:
        return region is not None and not region.contains_point(fp.position)

    def move(fp: FootprintInstance, at: Point, rotation: Udeg | None, side: Side | None) -> None:
        nonlocal design
        turns = (rotation is not None and rotation != fp.rotation) or (side is not None and side != fp.side)
        if turns:
            definitions.need(fp.lib_ref)
        try:
            changed = move_footprint(
                design,
                fp.id,
                at=at,
                rotation=rotation,
                side=side,
                definitions=definitions.found,
                force=bool(args.force),
            )
        except PlacementError as error:
            issues.extend(error.issues)
            return
        if changed is not design:
            design = changed
            moved_ids.append(fp.id)

    if strategy == "manual":
        for request in moves:
            fp = before.get(request.ref)
            if fp is None:
                issues.append(issue("place.unknown-ref", f"the board has no part {request.ref}", request.ref))
                continue
            move(fp, Point(origin.x + request.x, origin.y + request.y), request.rotation, request.side)
    else:
        staged = [fp for fp in design.board.footprints if off_board(fp)]
        if args.only is not None:
            wanted = [ref.strip() for ref in args.only.split(",") if ref.strip()]
            for ref in sorted(set(wanted) - set(before)):
                issues.append(issue("place.unknown-ref", f"the board has no part {ref}", ref))
            chosen = {before[ref].id for ref in wanted if ref in before}
            staged = [fp for fp in staged if fp.id in chosen]
        staged.sort(key=lambda fp: (paths[fp.id], fp.id))
        if staged and region is not None:
            known = {e.footprint_id: e for e in backend.placed_extents(design)}
            staged_ids = {fp.id for fp in staged}
            boxes: list[Box] = []
            faces: set[str] = set()
            for fp in staged:
                extent = known[fp.id]
                faces |= {face for face in ("front", "back") if getattr(extent, face)}
                box = _box((*extent.front, *extent.back)) or BBox.of_points([fp.position])
                relative = BBox(
                    box.x0 - fp.position.x,
                    box.y0 - fp.position.y,
                    box.x1 - fp.position.x,
                    box.y1 - fp.position.y,
                )
                boxes.append(Box(fp.id, footprint_ref(design, fp), relative))
            occupied: list[BBox] = []
            for fp in design.board.footprints:
                if fp.id in staged_ids or off_board(fp):
                    continue
                for face in sorted(faces):
                    occupied += [BBox.of_points(ring) for ring in getattr(known[fp.id], face)]
            cutouts = [BBox.of_points(ring) for ring in outline.rings[1:]]
            # the box of every rule area that forbids footprints is avoided like a cut-out (change c0113)
            cutouts += [BBox.of_points(area.outline) for area in forbidding]
            packed = grid_place(
                boxes, region, occupied=occupied, cutouts=cutouts, pitch=pitch, gap=gap, margin=margin
            )
            by_id = {fp.id: fp for fp in staged}
            for fp_id, at in packed.positions.items():
                move(by_id[fp_id], at, None, None)
            for fp_id in packed.unplaced:
                ref = footprint_ref(design, by_id[fp_id])
                issues.append(
                    issue(
                        "place.no-room",
                        f"the grid found no place for {ref}; it stays where it was",
                        ref,
                        "place it with --move, or enlarge the outline",
                    )
                )
    after = _by_ref(design)
    moved = set(moved_ids)
    names = {fp.id: ref for ref, fp in after.items()}
    extents = [
        extent
        for extent in backend.placed_extents(design)
        if extent.footprint_id in moved or not off_board(after[names[extent.footprint_id]])
    ]
    legality = check(extents, outline.rings, names=names, keepouts=design.board.keepouts)
    issues += legality
    cached = _cache(board_path.parent)
    pads_after = backend.board_pads(design)
    rules = placement_rules.rules_of(cached)
    judged = placement_rules.judge(design, rules, pads=pads_after)
    families = {family: dict(counts) for family, counts in judged.counts.items()}
    found_rules = list(judged.issues)
    rules_judged = judged.judged
    if rules.heights:
        # the height limits of the last build, on the layout after the moves (change c0140)
        heights = placement_rules.judge_heights(
            design, rules.heights, placement_rules.heights_of(design, cached), extents=extents
        )
        families.update({family: dict(counts) for family, counts in heights.counts.items()})
        found_rules += heights.issues
        rules_judged += heights.judged
    issues += [
        dataclasses.replace(found, severity="warning") if found.severity == "error" else found
        for found in found_rules
    ]
    wire_pitch = _wire_pitch(design, board_path)
    measures = placement_rules.measure(design, pads=pads_after, pitch=wire_pitch)
    change = {"hpwl": 0, "ratsnest": 0}
    if moved:
        original = kicad_pcb.read_board(board_path)
        pads_before = backend.board_pads(original)
        earlier = placement_rules.measure(original, pads=pads_before, pitch=wire_pitch)
        change = {"hpwl": measures.hpwl - earlier.hpwl, "ratsnest": measures.ratsnest - earlier.ratsnest}
        left = _copper_left(original, pads_before, moved)
        for fp_id in left:
            ref = names[fp_id]
            issues.append(
                issue(
                    "place.copper-left",
                    f"{ref} had copper on its pads; the tracks and vias stay where they were",
                    ref,
                    "route the part again, or move the copper in KiCad",
                )
            )
        locked = _script_locked(cached)
        for fp_id in sorted(moved, key=lambda i: names[i]):
            if paths[fp_id] in locked:
                issues.append(
                    issue(
                        "place.script-locked",
                        f"{names[fp_id]} has a locked placement in the last build; the next build "
                        "restores it",
                        names[fp_id],
                        "remove locked=True from its place() in the script",
                    )
                )
    refused = any(found.severity == "error" for found in issues) and not args.force
    writes: tuple[PlannedWrite, ...] = ()
    if moved and not refused:
        text = kicad_pcb.write_board(design, target=major, allow_lossy=ctx.allow_lossy).text
        if args.out is not None:
            target = str(args.out)
        else:
            try:
                target = str(board_path.relative_to(ctx.cwd))
            except ValueError:
                target = str(board_path)
        writes = (PlannedWrite(path=target, data=text.encode("utf-8"), kind="kicad_pcb"),)
    rows = [
        {"ref": ref, "path": paths[fp.id], "from": _placement(before[ref]), "to": _placement(fp)}
        for ref, fp in sorted(after.items())
        if fp.id in moved
    ]
    version_number = board_format(board_path)
    result: dict[str, Any] = {
        "board": board_path.name,
        "strategy": strategy,
        "moved": rows,
        "unplaced": sorted(ref for ref, fp in after.items() if off_board(fp)),
        "legality": dict(sorted(Counter(found.code for found in legality).items())),
        "rules": families,
        "measures": {**measures.to_json(), "change": change},
    }
    issues.sort(key=lambda found: (found.code, found.where))
    evidence = [EVIDENCE]
    if forbidding:
        evidence.append(KEEPOUT_EVIDENCE)
    if rules_judged:
        evidence.append(placement_rules.EVIDENCE)
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=Evidence.combine(*evidence),
        input=InputRef(
            path=board_path.name,
            sha256=hashlib.sha256(data).hexdigest(),
            kind="kicad_pcb",
            format_version=None if version_number is None else str(version_number),
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, board_path),
        write_on_error=bool(args.force),  # the one command that writes beside an error, when asked to
    )


_EXAMPLE = (EXAMPLE_BOARD, "--move", "R1=12mm,8mm", "--out", "fenolite-placed.kicad_pcb")
COMMAND = Command(
    name="place",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)
