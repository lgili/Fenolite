# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Electrical contracts in the DSL (change c0253; capability design-dsl, "Electrical contracts in the DSL" and
"Contract helpers in the DSL"; capability electrical-contracts, "Expectations are recorded data", "Test rig"
and "Rig never reaches outputs")."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from _contracts import cli, sensor, two_pin

import fenolite.dsl
from fenolite.dsl import (
    Design,
    DslError,
    Net,
    Rail,
    amp,
    at_least,
    block,
    connect,
    current_of,
    ohm,
    pct,
    rating_of,
    ratio,
    supply,
    to_model,
    value_of,
    volt,
    voltage_of,
    within,
)

HELPERS = (
    "within", "at_least", "at_most", "value_of", "rating_of", "voltage_of", "current_of", "supply", "sink", "ratio",
)  # fmt: skip


def test_build_contracts_are_built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Contracts are built": the good sensor's ``rules.json`` holds its contracts."""
    folder = sensor(tmp_path)
    code, env = cli(
        monkeypatch, "build", str(folder / "good.py"), "--out", str(folder / "build"), "--confirm"
    )
    assert code == 0, env["issues"]
    contracts = json.loads((folder / "build" / ".fenolite" / "rules.json").read_text(encoding="utf-8"))[
        "contracts"
    ]
    (rule,) = contracts["derating"]
    assert (rule["key"], rule["permille"]) == ("capacitor_voltage", 500)
    (bench,) = contracts["rig"]
    assert bench["name"] == "bench" and bench["voltage"] == {
        "high": {"e": -1, "m": 132},
        "low": {"e": -1, "m": 108},
        "nominal": {"e": 0, "m": 12},
        "unit": "volt",
    }
    assert [e["id"] for e in contracts["expects"]] == ["buck1/expect#1"]
    assert contracts["expects"][0]["origin"].startswith("contract_board.board:")


def test_ratio_not_whole_per_mille() -> None:
    """Scenario "A ratio that is not whole per-mille"."""
    with pytest.raises(DslError, match="resistor_power.*whole per-mille"):
        Design("t").derating(resistor_power=ratio("50.05"))


def test_exports_helpers_are_exported() -> None:
    """Scenario "Helpers are exported": the ten names, each in a ``fenolite-design`` block of the guide."""
    assert set(HELPERS) <= set(fenolite.dsl.__all__)
    pages = Path(fenolite.__file__).resolve().parent / "agent" / "skill" / "references"
    text = "\n".join(p.read_text(encoding="utf-8") for p in pages.glob("*.md"))
    blocks = [part.split("```", 1)[0] for part in text.split("```fenolite-design")[1:]]
    for name in HELPERS:
        assert any(f"{name}(" in found for found in blocks), name


def _part(d: Design) -> Any:
    d.devices(
        two_pin("Test:IND", 'current = { abs_max = "1A" }\ntemperature = { abs_max = { max = "125degC" } }')
    )
    part = d.part("L1", device="Test:IND", value="4u7")
    connect(Net("A"), part.P1)
    connect(Net("B"), part.P2)
    return part


def test_no_silent_branch() -> None:
    """Scenario "No silent branch"."""
    l1 = _part(Design("t"))
    with pytest.raises(DslError, match=r"design\.expect"):
        if rating_of(l1, "current"):
            pass
    with pytest.raises(DslError, match="no order"):
        _ = rating_of(l1, "current") >= amp(1)  # type: ignore[operator]
    with pytest.raises(DslError, match=r"design\.expect"):
        bool(at_least(rating_of(l1, "current"), amp(1)))


def test_an_unknown_rating_key() -> None:
    """Scenario "An unknown rating key"."""
    l1 = _part(Design("t"))
    with pytest.raises(DslError, match="current, temperature"):
        rating_of(l1, "saturation")
    with pytest.raises(DslError, match="abs_max"):
        rating_of(l1, "current", limit="operating")
    with pytest.raises(DslError, match="P1, P2"):
        rating_of(l1, "current", pin="SW")


def test_a_literal_comparison_is_refused() -> None:
    """Scenario "A literal comparison is refused"."""
    with pytest.raises(DslError, match=r"within\(a, b\)"):
        Design("t").expect(volt("3.3").pct(3).within(volt("3.3").pct(5)), "rail")


@block
def _buck(b: Any) -> None:
    out = b.port("VOUT", Rail, direction="out")
    r = b.part("R", device="Fenolite:R_0603", value=ohm("10k").pct(1))
    connect(out, r.P1)
    b.expect(within(value_of(r), ohm("10k").pct(5)), "the resistor holds")


