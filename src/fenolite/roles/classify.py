# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The class of each part, for the inference of net roles (change c0222; capability net-roles, "Part
classes"; ``docs/roles.md``, "Part classes").

A part gets one class of ``PART_CLASSES`` with its terminals (which pins are the gate, the drain, the sense
inputs, ...) and a confidence. The evidence is weighed strongest first:

1. the class the user states (``design.part_class`` or ``--class REF=CLASS``): ``high``;
2. the ``class`` of the part's device record (change c0274): ``high``, evidence ``device``;
3. the names of the pins, against the vocabulary below: ``high``;
4. the types of the pins: they give no class on their own, they serve the rules of ``infer``;
5. the prefixes ``FB``, ``F`` and ``JP`` (change c0274): ``ferrite``, ``fuse`` and ``jumper``, ``medium``,
   read before the value, since a ferrite's impedance and a fuse's rating read like a resistance;
6. the value and the pad count: a value with its unit (``10uF``, ``4.7uH``, ``10kΩ``) is ``high``; a
   resistance at or below the profile's ``shunt_max_mohm``, or a four-pad resistor, is a ``shunt`` of
   ``medium`` confidence (a heuristic); a bare number on a part whose reference says resistor is a
   ``medium`` resistor;
7. the reference prefix (``Q``, ``D``, ``L``, ``C``, ``R``, ``J``, ``U``): ``low``, the weakest.

A part in a net-tie group of the board is ``net_tie`` whatever else holds. The tables are Fenolite's own
vocabulary, written for this module from the pin names that datasheets commonly print; they are taken from
no library.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.model.circuit import Circuit, Component
from fenolite.model.rules import PART_CLASSES, PART_TERMINALS, PartClass, PartClassName

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
GATE = frozenset({"G", "GATE"})
DRAIN = frozenset({"D", "DRAIN", "C", "COLLECTOR"})
SOURCE = frozenset({"S", "SOURCE", "E", "EMITTER"})
KELVIN_SOURCE = frozenset({"KS", "SK", "KE", "KELVIN"})
TRANSISTOR_NAMES = GATE | DRAIN | SOURCE | KELVIN_SOURCE
ANODE = frozenset({"A", "ANODE"})
CATHODE = frozenset({"K", "CATHODE"})
INPUT_PAIRS: tuple[tuple[str, str], ...] = (
    ("IN+", "IN-"),
    ("+IN", "-IN"),
    ("SP", "SN"),
    ("CSP", "CSN"),
    ("SRP", "SRN"),
)
"""The names of an amplifier's input pair, positive first."""
DRIVE = frozenset({"HO", "LO", "GH", "GL", "OUT", "DRV", "OUTA", "OUTB", "CHG", "DSG"})
"""The names of a driver's output pins."""
SWITCH = frozenset({"HS", "VS", "SW", "PH"})
"""The names of a switching-node pin of a driver or a controller."""
RETURN = frozenset({"COM", "VEE", "LS", "PGND"})
"""The names of a driver's return pins."""
FEEDBACK = frozenset({"FB", "COMP", "VFB"})
"""The names of a controller's feedback pins."""
OUT = frozenset({"OUT", "VOUT", "OUTPUT"})
FORCE = frozenset({"F1", "F2", "F+", "F-", "I+", "I-", "FORCE1", "FORCE2"})
SENSE = frozenset({"S1", "S2", "S+", "S-", "K1", "K2", "SENSE1", "SENSE2"})
"""The pin names of a four-terminal shunt: its force (current) pins and its sense pins."""
PREFIXES: tuple[tuple[str, PartClassName], ...] = (
    ("Q", "transistor"),
    ("D", "diode"),
    ("L", "inductor"),
    ("C", "capacitor"),
    ("R", "resistor"),
    ("J", "connector"),
    ("U", "other"),
    ("FB", "ferrite"),
    ("F", "fuse"),
    ("JP", "jumper"),
)
"""Reference prefix → class: the one prefix table of the package tree."""
LINK_PREFIXES: frozenset[str] = frozenset({"FB", "F", "JP"})
"""The prefixes read before the value, with ``medium`` confidence (change c0274)."""
_PREFIX = re.compile(r"^([A-Za-z]+)\d")
_VALUE = re.compile(r"^\s*(\d+(?:\.\d+)?|\.\d+)\s*([pnuµmkMG]?)\s*(F|H|Ω|R|OHM|OHMS)?\s*$", re.IGNORECASE)
_CODE = re.compile(r"^\s*(\d*)([RKM])(\d+)\s*$")
_EXPONENTS = {"p": -12, "n": -9, "u": -6, "µ": -6, "m": -3, "": 0, "k": 3, "M": 6, "G": 9}


