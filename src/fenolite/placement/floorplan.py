# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compose reviewed block layouts into physical placement domains."""

from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from itertools import combinations
from typing import Protocol

from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point
from fenolite.geometry import Transform
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import PortDirection, components_under
from fenolite.model.design import Design
from fenolite.placement.optimization_contract import OptimizationBudget, ProposedPose
from fenolite.placement.optimize import Judge, PoseSet, SearchJudgment, SearchResult, beam_search
from fenolite.placement.pose_projection import project_poses
from fenolite.placement.protection import PlacementScope
from fenolite.placement.regions import Axis, Region, boundary
from fenolite.placement.relative import dependency_cycles
from fenolite.placement.topology import PadIdentity, resolved_incidences


@dataclass(frozen=True, slots=True)
class BlockOrigin:
    position: Point
    rotation: int = 0


class LayoutPose(Protocol):
    @property
    def at(self) -> Point: ...
    @property
    def rotation(self) -> int: ...
    @property
    def side(self) -> str: ...


class CheckedLayout(Protocol):
    @property
    def status(self) -> str: ...
    @property
    def parts(self) -> Mapping[str, LayoutPose]: ...


@dataclass(frozen=True, slots=True)
class BlockRequest:
    instance: str
    layout: Callable[[Design, str, Transform], CheckedLayout]
    origins: tuple[BlockOrigin, ...]
    rigid: bool = True


@dataclass(frozen=True, slots=True)
class BlockPort:
    port: str
    member: str
    net_id: str
    direction: PortDirection
    kind: str
    pads: tuple[PadIdentity, ...]


@dataclass(frozen=True, slots=True)
class BoundBlock:
    instance: str
    footprints: tuple[str, ...]
    alternatives: tuple[PoseSet, ...]
    ports: tuple[BlockPort, ...]
    rigid: bool


def bind_blocks(
    design: Design,
    requests: tuple[BlockRequest, ...],
    *,
    fixed: frozenset[str] = frozenset(),
) -> tuple[BoundBlock, ...]:
    """Validate reuse digests, actual pad-net bindings and every fixed member at each origin."""
    board = design.board
    if board is None:
        raise ValueError("block placement needs board footprints")
    by_component: dict[str, list[FootprintInstance]] = defaultdict(list)
    for footprint in board.footprints:
        by_component[footprint.component_id].append(footprint)
    incidence = resolved_incidences(design.circuit, board.footprints)
    modules = {module.path: module for module in design.circuit.modules}
    locked = fixed | {fp.id for fp in board.footprints if fp.locked}
    claimed: set[str] = set()
    blocks: list[BoundBlock] = []
    for request in sorted(requests, key=lambda row: row.instance):
        instance = request.instance
        module = modules.get(instance)
        if module is None or not module.block or not module.block_version:
            raise ValueError(f"missing block instance: {instance}")
        members = components_under(design.circuit, instance)
        if not members or any(len(by_component[part.id]) != 1 for part in members.values()):
            raise ValueError(f"unresolved block footprints: {instance}")
        physical = {path: by_component[part.id][0] for path, part in members.items()}
        footprint_ids = {fp.id for fp in physical.values()}
        if claimed & footprint_ids:
            raise ValueError(f"shared block footprints: {instance}")
        claimed.update(footprint_ids)
        member_ids = {part.id for part in members.values()}
        terminals = [row for row in incidence if row.terminal.component_id in member_ids]
        if any(row.problem is not None for row in terminals):
            raise ValueError(f"stale physical pad-net bindings: {instance}")
        net_pads: dict[str, set[PadIdentity]] = defaultdict(set)
        for row in terminals:
            net_pads[row.net_id].update(row.pads)
        ports: list[BlockPort] = []
        for port in sorted(
            (port for port in design.circuit.ports if port.owner == module.id), key=lambda p: p.id
        ):
            if port.split or (not port.members and not port.optional):
                raise ValueError(f"unresolved block port: {instance}/{port.name}")
            for member, net in sorted(port.members.items()):
                if not net_pads[net]:
                    raise ValueError(f"unresolved block port member: {instance}/{port.name}.{member}")
                ports.append(
                    BlockPort(port.name, member, net, port.direction, port.kind, tuple(sorted(net_pads[net])))
                )
        alternatives: list[PoseSet] = []
        if not request.origins:
            raise ValueError(f"missing block origins: {instance}")
        for origin in sorted(set(request.origins), key=lambda item: (item.position, item.rotation)):
            if origin.rotation not in (0, 90_000_000, 180_000_000, 270_000_000):
                raise ValueError(f"unsupported block rotation: {instance}")
            applied = request.layout(
                design, instance, Transform.placement(origin.position, origin.rotation, False)
            )
            if applied.status not in ("applied", "older"):
                raise ValueError(f"block reuse {applied.status}: {instance}")
            poses: list[ProposedPose] = []
            for path, placed in applied.parts.items():
                footprint = physical[path]
                if placed.side != footprint.side or (
                    footprint.id in locked
                    and (
                        placed.at != footprint.position or placed.rotation != footprint.rotation % 360_000_000
                    )
                ):
                    break
                if footprint.id not in locked:
                    poses.append(ProposedPose(footprint.id, placed.at, placed.rotation, footprint.side))
            else:
                alternatives.append(tuple(sorted(poses, key=lambda pose: pose.footprint_id)))
        if not alternatives:
            raise ValueError(f"block origins conflict with fixed poses or sides: {instance}")
        blocks.append(
            BoundBlock(
                instance,
                tuple(sorted(footprint_ids - locked)),
                tuple(dict.fromkeys(alternatives)),
                tuple(ports),
                request.rigid,
            )
        )
    return tuple(blocks)


