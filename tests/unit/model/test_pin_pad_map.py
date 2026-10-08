# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A pin bonded to several pads (capability design-model, "Persist per-component pin-to-pad maps"; change
c0123): the readers of the map, its canonical form, its validation, and the guard on other readers."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fenolite.model import canonical
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef, pin_pad_map_problems
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "src" / "fenolite"
STILL_ONE_PAD: frozenset[str] = frozenset()
"""Files that may turn the pairs into one pad per pin: none. Change c0123 emptied the set reader by
reader; a file is never added to it."""
ONE_PAD = re.compile(r"dict\(\s*[\w.\[\]]*pin_pad_map\s*\)")

BEFORE = """{
  "components": [
    {
      "id": "cmp_00000000-0000-4000-8000-000000000001",
      "ref": "D1",
      "pins": [
        {
          "id": "pin_00000000-0000-4000-8000-000000000001",
          "number": "1"
        },
        {
          "id": "pin_00000000-0000-4000-8000-000000000002",
          "number": "2"
        }
      ],
      "pin_pad_map": [
        [
          "1",
          "2"
        ],
        [
          "2",
          "1"
        ]
      ]
    },
    {
      "id": "cmp_00000000-0000-4000-8000-000000000002",
      "ref": "R1"
    }
  ]
}
"""
"""A ``circuit.json`` as ``canonical.dumps`` wrote it before a pin could occur twice (authored here)."""


def _pins(*numbers: str) -> tuple[Pin, ...]:
    return tuple(Pin(id=f"pin_00000000-0000-4000-8000-0000000000{n:0>2}", number=n) for n in numbers)


def _component(ref: str, pairs: tuple[tuple[str, str], ...], *pins: str) -> Component:
    return Component(
        id=f"cmp_00000000-0000-4000-8000-0000000000{ord(ref[0]):02d}",
        ref=ref,
        pins=_pins(*pins),
        pin_pad_map=pairs,
    )


def _codes(component: Component) -> list[tuple[str, str]]:
    design = Design.new("d", seed=1)
    design = Design(
        header=design.header,
        circuit=Circuit(components=(component,)),
        board=None,
        rules=None,
        manufacturing=None,
        findings=design.findings,
    )
    return [(i.code, i.where) for i in design.validate() if i.code == "model.pin-pad-map"]


def test_several_pads_of_one_pin() -> None:
    """Scenario "Several pads of one pin"."""
    component = _component("U1", (("3", "3"), ("3", "EP")), "1", "2", "3")
    assert component.pads_of("3") == ("3", "EP") and component.pads_of("1") == ("1",)
    assert component.pin_pads() == {"3": ("3", "EP")}
    text = canonical.dumps(component)
    assert json.loads(text)["pin_pad_map"] == [["3", "3"], ["3", "EP"]]
    assert canonical.loads(text, Component) == component
    assert _codes(component) == []


def test_pairs_of_a_pin_need_not_be_adjacent() -> None:
    component = _component("U1", (("3", "3"), ("1", "9"), ("3", "EP")), "1", "3")
    assert component.pads_of("3") == ("3", "EP")
    assert component.pin_pads() == {"3": ("3", "EP"), "1": ("9",)}
    assert component.pads_of("7") == ("7",) and Component(id="cmp_x", ref="R1").pin_pads() == {}


def test_one_pad_per_pin_keeps_its_bytes() -> None:
    """Scenario "One pad per pin keeps its bytes"."""
    circuit = canonical.loads(BEFORE, Circuit)
    assert circuit.components[0].pin_pad_map == (("1", "2"), ("2", "1"))
    assert canonical.dumps(circuit) == BEFORE
    assert canonical.dump_texts(Design.new("d", seed=1))["meta.json"].count('"schema_version": "0"') == 1


def test_pad_named_by_two_pins() -> None:
    """Scenario "Pad named by two pins"."""
    assert _codes(_component("U1", (("1", "2"),), "1", "2")) == [("model.pin-pad-map", "U1-1")]
    assert _codes(_component("U2", (("1", "5"), ("1", "5")), "1")) == [("model.pin-pad-map", "U2-1")]
    assert _codes(_component("U3", (("1", "5"), ("2", "5")), "1", "2")) == [("model.pin-pad-map", "U3-2")]
    assert _codes(_component("U4", (("1", ""),), "1")) == [("model.pin-pad-map", "U4-1")]


def test_maps_that_are_not_refused() -> None:
    swap = _component("D1", (("1", "2"), ("2", "1")), "1", "2")
    assert pin_pad_map_problems(swap) == () and _codes(swap) == []
    # a component without pins: the identity of an unlisted pin is not known, so it is not counted
    assert pin_pad_map_problems(_component("J1", (("1", "2"),))) == ()
    assert pin_pad_map_problems(_component("J2", (("1", "1"),), "1", "2")) == ()


def test_the_finding_is_an_error_of_the_design() -> None:
    component = _component("U1", (("1", "2"),), "1", "2")
    design = Design.new("d", seed=1)
    design = Design(
        header=design.header,
        circuit=Circuit(
            components=(component,),
            nets=(Net(id="net_x", name="N", members=(PinRef(component.id, "1"),)),),
        ),
        board=None,
        rules=None,
        manufacturing=None,
        findings=design.findings,
    )
    found = [i for i in design.validate() if i.code == "model.pin-pad-map"]
    assert [(i.severity, i.where) for i in found] == [("error", "U1-1")]
    assert "1" in found[0].message and "2" in found[0].message


def test_no_second_reader() -> None:
    """Scenario "No second reader": only ``model/circuit.py`` turns the pairs into a mapping."""
    found = {
        path.relative_to(SOURCES).as_posix()
        for path in sorted(SOURCES.rglob("*.py"))
        if ONE_PAD.search(path.read_text(encoding="utf-8"))
    }
    assert found - {"model/circuit.py"} == set(STILL_ONE_PAD)


def test_the_schema_describes_the_field() -> None:
    """Scenario "Schema regenerated"."""
    schema = json.loads((ROOT / "schemas" / "fenolite.model.v0" / "circuit.json").read_text(encoding="utf-8"))
    found: list[dict[str, object]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "pin_pad_map" in node and isinstance(node["pin_pad_map"], dict):
                found.append(node["pin_pad_map"])  # pyright: ignore[reportUnknownArgumentType]
            for value in node.values():  # pyright: ignore[reportUnknownVariableType]
                walk(value)
        elif isinstance(node, list):
            for value in node:  # pyright: ignore[reportUnknownVariableType]
                walk(value)

    walk(schema)
    assert len(found) == 1
    field = found[0]
    assert "several pairs" in str(field["description"])
    assert field["items"] == {
        "type": "array",
        "prefixItems": [{"type": "string"}, {"type": "string"}],
        "items": False,
    }
