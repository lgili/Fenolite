# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The inference rules of the net roles (change c0222; capability net-roles, "Inference rules" and
"Currents are never inferred") on authored circuits; the reference boards are in
``test_infer_reference.py``."""

from __future__ import annotations

from _rolecircuits import GND_PIN, buck, circuit

from fenolite.core.coords import Point
from fenolite.model.rules import NetRole, RoleSet
from fenolite.roles.classify import classify
from fenolite.roles.infer import infer, with_currents


def _rows(found: RoleSet) -> dict[str, tuple[str, str, str]]:
    return {role.net: (role.kind, role.rule, role.confidence) for role in found.nets}


def test_switching_node_and_hot_loop_of_a_buck() -> None:
    """Scenario "Switching node and hot loop of a buck", on the authored circuit of the buck: ``SW`` is a
    switch node by ``SW-1`` of high confidence, and the hot loop runs through ``C1`` and both switches."""
    made = buck()
    found = infer(made, classify(made))
    rows = _rows(found.roles)
    assert rows["SW"] == ("switch_node", "SW-1", "high")
    (loop,) = found.roles.loops
    assert loop.pads == ("C1-1", "Q1-3", "Q1-1", "Q2-3", "Q2-1", "C1-2")
    assert (loop.name, loop.rule, loop.confidence, loop.origin) == ("hot_SW", "HL-1", "high", "inferred")
    assert found.pads["SW"] == ("L1-1", "Q1-1", "Q2-3")


def test_every_net_of_the_buck() -> None:
    made = buck()
    found = infer(made, classify(made))
    assert _rows(found.roles) == {
        "FB": ("signal", "SIG-0", "low"),
        "GH": ("gate", "GD-1", "high"),
        "GL": ("gate", "GD-1", "high"),
        "GND": ("ground", "GND-1", "high"),
        "ISNS": ("signal", "SIG-0", "low"),
        "SW": ("switch_node", "SW-1", "high"),
        "VIN": ("power", "PWR-1", "medium"),
        "VL": ("power", "PWR-1", "medium"),
        "VOUT": ("power", "PWR-1", "medium"),
    }
    assert {role.source for role in found.roles.nets} == {"inferred"}
    (pair,) = found.roles.kelvins
    assert (pair.element, pair.receiver, pair.force) == (("R12-1", "R12-2"), ("U3-1", "U3-2"), ())
    assert (pair.rule, pair.confidence) == ("KS-1", "medium")  # the shunt is a heuristic of the value
    gates = {loop.name: loop for loop in found.roles.gates}
    assert sorted(gates) == ["gate_Q1", "gate_Q2"]
    assert gates["gate_Q1"].pads == ("U1-2", "Q1-2", "Q1-1", "U1-3")  # return on the controller's SW pin
    assert gates["gate_Q2"].pads == ("U1-4", "Q2-2", "Q2-1", "U1-5")  # return on its ground pin
    assert found.issues == ()


def test_the_nearest_capacitor_closes_the_hot_loop() -> None:
    """With two capacitors across the far nets, ``HL-1`` takes the one nearest the switches."""
    made = buck()
    parts = {c.ref: c for c in made.components}
    extra = circuit({"C9": ("100uF", ("", ""))}, {"VIN": ("C9.1",), "GND": ("C9.2",)})
    nets = tuple(
        net.__class__(
            id=net.id,
            name=net.name,
            members=net.members + next((n.members for n in extra.nets if n.name == net.name), ()),
        )
        for net in made.nets
    )
    both = made.__class__(
        components=(*parts.values(), *extra.components), nets=nets, interfaces=made.interfaces
    )
    near = {"C1-1": Point(40, 0), "C1-2": Point(40, 10), "C9-1": Point(1, 0), "C9-2": Point(1, 10)}
    switches = {name: Point(5, 5) for name in ("Q1-3", "Q1-1", "Q2-3", "Q2-1")}
    (loop,) = infer(both, classify(both), positions={**near, **switches}).roles.loops
    assert loop.pads[0] == "C9-1" and loop.pads[-1] == "C9-2"
    (first,) = infer(both, classify(both)).roles.loops
    assert first.pads[0] == "C1-1"  # without positions, the first reference


def test_no_high_voltage_from_a_name() -> None:
    """Scenario "No high voltage from a name": ``HV_BUS`` without a working voltage is not high voltage;
    with one at or above the user's ``high_voltage_mv`` it is."""
    made = circuit(
        {"J1": ("BUS", ("", "")), "C1": ("1uF", ("", "")), "U1": ("X", ("VIN", GND_PIN))},
        {"HV_BUS": ("J1.1", "C1.1", "U1.1"), "GND": ("J1.2", "C1.2", "U1.2")},
    )
    rows = _rows(infer(made, classify(made)).roles)
    assert rows["HV_BUS"][0] != "high_voltage"
    rows = _rows(infer(made, classify(made), working_mv={"HV_BUS": 400_000}, high_voltage_mv=60_000).roles)
    assert rows["HV_BUS"] == ("high_voltage", "HV-1", "high")
    rows = _rows(infer(made, classify(made), working_mv={"HV_BUS": 400_000}).roles)
    assert rows["HV_BUS"][0] != "high_voltage"  # the profile gives no high_voltage_mv