def search_block_placements(
    blocks: tuple[BoundBlock, ...],
    other_domains: Mapping[str, PoseSet],
    *,
    input_sha256: str,
    budget: OptimizationBudget,
    judge: Judge,
) -> SearchResult:
    """Search expanded blocks with the same whole-board judge as individual placement.

    A rigid block must retain one common block origin across all its assigned members.
    A flexible block supplies member seeds without fixing their relative transform.
    """
    domains = dict(other_domains)
    rigid: list[tuple[str, frozenset[str], tuple[frozenset[ProposedPose], ...]]] = []
    for block in blocks:
        members = frozenset(block.footprints)
        if members & domains.keys():
            raise ValueError(f"duplicate placement domains: {block.instance}")
        poses: dict[str, list[ProposedPose]] = defaultdict(list)
        for alternative in block.alternatives:
            for pose in alternative:
                poses[pose.footprint_id].append(pose)
        domains.update((key, tuple(dict.fromkeys(poses[key]))) for key in block.footprints)
        if block.rigid and members:
            rigid.append((block.instance, members, tuple(frozenset(row) for row in block.alternatives)))

    def check(poses: PoseSet, complete: bool) -> SearchJudgment:
        for instance, members, alternatives in rigid:
            assigned = {pose for pose in poses if pose.footprint_id in members}
            if assigned and not any(assigned <= option for option in alternatives):
                return SearchJudgment(hard=(f"block:{instance}:rigid-pose-conflict",))
        return judge(poses, complete)

    if not domains:
        raise ValueError("block placement needs at least one movable member or footprint")
    return beam_search(domains, input_sha256=input_sha256, budget=budget, judge=check)


@dataclass(frozen=True, slots=True)
class RegionPlan:
    assignments: dict[str, str]
    unplaced: tuple[str, ...]
    cut_weight: int
    reversed_direction_nm: int


@dataclass(frozen=True, slots=True)
class RegionPlans:
    hierarchy: RegionPlan
    coarsened: RegionPlan

    @property
    def best(self) -> RegionPlan:
        return min(
            (self.hierarchy, self.coarsened),
            key=lambda row: (len(row.unplaced), row.cut_weight, row.reversed_direction_nm),
        )


