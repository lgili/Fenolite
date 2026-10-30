# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part classes for the inference of net roles (change c0222; capability net-roles, "Part classes"). Every
circuit here is authored for Fenolite."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.model.circuit import Circuit, Component, Pin
from fenolite.model.rules import PartClass, Terminal
from fenolite.roles.classify import classify, classify_part, resistance_mohm


def part(ref: str, *names: str, value: str = "", numbers: tuple[str, ...] = ()) -> Component:
    pins = tuple(
        Pin(id=f"pin_{ref}_{i}", number=numbers[i - 1] if numbers else str(i), name=name)
        for i, name in enumerate(names, start=1)
    )
    return Component(id=f"cmp_{ref}", ref=ref, value=value, pins=pins)


def test_classes_from_pin_names() -> None:
    """Scenario "Classes from pin names": ``Q7`` (``G``, ``D``, ``S``, ``KS``) is a transistor with its
    Kelvin source on ``KS``, ``X1`` (``IN+``, ``IN-``, ``OUT``) an amplifier; both ``high``."""
    circuit = Circuit(components=(part("Q7", "G", "D", "S", "KS"), part("X1", "IN+", "IN-", "OUT")))
    found = classify(circuit)
    q7, x1 = found["Q7"], found["X1"]
    assert (q7.cls, q7.confidence, q7.evidence) == ("transistor", "high", "pin-names")
    assert q7.terminals == {"gate": ("1",), "drain": ("2",), "source": ("3",), "kelvin_source": ("4",)}
    assert (x1.cls, x1.confidence) == ("amplifier", "high")
    assert x1.terminals == {"in_p": ("1",), "in_n": ("2",), "out": ("3",)}


@pytest.mark.parametrize(
    ("component", "cls", "confidence", "evidence"),
    [
        (part("Q1", "S", "S", "S", "G", "D", "D", "D", "D"), "transistor", "high", "pin-names"),
        (part("U2", "VCC", "HIN", "LIN", "COM", "LO", "HS", "HO", "VB"), "driver", "high", "pin-names"),
        (part("U1", "VIN", "SW", "FB", "GND"), "controller", "high", "pin-names"),
        (part("U5", "VCC", "GH", "GL", "SW", "FB"), "controller", "high", "pin-names"),
        (part("U9", "VC1", "SRP", "SRN", "DSG", "CHG", "VSS"), "controller", "high", "pin-names"),
        (part("D3", "A", "K"), "diode", "high", "pin-names"),
        (part("R7", "F1", "S1", "S2", "F2"), "shunt", "high", "pin-names"),
        (part("C3", "", "", value="10uF"), "capacitor", "high", "value"),
        (part("L1", "", "", value="4.7uH"), "inductor", "high", "value"),
        (part("R12", "", "", value="5m"), "shunt", "medium", "value"),
        (part("R4", "", "", value="0.1"), "shunt", "medium", "value"),
        (part("R5", "", "", value="10k"), "resistor", "medium", "value"),
        (part("X2", "", "", value="10kΩ"), "resistor", "high", "value"),
        (part("Q3", "1", "2", "3"), "transistor", "low", "prefix"),
        (part("J1", "", ""), "connector", "low", "prefix"),
        (part("U8", "A1", "B1"), "other", "low", "prefix"),
        (part("TP1", ""), "other", "low", "none"),
    ],
)
def test_evidence_order(component: Component, cls: str, confidence: str, evidence: str) -> None:
    found = classify_part(component)
    assert (found.cls, found.confidence, found.evidence) == (cls, confidence, evidence)


