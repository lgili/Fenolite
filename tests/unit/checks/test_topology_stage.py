# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Topology verdicts measured against authored integer geometry and hand-calculated sums."""

from dataclasses import replace
from pathlib import Path

from _topologybench import MM, bench, ident

from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES, STAGE_ORDER
from fenolite.checks.documents import DOCUMENT_STAGES
from fenolite.checks.padpath import CopperGraph
from fenolite.checks.topology import measure_path, topology_stage
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Track
from fenolite.model.rules import Propagation, TopologyConstraint, TopologyEdge


def constrained(design, *constraints):
    assert design.rules is not None
    topology = replace(design.rules.topologies[0], constraints=constraints)
    return replace(design, rules=replace(design.rules, topologies=(topology,)))


def test_hand_computed_delay_and_subjects() -> None:
    design = bench()
    assert design.rules is not None
    topology = design.rules.topologies[0]
    measured = measure_path(topology, "U1-1", "U2-1", CopperGraph(design), design.rules)
    assert measured.status == "ok" and measured.low_fs == measured.high_fs == 325_000
    result = topology_stage(design, evidence=Evidence(Level.KICAD_VERIFIED))
    assert result.issues == () and result.summary["judged"] == 1
    assert result.evidence.level == Level.INFERRED
    result = topology_stage(bench(max_fs=300_000), evidence=Evidence(Level.KICAD_VERIFIED))
    (found,) = result.issues
    assert found.code == "topology.delay-out-of-range" and found.severity == "error"
    assert "325000 fs" in found.message and "300000 fs" in found.message
    assert "F.Cu=5900 fs/mm" in found.message and "via=10000 fs" in found.message
    assert {subject.kind for subject in result.subjects[0]} >= {"topology", "pad", "net"}
    colliding = bench(max_fs=300_000)
    colliding = replace(
        colliding,
        rules=replace(colliding.rules, topologies=(replace(colliding.rules.topologies[0], name="CLK"),)),
    )
    kinds = {subject.kind for subject in topology_stage(colliding).subjects[0]}
    assert kinds >= {"topology", "net", "pin", "pad"}


def test_delay_strict_side_rounding_and_die_delay() -> None:
    design = bench()
    assert design.board is not None and design.rules is not None
    fp = design.board.footprints[1]
    pad = replace(fp.pads[0], die_delay_fs=13)
    design = replace(
        design,
        board=replace(design.board, footprints=(design.board.footprints[0], replace(fp, pads=(pad,)))),
        rules=replace(
            design.rules,
            propagation=(Propagation("F.Cu", 1), Propagation("In1.Cu", 1), Propagation(via_fs=0)),
        ),
    )
    # Two whole segments remain exact; die delay is added once.
    measured = measure_path(design.rules.topologies[0], "U1-1", "U2-1", CopperGraph(design), design.rules)
    assert measured.low_fs == measured.high_fs == 63
    # Shift the via and both meeting track ends one nanometre: 30.000001 and 19.999999 fs.
    via = replace(design.board.vias[0], position=Point(30 * MM + 1, 0))
    front, inner = design.board.tracks
    design = replace(
        design,
        board=replace(
            design.board,
            vias=(via,),
            tracks=(replace(front, end=via.position), replace(inner, start=via.position)),
        ),
    )
    measured = measure_path(design.rules.topologies[0], "U1-1", "U2-1", CopperGraph(design), design.rules)
    assert (measured.low_fs, measured.high_fs) == (62, 64)
    design = constrained(design, TopologyConstraint("delay", ("U1-1", "U2-1"), min_fs=63, max_fs=63))
    assert "62 fs below minimum 63 fs" in topology_stage(design).issues[0].message