def plan_block_regions(
    blocks: tuple[BoundBlock, ...],
    regions: tuple[Region, ...],
    areas_nm2: Mapping[str, int],
    allowed_regions: Mapping[str, frozenset[str]],
    *,
    axis: Axis = "x",
) -> RegionPlans:
    """Compare individual hierarchy nodes with deterministic net-weighted coarsening.

    Region area is a coarse occupancy bound. A region choice still needs exact local
    containment and whole-board geometry checks.
    """
    ids = {block.instance for block in blocks}
    slots = {region.name: region.bbox for region in regions}
    if len(ids) != len(blocks) or len(slots) != len(regions) or not slots:
        raise ValueError("floorplanning needs distinct blocks and named regions")
    if set(areas_nm2) != ids or any(type(area) is not int or area <= 0 for area in areas_nm2.values()):
        raise ValueError("floorplanning needs a positive area for each block")
    if set(allowed_regions) - ids or any(set(keys) - slots.keys() for keys in allowed_regions.values()):
        raise ValueError("floorplanning region constraints refer to unknown blocks or regions")
    if any(box.width <= 0 or box.height <= 0 for box in slots.values()) or any(
        max(a.x0, b.x0) < min(a.x1, b.x1) and max(a.y0, b.y0) < min(a.y1, b.y1)
        for a, b in combinations(slots.values(), 2)
    ):
        raise ValueError("floorplanning needs positive regions without interior overlap")
    capacity = {name: box.width * box.height for name, box in slots.items()}
    centers = {
        name: (box.x0 + box.x1 if axis == "x" else box.y0 + box.y1) // 2 for name, box in slots.items()
    }
    allowed = {key: allowed_regions.get(key, frozenset(slots)) for key in ids}
    incident: dict[str, dict[str, set[PortDirection]]] = defaultdict(lambda: defaultdict(set))
    power: set[str] = set()
    for block in blocks:
        for port in block.ports:
            incident[port.net_id][block.instance].add(port.direction)
            if port.kind == "power":
                power.add(port.net_id)
    hyperedges: list[tuple[frozenset[str], int]] = []
    direction: dict[str, list[str]] = defaultdict(list)
    for net, members in sorted(incident.items()):
        if len(members) < 2:
            continue
        weight = max(1, 1024 // ((len(members) - 1) * (4 if net in power else 1)))
        hyperedges.append((frozenset(members), weight))
        drivers = [name for name, roles in members.items() if roles == {"out"}]
        sinks = [name for name, roles in members.items() if roles == {"in"}]
        if len(drivers) == 1 and len(sinks) + 1 == len(members):
            direction[drivers[0]].extend(sorted(sinks))

    feedback = dependency_cycles(sorted(ids), direction)
    cycle_of = {name: i for i, cycle in enumerate(feedback) for name in cycle}
    directed = tuple(
        (source, sink)
        for source, sinks in sorted(direction.items())
        for sink in sorted(set(sinks))
        if source not in cycle_of or cycle_of[source] != cycle_of.get(sink)
    )
    singles = tuple((key,) for key in sorted(ids))

    def compatible(cluster: tuple[str, ...]) -> frozenset[str]:
        first, *rest = cluster
        return allowed[first].intersection(*(allowed[name] for name in rest))

    def size(cluster: tuple[str, ...]) -> int:
        return sum(areas_nm2[name] for name in cluster)

    def fits(cluster: tuple[str, ...], free: Mapping[str, int]) -> tuple[str, ...]:
        return tuple(name for name in sorted(compatible(cluster)) if free[name] >= size(cluster))

    def cost(placed: Mapping[str, str]) -> tuple[int, int]:
        cut = sum(
            weight
            for members, weight in hyperedges
            if len({placed[name] for name in members if name in placed}) > 1
        )
        backward = sum(
            max(0, centers[placed[source]] - centers[placed[sink]])
            for source, sink in directed
            if source in placed and sink in placed
        )
        return cut, backward

    def pack(clusters: tuple[tuple[str, ...], ...]) -> RegionPlan:
        remaining = capacity.copy()
        assigned: dict[str, str] = {}
        queue = sorted(clusters, key=lambda cluster: (len(compatible(cluster)), -size(cluster), cluster))
        for cluster in queue:
            choices = fits(cluster, remaining)
            if not choices:
                if len(cluster) > 1:
                    queue.extend((key,) for key in cluster)
                continue
            best = min(
                choices,
                key=lambda name: (*cost(assigned | dict.fromkeys(cluster, name)), -remaining[name], name),
            )
            assigned.update(dict.fromkeys(cluster, best))
            remaining[best] -= size(cluster)
        return RegionPlan(
            dict(sorted(assigned.items())), tuple(sorted(ids - assigned.keys())), *cost(assigned)
        )

    groups: tuple[tuple[str, ...], ...] = tuple(
        tuple(cycle) for cycle in feedback if fits(tuple(cycle), capacity)
    )
    condensed = {name for group in groups for name in group}
    groups = tuple(sorted((*groups, *(group for group in singles if group[0] not in condensed))))
    while True:
        unused = list(groups)
        next_level: list[tuple[str, ...]] = []
        while unused:
            group = unused.pop(0)
            own = frozenset(group)
            partners: list[tuple[int, tuple[str, ...], tuple[str, ...]]] = []
            for partner in unused:
                other = frozenset(partner)
                affinity = sum(weight for members, weight in hyperedges if members & own and members & other)
                combined = tuple(sorted((*group, *partner)))
                if affinity and fits(combined, capacity):
                    partners.append((-affinity, partner, combined))
            if partners:
                _, partner, group = min(partners)
                unused.remove(partner)
            next_level.append(group)
        if len(next_level) == len(groups):
            break
        groups = tuple(sorted(next_level))
    return RegionPlans(pack(singles), pack(groups))


@dataclass(frozen=True, slots=True)
class RegionPlacement:
    assignments: dict[str, str]
    search: SearchResult | None
    attempts: int
    work: int
    blockers: tuple[str, ...]


def search_region_placements(
    design: Design,
    frame: BoardFrame,
    blocks: tuple[BoundBlock, ...],
    regions: tuple[Region, ...],
    areas_nm2: Mapping[str, int],
    allowed_regions: Mapping[str, frozenset[str]],
    other_domains: Mapping[str, PoseSet],
    *,
    input_sha256: str,
    budget: OptimizationBudget,
    judge: Judge,
) -> RegionPlacement:
    """Expand region choices and try bounded reassignments across shared boundaries."""
    plans = plan_block_regions(blocks, regions, areas_nm2, allowed_regions)
    slots = {region.name: region.bbox for region in regions}
    ids = {block.instance for block in blocks}
    eligible = {key: allowed_regions.get(key, frozenset(slots)) for key in ids}
    if design.board is None:
        raise ValueError("region search needs a board")
    scope = PlacementScope(tuple(sorted({key for block in blocks for key in block.footprints})), ())
    attempts, work = 0, 0
    failures: set[str] = set()

    def variations(assigned: dict[str, str]) -> Iterator[dict[str, str]]:
        yield assigned
        used = {name: sum(areas_nm2[key] for key, slot in assigned.items() if slot == name) for name in slots}
        for key, prior in sorted(assigned.items()):
            for name in sorted(eligible[key] - {prior}):
                box = slots[name]
                if (
                    boundary(slots[prior], box) is not None
                    and used[name] + areas_nm2[key] <= box.width * box.height
                ):
                    yield assigned | {key: name}
        for (first, left), (second, right) in combinations(sorted(assigned.items()), 2):
            if left == right or right not in eligible[first] or left not in eligible[second]:
                continue
            a, b = slots[left], slots[right]
            if (
                boundary(a, b) is not None
                and used[left] - areas_nm2[first] + areas_nm2[second] <= a.width * a.height
                and used[right] - areas_nm2[second] + areas_nm2[first] <= b.width * b.height
            ):
                yield assigned | {first: right, second: left}

    def fit(block: BoundBlock, region: str) -> BoundBlock:
        bbox = slots[region]
        options: list[PoseSet] = []
        for alternative in block.alternatives:
            projected = project_poses(design, scope, alternative)
            extents = {
                row.footprint_id: tuple(point for ring in (*row.front, *row.back) for point in ring)
                for row in frame.placed_extents(projected)
                if row.footprint_id in block.footprints
            }
            inside = {
                key
                for key, points in extents.items()
                if points and all(bbox.contains_point(p) for p in points)
            }
            if block.rigid:
                if inside == set(block.footprints):
                    options.append(alternative)
            else:
                options.append(tuple(pose for pose in alternative if pose.footprint_id in inside))
        if not block.rigid and {pose.footprint_id for row in options for pose in row} != set(
            block.footprints
        ):
            options.clear()
        return replace(block, alternatives=tuple(options))

    coarse = (plans.best, plans.coarsened if plans.best is plans.hierarchy else plans.hierarchy)
    # Preserve part coverage. A coarse overflow is not permission to drop a block from the local solve.
    complete = tuple(plan.assignments for plan in coarse if not plan.unplaced)
    for plan in coarse:
        failures.update(f"block:{key}:region-overflow" for key in plan.unplaced)
    seen: set[tuple[tuple[str, str], ...]] = set()
    max_attempts = min(6, budget.evaluations)
    for initial in complete:
        for assigned in variations(initial):
            key = tuple(sorted(assigned.items()))
            if key in seen:
                continue
            if attempts >= max_attempts or work >= budget.evaluations:
                return RegionPlacement({}, None, attempts, work, tuple(sorted(failures)))
            seen.add(key)
            attempts += 1
            filtered = tuple(fit(block, assigned[block.instance]) for block in blocks)
            empty = tuple(block.instance for block in filtered if not block.alternatives)
            if empty:
                failures.update(f"block:{name}:region-no-pose" for name in empty)
                continue
            quota = max(1, (budget.evaluations - work) // 2)
            result = search_block_placements(
                filtered,
                other_domains,
                input_sha256=input_sha256,
                budget=replace(budget, evaluations=quota),
                judge=judge,
            )
            work += result.work
            failures.update(result.blockers)
            if result.candidates:
                return RegionPlacement(assigned, result, attempts, work, tuple(sorted(failures)))
    return RegionPlacement({}, None, attempts, work, tuple(sorted(failures)))
