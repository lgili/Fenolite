# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proposal mode of the octilinear router (change c0280; capability routing, "Candidates in a routing
result", "Octilinear candidate families", "Zone fan-out candidates" and "Relaxed group candidates";
``docs/routing.md``, "Proposals"), on the authored benches of ``tests/unit/roles/_proposals.py`` and c0244's
Kelvin bench."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROLES_TESTS = Path(__file__).resolve().parents[1] / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))

import _planebench as pb  # noqa: E402
from _critical import bench, role_job  # noqa: E402
from _proposals import family_bench, propose_job, subject_bench  # noqa: E402
from _roleboards import Built  # noqa: E402

from fenolite.analysis.boundary import board_boundary  # noqa: E402
from fenolite.analysis.pour import DEFAULT_GRID_NM, pour_copper  # noqa: E402
from fenolite.backends.kicad.fanout import FanoutSizes, plan_fanout  # noqa: E402
from fenolite.checks.clearance import ClearanceResolver  # noqa: E402
from fenolite.core.coords import Point  # noqa: E402
from fenolite.geometry import Thick, thick_touch  # noqa: E402
from fenolite.model.board import Track  # noqa: E402
from fenolite.model.rules import RuleSubject  # noqa: E402
from fenolite.roles.proposals import ZoneCopper  # noqa: E402
from fenolite.routing.octilinear import OctilinearRouter  # noqa: E402
from fenolite.routing.propose import FAMILIES, distinct  # noqa: E402
from fenolite.routing.protocol import Candidate, JobAttach, JobSubject, RoutingJob  # noqa: E402

ROUTER = OctilinearRouter()


@pytest.fixture(scope="module")
def subjects_board(tmp_path_factory: pytest.TempPathFactory) -> Built:
    return subject_bench(tmp_path_factory.mktemp("subjects"))


def test_candidates_only(subjects_board: Built) -> None:
    """Scenario "Candidates only": a ``connection`` subject gets candidates and no track, arc or via; two runs
    give equal candidates with equal ids, each ``c-`` and 16 hex digits."""
    job = propose_job(subjects_board, kinds=("connection",))
    assert [s.key for s in job.subjects] == ["connection:SIG:R1-1~R2-1"]
    first, second = ROUTER.route(job), ROUTER.route(job)
    assert not (first.tracks or first.arcs or first.vias) and first.candidates
    assert first.candidates == second.candidates
    assert all(c.id.startswith("c-") and len(c.id) == 18 for c in first.candidates)
    assert first.candidates[0].source == "shape" and not any(
        t.locked for c in first.candidates for t in c.tracks
    )


def test_ids_ignore_unrelated_copper(subjects_board: Built) -> None:
    """Scenario "Ids ignore unrelated copper": a track of another net far from the connection keeps every
    candidate's id."""
    job = propose_job(subjects_board, kinds=("connection",))
    before = [c.id for c in ROUTER.route(job).candidates]
    design = job.design
    assert design.board is not None
    vs = next(net.id for net in design.circuit.nets if net.name == "VS")
    far = Track(
        id="trk_far",
        start=Point(130_000_000, 126_000_000),
        end=Point(135_000_000, 126_000_000),
        width=250_000,
        layer="F.Cu",
        net_id=vs,
    )
    moved = dataclasses.replace(
        design, board=dataclasses.replace(design.board, tracks=(*design.board.tracks, far))
    )
    after = [c.id for c in ROUTER.route(dataclasses.replace(job, design=moved)).candidates]
    assert after == before and before


