# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small circuits for the inference tests, authored for Fenolite: a part is a reference with named pins,
a net a name with ``REF.PIN`` members. Every value is a round illustrative number."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fenolite.model.circuit import Circuit, Component, Interface, Net, Pin, PinRef, PinType


def circuit(
    parts: Mapping[str, tuple[str, Sequence[str | tuple[str, PinType]]]],
    nets: Mapping[str, Sequence[str]],
    *,
    power: Sequence[str] = (),
) -> Circuit:
    """``parts`` maps a reference to its value and its pin names (pin ``i`` is number ``str(i)``; a pair
    gives a name and a type); ``nets`` maps a net name to its members ``REF.PIN``; ``power`` names the
    nets of a power interface (``hv``)."""
    components = []
    for ref, (value, names) in parts.items():
        pins = []
        for index, given in enumerate(names, start=1):
            name, etype = (given, "passive") if isinstance(given, str) else given
            pins.append(Pin(id=f"pin_{ref}_{index}", number=str(index), name=name, etype=etype))
        components.append(Component(id=f"cmp_{ref}", ref=ref, value=value, pins=tuple(pins)))
    made = []
    for name, members in nets.items():
        refs = tuple(PinRef(f"cmp_{m.split('.')[0]}", m.split(".")[1]) for m in members)
        made.append(Net(id=f"net_{name}", name=name, members=refs))
    interfaces = tuple(
        Interface(id=f"ifc_{name}", name=f"{name}/GND", kind="power", members={"hv": f"net_{name}"})
        for name in power
    )
    return Circuit(components=tuple(components), nets=tuple(made), interfaces=interfaces)


GND_PIN: tuple[str, PinType] = ("GND", "power_in")
VCC_PIN: tuple[str, PinType] = ("VCC", "power_in")


def buck() -> Circuit:
    """A synchronous buck with an output shunt sensed by an amplifier: ``SW`` between ``Q1`` and ``Q2``,
    ``L1`` to ``VL``, the shunt ``R12`` from ``VL`` to ``VOUT``, the input capacitor ``C1``."""
    return circuit(
        {
            "J1": ("SUPPLY", ("", "")),
            "C1": ("10uF", ("", "")),
            "Q1": ("NMOS", ("S", "G", "D")),
            "Q2": ("NMOS", ("S", "G", "D")),
            "L1": ("4.7uH", ("", "")),
            "R12": ("5m", ("", "")),
            "C3": ("22uF", ("", "")),
            "J2": ("LOAD", ("", "")),
            "U1": ("CTRL", (VCC_PIN, "HO", "SW", "LO", GND_PIN, "FB")),
            "U3": ("AMP", ("IN+", "IN-", "OUT", VCC_PIN, GND_PIN)),
            "R1": ("10k", ("", "")),
            "R2": ("10k", ("", "")),
        },
        {
            "VIN": ("J1.1", "C1.1", "Q1.3", "U1.1", "U3.4"),
            "GND": ("J1.2", "C1.2", "Q2.1", "C3.2", "J2.2", "U1.5", "U3.5", "R2.2"),
            "SW": ("Q1.1", "Q2.3", "L1.1", "U1.3"),
            "GH": ("U1.2", "Q1.2"),
            "GL": ("U1.4", "Q2.2"),
            "VL": ("L1.2", "R12.1", "U3.1"),
            "VOUT": ("R12.2", "C3.1", "J2.1", "U3.2", "R1.1"),
            "FB": ("R1.2", "R2.1", "U1.6"),
            "ISNS": ("U3.3",),
        },
        power=("VIN", "VOUT"),
    )
