# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board adapters and exact review for the placement search."""

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast

from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.projectset import project_set
from fenolite.cli.api import Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.cli.placement_capacity import placement_capacity
from fenolite.cli.placement_checks import check_placement_constraints
from fenolite.cli.placement_probes import probe_placement_intents
from fenolite.cli.placement_protection import inspect_attachments
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.geometry import BBox, ceil_sqrt
from fenolite.model import canonical
from fenolite.model.base import Entity
from fenolite.model.board import Board, Outline, OutlineArc, rule_areas
from fenolite.model.design import Design
from fenolite.placement.domains import pads_near_anchor, sample_domain
from fenolite.placement.intent import probe_intent_legs, resolve_intents
from fenolite.placement.legality import outline_rings
from fenolite.placement.optimization_contract import (
    OptimizationCandidate,
    OptimizationRequest,
    PadProbe,
    PlacementOptimization,
    ProposedPose,
    candidate_id,
)
from fenolite.placement.optimize import PoseSet, SearchJudgment, beam_search
from fenolite.placement.pose_projection import project_poses
from fenolite.placement.protection import placement_scope
from fenolite.placement.refine import refine_placement
from fenolite.placement.topology import PadIdentity


def propose(
    design: Design,
    path: Path,
    request: OptimizationRequest,
    source_locks: frozenset[str],
    *,
    frame: BoardFrame | None = None,
    design_rules: DesignRules | None = None,
    review: OptimizationCandidate | None = None,
    expected_fingerprint: str | None = None,
    additional_blockers: tuple[str, ...] = (),
) -> PlacementOptimization:
    """Check actual transformed geometry and return only a proposal, with no write plan."""
    board = design.board
    if board is None or board.outline is None or not board.outline.points:
        raise ValueError("optimization requires a closed board outline")
    backend = frame if frame is not None else KicadBackend()
    rules = (
        design_rules if design_rules is not None else KicadBackend().design_rules(design, project_set(path))
    )
    design = replace(design, circuit=rules.design.circuit, rules=rules.design.rules)
    pads = backend.board_pads(design)
    constraints = request.constraints
    scope = placement_scope(
        board,
        request.selected,
        constraints,
        source_locks=source_locks,
        attachments=inspect_attachments(design, pads, request.selected),
    )
    resolved = resolve_intents(
        request.intent,
        available_pads=frozenset(PadIdentity(p.footprint_id, p.pad_id) for p in pads),
    )
    unresolved = additional_blockers + tuple(
        f"intent:{row.key}:{row.problem}" for row in resolved if row.problem is not None
    )
    intents = tuple(row.effective for row in resolved if row.effective is not None)
    escapes = tuple(row for row in intents if probe_intent_legs(row))
    legs = tuple(leg for row in escapes for leg in probe_intent_legs(row))
    if len({row.key for row in legs}) != len(legs):
        raise ValueError("routing probe keys must be distinct after expanding gate loops")
    unknown = tuple(
        f"intent:{row.key}:unsupported"
        for row in intents
        if not (row.kind == "proximity" and len(row.endpoints) == 2) and row not in escapes
    )
    rings = tuple(tuple(ring) for ring in outline_rings(board.outline))
    bounds = BBox.of_points(rings[0])
    allowed = {row.footprint_id: row.rotations for row in request.rotations}
    parts = {fp.id: fp for fp in board.footprints}
    fixed = dict(scope.fixed)
    initial_pads = {PadIdentity(p.footprint_id, p.pad_id): p.position for p in pads}
    fixed_extents = (
        {
            row.footprint_id: BBox.of_points(points)
            for row in backend.placed_extents(design)
            if row.footprint_id in fixed
            and (points := tuple(point for ring in (*row.front, *row.back) for point in ring))
        }
        if intents
        else {}
    )
    near: dict[str, list[tuple[PadIdentity, PadIdentity]]] = defaultdict(list)
    proximity = tuple(row for row in intents if row.kind == "proximity" and len(row.endpoints) == 2)
    for row in (*proximity, *legs):
        a, b = row.endpoints
        for local, anchor in ((a, b), (b, a)):
            if local.footprint_id not in fixed and anchor.footprint_id in fixed_extents:
                near[local.footprint_id].append((local, anchor))
    domains: dict[str, PoseSet] = {}
    sampled: dict[str, int] = {}
    truncated: list[str] = []
    for ident in scope.movable:
        fp = parts[ident]
        current = ProposedPose(ident, fp.position, fp.rotation % 360_000_000, fp.side)
        envelopes: dict[int, BBox] = {}
        seeds: dict[int, tuple[Point, ...]] = {}
        for angle in allowed.get(ident, (current.rotation,)):
            oriented = project_poses(design, scope, (replace(current, rotation=angle),))
            extent = next(
                extent for extent in backend.placed_extents(oriented) if extent.footprint_id == ident
            )
            points = tuple(point for ring in (*extent.front, *extent.back) for point in ring)
            if points:
                envelopes[angle] = BBox.of_points(
                    Point(p.x - fp.position.x, p.y - fp.position.y) for p in points
                )
                if near.get(ident):
                    local_pads = {
                        PadIdentity(p.footprint_id, p.pad_id): Point(
                            p.position.x - fp.position.x, p.position.y - fp.position.y
                        )
                        for p in backend.board_pads(oriented)
                        if p.footprint_id == ident
                    }
                    seeds[angle] = tuple(
                        dict.fromkeys(
                            seed
                            for local, anchor in near[ident]
                            if local in local_pads
                            for seed in pads_near_anchor(
                                initial_pads[anchor],
                                fixed_extents[anchor.footprint_id],
                                local_pads[local],
                                envelopes[angle],
                                constraints.gap,
                            )
                        )
                    )
        domain = sample_domain(
            current,
            bounds,
            envelopes,
            constraints,
            oriented_anchors=seeds,
            max_attempts=constraints.max_candidates,
        )
        domains[ident] = domain.poses
        sampled[ident] = domain.attempts
        if domain.exhausted:
            truncated.append(ident)

    # Proposal identity binds the scorer's inputs. The write plan also binds the source files.
    fingerprint = hashlib.sha256(canonical.dumps((design, request, scope, rules)).encode()).hexdigest()
    mandatory_mechanical = bool(
        constraints.reservations or constraints.volumes != type(constraints.volumes)()
    )
    candidate_missing: dict[PoseSet, tuple[str, ...]] = {}
    candidate_channels: dict[PoseSet, dict[str, int]] = {}
    candidate_probes: dict[PoseSet, tuple[PadProbe, ...]] = {}

    def judge(poses: PoseSet, complete: bool) -> SearchJudgment:
        moved = project_poses(design, scope, poses)
        assert moved.board is not None
        active = set(parts) - set(scope.movable)
        active.update(pose.footprint_id for pose in poses)
        checked = replace(
            moved,
            board=replace(
                moved.board, footprints=tuple(fp for fp in moved.board.footprints if fp.id in active)
            ),
        )
        legality = check_placement_constraints(checked, backend, constraints, rules=rules)
        missing = legality.missing_inputs
        if complete:
            candidate_missing[poses] = missing
        # No assembly limits were supplied in a geometry-only request. Still expose unavailable
        # mechanical evidence and conservative pad hulls on every reported candidate.
        optional: set[str] = set(legality.mechanical.missing_inputs) if not mandatory_mechanical else set()
        required_missing = tuple(
            item for item in missing if item not in optional and not item.endswith(":conservative")
        )
        checked_pads = backend.board_pads(checked)
        positions = {PadIdentity(p.footprint_id, p.pad_id): p.position for p in checked_pads}
        by_net: dict[str, list[Point]] = defaultdict(list)
        for pad in checked_pads:
            if pad.net_id is not None and pad.kind != "np_thru_hole":
                by_net[pad.net_id].append(pad.position)
        boxes = (BBox.of_points(points) for points in by_net.values() if len(points) > 1)
        hpwl = sum(box.width + box.height for box in boxes)
        distances = 0
        hard = list(legality.hard)
        hard.extend(f"{item.code}:{item.where}" for item in legality.intrinsic)
        for row in proximity:
            first, second = (positions.get(pad) for pad in row.endpoints)
            if first is None or second is None:
                if complete and row.required:
                    hard.append(f"intent:{row.key}:missing_endpoint")
                continue
            distance = ceil_sqrt((first.x - second.x) ** 2 + (first.y - second.y) ** 2)
            distances += distance
            if row.required and row.max_distance_nm is not None and distance > row.max_distance_nm:
                hard.append(f"intent:{row.key}:distance")
        displacement = sum(
            abs(pose.position.x - parts[pose.footprint_id].position.x)
            + abs(pose.position.y - parts[pose.footprint_id].position.y)
            for pose in poses
        )
        if complete and not hard and not required_missing:
            capacity = placement_capacity(checked, rules, checked_pads, rings, frozenset(scope.movable))
            candidate_missing[poses] += capacity.unknown
            candidate_channels[poses] = dict(capacity.by_layer)
            pressure = len(capacity.unknown), capacity.overflow_nm
        else:
            pressure = (0, 0)
        return SearchJudgment((distances, *pressure, hpwl, displacement), tuple(hard), required_missing)

    score_fields = (
        "reviewed_pad_distances_nm",
        "unknown_capacity_inputs",
        "channel_overflow_nm",
        "pad_hpwl_nm",
        "movement_manhattan_nm",
    )
    if escapes:
        score_fields += ("probe_track_length_nm",)

    refinement_reserve = min(8, request.budget.evaluations // 4) if escapes else 0
    probe_slots = request.budget.beam_width + refinement_reserve

    def check_probes(poses: PoseSet) -> tuple[tuple[int, ...], tuple[str, ...]]:
        if not escapes:
            return (), ()
        projected = project_poses(design, scope, poses)
        per_subject = request.budget.probe_expansions // (probe_slots * len(legs))
        checks = probe_placement_intents(
            projected,
            rules,
            backend.board_pads(projected),
            rings,
            escapes,
            max_states=per_subject,
            pitch=constraints.pitch,
        )
        candidate_probes[poses] = checks
        failures = tuple(f"probe:{row.key}:{row.status}" for row in checks if row.status != "found")
        return (sum(row.length_nm or 0 for row in checks),), failures

    def candidate(ident: str, poses: PoseSet, score: tuple[int, ...]) -> OptimizationCandidate:
        return OptimizationCandidate(
            ident,
            poses,
            score,
            candidate_missing[poses],
            candidate_channels.get(poses, {}),
            candidate_probes.get(poses, ()),
        )

    if review is not None:
        if expected_fingerprint != fingerprint:
            raise CliError("FEN-4002", "placement inputs changed after the proposal")
        poses = tuple(sorted(review.poses, key=lambda pose: pose.footprint_id))
        if (
            len(poses) != len(domains)
            or {p.footprint_id for p in poses} != set(domains)
            or any(p not in domains[p.footprint_id] for p in poses)
            or candidate_id(fingerprint, poses) != review.id
        ):
            raise CliError("FEN-3004", "candidate identity or scoped poses do not match the request")
        judged = judge(poses, True)
        failures = (*unresolved, *unknown, *judged.hard, *judged.missing_inputs)
        if failures:
            raise CliError("FEN-3004", "candidate did not pass review: " + "; ".join(failures[:8]))
        probe_score, probe_failures = check_probes(poses)
        if probe_failures:
            raise CliError("FEN-3004", "candidate did not pass review: " + "; ".join(probe_failures[:8]))
        checked = candidate(review.id, poses, judged.score + probe_score)
        return PlacementOptimization(
            fingerprint,
            "complete",
            candidates=(checked,),
            score_fields=score_fields,
            fixed=dict(scope.fixed),
            movable=scope.movable,
            work=1,
        )
    search = (
        None
        if not domains or unresolved or unknown
        else beam_search(
            domains,
            input_sha256=fingerprint,
            budget=replace(request.budget, evaluations=request.budget.evaluations - refinement_reserve),
            judge=judge,
        )
    )
    checked_candidates: list[OptimizationCandidate] = []
    probe_blockers: set[str] = set()
    checks_by_pose: dict[PoseSet, tuple[tuple[int, ...], tuple[str, ...]]] = {}
    for row in search.candidates if search is not None else ():
        poses = row.candidate.poses
        probe_score, failures = check_probes(poses)
        checks_by_pose[poses] = probe_score, failures
        if failures:
            probe_blockers.update(failures)
            continue
        checked_candidates.append(candidate(row.candidate.id, poses, row.score + probe_score))
    refine_work = 0
    refine_exhausted = False
    if (
        search is not None
        and search.candidates
        and probe_blockers
        and not checked_candidates
        and refinement_reserve
    ):
        seed = search.candidates[0]
        windows = tuple(
            tuple(sorted({pad.footprint_id for pad in row.endpoints if pad.footprint_id in domains}))
            for row in escapes
        )

        def feedback(poses: PoseSet, complete: bool) -> SearchJudgment:
            assessed = judge(poses, complete)
            if assessed.hard or assessed.missing_inputs:
                return assessed
            if poses not in checks_by_pose:
                checks_by_pose[poses] = check_probes(poses)
            probe_score, failures = checks_by_pose[poses]
            probe_blockers.update(failures)
            return SearchJudgment((len(failures), *assessed.score, *probe_score))

        refined = refine_placement(
            seed.candidate.poses,
            domains,
            input_sha256=fingerprint,
            judge=feedback,
            max_attempts=refinement_reserve,
            step_nm=2 * constraints.pitch,
            windows=tuple(window for window in windows if len(window) >= 2),
        )
        refine_work = refined.work
        refine_exhausted = refined.termination == "budget_exhausted"
        if refined.best is not None and refined.best.score[0] == 0:
            found = refined.best
            checked_candidates.append(candidate(found.candidate.id, found.candidate.poses, found.score[1:]))
    checked_candidates.sort(key=lambda row: row.score)
    return PlacementOptimization(
        input_sha256=fingerprint,
        fixed=dict(scope.fixed),
        movable=scope.movable,
        sampled=sampled,
        domain_truncated=tuple(truncated),
        intent=resolved,
        score_fields=score_fields,
        termination=(
            "budget_exhausted"
            if refine_exhausted
            else search.termination
            if search is not None
            else "missing_inputs"
            if unresolved or unknown
            else "complete"
        ),
        work=(search.work if search is not None else 0) + refine_work,
        beam_pruned=search.beam_pruned if search is not None else False,
        blockers=(
            tuple(sorted(set(search.blockers) | probe_blockers))
            if search is not None
            else (*unresolved, *unknown)
        ),
        unplaced=search.unplaced
        if search is not None and not probe_blockers
        else (() if checked_candidates else scope.movable),
        partial=search.partial if search is not None else (),
        candidates=tuple(checked_candidates),
    )


def verify_kicad_readback(projected: Design, reread: Design) -> None:
    """The serialized board must retain the checked placements, local copper and edge geometry."""
    from fenolite.backends.kicad.outline import board_outline

    backend = KicadBackend()
    first, second = projected.board, reread.board
    if first is None or second is None:
        raise ValueError("candidate readback has no board")

    def poses(board: Board) -> dict[str, tuple[Point, int, str, bool]]:
        return {f.id: (f.position, f.rotation % 360_000_000, f.side, f.locked) for f in board.footprints}

    def board_graphics(board: Board) -> tuple[tuple[object, ...], ...]:
        return tuple(
            (g.kind, g.layer, g.points, g.width, g.filled, g.net_id)
            for g in board.graphics
            if g.layer != "Edge.Cuts"
        )

    def copper_entities(items: Sequence[Entity]) -> dict[str, Entity]:
        return {item.id: replace(item, provenance=None) for item in items}

    if (
        poses(first) != poses(second)
        or backend.board_pads(projected) != backend.board_pads(reread)
        or backend.placed_extents(projected) != backend.placed_extents(reread)
        or board_outline(projected).rings != board_outline(reread).rings
        or copper_entities(rule_areas(first)) != copper_entities(rule_areas(second))
        or copper_entities((*first.tracks, *first.arcs, *first.vias, *first.zones))
        != copper_entities((*second.tracks, *second.arcs, *second.vias, *second.zones))
        or board_graphics(first) != board_graphics(second)
    ):
        raise ValueError("candidate readback changed the checked board geometry or connectivity")


def propose_altium(path: Path, request_path: Path) -> Result:
    """Run the placement search against Altium's own read model without opening a write session."""
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.altium.read.project import load_project

    backend = AltiumBackend()
    pcb = path
    if path.suffix.lower() == ".prjpcb":
        documents = load_project(path).documents
        boards = [item.file for item in documents if item.document.kind == "pcb" and item.present]
        if len(boards) != 1 or boards[0] is None:
            raise CliError(
                "FEN-3004", "choose a PcbDoc explicitly when the project has no unique readable board"
            )
        pcb = boards[0]
    data = pcb.read_bytes()
    read = backend.read(path) if path != pcb else backend.board_from_bytes(data, file=pcb.name)
    design = read.design
    if design.board is None:
        raise CliError("FEN-3004", "Altium input did not resolve a board")
    rings = backend.board_edges(design)
    if not rings:
        raise CliError("FEN-3004", "Altium optimization requires a closed board outline")
    outline = Outline(
        id=derived_id("out", "placement", "altium-query"),
        points=rings[0].points,
        cutouts=tuple(ring.points for ring in rings[1:]),
        arcs=tuple(
            OutlineArc(i, j, mid)
            for i, ring in enumerate(rings)
            for j, mid in enumerate(ring.mids)
            if mid is not None
        ),
    )
    design = replace(design, board=replace(design.board, outline=outline))
    try:
        request = cast(
            OptimizationRequest,
            canonical.loads(
                request_path.read_text(encoding="utf-8"),
                OptimizationRequest,
                file=request_path.name,
            ),
        )
        rules = backend.rules_from_bytes(design, data, file=pcb.name)
        optimization = propose(
            design,
            pcb,
            request,
            frozenset(),
            frame=backend,
            design_rules=rules,
            additional_blockers=tuple(f"unmodeled_copper:{kind}" for kind, _, _ in rules.left_out),
        )
    except (OSError, UnicodeError, ValueError, FormatError) as error:
        raise CliError("FEN-3004", f"optimization request: {error}", where="--constraints") from None
    return Result(
        result={
            "board": pcb.name,
            "strategy": "optimize",
            "optimization": canonical.to_data(asdict(optimization)),
        },
        input=InputRef(pcb.name, hashlib.sha256(data).hexdigest(), "altium_pcbdoc", None),
        issues=tuple(issue for issue in read.issues if issue.severity != "info"),
        evidence=Evidence(Level.INFERRED, hypotheses=("H-G-CONSTRAINED-PLACE",)),
    )