def test_four_pad_resistor_is_a_shunt_and_the_user_wins() -> None:
    plain = part("R8", "", "", "", "")
    assert classify_part(plain, pads=4).cls == "shunt"
    assert classify_part(plain, pads=4).confidence == "medium"
    stated = PartClass("R8", "shunt", (Terminal("force", ("1", "4")), Terminal("sense", ("2", "3"))))
    found = classify_part(plain, user=stated, pads=4)
    assert (found.cls, found.confidence, found.evidence) == ("shunt", "high", "user")
    assert found.terminals == {"force": ("1", "4"), "sense": ("2", "3")}
    assert classify_part(part("Q1", "G", "D", "S"), net_tie=True).cls == "net_tie"


def test_two_pad_shunt_senses_on_both_pins() -> None:
    assert classify_part(part("R12", "", "", value="5mR"), pads=2).terminals == {"sense": ("1", "2")}


def test_shunt_limit_comes_from_the_profile() -> None:
    assert classify_part(part("R1", "", "", value="150m")).cls == "resistor"
    assert classify_part(part("R1", "", "", value="150m"), shunt_max_mohm=200).cls == "shunt"


@pytest.mark.parametrize(
    ("text", "milliohms"),
    [
        ("5m", Fraction(5)),
        ("5mΩ", Fraction(5)),
        ("5mR", Fraction(5)),
        ("0.005", Fraction(5)),
        ("R005", Fraction(5)),
        ("4k7", Fraction(4_700_000)),
        ("10 kΩ", Fraction(10_000_000)),
        ("10uF", None),
        ("4.7uH", None),
        ("IRF540", None),
    ],
)
def test_resistance(text: str, milliohms: Fraction | None) -> None:
    assert resistance_mohm(text) == milliohms


def test_prefixes_of_a_ferrite_a_fuse_and_a_jumper() -> None:
    """Scenario "A ferrite, a fuse and a jumper" (change c0274): the prefixes ``FB``, ``F`` and ``JP`` give
    their classes with ``medium`` confidence, read before the value (``600R`` reads like a resistance)."""
    circuit = Circuit(
        components=(part("FB1", "", "", value="600R"), part("F1", "", "", value="2A"), part("JP1", "", ""))
    )
    found = classify(circuit)
    assert [(found[r].cls, found[r].confidence, found[r].evidence) for r in ("FB1", "F1", "JP1")] == [
        ("ferrite", "medium", "prefix"),
        ("fuse", "medium", "prefix"),
        ("jumper", "medium", "prefix"),
    ]
    stated = classify(circuit, user=(PartClass("FB1", "resistor"),))
    assert (stated["FB1"].cls, stated["FB1"].evidence) == ("resistor", "user")


def test_prefixes_are_one_table() -> None:
    """The prefix table of the classifier is the one of the package tree: every class it names is a part
    class, and no module of ``checks`` holds a table of reference prefixes."""
    from pathlib import Path

    from fenolite.model.rules import PART_CLASSES
    from fenolite.roles.classify import LINK_PREFIXES, PREFIXES

    assert {cls for _, cls in PREFIXES} <= set(PART_CLASSES)
    assert LINK_PREFIXES == {"FB", "F", "JP"}
    checks = Path(__file__).resolve().parents[3] / "src" / "fenolite" / "checks"
    assert not [p for p in checks.rglob("*.py") if '("FB", "ferrite")' in p.read_text(encoding="utf-8")]


def test_class_of_the_device_record() -> None:
    """Scenario "A ferrite says what it is" (change c0274): the ``class`` of a part's device record is
    ``high`` evidence ``device``, after the user's class and before the pin names and the prefix."""
    circuit = Circuit(components=(part("L4", "", "", value="4.7uH"), part("Q2", "G", "D", "S")))
    found = classify(circuit, device_classes={"L4": "ferrite", "Q2": "transistor"})
    assert (found["L4"].cls, found["L4"].confidence, found["L4"].evidence) == ("ferrite", "high", "device")
    assert (found["Q2"].evidence, found["Q2"].terminals["gate"]) == ("device", ("1",))
    stated = classify(circuit, user=(PartClass("L4", "inductor"),), device_classes={"L4": "ferrite"})
    assert stated["L4"].evidence == "user"
