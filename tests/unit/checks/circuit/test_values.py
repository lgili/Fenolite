# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Applied values and part classes of the contract judge (change c0253; capability electrical-contracts,
"Applied values from stated sources", "Conflicting sources", "Part classes for contracts" and "Test rig")."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

from _contracts import judge, two_pin

from fenolite.checks.circuit.rails import View, _rail_issues  # pyright: ignore[reportPrivateUsage]
from fenolite.checks.circuit.values import resolve
from fenolite.cli._contracts import classes_of
from fenolite.dsl import Design, Rail, amp, block, connect, henry, ohm, supply, to_model, volt
from fenolite.model.design import Design as ModelDesign

CHECKS = Path(__file__).resolve().parents[4] / "src" / "fenolite" / "checks"
CAP = two_pin("Test:CAP_25V", 'voltage = { abs_max = "25V" }')
IND = two_pin("Test:IND_2A", 'current = { abs_max = "2A" }', symbol="Fenolite:Inductor")


def _values(model: ModelDesign, currents: dict[str, tuple[Fraction, str]] | None = None):  # type: ignore[no-untyped-def]
    contracts = model.rules.contracts if model.rules is not None else None
    view = View(model.circuit, contracts.rig if contracts is not None else ())
    _rail_issues(view)
    found = resolve(model, view, contracts, currents=currents)
    names = {net.id: net.name for net in model.circuit.nets}
    return (
        {names[k]: v for k, v in found.voltage.items()},
        {names[k]: v for k, v in found.current.items()},
        found,
    )


def _input(rig: bool = True) -> Design:
    d = Design("t")
    d.devices(CAP)
    gnd = d.ground("GND")
    v12 = d.rail("V12", ground=gnd)
    c1 = d.part("C1", device="Test:CAP_25V", value="10u")
    connect(v12, c1.P1)
    connect(gnd, c1.P2)
    if rig:
        d.rig(supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench"))
    return d


def test_rig_bounds_the_input() -> None:
    """Scenario "A rig bounds the input"."""
    volts, amps, _ = _values(to_model(_input()))
    v12 = volts["V12"]
    assert (v12.low, v12.high, v12.source, v12.basis) == (
        Fraction(108, 10),
        Fraction(132, 10),
        "user",
        "rig bench",
    )
    assert (amps["V12"].high, amps["V12"].basis) == (Fraction(3), "rig bench")
    assert (volts["GND"].low, volts["GND"].high) == (0, 0)
    assert v12.rigs == frozenset({"bench"})


def test_unconfirmed_roles_give_nothing() -> None:
    """Scenario "Unconfirmed roles give nothing": no rig, no rail, no stated role: every rating row is
    unknown."""
    d = Design("t")
    d.devices(CAP)
    c1 = d.part("C1", device="Test:CAP_25V", value="10u")
    connect(_net("A"), c1.P1)
    connect(_net("B"), c1.P2)
    result = judge(d)
    volts, amps, _ = _values(to_model(d))
    assert volts == {} and amps == {}
    assert [r.status for r in result.rows if r.id.startswith("circuit.rating")] == ["unknown"]


def _net(name: str):  # type: ignore[no-untyped-def]
    from fenolite.dsl import Net

    return Net(name)


def _switch(role_current: bool) -> Design:
    d = Design("t")
    d.devices(IND)
    sw, out = _net("SW"), _net("OUT")
    inductor = d.part("L1", device="Test:IND_2A", value=henry("4u7"))
    connect(sw, inductor.P1)
    connect(out, inductor.P2)
    d.net_role(sw, "switch_node", current=amp("1.5") if role_current else None)
    return d


def test_current_order() -> None:
    """Scenario "Currents in the order of roles": the role's own current, then the ``[[current]]`` row,
    then ``--current`` (``fenolite roles --check`` passes the two as ``currents``, in that order)."""
    model = to_model(_switch(False))
    row = {"SW": (Fraction(8, 10), "requirements.toml")}
    _, amps, _ = _values(model, row)
    assert (amps["SW"].high, amps["SW"].basis, amps["SW"].source) == (
        Fraction(8, 10),
        "requirements.toml",
        "user",
    )
    _, amps, _ = _values(model, {"SW": (Fraction(11, 10), "--current")})
    assert (amps["SW"].high, amps["SW"].basis) == (Fraction(11, 10), "--current")
    _, amps, _ = _values(to_model(_switch(True)), row)
    assert (amps["SW"].high, amps["SW"].source) == (Fraction(3, 2), "role")  # the role's own wins


def test_conflict_two_sources_disagree() -> None:
    """Scenario "Two sources disagree": the rail's range is used and one warning names both."""
    d = Design("t")
    d.devices(CAP)
    gnd = d.ground("GND")
    v33 = d.rail("3V3", voltage=volt("3.3").pct(3), ground=gnd)
    c1 = d.part("C1", device="Test:CAP_25V", value="10u")
    connect(v33, c1.P1)
    connect(gnd, c1.P2)
    d.net_role(v33.members["hv"], "power", voltage=volt("1.8"))
    volts, _, found = _values(to_model(d))
    assert volts["3V3"].basis == "rail 3V3"
    (conflict,) = found.issues
    assert conflict.code == "circuit.value-conflict" and conflict.severity == "warning"
    assert "rail 3V3" in conflict.message and "declared power role of 3V3" in conflict.message


def test_classes_a_stated_class_wins() -> None:
    """Scenario "A stated class wins": ``roles.classify`` with the user's class, run by the command."""
    d = _switch(True)
    model = to_model(d)
    (component,) = model.circuit.components
    assert classes_of(model)[component.id] == "inductor"
    d.part_class(d.parts["L1"], "resistor")
    model = to_model(d)
    assert classes_of(model)[component.id] == "resistor"


def test_one_table_no_prefix_table_in_checks() -> None:
    """Scenario "One prefix table": no module of ``checks`` maps reference prefixes to classes, and without
    ``classes`` the series and power rows are ``unknown`` with basis ``no class``."""
    for path in CHECKS.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Dict | ast.Tuple):
                texts = [
                    n.value
                    for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
                assert not {"inductor", "capacitor", "resistor"} <= set(texts) or "L" not in texts, path
    d = _switch(True)
    result = judge(d, classes=False)
    (current,) = [r for r in result.rows if r.id == "circuit.rating-current:L1:current"]
    assert current.status == "unknown" and current.missing == "no class"


@block
def _source(b, *, voltage=None, current=None):  # type: ignore[no-untyped-def]
    port = b.port("VOUT", Rail, direction="out", voltage=voltage, current=current)
    r = b.part("R", device="Fenolite:R_0603", value=ohm("1k"))
    connect(port, r.P1)


def test_rig_source_beside_a_regulator() -> None:
    """Scenario "A rig supply beside a regulator": the rig counts as a source of the rail."""
    d = Design("t")
    gnd = d.ground("GND")
    v33 = d.rail("3V3", ground=gnd)
    buck = d.use(_source, "buck", voltage=volt("3.3").pct(3), current=amp(1))
    connect(v33, buck.VOUT)
    bleeder = d.part("R9", device="Fenolite:R_0603", value=ohm("1k"))
    connect(v33, bleeder.P1)
    connect(gnd, bleeder.P2)
    d.rig(supply(v33, gnd, voltage=volt("3.3"), name="ext3"))
    result = judge(d)
    (sources,) = [i for i in result.issues if i.code == "circuit.rail-sources"]
    assert "rig ext3" in sources.message and "buck/VOUT" in sources.message
