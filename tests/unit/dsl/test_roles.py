# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net roles of a design script (change c0222; capability design-dsl, "Net roles in the DSL": "Declared
roles are built", "A pad of another part is refused")."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.dsl import Design, DslError, Net, Part, amp, connect, mm, ohm, volt
from fenolite.dsl.convert import to_model
from fenolite.model.canonical import load_dir
from fenolite.model.rules import GateLoop, HotLoop, KelvinPair, NetRole, PartClass, RoleLimit, Terminal

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "roles"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "roles"))
from _roleboards import build  # noqa: E402

from fenolite.roles.store import kept_confirmed, updated_rules  # noqa: E402


def _design() -> tuple[Design, dict[str, Part], dict[str, Net]]:
    design = Design("roles")
    design.board(mm(40), mm(30))
    parts = {
        "Q1": Part("Q1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="Q"),
        "Q2": Part("Q2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="Q"),
        "C1": Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="1uF"),
        "R1": Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10m"),
        "R2": Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10m"),
        "U1": Part("U1", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="DRV"),
    }
    design.add(*parts.values())
    nets = {name: Net(name) for name in ("VIN", "SW", "GND", "GATE")}
    connect(nets["VIN"], parts["C1"][1], parts["Q1"][1])
    connect(nets["SW"], parts["Q1"][2], parts["Q2"][1])
    connect(nets["GND"], parts["Q2"][2], parts["C1"][2])
    return design, parts, nets


def test_calls_record_declared_roles() -> None:
    design, p, n = _design()
    design.net_role(n["VIN"], "power", current=amp("1.5"), voltage=volt(48))
    design.net_role(n["GATE"], "signal", sensitive=True)
    design.hot_loop("buck", [p["C1"].pad(1), p["Q1"].pad(1), p["Q1"].pad(2), p["Q2"].pad(2), p["C1"].pad(2)])
    design.kelvin(
        "isense", element=(p["R1"].pad(1), p["R1"].pad(2)), receiver=(p["U1"].pad(1), p["U1"].pad(2))
    )
    u1, q1 = p["U1"], p["Q1"]
    design.gate_loop("hs", drive=u1.pad(3), gate=q1.pad(1), source=q1.pad(2), ret=u1.pad(4),
                     resistor=(p["R2"].pad(1), p["R2"].pad(2)))  # fmt: skip
    design.role_limits(loop_max="60mm2", kind="switch_node")
    design.role_limits(net=n["VIN"], milliamps_per_via=amp(1), shunt_max_mohm=ohm("50m"), temp_rise_mk="12.5")
    design.part_class(p["Q1"], "transistor", terminals={"gate": "1", "source": ["2"]})
    roles = to_model(design).rules.roles  # type: ignore[union-attr]
    assert roles is not None
    assert roles.nets == (
        NetRole("GATE", "signal", "declared", sensitive=True),
        NetRole("VIN", "power", "declared", milliamps=1500, working_mv=48_000),
    )
    assert roles.loops == (HotLoop("buck", ("C1-1", "Q1-1", "Q1-2", "Q2-2", "C1-2")),)
    assert roles.kelvins == (KelvinPair("isense", ("R1-1", "R1-2"), ("U1-1", "U1-2")),)
    assert roles.gates == (GateLoop("hs", "U1-3", "Q1-1", "Q1-2", "U1-4", resistor=("R2-1", "R2-2")),)
    assert set(roles.limits) == {
        RoleLimit("loop_max", 60 * 10**12, kind="switch_node"),
        RoleLimit("milliamps_per_via", 1000, net="VIN"),
        RoleLimit("shunt_max_mohm", 50, net="VIN"),
        RoleLimit("temp_rise_mk", 12_500, net="VIN"),
    }
    assert roles.classes == (
        PartClass("Q1", "transistor", (Terminal("gate", ("1",)), Terminal("source", ("2",)))),
    )


def test_a_script_without_roles_writes_none() -> None:
    design, _, _ = _design()
    assert to_model(design).rules.roles is None  # type: ignore[union-attr]


def test_a_pad_of_another_part_is_refused() -> None:
    design, p, _ = _design()
    u1 = p["U1"]
    with pytest.raises(DslError, match=r"kelvin\(\) 'i': both element pads must belong to one part"):
        design.kelvin("i", element=(p["R1"].pad(1), p["R2"].pad(2)), receiver=(u1.pad("IN+"), u1.pad("IN-")))


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda d, p, n: d.net_role(n["SW"], "motor"), "kind 'motor' is not one of"),
        (
            lambda d, p, n: d.net_role(n["SW"], "power", current=amp("0.0005")),
            "not a whole number of milliamps",
        ),
        (lambda d, p, n: d.net_role(n["SW"], "power", current=volt(1)), "not a quantity in ampere"),
        (
            lambda d, p, n: d.net_role(n["SW"], "power", sensitive=True),
            "sensitive is a flag of a signal role",
        ),
        (lambda d, p, n: d.hot_loop("h", [p["C1"].pad(1), p["Q1"].pad(1)]), "at least three pads"),
        (
            lambda d, p, n: d.hot_loop("h", [p["C1"][1], p["Q1"].pad(1), p["Q1"].pad(2)]),
            "takes pads, not the pin",
        ),
        (lambda d, p, n: d.hot_loop("bad name", [p["C1"].pad(1)] * 3), "must match"),
        (
            lambda d, p, n: d.gate_loop("g", p["U1"].pad(1), p["Q1"].pad(1), p["Q2"].pad(2), p["U1"].pad(2)),
            "the gate and source pads must belong to one part",
        ),  # fmt: skip
        (lambda d, p, n: d.role_limits(loop_max=5), "is not an area"),
        (lambda d, p, n: d.role_limits(color=1), "unknown key 'color'"),
        (lambda d, p, n: d.role_limits(kelvin_pair=1), "is a flag"),
        (lambda d, p, n: d.role_limits(net=n["SW"], kind="power", loop_max="1mm2"), "not both"),
        (lambda d, p, n: d.part_class(p["Q1"], "valve"), "class 'valve' is not one of"),
        (lambda d, p, n: d.part_class(p["Q1"], "transistor", {"base": "1"}), "has no terminal 'base'"),
    ],
)
def test_bad_calls_are_refused(call: object, message: str) -> None:
    design, p, n = _design()
    with pytest.raises(DslError, match=message):
        call(design, p, n)  # type: ignore[operator]


