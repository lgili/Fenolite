# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The corners of the test rig (change c0253; capability electrical-contracts, "Rig corners")."""

from __future__ import annotations

from _contracts import judge, row, two_pin

from fenolite.checks.circuit.corners import MAX_SUPPLIES, TOO_MANY, corners
from fenolite.dsl import Design, Net, amp, connect, supply, to_model, volt


def test_the_corners_of_the_bench() -> None:
    """Scenario "The corners of the bench"."""
    d = Design("t")
    d.devices(two_pin("Test:CAP_12V", 'voltage = { abs_max = "12V" }'))
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    c1 = d.part("C1", device="Test:CAP_12V", value="10u")
    connect(v12, c1.P1)
    connect(gnd, c1.P2)
    d.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))
    result = judge(d)
    found = row(result, "circuit.rating-voltage:C1:voltage")
    assert found.status == "fail"
    assert [(c.corner, c.status, c.text) for c in found.corners] == [
        ("bench=min", "pass", "10.8V"),
        ("bench=max", "fail", "13.2V"),
    ]
    (issue,) = [i for i in result.issues if i.code == "circuit.rating-voltage"]
    assert "fails at bench=max" in issue.message and "bench=min" not in issue.message
    assert result.summary["corners"] == 2


def test_too_many_supplies() -> None:
    d = Design("t")
    gnd = d.ground("GND")
    for index in range(MAX_SUPPLIES + 1):
        net = Net(f"N{index}")
        part = d.part(f"R{index}", device="Fenolite:R_0603", value="1k")
        connect(net, part.P1)
        connect(gnd, part.P2)
        d.rig(supply(net, gnd, voltage=volt("1").pct(5), name=f"s{index}"))
    model = to_model(d)
    assert model.rules is not None and corners(model.rules.contracts) is None
    assert judge(d).summary["corners"] == TOO_MANY
