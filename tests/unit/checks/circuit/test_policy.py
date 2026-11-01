# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The derating policy (change c0253; capability electrical-contracts, "Derating policy", "Ratings without a
policy" and "No shipped derating values")."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

from _contracts import judge, row, two_pin

from fenolite.dsl import Design, amp, connect, ratio, select, supply, volt
from fenolite.model.rules import DERATING_KEYS

SRC = Path(__file__).resolve().parents[4] / "src" / "fenolite"


def _input(*rules: dict[str, object]) -> Design:
    d = Design("t")
    d.devices(two_pin("Test:CAP_16V", 'voltage = { abs_max = "16V" }'))
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    c1 = d.part("C1", device="Test:CAP_16V", value="10u")
    connect(v12, c1.P1)
    connect(gnd, c1.P2)
    d.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))
    for rule in rules:
        d.derating(**rule)  # type: ignore[arg-type]
    return d


def test_tightens_the_input_capacitor() -> None:
    """Scenario "The policy tightens the input capacitor"."""
    result = judge(_input({"capacitor_voltage": ratio(50)}))
    found = row(result, "circuit.rating-voltage:C1:voltage")
    assert found.status == "fail" and found.value.range.high == Fraction(132, 10)
    assert found.limit.range.high == 8 and found.limit.source == "policy"
    assert all(t in found.limit.basis for t in ("capacitor_voltage", "500‰", "16V"))
    assert [i.severity for i in result.issues if i.code == "circuit.rating-voltage"] == ["error"]


def test_a_part_scope_wins() -> None:
    """Scenario "A part scope wins"."""
    rules = ({"capacitor_voltage": ratio(50)}, {"capacitor_voltage": ratio(90), "parts": select.ref("C1")})
    found = row(judge(_input(*rules)), "circuit.rating-voltage:C1:voltage")
    assert found.limit.range.high == Fraction(144, 10) and found.status == "pass"


def test_a_class_key_beats_a_generic_key() -> None:
    found = row(
        judge(_input({"voltage": ratio(50)}, {"capacitor_voltage": ratio(90)})),
        "circuit.rating-voltage:C1:voltage",
    )
    assert found.limit.range.high == Fraction(144, 10)


def test_missing_no_policy_no_derating() -> None:
    """Scenario "No policy, no derating"."""
    result = judge(_input())
    found = row(result, "circuit.rating-voltage:C1:voltage")
    assert found.status == "pass" and found.limit.range.high == 16 and found.limit.source == "device"
    (policy,) = [i for i in result.issues if i.code == "circuit.policy-missing"]
    assert policy.severity == "info" and "circuit.rating-voltage:C1:voltage" in policy.message


def test_no_defaults_in_the_code() -> None:
    """Scenario "No defaults in the code": without a ``derating`` call every limit is the device's, and no
    module of the model rules or the judge maps a derating key to a number."""
    result = judge(_input())
    assert {r.limit.source for r in result.rows if r.id.startswith("circuit.rating")} == {"device"}
    for path in (SRC / "model" / "rules.py", *sorted((SRC / "checks" / "circuit").glob("*.py"))):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if isinstance(key, ast.Constant) and key.value in DERATING_KEYS:
                        assert not (isinstance(value, ast.Constant) and isinstance(value.value, int)), path
            if isinstance(node, ast.keyword) and node.arg in DERATING_KEYS:
                assert not isinstance(node.value, ast.Constant), path
