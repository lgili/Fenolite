# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place PATH``: staged parts placed on the board in a deterministic grid, or named parts moved
(capability cli-contract, "Place command"; ``docs/placement.md``; ``docs/cli-contract.md``, "place").

The command reads the board, moves footprints with ``backends.kicad.replace.move_footprint``, judges the
resulting layout with ``placement.legality.check`` and plans one write: the board. It runs no tool but
``kicad-cli`` for ``--drc`` of the reuse strategy. An illegal placement is not written unless ``--force``
is given; KiCad's DRC stays the judge of the board.

The legality check gets the board's keep-outs, and the grid leaves the box of every rule area that forbids
footprints free. The placement rules of a built project (``.fenolite/``) are judged on the layout after
the moves and reported as warnings, which never refuse the write, and ``result.measures`` holds the wire
length and the congestion of that layout (``checks.placement``; change c0113).

``--strategy regions`` (change c0205) packs each domain of parts into its own region with the same grid,
the barrier parts across the boundaries; its glue (domains, regions, crossings) is ``cli.place_regions``.

``--strategy reuse`` (change c0210, implied by ``--from``) copies the placement, and with ``--copper`` the
copper, of a block of a reference board onto the ``--only`` parts, fitted by their pads; its glue is
``cli.place_reuse``.

``--turn REFS --about X,Y --angle DEG`` and ``--shift REFS --by DX,DY`` (change c0227, the strategy
``group``) move a group of parts rigidly with the copper and zones joined to their pads only, and
``--pose-search`` ranks the poses of a turned group by the demand across its border; its glue is
``cli.place_group``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from fenolite.backends.base import BoardPad, PlacedExtent
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
from fenolite.cli import place_group, place_reuse
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import board_format
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.cli.place_regions import RegionPlan, parse_options, plan_regions
from fenolite.cli.place_regions import crossings as region_crossings
from fenolite.cli.place_regions import evidence as region_evidence
from fenolite.cli.place_regions import to_json as regions_json
from fenolite.cli.placement_checks import check_placement_constraints
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, Udeg, parse_angle, parse_length
from fenolite.geometry import BBox
from fenolite.model import canonical
from fenolite.model.board import FootprintInstance, Keepout, Outline, Side
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.placement import EVIDENCE, KEEPOUT_EVIDENCE, Box, check
from fenolite.placement import place as grid_place
from fenolite.placement.codes import issue
from fenolite.placement.constrained import EVIDENCE as CONSTRAINED_EVIDENCE
from fenolite.placement.constrained import PlacementProposal, propose_placement
from fenolite.placement.constraints import PlacementConstraints, PlacementRequest
from fenolite.placement.grid import DEFAULT_GAP, DEFAULT_MARGIN, DEFAULT_PITCH
from fenolite.placement.legality import forbids_footprints
from fenolite.placement.preview import placement_preview

HELP = "place staged parts on the board in a grid, or move named parts (edits the board)"
STRATEGIES = ("grid", "manual", "constrained", "regions", "reuse", "group")
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
        help="grid (default): place every part that is off the board; manual: only the --move parts; "
        "regions: each domain of parts in its own region of the board; reuse: copy a block of --from; "
        "group: turn or shift parts with their copper",
    )
    parser.add_argument(
        "--move",
        action="append",
        default=[],
        metavar="REF=X,Y[,ROT[,SIDE]]",
        help="move one part (repeatable; implies --strategy manual): lengths with a unit, from the top-left "
        "corner of the outline, Y down; ROT in degrees; SIDE top or bottom",
    )
    parser.add_argument(
        "--only",
        default=None,
        metavar="REF,REF",
        help="grid, regions: place only these parts; reuse: the parts of the block",
    )
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
        "--constraints", default=None, metavar="FILE", help="constrained: integer JSON request"
    )
    parser.add_argument(
        "--max-candidates", type=int, default=None, help="constrained: bounded candidates per part"
    )
    parser.add_argument(
        "--preview-dir", default=None, metavar="DIR", help="constrained: write both copper SVG views"
    )
    parser.add_argument(
        "--barrier",
        action="append",
        default=[],
        metavar="REF[,REF...]",
        help="regions: parts (isolators, transformers) that separate the domains; each is placed across "
        "the boundary between the two regions it joins (repeatable)",
    )
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        metavar="NAME=GLOB[,GLOB...]",
        help="regions: a domain of the parts whose reference matches a glob, in band order (repeatable; "
        "default: the islands of nets once the --barrier parts are removed)",
    )
    parser.add_argument(
        "--region",
        action="append",
        default=[],
        metavar="NAME=X1,Y1,X2,Y2",
        help="regions: the rectangle of the group NAME, lengths with a unit from the top-left corner of "
        "the outline, Y down (repeatable; default: one band of the outline per domain)",
    )
    parser.add_argument(
        "--split",
        choices=("x", "y"),
        default=None,
        help="regions: the axis along which the default bands follow each other (default: the longer side)",
    )
    place_reuse.register(parser)
    place_group.register(parser)
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


