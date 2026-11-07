# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored hostile full-board deltas; never trust retained or changed native IDs."""

from dataclasses import replace

import pytest
from _searchbench import bench, point, wall

from fenolite.core.coords import Point, Size
from fenolite.model.base import ExtBag
from fenolite.model.board import FootprintInstance, Outline, Pad
from fenolite.routing.external_delta import board_delta


def board():
    job, _, _ = bench(tracks=(wall("old", 4, 0, 2),))
    pad = Pad(
        id="pad_a",
        number="1",
        shape="rect",
        size=Size(500_000, 500_000),
        position=Point(0, 0),
        layers=("F.Cu",),
        net_id="net_sig",
    )
    fp = FootprintInstance(id="fp_a", component_id="", lib_ref="authored", position=point(2, 5), pads=(pad,))
    return replace(
        job.design,
        board=replace(
            job.design.board,
            footprints=(fp,),
            outline=Outline(id="out_a", points=(point(0, 0), point(12, 0), point(12, 10), point(0, 10))),
        ),
    )


def added(design):
    route = replace(wall("external", 3, 3, 6), net_id="net_sig")
    return replace(design, board=replace(design.board, tracks=(*design.board.tracks, route)))


def test_delta_accepts_only_new_selected_copper_without_mutating_input():
    before = board()
    snapshot = repr(before)
    after = added(before)
    delta = board_delta(before, after, ("SIG",))
    assert delta.reason == "" and delta.copper.tracks == after.board.tracks[1:]
    assert repr(before) == snapshot


def test_delta_ignores_external_identity_and_entity_order_but_resolves_nets():
    before = board()
    after = added(before)
    after = replace(
        after,
        circuit=replace(
            after.circuit,
            nets=tuple(
                replace(n, id="returned_sig") if n.name == "SIG" else n for n in reversed(after.circuit.nets)
            ),
        ),
        board=replace(
            after.board,
            id="returned_board",
            tracks=tuple(
                replace(
                    t, id="returned_" + str(i), net_id="returned_sig" if t.net_id == "net_sig" else t.net_id
                )
                for i, t in enumerate(reversed(after.board.tracks))
            ),
            footprints=tuple(
                replace(
                    fp,
                    id="returned_fp",
                    pads=tuple(replace(p, id="returned_pad", net_id="returned_sig") for p in fp.pads),
                )
                for fp in after.board.footprints
            ),
        ),
    )
    delta = board_delta(before, after, ("SIG",))
    assert delta.reason == "" and len(delta.copper.tracks) == 1
    assert delta.copper.tracks[0].net_id == "net_sig"


@pytest.mark.parametrize("edit", ["move-pad", "move-footprint", "outline", "layer", "opaque", "net-name"])
def test_delta_rejects_topology_changes_even_when_native_ids_stay(edit):
    before = board()
    after = added(before)
    b = after.board
    fp = b.footprints[0]
    if edit == "move-pad":
        b = replace(b, footprints=(replace(fp, pads=(replace(fp.pads[0], position=point(1, 0)),)),))
    elif edit == "move-footprint":
        b = replace(b, footprints=(replace(fp, position=point(3, 5)),))
    elif edit == "outline":
        b = replace(b, outline=replace(b.outline, points=b.outline.points[:-1]))
    elif edit == "layer":
        b = replace(b, layers=(replace(b.layers[0], name="Changed.Cu"), *b.layers[1:]))
    elif edit == "opaque":
        b = replace(b, ext={"kicad": ExtBag(payload=(("unknown", "changed"),))})
    else:
        after = replace(
            after,
            circuit=replace(
                after.circuit, nets=tuple(replace(n, name="Changed") for n in after.circuit.nets)
            ),
        )
    assert board_delta(before, replace(after, board=b), ("SIG",)).reason == "external-topology-changed"


@pytest.mark.parametrize("edit", ["remove", "move", "width", "unlock"])
def test_delta_rejects_old_copper_edits_and_retains_nothing(edit):
    before = board()
    before = replace(
        before, board=replace(before.board, tracks=(replace(before.board.tracks[0], locked=True),))
    )
    after = added(before)
    old, new = after.board.tracks
    changed = {
        "move": replace(old, end=point(8, 2)),
        "width": replace(old, width=900_000),
        "unlock": replace(old, locked=False),
    }
    tracks = (new,) if edit == "remove" else (changed[edit], new)
    delta = board_delta(before, replace(after, board=replace(after.board, tracks=tracks)), ("SIG",))
    assert delta.reason in {"external-copper-changed", "external-unselected-copper"}
    assert not delta.copper.tracks


def test_delta_rejects_unselected_and_duplicate_additions():
    before = board()
    after = added(before)
    wrong = replace(after.board.tracks[-1], id="wrong", net_id="net_wall")
    duplicate = replace(after.board.tracks[-1], id="duplicate")
    for extra, reason in ((wrong, "external-unselected-copper"), (duplicate, "external-duplicate-copper")):
        bad = replace(after, board=replace(after.board, tracks=(*after.board.tracks, extra)))
        assert board_delta(before, bad, ("SIG",)).reason == reason