def test_a_name_used_twice_is_refused() -> None:
    design, p, n = _design()
    pads = [p["C1"].pad(1), p["Q1"].pad(1), p["Q1"].pad(2)]
    design.hot_loop("h", pads)
    with pytest.raises(DslError, match="used twice"):
        design.hot_loop("h", pads)
    design.net_role(n["SW"], "switch_node")
    with pytest.raises(DslError, match="has a role already"):
        design.net_role(n["SW"], "signal")
    design.role_limits(loop_max="1mm2")
    with pytest.raises(DslError, match="given twice"):
        design.role_limits(loop_max="2mm2")


def test_build(tmp_path: Path) -> None:
    """Declared roles are built: the bus of the good half-bridge in ``.fenolite/rules.json``."""
    built = build("half_bridge", "good", tmp_path / "out", fill=False)
    data = json.loads((built.out / ".fenolite" / "rules.json").read_text(encoding="utf-8"))
    (bus,) = [row for row in data["roles"]["nets"] if row["net"] == "VBUS"]
    assert (bus["milliamps"], bus["working_mv"], bus["source"]) == (20_000, 400_000, "declared")
    assert data["roles"]["limits"] == [{"key": "milliamps_per_via", "net": "VBUS", "value": 4000}]
    roles = load_dir(built.out / ".fenolite").rules.roles  # type: ignore[union-attr]
    assert roles is not None and roles.role_of("VBUS") == NetRole(
        "VBUS", "power", "declared", milliamps=20_000, working_mv=400_000
    )


def test_a_rebuild_keeps_the_confirmed_roles(tmp_path: Path) -> None:
    """``fenolite roles --confirm`` stores confirmed roles in ``rules.json``; the next build keeps them
    beside the script's declarations."""
    out = tmp_path / "out"
    build("buck_shunt", "good", out, fill=False)
    rules = out / ".fenolite" / "rules.json"
    model = load_dir(out / ".fenolite").rules
    assert model is not None and model.roles is not None
    confirmed = NetRole("GND", "ground", "confirmed")
    mine = type(model.roles)(
        nets=(*model.roles.nets, confirmed), limits=model.roles.limits, rejected=("hot_SW",)
    )
    rules.write_bytes(updated_rules(rules.read_text(encoding="utf-8"), mine))
    stdout, stderr = io.StringIO(), io.StringIO()
    script = EXAMPLES / "buck_shunt" / "good.py"
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json"])
    assert code == 0, stderr.getvalue()
    roles = load_dir(out / ".fenolite").rules.roles  # type: ignore[union-attr]
    assert roles is not None and roles.role_of("GND") == confirmed and roles.rejected == ("hot_SW",)
    assert roles.role_of("SW") == NetRole("SW", "switch_node", "declared", milliamps=2000)
    assert kept_confirmed(rules.read_bytes(), tmp_path / "missing.json") == rules.read_bytes()