@dataclass(frozen=True, slots=True)
class _Packing:
    """What the grid and the regions pack around: each footprint's box relative to its position (``path``
    the footprint id), the courtyard boxes of the parts that stay, and the cut-outs."""

    boxes: dict[str, Box]
    occupied: list[BBox]
    cutouts: list[BBox]


def _packing(
    design: Design,
    extents: Sequence[PlacedExtent],
    staged: Sequence[FootprintInstance],
    cutout_rings: Sequence[Sequence[Point]],
    forbidding: Sequence[Keepout],
    stays: set[str],
) -> _Packing:
    """The boxes of every footprint, the courtyard boxes of the footprints of ``stays`` on the faces that
    the staged parts use, and the cut-outs with the box of every rule area that forbids footprints."""
    assert design.board is not None
    known = {e.footprint_id: e for e in extents}
    boxes: dict[str, Box] = {}
    for fp in design.board.footprints:
        extent = known[fp.id]
        box = _box((*extent.front, *extent.back)) or BBox.of_points([fp.position])
        relative = BBox(
            box.x0 - fp.position.x, box.y0 - fp.position.y, box.x1 - fp.position.x, box.y1 - fp.position.y
        )
        boxes[fp.id] = Box(fp.id, footprint_ref(design, fp), relative)
    faces = {face for fp in staged for face in ("front", "back") if getattr(known[fp.id], face)}
    occupied: list[BBox] = []
    for fp in design.board.footprints:
        if fp.id in stays:
            for face in sorted(faces):
                occupied += [BBox.of_points(ring) for ring in getattr(known[fp.id], face)]
    cutouts = [BBox.of_points(ring) for ring in cutout_rings]
    # the box of every rule area that forbids footprints is avoided like a cut-out (change c0113)
    cutouts += [BBox.of_points(area.outline) for area in forbidding]
    return _Packing(boxes, occupied, cutouts)


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


def _constraints(
    args: argparse.Namespace, ctx: Context, pitch: int, gap: int, margin: int
) -> PlacementRequest:
    request = PlacementRequest(constraints=PlacementConstraints(pitch=pitch, gap=gap, edge_clearance=margin))
    if args.constraints is not None:
        path = Path(args.constraints)
        path = path if path.is_absolute() else ctx.cwd / path
        try:
            raw = path.read_bytes()
            data = json.loads(raw)
            if (
                not isinstance(data, dict)
                or cast(dict[str, Any], data).get("schema") != "fenolite.placement-request.v0"
            ):
                raise ValueError("constraints need explicit schema fenolite.placement-request.v0")
            request = canonical.loads(raw.decode("utf-8"), PlacementRequest, file=path.name)
        except (OSError, UnicodeError, ValueError, FormatError) as error:
            raise CliError("FEN-3004", f"{path.name}: {error}", where=path.name) from None
        request = replace(
            request,
            constraints=replace(
                request.constraints,
                source_hashes=(
                    *request.constraints.source_hashes,
                    (path.name, hashlib.sha256(raw).hexdigest()),
                ),
            ),
        )
    changes = {}
    if args.max_candidates is not None:
        changes["max_candidates"] = args.max_candidates
    for name, given, value in (
        ("pitch", args.pitch, pitch),
        ("gap", args.gap, gap),
        ("edge_clearance", args.margin, margin),
    ):
        if given is not None:
            changes[name] = value
    try:
        return replace(request, constraints=replace(request.constraints, **changes))
    except ValueError as error:
        raise CliError("FEN-2001", str(error)) from None


def _proposal_json(proposal: PlacementProposal) -> dict[str, Any]:
    return {
        "source_sha256": proposal.source_sha256,
        "request_sha256": proposal.request_sha256,
        "constraints": canonical.to_data(proposal.constraints),
        "selected": list(proposal.selected),
        "candidate_counts": dict(proposal.candidate_counts),
        "positions": canonical.to_data(proposal.positions),
        "unplaced": canonical.to_data(proposal.unplaced),
        "objectives": canonical.to_data(proposal.objectives),
        "hard_findings": list(proposal.legality.hard),
        "missing_inputs": list(proposal.legality.missing_inputs),
        "intrinsic": canonical.to_data(proposal.intrinsic),
        "assessment": canonical.to_data(proposal.assessment),
        "objective_metric": "pad-centre Euclidean distance rounded up in nm; routing not run",
    }


