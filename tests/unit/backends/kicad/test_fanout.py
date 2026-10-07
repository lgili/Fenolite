# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plane fan-out engine (capability routing, "Plane fan-out"; change c0107). Hermetic: the bench is built
in process from the built-in catalog, and the copper check judges the plan."""

from __future__ import annotations

import ast
import dataclasses
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import _planebench as pb
import pytest

from fenolite.backends.kicad import fanout
from fenolite.backends.kicad.fanout import FanoutPlan, FanoutSizes, plan_fanout, plane_nets
from fenolite.checks.clearance import ClearanceResolver
from fenolite.checks.copper import check_copper
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id
from fenolite.geometry import Location, point_in_ring
from fenolite.model.board import Keepout, Track, Via
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSubject, Selector
from fenolite.routing.merge import apply
from fenolite.routing.protocol import RoutingResult

ROOT = Path(__file__).resolve().parents[4]
SIZES = FanoutSizes(**pb.SIZES)
NETS = {"GND": SIZES, "VCC": SIZES}


@pytest.fixture(scope="module")
def found(tmp_path_factory: pytest.TempPathFactory) -> Iterator[pb.Loaded]:
    folder = tmp_path_factory.mktemp("planebench")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        yield pb.load(pb.build_project(folder))


def plan(found: pb.Loaded, design: Design | None = None, **changes: object) -> FanoutPlan:
    used = design or found.design
    rules = dataclasses.replace(found.rules, design=used)
    resolver = ClearanceResolver(
        used,
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )

    def clearance(a: RuleSubject, b: RuleSubject) -> int:
        return resolver.resolve(a, b).value or 0

    arguments: dict[str, object] = {
        "nets": NETS,
        "plane_layers": found.plane_layers,
        "outline": found.outline,
        "edge_clearance": pb.EDGE_CLEARANCE,
        "clearance": clearance,
        **changes,
    }
    return plan_fanout(used, found.pads, **arguments)  # type: ignore[arg-type]


def merged(design: Design, made: FanoutPlan) -> Design:
    return apply(design, RoutingResult(tracks=made.tracks, vias=made.vias))


def with_board(design: Design, **changes: object) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, **changes))  # type: ignore[arg-type]


def findings(found: pb.Loaded, design: Design) -> list[str]:
    report = check_copper(
        design,
        pads=found.pads,
        min_clearance=found.rules.min_clearance,
        rules_over_classes=found.rules.rules_over_classes,
        floor_over_rules=found.rules.floor_over_rules,
    )
    return [f"{finding.code}: {finding.message}" for finding in report.findings]


def by_pad(found: pb.Loaded, made: FanoutPlan) -> dict[str, tuple[Track, Via]]:
    """Each fanned-out pad's track and via, by ``REF-NUMBER``."""
    out: dict[str, tuple[Track, Via]] = {}
    for track, via in zip(made.tracks, made.vias, strict=True):
        pad = next(p for p in found.pads if p.position == track.start and p.net_id == track.net_id)
        assert track.end == via.position
        out[f"{pad.ref}-{pad.number}"] = (track, via)
    return out


# -- the bench


def test_bench_one_dogbone_per_smd_pad(found: pb.Loaded) -> None:
    """Scenario "One dog-bone per SMD pad"."""
    made = plan(found)
    assert made.pads == pb.PLANE_PADS and made.joined == () and made.failed == () and made.issues == ()
    assert len(made.tracks) == len(made.vias) == 6
    pads = by_pad(found, made)
    assert tuple(pads) == pb.PLANE_PADS
    board = found.design.board
    assert board is not None
    zone_of = {zone.net_id: zone.outline for zone in board.zones}
    for where, (track, via) in pads.items():
        assert (track.width, track.layer) == (SIZES.width, "F.Cu"), where
        assert (via.diameter, via.drill, via.layers, via.via_type) == (
            SIZES.via_diameter, SIZES.via_drill, ("F.Cu", "B.Cu"), "through",
        )  # fmt: skip
        assert via.net_id == track.net_id == found.pad(where).net_id
        assert via.position.x % 1000 == 0 and via.position.y % 1000 == 0
        assert point_in_ring(via.position, zone_of[via.net_id]) is Location.INSIDE
    assert findings(found, merged(found.design, made)) == []
    assert findings(found, found.design) == []


