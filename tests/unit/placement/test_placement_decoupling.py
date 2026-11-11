# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

from fenolite.model.circuit import PinRef
from fenolite.placement.decoupling import Capacitor, SupplyBank, assign_bypass_banks, suggest_bypass
from fenolite.placement.topology import Incidence, PadIdentity


def row(owner, number, net):
    return Incidence(PinRef(owner, number), net, (PadIdentity(owner, number),))


DIGITAL = SupplyBank("digital", PinRef("cpu", "VDD"), PinRef("cpu", "VSS"), "authored device")
ANALOG = SupplyBank("analog", PinRef("cpu", "AVDD"), PinRef("cpu", "VSS"), "authored device")
OTHER = SupplyBank("other", PinRef("other", "VDD"), PinRef("other", "VSS"), "authored device")
ROWS = (
    row("cpu", "VDD", "main"),
    row("cpu", "AVDD", "filtered"),
    row("cpu", "VSS", "return"),
    row("other", "VDD", "main"),
    row("other", "VSS", "return"),
    row("C1", "1", "return"),
    row("C1", "2", "main"),
    row("C2", "1", "filtered"),
    row("C2", "2", "return"),
)


def test_both_pad_legs_and_shared_rail_ambiguity():
    c1, c2 = suggest_bypass(
        ROWS, (DIGITAL, OTHER, ANALOG), (Capacitor("C1", "1", "2"), Capacitor("C2", "1", "2"))
    )
    assert c1.state == "ambiguous"
    assert [match.bank.key for match in c1.matches] == ["digital", "other"]
    assert c1.matches[0].cap_supply == (PadIdentity("C1", "2"),)
    assert c1.matches[0].cap_return == (PadIdentity("C1", "1"),)
    assert c2.state == "suggested"
    assert c2.matches[0].bank == ANALOG
    assert c2.matches[0].bank_supply == (PadIdentity("cpu", "AVDD"),)


def test_explicit_bulk_dnp_and_incomplete_bank():
    cap = Capacitor("C1", "1", "2")
    assert suggest_bypass(ROWS, (DIGITAL,), (replace(cap, function="bulk"),))[0].state == "bulk"
    assert suggest_bypass(ROWS, (DIGITAL,), (replace(cap, dnp=True),))[0].state == "excluded"
    rows = tuple(r for r in ROWS if r.terminal != OTHER.return_pin)
    (result,) = suggest_bypass(rows, (DIGITAL, OTHER), (cap,))
    assert result.state == "unresolved"
    assert result.unresolved_banks == ("other",)


def test_assignment_recovers_coverage_through_an_augmenting_path():
    result = assign_bypass_banks({"a": ("1", "2"), "b": ("1", "3"), "c": ("1", "3")}, edge_budget=20)
    assert dict(result.assignments) == {"a": "2", "b": "3", "c": "1"}
    assert not result.uncovered and not result.exhausted


def test_one_capacitor_cannot_count_twice_without_permission():
    eligible = {"bank-a": ("cap",), "bank-b": ("cap",)}
    assert assign_bypass_banks(eligible, edge_budget=5).uncovered == ("bank-b",)
    assert not assign_bypass_banks(eligible, shareable=frozenset({"cap"}), edge_budget=5).uncovered
    limited = assign_bypass_banks(eligible, edge_budget=1)
    assert limited.exhausted and limited.uncovered == ("bank-b",)