@dataclass(frozen=True, slots=True)
class Classified:
    """The class of one part: ``cls``, its ``terminals`` (terminal name → pin numbers), the confidence and
    the evidence that decided it (``user``, ``device``, ``pin-names``, ``value``, ``pads``, ``prefix``,
    ``net-tie``, ``none``)."""

    ref: str
    cls: PartClassName
    confidence: str
    evidence: str
    terminals: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {})

    def pins(self, terminal: str) -> tuple[str, ...]:
        return self.terminals.get(terminal, ())


def lowest(*confidences: str) -> str:
    """The lowest of the confidences given."""
    return min(confidences, key=lambda found: CONFIDENCE_ORDER[found])


def _name(text: str) -> str:
    return text.strip().upper().replace(" ", "")


def _by_names(component: Component) -> tuple[PartClassName, dict[str, tuple[str, ...]]] | None:
    named = [(pin.number, _name(pin.name)) for pin in component.pins if pin.name.strip()]
    if not named:
        return None
    names = {name for _, name in named}

    def pins_of(vocabulary: Collection[str]) -> tuple[str, ...]:
        return tuple(number for number, name in named if name in vocabulary)

    if names <= TRANSISTOR_NAMES and names & GATE and names & DRAIN and names & SOURCE:
        terminals = {"gate": pins_of(GATE), "drain": pins_of(DRAIN), "source": pins_of(SOURCE)}
        if names & KELVIN_SOURCE:
            terminals["kelvin_source"] = pins_of(KELVIN_SOURCE)
        return "transistor", terminals
    if names <= ANODE | CATHODE and names & ANODE and names & CATHODE:
        return "diode", {"anode": pins_of(ANODE), "cathode": pins_of(CATHODE)}
    if len(names & FORCE) == 2 and len(names & SENSE) == 2 and names <= FORCE | SENSE:
        return "shunt", {"force": pins_of(FORCE), "sense": pins_of(SENSE)}
    terminals: dict[str, tuple[str, ...]] = {}
    for positive, negative in INPUT_PAIRS:
        if positive in names and negative in names:
            terminals["in_p"], terminals["in_n"] = pins_of({positive}), pins_of({negative})
            break
    drive = pins_of(DRIVE - ({"OUT"} if "in_p" in terminals else set()))
    switch, ret = pins_of(SWITCH), pins_of(RETURN)
    if drive:
        terminals["drive"] = drive
    if switch:
        terminals["sw"] = switch
    if ret:
        terminals["ret"] = ret
    if "in_p" in terminals and not drive and not switch:
        out = pins_of(OUT)
        if out:
            terminals["out"] = out
        return "amplifier", terminals
    if "in_p" in terminals or (drive or switch) and names & FEEDBACK or (switch and not drive):
        return "controller", terminals
    if drive:
        return "driver", terminals
    return None


def resistance_mohm(value: str) -> Fraction | None:
    """The resistance that a value text states, in milliohms: ``5m``, ``5mΩ``, ``0.005``, ``R005``,
    ``4k7``, ``10kΩ``; ``None`` for a text that is no resistance (a capacitance, an inductance, a word)."""
    text = value.strip().replace("ohm", "Ω").replace("Ohm", "Ω").replace("Ω", "Ω")
    found = _VALUE.match(text)
    if found is not None:
        number, prefix, unit = found.groups()
        if unit is not None and unit.upper() in ("F", "H"):
            return None
        prefix = {"K": "k", "μ": "µ"}.get(prefix, prefix)
        exponent = _EXPONENTS.get(prefix)
        if exponent is None:
            return None
        return Fraction(number) * Fraction(10) ** exponent * 1000
    coded = _CODE.match(text.upper())
    if coded is not None:
        whole, mark, decimals = coded.groups()
        scale = {"R": 0, "K": 3, "M": 6}[mark]
        return Fraction(f"{whole or 0}.{decimals}") * Fraction(10) ** scale * 1000
    return None


