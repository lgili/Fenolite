# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC lite on authored models (capability verification-loop, "ERC lite stage"; change c0013)."""

from __future__ import annotations

import dataclasses
import io
import json
from pathlib import Path

import pytest
from _buildhelp import blink_variant

import fenolite
import fenolite.cli.main as cli_main
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


# --- no-connect marks (change c0036) ------------------------------------------------------------------


def _marked(design: Design, *marks: tuple[str, str]) -> Design:
    circuit = dataclasses.replace(design.circuit, no_connects=tuple(PinRef(c, p) for c, p in marks))
    return dataclasses.replace(design, circuit=circuit)


def test_erc_lite_no_connect_marked_pin_is_not_floating() -> None:
    u1 = _part("cmp_1", "U1", ("11", "input"), ("12", "input"), ("13", "input"))
    design = _marked(_design((u1,), ()), ("cmp_1", "11"), ("cmp_1", "12"))
    found = erc_lite(design)
    assert [(i.code, i.where, i.severity) for i in found] == [("erc.lite.floating-pin", "U1-13", "warning")]
    assert erc_stage(design).summary["floating-pin"] == 1
    assert len(erc_lite(_design((u1,), ()))) == 3


def test_erc_lite_no_connect_mark_matches_component_and_pin_number() -> None:
    u1 = _part("cmp_1", "U1", ("11", "input"))
    u2 = _part("cmp_2", "U2", ("11", "input"), ("12", "input"))
    design = _marked(_design((u1, u2), ()), ("cmp_2", "11"), ("cmp_1", "NRST"))
    assert sorted(i.where for i in erc_lite(design)) == ["U1-11", "U2-12"]


def test_erc_lite_no_connect_marked_pin_on_a_net_is_not_reported() -> None:
    """A marked pin that a net lists is ``model.no-connect-on-net``; the three rules leave it alone."""
    other = _part("cmp_3", "U3", ("1", "output"))
    nets = (
        _net("net_1", "VCC", ("cmp_1", "1"), ("cmp_2", "1")),
        _net("net_2", "SIG", ("cmp_1", "2"), ("cmp_2", "2"), ("cmp_3", "1")),
    )
    conflict = _design((DRIVER, LOAD, other), nets)
    assert _codes(conflict) == ["erc.lite.output-conflict"]
    marked = _marked(conflict, ("cmp_3", "1"))
    assert _codes(marked) == []
    assert [i.code for i in marked.validate() if i.code.startswith("model.no-connect")] == [
        "model.no-connect-on-net"
    ]
    undriven = _design((DRIVER, LOAD), (_net("net_1", "VCC", ("cmp_2", "1")),))
    assert "erc.lite.power-undriven" in _codes(undriven)
    assert "erc.lite.power-undriven" not in _codes(_marked(undriven, ("cmp_2", "1")))


def test_erc_lite_no_connect_marked_pins_of_a_built_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unused = [n for n in range(1, 33) if n not in (1, 9, 10)]
    marks = ", ".join(f"u1[{n}]" for n in unused)
    script = blink_variant(
        tmp_path / "v", append=f"\nfrom fenolite.dsl import no_connect  # noqa: E402\n\nno_connect({marks})\n"
    )
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))

    def run(*args: str) -> tuple[int, dict[str, object]]:
        out = io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        monkeypatch.setattr("sys.stderr", io.StringIO())
        code = cli_main.main([*args, "--json"])
        return code, json.loads(out.getvalue() or "{}")

    built = tmp_path / "B"
    code, _ = run("build", str(script), "--out", str(built), "--confirm")
    assert code == 0
    code, reply = run("check", str(built), "--stages", "erc.lite")
    floating = [i for i in reply["issues"] if i["code"] == "erc.lite.floating-pin"]  # type: ignore[union-attr]
    assert code == 0 and not [i for i in floating if i["where"].startswith("U1-")], floating
    plain = tmp_path / "plain"
    code, _ = run("build", str(blink_variant(tmp_path / "p")), "--out", str(plain), "--confirm")
    code, reply = run("check", str(plain), "--stages", "erc.lite")
    floating = [i for i in reply["issues"] if i["code"] == "erc.lite.floating-pin"]  # type: ignore[union-attr]
    assert {"U1-11", "U1-12"} <= {i["where"] for i in floating}, "the control: unmarked pins still float"