def test_families_give_distinct_candidates(tmp_path: Path) -> None:
    """Scenario "Distinct candidates": at most 4 candidates, no two with the same layer set, via count and
    centre line, in family order; a connection whose ends share no layer gets via-L candidates only."""
    built = family_bench(tmp_path)
    job = propose_job(built, {"candidates": "4"})
    result = ROUTER.route(job)
    found = [c for c in result.candidates if c.subject == "connection:LNK:J2-1~J3-1"]
    assert 1 <= len(found) <= 4
    ranks = [FAMILIES.index(c.source) for c in found]
    assert ranks == sorted(ranks) and found[0].source == "shape"
    for index, one in enumerate(found):
        assert distinct(one, found[:index], 200_000)
    assert {frozenset(c.layers) for c in found} >= {frozenset({"F.Cu"}), frozenset({"B.Cu"})}
    via_l = [c for c in result.candidates if c.subject == "connection:LNK2:R10-1~R11-1"]
    assert via_l and {c.source for c in via_l} == {"via-l"}
    assert all(len(c.vias) == 1 and set(c.layers) == {"F.Cu", "B.Cu"} for c in via_l)
    for index, one in enumerate(via_l):
        assert distinct(one, via_l[:index], 200_000)


def test_distinct_rule() -> None:
    """Two candidates are one when they share layers, via count and a centre line within the clearance."""
    a = Candidate(
        "c-a",
        "s",
        "shape",
        tracks=(Track(id="t1", start=Point(0, 0), end=Point(1_000_000, 0), width=1, layer="F.Cu"),),
        layers=("F.Cu",),
    )
    near = Candidate(
        "c-b",
        "s",
        "shape",
        tracks=(Track(id="t2", start=Point(0, 100), end=Point(1_000_000, 100), width=1, layer="F.Cu"),),
        layers=("F.Cu",),
    )
    far = Candidate(
        "c-c",
        "s",
        "shape",
        tracks=(Track(id="t3", start=Point(0, 0), end=Point(0, 1_000_000), width=1, layer="F.Cu"),),
        layers=("F.Cu",),
    )
    other = dataclasses.replace(near, id="c-d", layers=("B.Cu",))
    assert not distinct(near, [a], 200_000)
    assert distinct(far, [a], 200_000) and distinct(other, [a], 200_000)


def test_fanout_matches_the_plane_fanout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The same search as plane fan-out": on c0107's plane bench, each SMD pad of a plane net gets a
    first ``fanout`` candidate whose via stands where ``plan_fanout`` puts it."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    found = pb.load(pb.build_project(tmp_path))
    design = found.design
    assert design.board is not None
    resolver = ClearanceResolver(
        design,
        min_clearance=found.rules.min_clearance,
        rules_over_classes=found.rules.rules_over_classes,
        floor_over_rules=found.rules.floor_over_rules,
    )

    def clearance(a: RuleSubject, b: RuleSubject) -> int:
        return resolver.resolve(a, b).value or 0

    sizes = FanoutSizes(**pb.SIZES)
    planned = plan_fanout(
        design, found.pads, nets={"GND": sizes, "VCC": sizes}, plane_layers=found.plane_layers,
        outline=found.outline, edge_clearance=pb.EDGE_CLEARANCE, clearance=clearance,
    )  # fmt: skip
    expected = {
        f"{p.ref}-{p.number}": next(v.position for v in planned.vias if t.end == v.position)
        for p in found.pads
        for t in planned.tracks
        if t.start == p.position and f"{p.ref}-{p.number}" in pb.PLANE_PADS
    }
    assert sorted(expected) == sorted(pb.PLANE_PADS)
    pour = pour_copper(design, pads=found.pads, boundary=board_boundary(design.board), grid=DEFAULT_GRID_NM)
    layers = tuple(x.name for x in sorted(design.board.layers, key=lambda i: i.ordinal) if x.kind == "copper")
    for where, via in sorted(expected.items()):
        pad = found.pad(where)
        assert pad.net is not None
        plane = next(layer for layer, net in pb.PLANES.items() if net == pad.net)
        a = JobAttach("pad", pad.net, pad.position, ("F.Cu",), where)
        b = JobAttach("zone", pad.net, pad.position, (plane,), f"zone@{plane}")
        subject = JobSubject(
            f"fanout:{pad.net}:{where}", "fanout", pad.net, a, b, sizes.width, ("F.Cu", "B.Cu"),
            sizes.via_diameter, sizes.via_drill,
        )  # fmt: skip
        extra = {
            "board_pads": found.pads,
            "outline": found.outline,
            "clearance": clearance,
            "zone_copper": ZoneCopper(design, pour).covers,
        }
        job = RoutingJob(design, (), layers, {}, extra, plane_layers=found.plane_layers, subjects=(subject,))
        fanouts = [c for c in ROUTER.route(job).candidates if c.source == "fanout"]
        assert fanouts, where
        assert fanouts[0].vias[0].position == via, where