def _unit(value: str) -> str | None:
    """``F``, ``H`` or ``Ω`` when the value text ends with that unit."""
    found = _VALUE.match(value.strip().replace("Ω", "Ω"))
    if found is None or found.group(3) is None:
        return None
    unit = found.group(3).upper()
    return {"F": "F", "H": "H"}.get(unit, "Ω")


def _head(ref: str) -> str:
    found = _PREFIX.match(ref)
    return found.group(1).upper() if found is not None else ""


def _prefix(ref: str) -> PartClassName | None:
    head = _head(ref)
    return next((cls for letter, cls in PREFIXES if head == letter), None)


def _shunt_terminals(component: Component, pads: int) -> dict[str, tuple[str, ...]]:
    """A two-pad shunt's two pins are its sense pins; a four-pad one has no terminal map without names."""
    pins = tuple(pin.number for pin in component.pins)
    return {"sense": pins} if pads == 2 and len(pins) == 2 else {}


def classify_part(
    component: Component,
    *,
    user: PartClass | None = None,
    device_cls: str | None = None,
    pads: int | None = None,
    net_tie: bool = False,
    shunt_max_mohm: int = 100,
) -> Classified:
    """The class of one component (the evidence order of the module docstring); ``device_cls`` is the
    ``class`` of its device record."""
    ref = component.ref
    if net_tie:
        return Classified(ref, "net_tie", "high", "net-tie")
    if user is not None:
        terminals = {terminal.name: terminal.pins for terminal in user.terminals}
        return Classified(ref, user.cls, "high", "user", terminals)
    named = _by_names(component)
    if device_cls is not None and device_cls in PART_CLASSES:
        terminals = named[1] if named is not None and named[0] == device_cls else {}
        return Classified(ref, device_cls, "high", "device", terminals)
    if named is not None:
        return Classified(ref, named[0], "high", "pin-names", named[1])
    count = pads if pads is not None else len(component.pins)
    prefix = _prefix(ref)
    if prefix is not None and _head(ref) in LINK_PREFIXES:
        return Classified(ref, prefix, "medium", "prefix")
    unit = _unit(component.value)
    if unit == "F":
        return Classified(ref, "capacitor", "high", "value")
    if unit == "H":
        return Classified(ref, "inductor", "high", "value")
    milliohms = resistance_mohm(component.value) if unit == "Ω" or prefix == "resistor" else None
    if milliohms is not None:
        if milliohms <= shunt_max_mohm or count == 4:
            return Classified(ref, "shunt", "medium", "value", _shunt_terminals(component, count))
        return Classified(ref, "resistor", "high" if unit == "Ω" else "medium", "value")
    if prefix == "resistor" and count == 4:
        return Classified(ref, "shunt", "medium", "pads")
    if prefix is not None:
        return Classified(ref, prefix, "low", "prefix")
    return Classified(ref, "other", "low", "none")


def classify(
    circuit: Circuit,
    *,
    user: Sequence[PartClass] = (),
    pad_counts: Mapping[str, int] | None = None,
    net_ties: Collection[str] = (),
    shunt_max_mohm: int = 100,
    device_classes: Mapping[str, str] | None = None,
) -> dict[str, Classified]:
    """The class of every component of ``circuit``, by reference. ``user`` holds the classes the user
    states; ``pad_counts`` the number of pads of each part when the board is known; ``net_ties`` the
    references of the parts in a net-tie group of the board; ``device_classes`` the ``class`` of each part's
    device record, by reference (change c0274)."""
    stated = {found.ref: found for found in user}
    counts = pad_counts or {}
    devices = device_classes or {}
    return {
        component.ref: classify_part(
            component,
            user=stated.get(component.ref),
            device_cls=devices.get(component.ref),
            pads=counts.get(component.ref),
            net_tie=component.ref in net_ties,
            shunt_max_mohm=shunt_max_mohm,
        )
        for component in sorted(circuit.components, key=lambda found: found.ref)
    }


__all__ = [
    "CONFIDENCE_ORDER",
    "DRIVE",
    "FEEDBACK",
    "INPUT_PAIRS",
    "LINK_PREFIXES",
    "PART_CLASSES",
    "PART_TERMINALS",
    "PREFIXES",
    "RETURN",
    "SWITCH",
    "Classified",
    "classify",
    "classify_part",
    "lowest",
    "resistance_mohm",
]