def test_ids_take_the_instance_path() -> None:
    """Scenario "Ids take the instance path"."""
    d = Design("t")
    d.use(_buck, "buck1")
    d.use(_buck, "buck2")
    d.expect(within(value_of(d.parts["buck1/R"]), ohm("10k").pct(2)), "top level")
    model = to_model(d)
    assert model.rules is not None and model.rules.contracts is not None
    assert [e.id for e in model.rules.contracts.expects] == [
        "buck1/expect#1",
        "buck2/expect#1",
        "design/expect#1",
    ]
    with pytest.raises(DslError, match="used twice"):
        d.expect(within(value_of(d.parts["buck1/R"]), ohm("10k").pct(2)), "top level")


def test_a_rig_on_a_net_without_parts() -> None:
    """Scenario "A rig on a net without parts"."""
    d = Design("t")
    gnd = d.ground("GND")
    r = d.part("R1", device="Fenolite:R_0603", value="1k")
    connect(gnd, r.P1)
    connect(Net("X"), r.P2)
    d.rig(supply(Net("EXT"), gnd, voltage=volt(5), name="ext"))
    with pytest.raises(DslError, match="EXT") as info:
        to_model(d)
    assert "ext" in str(info.value)


def test_a_rig_needs_one_ground() -> None:
    d = Design("t")
    r = d.part("R1", device="Fenolite:R_0603", value="1k")
    v5 = Net("V5")
    connect(v5, r.P1)
    connect(Net("X"), r.P2)
    d.rig(supply(v5, voltage=volt(5), name="ext"))
    with pytest.raises(DslError, match="0 grounds"):
        to_model(d)


def test_bad_ratios() -> None:
    """Scenario "Bad ratios"."""
    d = Design("t")
    with pytest.raises(DslError):
        d.derating(capacitor_voltage=ratio(120))
    with pytest.raises(DslError, match=r"ratio\(50\)"):
        d.derating(capacitor_voltage=pct(50))
    with pytest.raises(DslError, match="capacitor_voltage.*temperature_margin"):
        d.derating(gate_charge=ratio(50))
    with pytest.raises(DslError, match="not exact"):
        ratio(50.0)  # type: ignore[arg-type]


def test_handles_of_nets() -> None:
    d = Design("t")
    gnd = d.ground("GND")
    v12 = d.rail("V12", voltage=volt(12), ground=gnd)
    r = d.part("R1", device="Fenolite:R_0603", value=ohm("1k").pct(1))
    connect(v12, r.P1)
    connect(gnd, r.P2)
    d.expect(at_least(voltage_of(v12) / value_of(r), current_of(v12) * 0), "a bleeder current")
    model = to_model(d)
    assert model.rules is not None and model.rules.contracts is not None
    test = model.rules.contracts.expects[0].test
    assert (test.op, test.a.op, test.a.a.ref) == ("at_least", "div", "voltage")  # type: ignore[union-attr]
    with pytest.raises(DslError, match="unit"):
        within(voltage_of(v12), ohm(1))
    with pytest.raises(DslError, match="not exact"):
        _ = voltage_of(v12) * 1.5  # type: ignore[operator]


def _files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_rig_outputs_are_unchanged_by_a_rig(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Outputs are unchanged by a rig": a build with and without ``design.rig`` writes the same
    bytes in every file but ``.fenolite/rules.json``. (The BOM and the pick-and-place file are exported from
    these files by ``kicad-cli``, so they follow.)"""
    folder = sensor(tmp_path)
    (folder / "norig.py").write_text(
        "from contract_board.board import sensor_board\n\nfrom fenolite.dsl import Design\n\n"
        'design = sensor_board(Design("sensor_contracts"), rig=False)\n',
        encoding="utf-8",
    )
    flags = ("--seed", "1", "--timestamp", "2026-01-01T00:00:00Z", "--confirm")
    for script, out in (("good.py", "with"), ("norig.py", "without")):
        code, env = cli(monkeypatch, "build", str(folder / script), "--out", str(folder / out), *flags)
        assert code == 0, env["issues"]
        (folder / "design.lock").unlink(missing_ok=True)
    with_rig, without_rig = _files(folder / "with"), _files(folder / "without")
    assert set(with_rig) == set(without_rig)
    differing = sorted(name for name in with_rig if with_rig[name] != without_rig[name])
    assert differing == [".fenolite/rules.json"]
