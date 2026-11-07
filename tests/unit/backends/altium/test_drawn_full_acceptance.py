# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original FULL acceptance keeps old pins and adds real bus loads (c0276/6.5)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import _drawn
import pytest

from fenolite.api import run
from fenolite.backends.altium.read import sch


def test_full_has_real_bus_loads_and_only_genuinely_unused_input_marks() -> None:
    code = _drawn.design("full")
    assert set(code.parts) == {"U1", "R1", "sub/R2", "R3", "R4"}
    for ref, bus, pin in (("R3", "B0", "18"), ("R4", "B1", "19")):
        resistor = code.parts[ref]
        assert resistor.value == "10k"
        assert resistor.connections["1"].name == code.parts["U1"].connections[pin].name == bus
        assert resistor.connections["2"].name == "GND"
        assert not resistor.no_connects
    assert code.parts["U1"].no_connects == {"11", "12"}
    assert not (code.parts["U1"].no_connects & code.parts["U1"].connections.keys())
    assert all(not p.no_connects for key, p in code.parts.items() if key != "U1")
    root = _drawn.drawn("full").sheet("root")
    assert root is not None
    assert {symbol.part for symbol in root.symbols} == {"U1", "R1", "R3", "R4"}
    points = _drawn.pins(_drawn.drawn("full"), "full")[("root", "symbol", 0)]
    assert set(root.no_connects) == {point.at for point in points if point.number in {"11", "12"}}
    start, end = root.wires[2]
    assert any(
        label.text == "IN"
        and label.at.y == start.y == end.y
        and min(start.x, end.x) <= label.at.x <= max(start.x, end.x)
        for label in root.labels
    )


# Native file counts cover the complete original36 pins plus four new resistor pins.
def _old_and_new_pins() -> set[tuple[str, str]]:
    return {("U1", str(number)) for number in range(1, 33)} | {
        (ref, pin) for ref in ("R1", "R2", "R3", "R4") for pin in ("1", "2")
    }


@pytest.mark.parametrize("form", ("binary", "ascii"))
def test_full_native_records_and_circuit_cover_every_old_and_new_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    out = tmp_path / "out"
    reply = run(
        "build", str(_drawn.folder("full") / "design.py"), "--target", "altium",
        "--altium-format", form, "--out", str(out), "--confirm",
        seed=1, timestamp="2026-11-03T00:00:00Z",
    )  # fmt: skip
    assert reply.exit_code == 0, (reply.error, reply.envelope)
    value = json.loads((out / ".fenolite/circuit.json").read_text())
    refs = {c["id"]: c["ref"] for c in value["components"]}
    assert len(refs) == 5
    assert {(c["ref"], p["number"]) for c in value["components"] for p in c["pins"]} == _old_and_new_pins()
    groups = {n["name"]: {(refs[p["component_id"]], p["pin"]) for p in n["members"]} for n in value["nets"]}
    assert groups == {
        "B0": {("U1", "18"), ("R3", "1")},
        "B1": {("U1", "19"), ("R4", "1")},
        "GND": {("U1", "10"), ("R2", "2"), ("R3", "2"), ("R4", "2")},
        "IN": {("U1", "1"), ("R2", "1")},
        "SDA": {("U1", "17"), ("R1", "2")},
        "VCC": {("U1", "9"), ("R1", "1")},
    }
    assigned = set().union(*groups.values())
    assert len(groups) + len(_old_and_new_pins() - assigned) == 32
    documents = [sch.read_schematic(p.read_bytes()) for p in out.glob("*.SchDoc")]
    pins = [pin for doc in documents for pin in doc.of_type(sch.Pin)]
    assert len(pins) == 40
    markers = [marker for doc in documents for marker in doc.no_ercs()]
    assert len(markers) == 2 and all(m.active and m.suppress_all for m in markers)
    assert Counter(m.location for m in markers) == Counter(
        p.hot_end for p in pins if p.designator in {"11", "12"}
    )
    assert any(n.text == "IN" for doc in documents for n in doc.of_type(sch.NetLabel))
