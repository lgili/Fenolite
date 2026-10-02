# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC lite on authored models (capability verification-loop, "ERC lite stage"; change c0013)."""

from __future__ import annotations

import dataclasses

import pytest

import fenolite
from fenolite.checks import erc_lite as erc
from fenolite.checks.erc_lite import ERC_RULES, REMOVE_IN, check_removal, erc_lite, erc_stage
from fenolite.model.circuit import Circuit, Component, Interface, Net, Pin, PinRef
from fenolite.model.design import Design


def _part(cid: str, ref: str, *pins: tuple[str, str], dnp: bool = False) -> Component:
    return Component(
        id=cid, ref=ref, dnp=dnp, pins=tuple(Pin(id=f"pin_{cid}_{n}", number=n, etype=t) for n, t in pins)
    )  # type: ignore[arg-type]


def _net(nid: str, name: str, *members: tuple[str, str]) -> Net:
    return Net(id=nid, name=name, members=tuple(PinRef(c, p) for c, p in members))


def _design(
    components: tuple[Component, ...], nets: tuple[Net, ...], interfaces: tuple[Interface, ...] = ()
) -> Design:
    return dataclasses.replace(
        Design.new("erc", seed=0), circuit=Circuit(components=components, nets=nets, interfaces=interfaces)
    )


def _codes(design: Design) -> list[str]:
    return sorted(i.code for i in erc_lite(design))


DRIVER = _part("cmp_1", "U1", ("1", "power_out"), ("2", "output"))
LOAD = _part("cmp_2", "U2", ("1", "power_in"), ("2", "input"))
CLEAN = _design(
    (DRIVER, LOAD),
    (
        _net("net_1", "VCC", ("cmp_1", "1"), ("cmp_2", "1")),
        _net("net_2", "SIG", ("cmp_1", "2"), ("cmp_2", "2")),
    ),
)


def test_erc_lite_clean_control() -> None:
    assert _codes(CLEAN) == []
    assert erc_stage(CLEAN).status == "ok"


def test_erc_lite_output_conflict() -> None:
    other = _part("cmp_3", "U3", ("1", "output"))
    nets = (
        _net("net_1", "VCC", ("cmp_1", "1"), ("cmp_2", "1")),
        _net("net_2", "SIG", ("cmp_1", "2"), ("cmp_2", "2"), ("cmp_3", "1")),
    )
    assert _codes(_design((DRIVER, LOAD, other), nets)) == ["erc.lite.output-conflict"]


def test_erc_lite_power_undriven() -> None:
    nets = (
        _net("net_1", "VCC", ("cmp_2", "1")),
        _net("net_2", "SIG", ("cmp_1", "1"), ("cmp_1", "2"), ("cmp_2", "2")),
    )
    found = _codes(_design((DRIVER, LOAD), nets))
    assert "erc.lite.power-undriven" in found and "erc.lite.floating-pin" not in found


def test_erc_lite_power_interface_drives_a_net() -> None:
    nets = (_net("net_1", "VCC", ("cmp_2", "1")), _net("net_2", "SIG", ("cmp_2", "2")))
    power = Interface(id="ifc_1", name="P", kind="power", members={"hv": "net_1", "lv": "net_9"})
    assert "erc.lite.power-undriven" not in _codes(_design((LOAD,), nets, (power,)))


def test_erc_lite_floating_pin() -> None:
    lonely = _part("cmp_3", "R1", ("1", "passive"), ("2", "no_connect"))
    found = erc_lite(_design((DRIVER, LOAD, lonely), CLEAN.circuit.nets))
    assert [(i.code, i.where) for i in found] == [("erc.lite.floating-pin", "R1-1")]


def test_erc_lite_ignores_dnp_pins() -> None:
    dnp = _part("cmp_3", "U3", ("1", "output"), ("2", "passive"), dnp=True)
    nets = (CLEAN.circuit.nets[0], _net("net_2", "SIG", ("cmp_1", "2"), ("cmp_2", "2"), ("cmp_3", "1")))
    assert _codes(_design((DRIVER, LOAD, dnp), nets)) == []


def test_erc_lite_warnings_only() -> None:
    nets = (_net("net_1", "VCC", ("cmp_2", "1")),)
    found = erc_lite(_design((DRIVER, LOAD), nets))
    assert found and {i.severity for i in found} == {"warning"}
    assert set(ERC_RULES) == {"output-conflict", "power-undriven", "floating-pin"}
    assert erc.EVIDENCE.hypotheses == ("H-K-CHECK-ERC",)


def test_remove_in_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    assert REMOVE_IN == (0, 2)
    monkeypatch.setattr(fenolite, "__version__", "0.2.0")
    with pytest.raises(RuntimeError, match=r"erc\.lite.*REMOVE_IN"):
        check_removal(fenolite.__version__)


def test_remove_in_live_version() -> None:
    assert check_removal(fenolite.__version__) is None