def test_a_power_net_without_a_current() -> None:
    """Scenario "A power net without a current", for the inference: no role gets a current that no one
    stated; a ``[[current]]`` row comes before ``--current``, and the role's own comes first."""
    made = buck()
    roles = infer(made, classify(made)).roles
    assert all(role.milliamps is None for role in roles.nets)
    assert with_currents(roles).nets == roles.nets
    given = with_currents(roles, requirements_current={"VOUT": 2000}, given={"VOUT": 3000, "VIN": 1000})
    assert {r.net: r.milliamps for r in given.nets if r.milliamps} == {"VOUT": 2000, "VIN": 1000}
    stated = RoleSet(nets=(NetRole("VIN", "power", "confirmed", milliamps=500),))
    assert with_currents(stated, given={"VIN": 1000}).nets[0].milliamps == 500


def test_two_kinds_at_one_confidence_are_ambiguous() -> None:
    """A switching-node pin of a controller (``SW-3``, medium) on a net that is also a far net of a switch
    (``PWR-1``, medium) keeps the first kind and adds ``roles.ambiguous``."""
    made = circuit(
        {
            "Q1": ("N", ("S", "G", "D")),
            "Q2": ("N", ("S", "G", "D")),
            "L1": ("1uH", ("", "")),
            "U1": ("C", ("PH", "FB")),
        },
        {"SW": ("Q1.1", "Q2.3", "L1.1"), "X": ("Q1.3", "U1.1"), "GND": ("Q2.1",), "OUT": ("L1.2",)},
    )
    found = infer(made, classify(made))
    rows = _rows(found.roles)
    assert rows["X"] == ("switch_node", "SW-3", "medium")
    (ambiguous,) = found.issues
    assert ambiguous.code == "roles.ambiguous" and ambiguous.severity == "warning" and ambiguous.where == "X"
    assert "power by PWR-1" in ambiguous.message
    assert rows["GND"] == ("ground", "GND-1", "medium")  # PWR-1 does not contest a ground


def test_low_results_fall_to_signal() -> None:
    """A rule that reads a class found only from a prefix gives nothing: the net is a low ``signal``."""
    made = circuit(
        {"Q1": ("", ("1", "2", "3")), "Q2": ("", ("1", "2", "3")), "L1": ("", ("", ""))},
        {"N1": ("Q1.1", "Q2.3", "L1.1"), "N2": ("L1.2",)},
    )
    rows = _rows(infer(made, classify(made)).roles)
    assert rows == {"N1": ("signal", "SIG-0", "low"), "N2": ("signal", "SIG-0", "low")}