def test_loss_budget_and_bridge_delay() -> None:
    design = constrained(
        bench(), TopologyConstraint("loss", ("U1-1", "U2-1"), max_mdb=241, severity="warning")
    )
    result = topology_stage(design)
    assert result.issues[0].code == "topology.loss-over-budget"
    assert result.issues[0].severity == "warning" and "242 mdb" in result.issues[0].message
    assert design.rules is not None
    topology = replace(
        design.rules.topologies[0],
        nodes=("R1-1", "R1-2"),
        constraints=(),
        edges=(TopologyEdge("R1-1", "R1-2", "bridge", delay_fs=19, loss_mdb=3),),
    )
    measured = measure_path(topology, "R1-1", "R1-2", CopperGraph(design), design.rules)
    assert measured.low_fs == measured.high_fs == 19
    assert measure_path(topology, "R1-1", "R1-2", CopperGraph(design), design.rules, loss=True).high_mdb == 3


def test_input_missing_and_unrouted_are_not_judged() -> None:
    design = bench(max_fs=1)
    assert design.rules is not None and design.board is not None
    design = replace(
        design,
        rules=replace(
            design.rules, propagation=tuple(row for row in design.rules.propagation if row.layer != "In1.Cu")
        ),
    )
    result = topology_stage(design, evidence=Evidence(Level.KICAD_VERIFIED))
    assert [found.code for found in result.issues] == ["topology.input-missing"]
    assert result.summary["not_judged"] == 1 and result.summary["judged"] == 0
    assert result.evidence.level == Level.UNVERIFIED
    design = replace(design, board=replace(design.board, tracks=design.board.tracks[:1]))
    result = topology_stage(design)
    assert [found.code for found in result.issues] == ["topology.unrouted"]
    assert "U2-1" in result.issues[0].message and result.summary["not_judged"] == 1


def test_loads_out_of_order() -> None:
    design = bench()
    assert design.board is not None and design.rules is not None
    part = replace(
        design.circuit.components[0],
        id=ident("cmp", "U3"),
        ref="U3",
        path="U3",
        pins=(replace(design.circuit.components[0].pins[0], id=ident("pin", "U3-1")),),
    )
    fp = design.board.footprints[0]
    fp = replace(
        fp,
        id=ident("fp", "U3"),
        component_id=part.id,
        position=Point(20 * MM, 0),
        pads=(replace(fp.pads[0], id=ident("pad", "U3")),),
    )
    topology = replace(
        design.rules.topologies[0],
        nodes=("U1-1", "U2-1", "U3-1"),
        edges=(TopologyEdge("U1-1", "U2-1", net="CLK"), TopologyEdge("U2-1", "U3-1", net="CLK")),
        constraints=(TopologyConstraint("order"),),
    )
    design = replace(
        design,
        circuit=replace(design.circuit, components=(*design.circuit.components, part)),
        board=replace(design.board, footprints=(*design.board.footprints, fp)),
        rules=replace(design.rules, topologies=(topology,)),
    )
    result = topology_stage(design)
    assert len(result.issues) == 1 and result.issues[0].code == "topology.order"
    assert "U3-1 is reached before U2-1" in result.issues[0].message


def test_order_loops_and_stub_length() -> None:
    design = constrained(bench(), TopologyConstraint("stub", max_nm=2 * MM), TopologyConstraint("order"))
    assert design.board is not None
    track = design.board.tracks[0]
    spur = Track(
        id=ident("trk", "spur"),
        start=Point(10 * MM, 0),
        end=Point(10 * MM, 3 * MM),
        width=track.width,
        layer=track.layer,
        net_id=track.net_id,
    )
    design = replace(design, board=replace(design.board, tracks=(*design.board.tracks, spur)))
    result = topology_stage(design)
    assert [found.code for found in result.issues] == ["topology.stub-too-long"]
    assert "3000000 nm" in result.issues[0].message