def test_bench_first_candidate_runs_outward(found: pb.Loaded) -> None:
    """The first direction is the nearest of the eight to the line from the footprint to the pad, and the
    first distance is the smallest multiple of the step that keeps the neck."""
    pads = by_pad(found, plan(found))
    step = fanout.step_of(SIZES)
    assert step == 150_000
    for where in ("C1-1", "C1-2", "C2-1", "C2-2"):
        pad, (_track, via) = found.pad(where), pads[where]
        assert via.position.y == pad.position.y, where
        outward = 1 if pad.number == "2" else -1
        reach = (via.position.x - pad.position.x) * outward
        # half the pad (0.45 mm), the neck (0.2 mm) and half the via (0.3 mm): 0.95 mm, on the next step
        assert reach == 1_050_000 and reach % step == 0, (where, reach)
    for where in ("U1-4", "U1-8"):
        pad, (_track, via) = found.pad(where), pads[where]
        dx, dy = via.position.x - pad.position.x, via.position.y - pad.position.y
        side = -1 if where == "U1-4" else 1
        assert dx * side > 0 and dy * (pad.position.y - pb.at(20, 15, found.design).y) >= 0, (where, dx, dy)


def test_bench_ids_are_those_of_a_merge(found: pb.Loaded) -> None:
    made = plan(found)
    anonymous = RoutingResult(
        tracks=tuple(dataclasses.replace(track, id="") for track in made.tracks),
        vias=tuple(dataclasses.replace(via, id="") for via in made.vias),
    )
    board = apply(found.design, anonymous).board
    assert board is not None
    assert [t.id for t in board.tracks] == [t.id for t in made.tracks]
    assert [v.id for v in board.vias] == [v.id for v in made.vias]


def test_bench_nets_and_arguments(found: pb.Loaded) -> None:
    assert plane_nets(found.design, found.plane_layers) == ("GND", "VCC")
    assert plane_nets(found.design, ("In1.Cu",)) == ("GND",) and plane_nets(found.design, ()) == ()
    only = plan(found, nets={"GND": SIZES})
    assert only.pads == ("C1-2", "C2-2", "U1-4") and len(only.vias) == 3
    assert plan(found, nets={}) == FanoutPlan()
    before = found.design
    plan(found)
    assert found.design is before and before.board is not None and not before.board.vias


# -- joined pads


def test_pads_already_joined(found: pb.Loaded) -> None:
    """Scenario "Pads already joined": a via inside ``C1-2``, and a track from ``C2-2`` to ``U1-4``."""
    board = found.design.board
    assert board is not None
    gnd = found.net_id("GND")
    inside = Via(
        id=derived_id("via", "test", "c1"), position=found.pad("C1-2").position, diameter=600_000,
        drill=300_000, layers=("F.Cu", "B.Cu"), net_id=gnd,
    )  # fmt: skip
    corner = Point(found.pad("C2-2").position.x, found.pad("U1-4").position.y)
    tie = (
        Track(id=derived_id("trk", "test", "tie1"), start=found.pad("C2-2").position, end=corner,
              width=200_000, layer="F.Cu", net_id=gnd),
        Track(id=derived_id("trk", "test", "tie2"), start=corner, end=found.pad("U1-4").position,
              width=200_000, layer="F.Cu", net_id=gnd),
    )  # fmt: skip
    design = with_board(found.design, vias=(inside,), tracks=tie)
    made = plan(found, design)
    assert made.joined == ("C1-2", "U1-4") and made.failed == ()
    pads = by_pad(found, made)
    assert sorted(pads) == ["C1-1", "C2-1", "C2-2", "U1-8"]
    assert len(made.vias) == 4, (
        "C2-2 is first in board order: it gets the via, U1-4 is joined through the track"
    )


