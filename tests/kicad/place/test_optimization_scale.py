# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from functools import partial
from pathlib import Path
from shutil import copyfile
from time import perf_counter

import pytest
from _kicad import major
from _resources import kicad_cli
from _searchbench import MM, point

from fenolite.api import run
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli.placement_checks import check_placement_constraints
from fenolite.core.coords import Point, Size
from fenolite.geometry import BBox
from fenolite.model.board import Board, FootprintInstance, Outline, Pad
from fenolite.model.circuit import Circuit, Component, Module, Net, Pin, PinRef
from fenolite.model.design import Design, DesignHeader
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.floorplan import BlockOrigin, BlockRequest, bind_blocks, search_region_placements
from fenolite.placement.optimization_contract import OptimizationBudget
from fenolite.placement.optimize import SearchJudgment
from fenolite.placement.pose_projection import project_poses
from fenolite.placement.protection import PlacementScope
from fenolite.placement.regions import Region
from fenolite.reuse.blocklayout import BlockLayout, LayoutPart, apply_block_layout, nets_digest, parts_digest

pytestmark = pytest.mark.needs_kicad
REGIONS = tuple(Region(f"bay-{i}", BBox(i * 25 * MM, 0, (i + 1) * 25 * MM, 42 * MM)) for i in range(3))


def repeated_channels(four_layers: bool):
    layers = created_layers(4 if four_layers else 2)
    components: list[Component] = []
    footprints: list[FootprintInstance] = []
    modules: list[Module] = []
    nets: list[Net] = []
    saved: dict[str, dict[str, LayoutPart]] = {}
    targets: dict[str, Point] = {}
    for channel in range(15):
        name = f"channel-{channel:02d}"
        x, y = 4 + (channel % 5) * 13, 3 + (channel // 5) * 12
        origin = point(x, y)
        targets[name] = origin
        local = saved.setdefault(name, {})
        side = "bottom" if four_layers and channel % 2 else "top"
        layer = "B.Cu" if side == "bottom" else "F.Cu"
        for pair in range(5):
            net_id = f"net-{channel}-{pair}"
            members = []
            for end in range(2):
                number = channel * 10 + pair * 2 + end + 1
                ref = f"R{number}"
                component = Component(
                    id=f"c{number}",
                    ref=ref,
                    path=f"{name}/{ref}",
                    lib_footprint_ref="Bench:R",
                    pins=(Pin(id=f"pin{number}", number="1"),),
                )
                components.append(component)
                members.append(PinRef(component.id, "1"))
                at = point(1 + 3 * end, pair + 1)
                local[ref] = LayoutPart(at, 0, side, "Bench:R")
                footprints.append(
                    FootprintInstance(
                        id=f"f{number}",
                        component_id=component.id,
                        lib_ref="Bench:R",
                        side=side,
                        position=Point(origin.x + at.x, origin.y + at.y + 500_000),
                        pads=(
                            Pad(
                                id=f"p{number}",
                                number="1",
                                shape="rect",
                                size=Size(400_000, 400_000),
                                position=Point(0, 0),
                                layers=(layer,),
                                net_id=net_id,
                            ),
                        ),
                    )
                )
            nets.append(Net(id=net_id, name=f"CH{channel:02d}_S{pair}", members=tuple(members)))
        modules.append(
            Module(
                id=f"m{channel}",
                path=name,
                block="bench.channel",
                block_version="1.0.0",
                component_ids=tuple(component.id for component in components[-10:]),
            )
        )
    design = Design(
        header=DesignHeader(id="scale", name="placement-scale", schema_version="0", fenolite_version="0"),
        circuit=Circuit(components=tuple(components), nets=tuple(nets), modules=tuple(modules)),
        board=Board(
            id="scale-board",
            layers=layers,
            outline=Outline(id="outline", points=(point(0, 0), point(75, 0), point(75, 42), point(0, 42))),
            footprints=tuple(footprints),
        ),
    )
    requests = tuple(
        BlockRequest(
            module.path,
            partial(
                apply_block_layout,
                BlockLayout(
                    module.block,
                    module.block_version,
                    parts_digest(design, module.path),
                    nets_digest(design, module.path),
                    "Apache-2.0",
                    "INFERRED",
                    saved[module.path],
                ),
            ),
            (BlockOrigin(targets[module.path]),),
        )
        for module in modules
    )
    allowed = {name: frozenset({f"bay-{point.x // (25 * MM)}"}) for name, point in targets.items()}
    return design, requests, allowed


@pytest.mark.parametrize("four_layers", [False, True], ids=["baseline-two-layer", "holdout-four-layer"])
def test_repeated_channels_scale(tmp_path, monkeypatch, four_layers):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    start = perf_counter()
    design, requests, allowed = repeated_channels(four_layers)
    frame = KicadBackend()
    blocks = bind_blocks(design, requests)
    scope = PlacementScope(tuple(sorted(key for block in blocks for key in block.footprints)), ())

    def judge(poses, complete):
        if not complete:
            return SearchJudgment((0,))
        placed = project_poses(design, scope, poses)
        checked = check_placement_constraints(placed, frame, PlacementConstraints())
        return SearchJudgment((0,), checked.hard)

    result = search_region_placements(
        design,
        frame,
        blocks,
        REGIONS,
        {block.instance: 20 * MM**2 for block in blocks},
        allowed,
        {},
        input_sha256="scale",
        budget=OptimizationBudget(360, 1),
        judge=judge,
    )
    assert result.search is not None and result.work == 150, result
    poses = result.search.candidates[0].candidate.poses
    assert len(poses) == 150 and len(result.assignments) == 15
    path = tmp_path / "channels.kicad_pcb"
    projected = project_poses(design, scope, poses)
    path.write_text(write_board(projected, target=major()).text)
    assert len(read_board(path).board.footprints) == 150
    fixture = Path(__file__).resolve().parents[2] / "data/kicad/project/empty_10.kicad_pro"
    copyfile(fixture, path.with_suffix(".kicad_pro"))
    placed_seconds = perf_counter() - start
    routed = run("route", str(path), "--router", "octilinear", "--confirm", cwd=tmp_path)
    assert routed.ok and not routed.result["unrouted"], routed.envelope or routed.error
    assert len(routed.result["routed"]) == 75
    native = kicad_cli()
    assert native is not None
    checked = run("check", str(path), "--kicad-cli", str(native), cwd=tmp_path)
    assert checked.ok, checked.envelope or checked.error
    print(
        f"poses={len(poses)} work={result.work} nets=75 "
        f"placement_s={placed_seconds:.2f} total_s={perf_counter() - start:.2f}"
    )