KELVIN = """
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("{name}")
design.board(mm(40), mm(30))
r1 = Part("R1", "Fenolite:Resistor", footprint="Roles:Roles_Shunt_2512", value="5m")
u1 = Part("U1", "Roles:Roles_Sense_Amplifier", footprint="Fenolite:SOT23_5", value="AMP")
j9 = Part("J9", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="SW")
design.add(r1, u1, j9)
va, vb, sw = Net("VA"), Net("VB"), Net("SW")
connect(va, r1[1], u1["IN+"])
connect(vb, r1[2], u1["IN-"])
connect(sw, j9[1], j9[2])
design.net_role(va, "power")
design.net_role(vb, "power")
design.net_role(sw, "switch_node")
design.kelvin("kelvin_R1", (r1.pad(1), r1.pad(2)), (u1.pad(3), u1.pad(4)))
r1.place(mm(8), mm(8), rot=90)
u1.place(mm(28), mm(20), rot=90)
j9.place(mm(30), mm(26))
ring = tuple((mm(str(x)), mm(str(y))) for x, y in ((12, 11), (24, 11), (24, 17), (12, 17)))
design.zone(sw, layers=("B.Cu",), name="SW_B", outline=ring, clearance=mm("0.3"), connection="solid")
"""


def test_relaxed_group_candidates(tmp_path: Path) -> None:
    """Scenario "A pair over switching copper": on c0244's keep-away bench with ``z-shapes=off`` the pair has
    no default candidate, one labelled ``keep-away=clearance``, and no candidate touches a zone outline of its
    own net (isolation is never relaxed)."""
    built = bench(tmp_path, "keepaway", KELVIN.format(name="keepaway"))
    job = role_job(built, options={"z-shapes": "off"})
    first = job.roles[0]
    a = JobAttach("pad", first.net, first.a.at, first.a.layers, first.a.label)
    b = JobAttach("pad", first.net, first.b.at, first.b.layers, first.b.label)
    subject = JobSubject(
        "group:kelvin_R1", "group", first.net, a, b, first.width, job.layers, group="kelvin_R1"
    )
    result = ROUTER.route(dataclasses.replace(job, subjects=(subject,)))
    assert not (result.tracks or result.vias)
    labels = [c.relaxed for c in result.candidates]
    assert () not in labels and ("keep-away=clearance",) in labels
    design = job.design
    assert design.board is not None
    for candidate in result.candidates:
        assert candidate.source == "role"
        for track in candidate.tracks:
            for zone in design.board.zones:
                if zone.net_id == track.net_id:
                    assert not thick_touch(
                        Thick((track.start, track.end), track.width), Thick(zone.outline, 0, True)
                    )


def test_unknown_options_are_reported(subjects_board: Built) -> None:
    job = propose_job(subjects_board, {"candidates": "9", "colour": "red"}, kinds=("connection",))
    result = ROUTER.route(job)
    assert sorted(i.where for i in result.issues if i.code == "route.option-ignored") == [
        "candidates",
        "colour",
    ]
    assert result.candidates


def test_plain_jobs_are_unchanged(subjects_board: Built) -> None:
    """A job without subjects routes as before: copper, no candidate."""
    job = propose_job(subjects_board, kinds=("connection",))
    plain = dataclasses.replace(job, subjects=())
    result = ROUTER.route(plain)
    assert result.candidates == () and result.refusals == () and result.tracks