def _query_outline(design: Design) -> Design:
    """Lift the exact queried edge rings for analysis only; never add duplicate source edge records."""
    rings = board_outline(design).rings
    if design.board is None or not rings:
        return design
    return replace(
        design,
        board=replace(
            design.board,
            outline=Outline(
                id=derived_id("out", "placement", "queried-outline"),
                points=rings[0],
                cutouts=tuple(rings[1:]),
            ),
        ),
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    moves = [parse_move(text) for text in args.move]
    strategy = args.strategy or (
        "manual"
        if moves
        else "reuse"
        if args.source is not None
        else "group"
        if place_group.implied(args)
        else "grid"
    )
    if moves and strategy != "manual":
        raise CliError("FEN-2001", "--move needs --strategy manual", where="--move", hint="drop --strategy")
    if args.only is not None and strategy not in ("grid", "constrained", "regions", "reuse"):
        raise CliError("FEN-2001", "--only narrows the grid strategy", where="--only", hint="drop --only")
    if strategy == "constrained" and args.force:
        raise CliError("FEN-2001", "constrained placement cannot use --force", where="--force")
    if strategy != "constrained" and any(
        value is not None for value in (args.constraints, args.max_candidates, args.preview_dir)
    ):
        raise CliError(
            "FEN-2001", "--constraints, --max-candidates and --preview-dir need --strategy constrained"
        )
    region_options = parse_options(args)
    if region_options.given and strategy != "regions":
        raise CliError("FEN-2001", "--barrier, --group, --region and --split need --strategy regions")
    if strategy != "reuse" and (args.source is not None or place_reuse.given(args)):
        raise CliError(
            "FEN-2001", "--from, --anchor, --map, --copper, --tolerance and --drc need --strategy reuse"
        )
    reuse_options = place_reuse.options(args) if strategy == "reuse" else None
    if strategy != "group" and place_group.given(args):
        raise CliError(
            "FEN-2001",
            "--turn, --about, --angle, --shift, --by, --pose-search and --within need --strategy group",
        )
    group_options = place_group.options(args) if strategy == "group" else None
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
    proposal: PlacementProposal | None = None
    region_plan: RegionPlan | None = None
    reuse_plan: place_reuse.ReusePlan | None = None
    group_plan: place_group.GroupPlan | None = None

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

    if strategy == "constrained":
        request = _constraints(args, ctx, pitch, gap, margin)
        locked_paths = _script_locked(_cache(board_path.parent))
        design = replace(
            design,
            board=replace(
                design.board,
                footprints=tuple(
                    replace(fp, locked=True) if paths[fp.id] in locked_paths else fp
                    for fp in design.board.footprints
                ),
            ),
        )
        rule_source = backend.design_rules(design, project_set(board_path))
        # File rules/class assignments supplement the board without changing the user's topology.
        design = replace(design, circuit=rule_source.design.circuit, rules=rule_source.design.rules)
        assert design.board is not None
        if args.only is None:
            chosen = {fp.id for fp in design.board.footprints if off_board(fp)}
        else:
            wanted = {ref.strip() for ref in args.only.split(",") if ref.strip()}
            for ref in sorted(wanted - set(before)):
                issues.append(issue("place.unknown-ref", f"the board has no part {ref}", ref))
            chosen = {before[ref].id for ref in wanted if ref in before}
        try:
            proposal = propose_placement(
                _query_outline(design),
                backend,
                sorted(chosen),
                constraints=request.constraints,
                objectives=request.objectives,
                rules=rule_source,
                checker=check_placement_constraints,
            )
        except ValueError as error:
            raise CliError("FEN-3004", f"placement request: {error}", where="--constraints") from None
        for identity, at in proposal.positions:
            fp = next(fp for fp in design.board.footprints if fp.id == identity)
            move(fp, at, None, None)
        issues += [issue("place.constraint", reason, "board") for reason in proposal.legality.hard]
        issues += [f.to_issue() for f in proposal.intrinsic]
        issues += [issue("place.incomplete", reason, "board") for reason in proposal.legality.missing_inputs]
        for unplaced in proposal.unplaced:
            ref = footprint_ref(
                design, next(fp for fp in design.board.footprints if fp.id == unplaced.footprint_id)
            )
            issues.append(issue("place.no-room", "; ".join(unplaced.reasons), ref))
        for objective in proposal.objectives:
            if objective.status != "met":
                issues.append(
                    issue(
                        "place.objective",
                        f"{objective.key}: {objective.status} {objective.reason}",
                        objective.key,
                    )
                )
    elif reuse_options is not None:
        reuse_plan = place_reuse.plan_reuse(
            reuse_options, ctx, design, board_path, definitions=definitions.found, need=definitions.need
        )
        design = reuse_plan.design
        assert design.board is not None
        moved_ids.extend(reuse_plan.moved)
        issues += reuse_plan.issues
    elif group_options is not None:
        group_plan = place_group.plan_group(
            group_options,
            design,
            board_path,
            origin=origin,
            pitch=pitch,
            definitions=definitions.found,
            need=definitions.need,
            force=bool(args.force),
        )
        design = group_plan.design
        assert design.board is not None
        moved_ids.extend(group_plan.moved)
        issues += group_plan.issues
    elif strategy == "manual":
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
        staged_ids = {fp.id for fp in staged}
        by_id = {fp.id: fp for fp in staged}
        if staged and region is not None:
            stays = {fp.id for fp in design.board.footprints if fp.id not in staged_ids and not off_board(fp)}
            packing = _packing(
                design, backend.placed_extents(design), staged, outline.rings[1:], forbidding, stays
            )
            if strategy == "regions":
                region_plan = plan_regions(
                    design,
                    region_options,
                    outline=region,
                    refs={fp.id: footprint_ref(design, fp) for fp in design.board.footprints},
                    boxes=packing.boxes,
                    staged=staged,
                    occupied=packing.occupied,
                    cutouts=packing.cutouts,
                    pitch=pitch,
                    gap=gap,
                    margin=margin,
                )
                issues += region_plan.issues
                positions = dict(region_plan.result.positions)
                unplaced_ids: tuple[str, ...] = ()
            else:
                packed = grid_place(
                    [packing.boxes[fp.id] for fp in staged],
                    region,
                    occupied=packing.occupied,
                    cutouts=packing.cutouts,
                    pitch=pitch,
                    gap=gap,
                    margin=margin,
                )
                positions, unplaced_ids = dict(packed.positions), packed.unplaced
            for fp in staged:
                if fp.id in positions:
                    move(fp, positions[fp.id], None, None)
            for fp_id in unplaced_ids:
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
    crossing_rows: list[dict[str, Any]] = []
    crossing_evidence: list[Evidence] = []
    if region_plan is not None:
        crossing_rows, found_crossings, found_evidence = region_crossings(region_plan, design, pads_after)
        issues += found_crossings
        crossing_evidence.append(found_evidence)
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
        stayed = original if group_plan is None else place_group.without(original, group_plan.copper)
        left = _copper_left(stayed, pads_before, moved)
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
    copied = reuse_plan is not None and reuse_plan.copied
    if (moved or copied) and not refused:
        text = kicad_pcb.write_board(design, target=major, allow_lossy=ctx.allow_lossy).text
        if args.out is not None:
            target = str(args.out)
        else:
            try:
                target = str(board_path.relative_to(ctx.cwd))
            except ValueError:
                target = str(board_path)
        grown = (
            place_reuse.run_drc(reuse_plan, board_path, text.encode("utf-8"))
            if reuse_plan is not None and reuse_options is not None and reuse_options.drc
            else []
        )
        issues += grown
        if not grown:
            writes = (PlannedWrite(path=target, data=text.encode("utf-8"), kind="kicad_pcb"),)
    if proposal is not None and args.preview_dir is not None and not refused:
        if writes:
            written = _query_outline(
                kicad_pcb.read_board(writes[0].data.decode("utf-8"), file=board_path.name)
            )
            preview_sha = hashlib.sha256(writes[0].data).hexdigest()
        else:
            written = _query_outline(kicad_pcb.read_board(board_path))
            preview_sha = hashlib.sha256(data).hexdigest()
        writes += tuple(
            PlannedWrite(
                path=str(Path(args.preview_dir) / f"placement-{face}.svg"),
                data=placement_preview(written, backend, face=face).encode(),
                kind="svg",
            )
            for face in SIDES
        )
        # A preview comes from the serialized board readback, not from the candidate envelope.
        preview_manifest = {"source_sha256": preview_sha, "source": "written/readback", "faces": list(SIDES)}
    else:
        preview_manifest = None
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
    if strategy == "regions":
        refs = {fp.id: ref for ref, fp in after.items()}
        result["regions"] = (
            None if region_plan is None else regions_json(region_plan, crossing_rows, origin, refs)
        )
    if reuse_plan is not None:
        result["reuse"] = place_reuse.to_json(reuse_plan)
    if group_plan is not None:
        result["group"] = place_group.to_json(group_plan)
    if proposal is not None:
        result["placement"] = _proposal_json(proposal)
        result["preview"] = preview_manifest
    issues.sort(key=lambda found: (found.code, found.where))
    evidence = [EVIDENCE]
    if forbidding:
        evidence.append(KEEPOUT_EVIDENCE)
    if rules_judged:
        evidence.append(placement_rules.EVIDENCE)
    if region_plan is not None:
        evidence += [*region_evidence(region_plan), *crossing_evidence]
    if reuse_plan is not None:
        evidence.append(reuse_plan.evidence)
    if group_plan is not None:
        evidence.append(group_plan.evidence)
    if proposal is not None:
        evidence += [CONSTRAINED_EVIDENCE, Evidence(Level.INFERRED, hypotheses=("H-G-PLACEMENT-PREVIEW",))]
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
