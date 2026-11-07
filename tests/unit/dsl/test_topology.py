# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored topology trees, including a series terminator and invalid graphs."""

import dataclasses
import io
import json
from pathlib import Path

import pytest

from fenolite.catalog.devices import device_text, parse_device, shipped_device
from fenolite.dsl import Design, DslError, Net, Part, connect, fs, mdb, ps, to_model
from fenolite.model import canonical
from fenolite.model.library import DeviceBridge


def circuit(*, bridge: bool = True) -> tuple[Design, list[Part]]:
    design = Design("clock")
    parts = [Part(f"U{i}", "Fenolite:Conn_1x02", "Fenolite:Header_1x02_P2.54mm") for i in range(1, 5)]
    resistor = Part("R1", device="Fenolite:R_0402")
    design.add(*parts, resistor)
    connect(Net("CLK_A"), parts[0][1], resistor[1])
    connect(Net("CLK_B"), resistor[2], *(part[1] for part in parts[1:]))
    if bridge:
        design.bridge(resistor, 1, 2, delay=fs(25), loss=mdb(2))
    return design, [parts[0], resistor, *parts[1:]]


def test_daisy_chain_round_trip() -> None:
    design, (u1, r1, u2, u3, u4) = circuit()
    tree = design.topology("clk", u1[1] >> r1[1], r1[2] >> u2[1] >> u3[1] >> u4[1])
    tree.delay(u1[1], u4[1], min=ps(1), max=ps(900))
    tree.skew(u2[1], u3[1], u4[1], max=ps(50))
    tree.order()
    model = to_model(design)
    assert model.rules is not None
    (topology,) = model.rules.topologies
    assert len(topology.edges) == 5
    assert sum(edge.kind == "net" for edge in topology.edges) == 4
    assert {edge.net for edge in topology.edges if edge.kind == "net"} == {"CLK_A", "CLK_B"}
    bridge = next(edge for edge in topology.edges if edge.kind == "bridge")
    assert (bridge.a, bridge.b, bridge.delay_fs, bridge.loss_mdb) == ("R1-1", "R1-2", 25, 2)
    assert canonical.loads(canonical.dumps(model.rules), type(model.rules)) == model.rules


def test_cycle_refused() -> None:
    design = Design("cycle")
    a, b, c = (Part(f"U{i}", "Fenolite:Conn_1x02", "Fenolite:Header_1x02_P2.54mm") for i in range(1, 4))
    design.add(a, b, c)
    connect(Net("CLK"), a[1], b[1], c[1])
    with pytest.raises(DslError, match="cycle.*U1-1"):
        design.topology("cycle", a[1] >> b[1] >> c[1] >> a[1])
    with pytest.raises(DslError, match="cycle.*U1-1"):
        design.topology("self", a[1] >> a[1])


def test_branch_and_disconnected_refused() -> None:
    design, (a, r, b, c, _) = circuit()
    tree = design.topology("fan", r[2] >> (b[1], c[1]))
    assert len(tree.to_model().edges) == 2
    with pytest.raises(DslError, match="repeated branch"):
        design.topology("twice", r[2] >> (b[1], c[1]), c[1] >> b[1])
    with pytest.raises(DslError, match="disconnected"):
        design.topology("disjoint", a[1] >> r[1], b[1] >> c[1])


def test_bridge_missing_is_retained_for_build() -> None:
    design, (u1, r1, u2, u3, _) = circuit(bridge=False)
    tree = design.topology("clk", u1[1] >> r1[1], r1[2] >> u2[1] >> u3[1])
    assert tree.to_model().missing_bridges == ("R1",)


def test_bridge_missing_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fenolite.cli.main import main

    script = tmp_path / "design.py"
    script.write_text("""from fenolite.dsl import Design, Net, Part, connect, mm
design = Design("missing")
a = Part("J1", device="Fenolite:Conn_1x2_P2.54")
b = Part("J2", device="Fenolite:Conn_1x2_P2.54")
r = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0402")
design.add(a, b, r)
connect(Net("A"), a[1], r[1])
connect(Net("B"), r[2], b[1])
design.topology("clk", a[1] >> r[1], r[2] >> b[1])
design.board(mm(40), mm(20))
a.place(mm(5), mm(5))
r.place(mm(15), mm(5))
b.place(mm(25), mm(5))
""")
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = main(["build", str(script), "--out", str(tmp_path / "out"), "--dry-run", "--json"])
    result = json.loads(out.getvalue() or "{}")
    assert code == 5, result
    findings = [row for row in result["issues"] if row["code"] == "topology.bridge-missing"]
    assert len(findings) == 1 and "R1" in findings[0]["message"]
    assert not (tmp_path / "out").exists()


def test_device_bridge_round_trip() -> None:
    from fenolite.catalog.records import DeviceRecord, parse_record, record_text, upgraded_device

    original = shipped_device("Fenolite:R_0402")
    record = dataclasses.replace(original, bridges=(DeviceBridge(("P1", "P2"), 100, 2),))
    assert parse_device(device_text(record)) == record
    legacy = parse_record(device_text(record))
    assert isinstance(legacy, DeviceRecord)
    modern = upgraded_device(legacy, licence="CC0-1.0")
    assert parse_record(record_text(modern)) == modern and modern.device.bridges == record.bridges
    design, (u1, r1, u2, _, _) = circuit(bridge=False)
    r1.device = record
    tree = design.topology("device", u1[1] >> r1[1], r1[2] >> u2[1])
    model = tree.to_model()
    assert not model.missing_bridges
    assert next(edge for edge in model.edges if edge.kind == "bridge").delay_fs == 100
