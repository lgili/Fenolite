# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

from _searchbench import MM, bench, point, wall

from fenolite.backends.base import BoardPad, PadCopper
from fenolite.cli.placement_probes import probe_pad_connections
from fenolite.core.coords import Point
from fenolite.model.circuit import Net
from fenolite.routing.protocol import JobAttach, JobNet, JobSubject
from fenolite.routing.search import Limits

LAYER = ("F.Cu",)


def physical(end: JobAttach, ref: str, net_id: str) -> BoardPad:
    return BoardPad(
        ref,
        ref,
        ref,
        ref + "-pad",
        "1",
        "smd",
        end.at,
        0,
        "top",
        LAYER,
        net_id,
        end.net,
        (PadCopper(LAYER[0], (end.at,), 100_000),),
    )


def test_exact_pad_route_and_blocked_exit_under_same_bounds():
    for obstacles, status in (((), "found"), ((wall("barrier", 6, 0, 10),), "no-room")):
        job, subject, world = bench(tracks=obstacles, allowed=LAYER)
        pads = (physical(subject.a, "A", "net_sig"), physical(subject.b, "B", "net_sig"))
        (result,) = probe_pad_connections(
            job, pads, job.extra["outline"], Limits(MM, 2000, 0), max_length=40 * MM
        )
        assert result.status == status
        assert (result.length_nm is not None) == (status == "found")
        assert result.expanded <= 2000
        assert job.design.board.tracks == obstacles and world.placed == []


def test_cancelled_and_coupled_probes_do_not_become_independent_paths():
    from fenolite.routing.protocol import JobPair

    job, subject, _ = bench(allowed=LAYER)
    pads = (physical(subject.a, "A", "net_sig"), physical(subject.b, "B", "net_sig"))
    outline = job.extra["outline"]
    limits = Limits(MM, 2000, 0)
    cancelled = probe_pad_connections(
        job, pads, outline, limits, max_length=40 * MM, stop=lambda: "cancelled"
    )
    assert cancelled[0].status == "cancelled" and cancelled[0].expanded == 0
    paired = replace(job, pairs=(JobPair("pair", "SIG", "WALL", 100_000, 100_000),))
    result = probe_pad_connections(paired, pads, outline, limits, max_length=40 * MM)
    assert result[0].status == "search-unsupported" and result[0].length_nm is None
    duplicate = probe_pad_connections(job, (*pads, pads[0]), outline, limits, max_length=40 * MM)
    assert duplicate[0].status == "unresolved-pad"


