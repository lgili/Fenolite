# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Circuit layer: components, pins, nets, net classes, interfaces and modules."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.units import Nm
from fenolite.model.base import Entity

PinType = Literal[
    "input", "output", "bidirectional", "tri_state", "passive", "free", "unspecified",
    "power_in", "power_out", "open_collector", "open_emitter", "no_connect",
]  # fmt: skip


@dataclass(frozen=True, slots=True)
class Pin(Entity):
    """A pin of a component, identified by its number (``"1"``, ``"A3"``, ``"PA5"``)."""

    number: str
    name: str = ""
    etype: PinType = "passive"


PIN_PAD_MAP_DESCRIPTION = (
    "Pairs of (symbol pin number, footprint pad number), in order. A pin may occur in several pairs: it is "
    "bonded to each of those pads, and the first is the pad a schematic symbol shows. A pad occurs once. "
    "A pin without a pair has the pad of its own number."
)


@dataclass(frozen=True, slots=True)
class Component(Entity):
    """A part in the circuit. ``ref`` is an attribute, never a key; ``path`` is hierarchical."""

    ref: str
    value: str = ""
    dnp: bool = False
    lib_symbol_ref: str = ""
    lib_footprint_ref: str = ""
    properties: dict[str, str] = field(default_factory=lambda: {})
    path: str = ""
    pins: tuple[Pin, ...] = ()
    pin_pad_map: tuple[tuple[str, str], ...] = field(
        default=(), metadata={"ordered": True, "description": PIN_PAD_MAP_DESCRIPTION}
    )

    def pads_of(self, pin: str) -> tuple[str, ...]:
        """The pads that ``pin`` is bonded to: the pads of its pairs in ``pin_pad_map``, in map order, the
        first being the pad a schematic symbol shows as the pin's number; the pin's own number when the
        map does not hold the pin."""
        return tuple(pad for source, pad in self.pin_pad_map if source == pin) or (pin,)

    def pin_pads(self) -> dict[str, tuple[str, ...]]:
        """The pads of each pin that ``pin_pad_map`` holds, the pins in the order of their first pair."""
        found: dict[str, list[str]] = {}
        for pin, pad in self.pin_pad_map:
            found.setdefault(pin, []).append(pad)
        return {pin: tuple(pads) for pin, pads in found.items()}


SHARED_PAD_IS_AN_ERROR = True
"""A pad that two pins name is refused (``model.pin-pad-map``). The one place of that choice (change
c0123): a model in which pins share a pad would need every reader of the map to say which pin a pad
stands for."""


def pin_pad_map_problems(component: Component) -> tuple[tuple[str, str], ...]:
    """What is wrong with the pin-to-pad map of ``component``, as (pin, message), in map order: a pair
    with an empty pin or pad, a pair that occurs twice, and a pad that two pins name. For a component
    that holds pins, a pin outside the map names the pad of its own number."""
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    mapped = {pin for pin, _pad in component.pin_pad_map}
    holder = {pin.number: pin.number for pin in component.pins if pin.number and pin.number not in mapped}
    for pin, pad in component.pin_pad_map:
        if not pin or not pad:
            found.append((pin, f"{component.ref}: the pin-to-pad map holds a pair with an empty text"))
            continue
        if (pin, pad) in seen:
            found.append((pin, f"{component.ref}: the pin-to-pad map holds the pair {pin} -> {pad} twice"))
            continue
        seen.add((pin, pad))
        other = holder.setdefault(pad, pin)
        if other != pin and SHARED_PAD_IS_AN_ERROR:
            found.append((pin, f"{component.ref}: the pins {other} and {pin} both name the pad {pad}"))
    return tuple(found)


def normal_pin_pad_map(component: Component) -> tuple[tuple[str, str], ...]:
    """The pin-to-pad map of ``component`` in the one form two equal maps share: the pairs sorted by pin,
    the pads of one pin in map order, without a pin whose one pad is the pad of its own number. A
    comparison of two readings of one design uses it, since the order of the pins and an identity pair are
    no fact of the design."""
    groups = component.pin_pads()
    return tuple((pin, pad) for pin in sorted(groups) if groups[pin] != (pin,) for pad in groups[pin])


def with_normal_pin_maps(circuit: Circuit) -> Circuit:
    """``circuit`` with ``normal_pin_pad_map`` as the map of every component that holds one."""
    if not any(component.pin_pad_map for component in circuit.components):
        return circuit
    components = tuple(
        dataclasses.replace(component, pin_pad_map=normal_pin_pad_map(component))
        if component.pin_pad_map
        else component
        for component in circuit.components
    )
    return dataclasses.replace(circuit, components=components)


@dataclass(frozen=True, slots=True, order=True)
class PinRef:
    """A pin of a component, as a member of a net."""

    component_id: str
    pin: str


@dataclass(frozen=True, slots=True)
class NetClass(Entity):
    """Default physical constraints of a group of nets (all lengths in nm)."""

    name: str
    clearance: Nm | None = None
    track_width: Nm | None = None
    via_diameter: Nm | None = None
    via_drill: Nm | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class Net(Entity):
    """An electrical net and the pins it connects."""

    name: str
    netclass_id: str | None = None
    members: tuple[PinRef, ...] = ()


@dataclass(frozen=True, slots=True)
class Interface(Entity):
    """A typed bundle of nets (power, I2C, SPI…): role name → net id."""

    name: str
    kind: str
    members: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class Module(Entity):
    """A node of the design hierarchy (``power/ldo``) and the components it owns."""

    path: str
    parent: str | None = None
    component_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BusMember:
    """One member of a bus: its index in the vector and the net it names."""

    index: int
    net_id: str


@dataclass(frozen=True, slots=True)
class Bus(Entity):
    """An indexed vector of nets (``D[0..7]``): ``name`` is the vector's name without its range and
    ``members`` its nets in order. A member without a net is left out, so indexes may have gaps. A group
    of nets with different names (a harness) is an ``Interface``, not a bus."""

    name: str
    members: tuple[BusMember, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class Circuit:
    """The circuit layer of a design (``circuit.json``)."""

    components: tuple[Component, ...] = ()
    nets: tuple[Net, ...] = ()
    netclasses: tuple[NetClass, ...] = ()
    interfaces: tuple[Interface, ...] = ()
    modules: tuple[Module, ...] = ()
    #: Buses, indexed vectors of nets; a bus gives no net and no net member.
    buses: tuple[Bus, ...] = ()
    #: Pins the design leaves unconnected on purpose, in the form of net members: ``pin`` holds a
    #: designator as written until a build resolves it, and a pin number afterwards.
    no_connects: tuple[PinRef, ...] = ()


__all__ = [
    "Bus",
    "BusMember",
    "Circuit",
    "Component",
    "Interface",
    "Module",
    "Net",
    "NetClass",
    "Pin",
    "PinRef",
    "PinType",
    "normal_pin_pad_map",
    "pin_pad_map_problems",
    "with_normal_pin_maps",
]