def dispatch_fixture():
    from fenolite.routing.external_candidates import Adapter
    from fenolite.routing.protocol import RouterStatus, RoutingResult

    job, subject, _ = bench()
    track = replace(
        wall("tool-id", 2, 5, 5), start=subject.a.at, end=subject.b.at, width=subject.width, net_id="net_sig"
    )
    calls = []

    def route(scoped):
        calls.append(scoped)
        return RoutingResult(tracks=(track,), tool_version="authored")

    adapter = Adapter("kicadroutingtools", "board", lambda _: RouterStatus(True, version="authored"), route)
    return job, subject, adapter, track, calls


def test_scoped_dispatch_is_read_only_and_canonical_across_external_ids():
    from fenolite.routing.budget import Budget
    from fenolite.routing.external_candidates import generate_external
    from fenolite.routing.protocol import RoutingResult

    job, subject, adapter, track, calls = dispatch_fixture()
    before = repr(job)
    found = generate_external(job, (subject,), (adapter,), budget=Budget(5), judge=lambda *_: "")
    assert len(found.candidates) == 1 and not found.refusals
    assert found.candidates[0].source == "external:kicadroutingtools"
    assert found.provenance[0][1].version == "authored"
    assert found.provenance[0][1].deterministic is False
    again = generate_external(
        job,
        (subject,),
        (
            replace(
                adapter,
                route=lambda _: RoutingResult(
                    tracks=(replace(track, id="changed", native_ids={"kicad": "random"}),)
                ),
            ),
        ),
        budget=Budget(5),
        judge=lambda *_: "",
    )
    assert found.candidates == again.candidates
    assert repr(job) == before
    assert calls[0].nets == job.nets and calls[0].subjects == ()
    assert calls[0].on_run is None and calls[0].extra["external_candidate"] is True


def test_no_judge_no_process_and_unsupported_subject_no_process():
    from fenolite.routing.budget import Budget
    from fenolite.routing.external_candidates import generate_external

    job, subject, adapter, _, calls = dispatch_fixture()
    found = generate_external(job, (subject,), (adapter,), budget=Budget(5), judge=None)
    assert found.refusals[0][1] == "external-judge-missing" and not calls
    found = generate_external(
        job, (replace(subject, kind="group"),), (adapter,), budget=Budget(5), judge=lambda *_: ""
    )
    assert found.refusals[0][1] == "external-unsupported" and not calls


@pytest.mark.parametrize(
    "problem", ["unselected", "arc", "inner-via", "bad-via", "narrow", "judge", "partial", "outside"]
)
def test_dispatch_discards_whole_invalid_output(problem):
    from fenolite.core.errors import Issue
    from fenolite.model.board import Arc, Via
    from fenolite.routing.budget import Budget
    from fenolite.routing.external_candidates import generate_external
    from fenolite.routing.protocol import RoutingResult

    job, subject, adapter, track, _ = dispatch_fixture()
    result = RoutingResult(tracks=(track,))
    if problem == "unselected":
        result = replace(result, tracks=(track, replace(track, id="wrong", net_id="net_wall")))
    elif problem == "arc":
        result = replace(
            result,
            arcs=(
                Arc(
                    id="arc",
                    start=track.start,
                    mid=point(3, 6),
                    end=track.end,
                    width=track.width,
                    layer="F.Cu",
                    net_id="net_sig",
                ),
            ),
        )
    elif "via" in problem:
        via = Via(
            id="via",
            position=point(6, 5),
            diameter=600_000,
            drill=300_000,
            net_id="net_sig",
            layers=("F.Cu", "In1.Cu") if problem == "inner-via" else job.layers,
            via_type="blind_buried" if problem == "bad-via" else "through",
        )
        result = replace(result, vias=(via,))
    elif problem == "narrow":
        result = replace(result, tracks=(replace(track, width=1),))
    elif problem == "partial":
        result = replace(result, issues=(Issue("route.tool-failed", "error", "partial"),))
    elif problem == "outside":
        result = replace(result, tracks=(replace(track, end=point(15, 5)),))
    found = generate_external(
        job,
        (subject,),
        (replace(adapter, route=lambda _: result),),
        budget=Budget(5),
        judge=lambda *_: "external-scope" if problem == "judge" else "",
    )
    assert not found.candidates and found.refusals


def test_via_barrel_cannot_pass_inner_copper_even_when_tracks_use_outer_layers():
    from fenolite.model.board import Via
    from fenolite.routing.budget import Budget
    from fenolite.routing.external_candidates import generate_external
    from fenolite.routing.protocol import RoutingResult

    job, subject, adapter, track, _ = dispatch_fixture()
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    job, subject, _ = bench(
        layers=layers, allowed=("F.Cu", "B.Cu"), tracks=(wall("inner", 6, 0, 10, "In1.Cu"),)
    )
    via = Via(
        id="toolvia",
        position=point(6, 5),
        diameter=600_000,
        drill=300_000,
        net_id="net_sig",
        layers=(layers[0], layers[-1]),
    )
    result = RoutingResult(tracks=(track,), vias=(via,))
    found = generate_external(
        job, (subject,), (replace(adapter, route=lambda _: result),), budget=Budget(5), judge=lambda *_: ""
    )
    assert not found.candidates and found.refusals[0][1] == "external-geometry"
