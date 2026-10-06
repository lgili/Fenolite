# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place PATH``: staged parts placed on the board in a deterministic grid, or named parts moved
(capability cli-contract, "Place command"; ``docs/placement.md``; ``docs/cli-contract.md``, "place").

The command reads the board, moves footprints with ``backends.kicad.replace.move_footprint``, judges the
resulting layout with ``placement.legality.check`` and plans one write: the board. It runs no tool. An
illegal placement is not written unless ``--force`` is given; KiCad's DRC stays the judge of the board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

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
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import board_format
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.cli.placement_checks import check_placement_constraints
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, Udeg, parse_angle, parse_length
from fenolite.geometry import BBox
from fenolite.model import canonical
from fenolite.model.board import FootprintInstance, Outline, Side
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.placement import EVIDENCE, Box, check
from fenolite.placement import place as grid_place
from fenolite.placement.codes import issue
from fenolite.placement.constrained import EVIDENCE as CONSTRAINED_EVIDENCE
from fenolite.placement.constrained import PlacementProposal, propose_placement
from fenolite.placement.constraints import PlacementConstraints, PlacementRequest
from fenolite.placement.grid import DEFAULT_GAP, DEFAULT_MARGIN, DEFAULT_PITCH
from fenolite.placement.preview import placement_preview

HELP = "place staged parts on the board in a grid, or move named parts (edits the board)"
STRATEGIES = ("grid", "manual", "constrained")
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
        "--constraints", default=None, metavar="FILE", help="constrained: integer JSON request"
    )
    parser.add_argument(
        "--max-candidates", type=int, default=None, help="constrained: bounded candidates per part"
    )
    parser.add_argument(
        "--preview-dir", default=None, metavar="DIR", help="constrained: write both copper SVG views"
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


def _script_locked(folder: Path) -> set[str]:
    """The component paths whose placement is locked in ``.fenolite/`` (empty without a readable cache)."""
    try:
        cached = canonical.load_dir(folder / CACHE_DIR)
    except (FenoliteError, OSError, ValueError):
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
    strategy = args.strategy or ("manual" if moves else "grid")
    if moves and strategy != "manual":
        raise CliError("FEN-2001", "--move needs --strategy manual", where="--move", hint="drop --strategy")
    if args.only is not None and strategy not in ("grid", "constrained"):
        raise CliError("FEN-2001", "--only narrows the grid strategy", where="--only", hint="drop --only")
    if strategy == "constrained" and args.force:
        raise CliError("FEN-2001", "constrained placement cannot use --force", where="--force")
    if strategy != "constrained" and any(
        value is not None for value in (args.constraints, args.max_candidates, args.preview_dir)
    ):
        raise CliError(
            "FEN-2001", "--constraints, --max-candidates and --preview-dir need --strategy constrained"
        )
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
    region = BBox.of_points(outline.rings[0]) if outline.rings else None
    origin = Point(region.x0, region.y0) if region is not None else Point(0, 0)
    before = _by_ref(design)
    paths = _paths(design)
    issues: list[Issue] = [found for found in reader_issues if found.severity != "info"]
    definitions = _Definitions(board_path.parent, major)
    moved_ids: list[str] = []
    proposal: PlacementProposal | None = None

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
        locked_paths = _script_locked(board_path.parent)
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
    legality = check(extents, outline.rings, names=names)
    issues += legality
    if moved:
        original = kicad_pcb.read_board(board_path)
        left = _copper_left(original, backend.board_pads(original), moved)
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
        locked = _script_locked(board_path.parent)
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
    }
    if proposal is not None:
        result["placement"] = _proposal_json(proposal)
        result["preview"] = preview_manifest
    issues.sort(key=lambda found: (found.code, found.where))
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=Evidence.combine(
            EVIDENCE, CONSTRAINED_EVIDENCE, Evidence(Level.INFERRED, hypotheses=("H-G-PLACEMENT-PREVIEW",))
        )
        if proposal is not None
        else EVIDENCE,
        input=InputRef(
            path=board_path.name,
            sha256=hashlib.sha256(data).hexdigest(),
            kind="kicad_pcb",
            format_version=None if version_number is None else str(version_number),
        ),
        writes=writes,
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