def test_joined_through_a_drilled_pad_and_not_through_another_net(found: pb.Loaded) -> None:
    vcc, sig = found.net_id("VCC"), found.net_id("SIG1")
    to_header = Track(
        id=derived_id("trk", "test", "hdr"), start=found.pad("C1-1").position, end=found.pad("J1-1").position,
        width=200_000, layer="F.Cu", net_id=vcc,
    )  # fmt: skip
    made = plan(found, with_board(found.design, tracks=(to_header,)))
    assert made.joined == ("C1-1",)
    wrong_layer = dataclasses.replace(to_header, layer="B.Cu")
    wrong_net = dataclasses.replace(to_header, net_id=sig)
    stub = dataclasses.replace(to_header, end=pb.at(18, 8, found.design))
    for other in (wrong_layer, stub):
        assert plan(found, with_board(found.design, tracks=(other,))).joined == ()
    assert "C1-1" not in plan(found, with_board(found.design, tracks=(wrong_net,))).joined


# -- a pad without room


def test_a_pad_without_room(found: pb.Loaded) -> None:
    """Scenario "A pad without room": a keep-out for vias over ``U1`` and 2 mm around it."""
    centre = pb.at(20, 15, found.design)
    half_x, half_y = 2_700_000 + 775_000 + 2_000_000, 1_905_000 + 300_000 + 2_000_000
    area = Keepout(
        id=derived_id("kpo", "test", "u1"),
        outline=(
            Point(centre.x - half_x, centre.y - half_y), Point(centre.x + half_x, centre.y - half_y),
            Point(centre.x + half_x, centre.y + half_y), Point(centre.x - half_x, centre.y + half_y),
        ),
        layers=("*.Cu",),
        no_vias=True,
    )  # fmt: skip
    made = plan(found, with_board(found.design, keepouts=(area,)))
    assert made.failed == ("U1-4", "U1-8") and made.joined == ()
    assert [(i.code, i.severity, i.where) for i in made.issues] == [
        ("kicad.fanout.failed", "warning", "U1-4"),
        ("kicad.fanout.failed", "warning", "U1-8"),
    ]
    for issue, net in zip(made.issues, ("GND", "VCC"), strict=True):
        assert issue.where in issue.message and net in issue.message and "keep-out" in issue.message
    assert sorted(by_pad(found, made)) == ["C1-1", "C1-2", "C2-1", "C2-2"]


def test_what_blocks_a_candidate(found: pb.Loaded) -> None:
    """A track keep-out, other copper, the board edge and a missing zone each stop a via."""
    design = found.design
    # a wall of another net right of C1-2: its first direction is taken, the next one serves
    pad = found.pad("C1-2")
    wall = Track(
        id=derived_id("trk", "test", "wall"),
        start=Point(pad.position.x + 1_050_000, pad.position.y - 2_000_000),
        end=Point(pad.position.x + 1_050_000, pad.position.y + 2_000_000), width=200_000, layer="B.Cu",
        net_id=found.net_id("SIG1"),
    )  # fmt: skip
    plain, walled = by_pad(found, plan(found)), by_pad(found, plan(found, with_board(design, tracks=(wall,))))
    assert walled["C1-2"][1].position != plain["C1-2"][1].position
    assert walled["C1-1"] == plain["C1-1"]
    assert (
        findings(
            found, merged(with_board(design, tracks=(wall,)), plan(found, with_board(design, tracks=(wall,))))
        )
        == []
    )
    # no track may leave C1: a keep-out for tracks on F.Cu over the part and 3 mm around it
    c1 = pb.at(20, 8, design)
    ring = (
        Point(c1.x - 4_000_000, c1.y - 3_500_000), Point(c1.x + 4_000_000, c1.y - 3_500_000),
        Point(c1.x + 4_000_000, c1.y + 3_500_000), Point(c1.x - 4_000_000, c1.y + 3_500_000),
    )  # fmt: skip
    no_tracks = Keepout(id=derived_id("kpo", "test", "c1"), outline=ring, layers=("F.Cu",), no_tracks=True)
    made = plan(found, with_board(design, keepouts=(no_tracks,)))
    assert made.failed == ("C1-1", "C1-2") and "forbids tracks" in made.issues[0].message
    other_layer = dataclasses.replace(no_tracks, layers=("B.Cu",))
    assert plan(found, with_board(design, keepouts=(other_layer,))).failed == ()
    # without a zone of the net on a plane layer nothing passes
    board = design.board
    assert board is not None
    no_gnd = with_board(design, zones=tuple(z for z in board.zones if z.net_id != found.net_id("GND")))
    made = plan(found, no_gnd)
    assert made.failed == ("C1-2", "C2-2", "U1-4") and "zone of GND" in made.issues[0].message
    # an edge clearance wider than the board leaves no room
    made = plan(found, edge_clearance=25_000_000)
    assert set(made.failed) == set(pb.PLANE_PADS) and "board edge" in made.issues[0].message


