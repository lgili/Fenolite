# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Circuit layer: components, pins, nets, net classes, interfaces and modules."""

from __future__ import annotations

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
    pin_pad_map: tuple[tuple[str, str], ...] = field(default=(), metadata={"ordered": True})


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
]