def test_provisional_shared_occupancy_blocks_an_individually_routable_crossing():
    job, first, _ = bench(start=Point(80_000, 5 * MM), end=Point(12 * MM - 80_000, 5 * MM), allowed=LAYER)
    second = JobSubject(
        "crossing",
        "connection",
        "RETURN",
        JobAttach("pad", "RETURN", point(6, 2), LAYER, "C-1"),
        JobAttach("pad", "RETURN", point(6, 8), LAYER, "D-1"),
        100_000,
        LAYER,
    )
    pads = (
        physical(first.a, "A", "net_sig"),
        physical(first.b, "B", "net_sig"),
        physical(second.a, "C", "net_return"),
        physical(second.b, "D", "net_return"),
    )
    circuit = job.design.circuit
    job = replace(
        job,
        design=replace(
            job.design, circuit=replace(circuit, nets=(*circuit.nets, Net(id="net_return", name="RETURN")))
        ),
        nets=(*job.nets, JobNet("RETURN", "net_return", (), 100_000, 100_000, 0, 0)),
    )
    before = job.design
    outline = job.extra["outline"]
    limits = Limits(MM // 2, 4000, 0)
    isolated = probe_pad_connections(
        replace(job, subjects=(second,)), pads, outline, limits, max_length=40 * MM
    )
    shared = probe_pad_connections(
        replace(job, subjects=(second, first)), pads, outline, limits, max_length=40 * MM
    )
    assert isolated[0].status == "found"
    assert [(row.key, row.status) for row in shared] == [(first.key, "found"), (second.key, "no-room")]
    assert job.design == before and not job.design.board.tracks


def test_cli_probes_reviewed_pad_ids_and_keeps_provisional_copper_out_of_plan(tmp_path, monkeypatch):
    import json
    import shutil
    from pathlib import Path

    from _checkcli import run
    from _coppercheck import Copper

    from fenolite.backends.kicad.pcb import read_board, write_board
    from fenolite.model.board import Outline

    copper = Copper()
    copper.pad("J1", "1", "SIG")
    copper.pad("R1", "1", "SIG")
    design = copper.build()
    board = replace(
        design.board,
        outline=Outline(id="out_authored", points=(point(0, 0), point(12, 0), point(12, 10), point(0, 10))),
        footprints=tuple(
            replace(fp, position=point(x, 5), locked=x == 4)
            for fp, x in zip(design.board.footprints, (4, 6), strict=True)
        ),
    )
    path = tmp_path / "escape.kicad_pcb"
    path.write_text(write_board(replace(design, board=board), target=10).text)
    fixture = Path(__file__).resolve().parents[3] / "tests/data/kicad/project/empty_10.kicad_pro"
    shutil.copyfile(fixture, path.with_suffix(".kicad_pro"))
    actual = read_board(path)
    anchor, movable = sorted(actual.board.footprints, key=lambda item: not item.locked)
    request = tmp_path / "request.json"
    config = {
        "schema": "fenolite.placement-optimization.v0",
        "selected": [movable.id],
        "budget": {"evaluations": 8, "beam_width": 2, "probe_expansions": 20000},
        "constraints": {"max_candidates": 8, "pitch": MM},
        "intent": [
            {
                "key": "exact-signal",
                "kind": "escape",
                "endpoints": [{"footprint_id": fp.id, "pad_id": fp.pads[0].id} for fp in (anchor, movable)],
                "origin": "declared",
                "source": "authored fixture",
                "rule_version": "v0",
                "rationale": "verify one exact same-net pad exit",
                "required": True,
                "max_distance_nm": 8 * MM,
            }
        ],
    }
    request.write_text(json.dumps(config))
    before = path.read_bytes()
    command = ("place", str(path), "--strategy", "optimize", "--constraints", str(request))
    code, env, err, _ = run(monkeypatch, tmp_path, *command, "--dry-run")
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    assert result["score_fields"][-1] == "probe_track_length_nm" and result["candidates"], result
    assert all(candidate["score"][-1] > 0 for candidate in result["candidates"])
    for candidate in result["candidates"]:
        (probe,) = candidate["probes"]
        assert probe["key"] == "exact-signal" and probe["status"] == "found"
        assert probe["length_nm"] == candidate["score"][-1]
        assert "F.Cu" in candidate["channel_overflow_by_layer"]
    saved = tmp_path / "proposal.json"
    saved.write_text(json.dumps(result))
    selected = (*command, "--proposal", str(saved), "--candidate", result["candidates"][0]["id"])
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    code, env, err, _ = run(monkeypatch, tmp_path, *selected, "--dry-run")
    assert code == 0 and path.read_bytes() == before, (env, err)
    code, env, err, _ = run(monkeypatch, tmp_path, *selected, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0 and not read_board(path).board.tracks, (env, err)
    config["budget"]["probe_expansions"] = 0
    request.write_text(json.dumps(config))
    code, env, err, _ = run(monkeypatch, tmp_path, *command, "--dry-run")
    assert code == 0, (env, err)
    result = env["result"]["optimization"]
    assert not result["candidates"] and "probe:exact-signal:budget" in result["blockers"], result


def test_capacity_reads_net_classes_layers_and_projected_blockers():
    from fenolite.backends.base import DesignRules
    from fenolite.cli.placement_capacity import placement_capacity
    from fenolite.model.circuit import NetClass

    job, subject, _ = bench(allowed=LAYER)
    pads = (physical(subject.a, "A", "net_sig"), physical(subject.b, "B", "net_sig"))
    default = NetClass(id="class_default", name="Default", track_width=500_000, clearance=100_000)
    design = replace(job.design, circuit=replace(job.design.circuit, netclasses=(default,)))
    outline = job.extra["outline"]
    selected = frozenset({"B"})
    open_board = placement_capacity(design, DesignRules(design), pads, outline, selected)
    assert open_board.overflow_nm == 0 and not open_board.unknown
    blocked = replace(design, board=replace(design.board, tracks=(wall("barrier", 6, 0, 10),)))
    estimate = placement_capacity(blocked, DesignRules(blocked), pads, outline, selected)
    assert estimate.overflow_nm == 600_000 and not estimate.unknown
    unknown = placement_capacity(job.design, DesignRules(job.design), pads, outline, selected)
    assert unknown.unknown == ("capacity:net:SIG",)
    no_layers = replace(design, board=replace(design.board, layers=()))
    assert placement_capacity(no_layers, DesignRules(no_layers), pads, outline, selected).unknown == (
        "capacity:layers",
    )


def test_capacity_reserves_one_indivisible_differential_lane():
    from fenolite.backends.base import DesignRules
    from fenolite.cli.placement_capacity import placement_capacity
    from fenolite.model.circuit import NetClass

    job, subject, _ = bench(allowed=LAYER)
    pads = tuple(
        physical(replace(subject.a, net=name, at=point(2, y)), first, net_id)
        for name, y, first, net_id in (("USB_P", 4, "A", "dp"), ("USB_N", 6, "C", "dn"))
    ) + tuple(
        physical(replace(subject.b, net=name, at=point(10, y)), second, net_id)
        for name, y, second, net_id in (("USB_P", 4, "B", "dp"), ("USB_N", 6, "D", "dn"))
    )
    default = NetClass(
        id="class_default",
        name="Default",
        track_width=300_000,
        clearance=100_000,
        diff_pair_width=500_000,
        diff_pair_gap=200_000,
    )
    design = replace(
        job.design,
        circuit=replace(
            job.design.circuit,
            netclasses=(default,),
            nets=(
                *job.design.circuit.nets,
                Net(id="dp", name="USB_P"),
                Net(id="dn", name="USB_N"),
            ),
        ),
        board=replace(job.design.board, tracks=(wall("barrier", 6, 1, 9),)),
    )
    estimate = placement_capacity(
        design,
        DesignRules(design),
        pads,
        job.extra["outline"],
        frozenset({"B", "D"}),
    )
    assert estimate.overflow_nm == 1_300_000 and not estimate.unknown