def test_hole_to_hole_rule_is_kept(found: pb.Loaded) -> None:
    pitch = Rule(
        id=derived_id("rul", "test", "pitch"), name="pitch", kind="hole_to_hole",
        selector_a=Selector("all"), min=2_000_000,
    )  # fmt: skip
    wide = pb.with_rules(found, pitch)
    made = plan(wide, wide.design)
    drills = [(via.position, via.drill) for via in made.vias]
    for i, (a, drill_a) in enumerate(drills):
        for b, drill_b in drills[i + 1 :]:
            gap2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
            assert gap2 >= (2_000_000 + (drill_a + drill_b) // 2) ** 2
    assert made.failed == ()


# -- determinism, the table of codes, the imports

SCRIPT = """
import sys
sys.path[:0] = {paths!r}
from pathlib import Path
import _planebench as pb
from test_fanout import plan
found = pb.load(Path({board!r}))
made = plan(found)
print([t.id for t in made.tracks], [v.id for v in made.vias])
print([(v.position.x, v.position.y) for v in made.vias])
"""


def test_deterministic(found: pb.Loaded, tmp_path: Path) -> None:
    """Scenario "Deterministic": two processes with different hash seeds give equal plans, ids included."""
    assert plan(found) == plan(found)
    board = pb.build_project(tmp_path)
    paths = [str(ROOT / "tests" / "routing"), str(ROOT / "tests"), str(Path(__file__).resolve().parent)]
    script = tmp_path / "run.py"
    script.write_text(SCRIPT.format(paths=paths, board=str(board)), encoding="utf-8")
    outputs = []
    for seed in ("1", "2"):
        run = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, check=False,
            env={"PYTHONHASHSEED": seed, "PATH": "", "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
        )  # fmt: skip
        assert run.returncode == 0, run.stderr
        outputs.append(run.stdout)
    made = plan(found)
    assert outputs[0] == outputs[1] and str([t.id for t in made.tracks]) in outputs[0]


def test_codes_and_evidence() -> None:
    assert dict(fanout.FANOUT_ISSUE_CODES) == {"kicad.fanout.failed": "warning"}
    assert fanout.EVIDENCE.level is Level.INFERRED and fanout.EVIDENCE.hypotheses == ("H-K-FANOUT",)
    with pytest.raises(ValueError, match="drill"):
        FanoutSizes(400_000, 600_000, 600_000, 200_000)
    with pytest.raises(ValueError, match="width"):
        FanoutSizes(0, 600_000, 300_000, 200_000)


def test_module_imports() -> None:
    """The engine imports only the standard library, ``core``, ``model``, ``geometry``, ``backends.base``
    and modules of ``backends.kicad``."""
    tree = ast.parse(Path(fanout.__file__).read_text(encoding="utf-8"))
    names = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    allowed = (
        "fenolite.core",
        "fenolite.model",
        "fenolite.geometry",
        "fenolite.backends.base",
        "fenolite.backends.kicad",
    )
    assert all(name.startswith(allowed) or not name.startswith("fenolite") for name in names), names