def test_skew_from_root_and_native_die_input_missing() -> None:
    from fenolite.model.base import ExtBag

    design = bench()
    assert design.board is not None and design.rules is not None
    part = replace(
        design.circuit.components[0],
        id=ident("cmp", "U3"),
        ref="U3",
        path="U3",
        pins=(replace(design.circuit.components[0].pins[0], id=ident("pin", "U3-1")),),
    )
    fp = design.board.footprints[0]
    extra = replace(
        fp,
        id=ident("fp", "U3"),
        component_id=part.id,
        position=Point(20 * MM, 0),
        pads=(replace(fp.pads[0], id=ident("pad", "U3")),),
    )
    topology = replace(
        design.rules.topologies[0],
        nodes=("U1-1", "U2-1", "U3-1"),
        edges=(TopologyEdge("U1-1", "U2-1", net="CLK"), TopologyEdge("U1-1", "U3-1", net="CLK")),
        constraints=(TopologyConstraint("skew", ("U2-1", "U3-1"), max_fs=200_000),),
    )
    design = replace(
        design,
        circuit=replace(design.circuit, components=(*design.circuit.components, part)),
        board=replace(design.board, footprints=(*design.board.footprints, extra)),
        rules=replace(design.rules, topologies=(topology,)),
    )
    result = topology_stage(design)
    assert [row.code for row in result.issues] == ["topology.skew-out-of-range"]
    assert "U3-1 skew -207000 fs" in result.issues[0].message
    design = bench()
    fp = design.board.footprints[0]
    pad = replace(fp.pads[0], ext={"kicad": ExtBag(payload=(("slot:0", "(die_delay\n1.2)"),))})
    design = replace(
        design, board=replace(design.board, footprints=(replace(fp, pads=(pad,)), design.board.footprints[1]))
    )
    result = topology_stage(design)
    assert [row.code for row in result.issues] == ["topology.input-missing"]
    assert result.summary["not_judged"] == 1


def test_equal_fractional_path_delays_have_zero_protocol_skew() -> None:
    from fenolite.model.rules import ProtocolSkew

    design = bench()
    assert design.board is not None and design.rules is not None
    via = replace(design.board.vias[0], position=Point(30 * MM + 1, 0))
    front, inner = design.board.tracks
    a = replace(design.rules.topologies[0], name="a", constraints=())
    b = replace(a, id=ident("top", "b"), name="b")
    design = replace(
        design,
        board=replace(
            design.board,
            tracks=(replace(front, end=via.position), replace(inner, start=via.position)),
            vias=(via,),
        ),
        rules=replace(
            design.rules, topologies=(a, b), protocol_skews=(ProtocolSkew("comparison", ("a", "b"), 0),)
        ),
    )
    measured = measure_path(a, "U1-1", "U2-1", CopperGraph(design), design.rules)
    assert measured.low_fs < measured.high_fs
    assert not topology_stage(design).issues


def test_default_order_and_skip_reasons() -> None:
    assert STAGE_ORDER[STAGE_ORDER.index("length.rules") + 1] == "topology.rules"
    assert "topology.rules" in DEFAULT_STAGES
    assert "topology.rules" not in (*ORACLE_STAGES, *DOCUMENT_STAGES)
    assert topology_stage(None).reason == "read-refused"
    design = bench()
    assert design.rules is not None
    assert topology_stage(replace(design, rules=replace(design.rules, topologies=()))).reason == "no-topology"


def test_example_build_and_stage(monkeypatch, tmp_path: Path) -> None:
    from _checkcli import run

    example = Path(__file__).resolve().parents[3] / "examples" / "topologies" / "design.py"
    folder = tmp_path / "topologies"
    code, built, _, _ = run(monkeypatch, tmp_path, "build", str(example), "--out", str(folder), "--confirm")
    assert code == 0, built
    assert "pair_usb_skew" in (folder / "topologies.kicad_dru").read_text()
    code, checked, _, _ = run(monkeypatch, tmp_path, "check", str(folder), "--stages", "topology.rules")
    assert code == 0, checked
    (stage,) = checked["result"]["stages"]
    assert stage["summary"] == {
        "topologies": 3,
        "constraints": {"delay": 3, "loss": 3, "order": 1, "skew": 2, "stub": 1},
        "judged": 10,
        "not_judged": 0,
    }
