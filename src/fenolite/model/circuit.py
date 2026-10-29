# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Circuit layer: components, pins, nets, net classes, interfaces and modules."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal, get_args

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


DECIMAL10_DIGITS = 15
"""The most significant digits of a ``Decimal10`` mantissa: every integer stays below 2^53."""
DECIMAL10_EXPONENTS = range(-30, 31)
"""The exponents a ``Decimal10`` may hold."""


@dataclass(frozen=True, slots=True)
class Decimal10:
    """The exact decimal m · 10^e in its one canonical form (change c0246).

    ``|m| <= 10^15 - 1``, ``-30 <= e <= 30``, no trailing zero digit in ``m``, and zero as
    ``Decimal10(0, 0)``, so one value has one form and every integer stays below 2^53.
    """

    m: int
    e: int

    def __post_init__(self) -> None:
        for name, value in (("m", self.m), ("e", self.e)):
            if isinstance(value, bool) or not isinstance(value, int):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ValueError(f"Decimal10.{name} must be an integer, not {value!r}")
        if abs(self.m) >= 10**DECIMAL10_DIGITS:
            raise ValueError(f"Decimal10.m holds at most {DECIMAL10_DIGITS} digits, not {self.m}")
        if self.e not in DECIMAL10_EXPONENTS:
            raise ValueError(f"Decimal10.e lies in -30..30, not {self.e}")
        if self.m == 0 and self.e != 0:
            raise ValueError("zero is Decimal10(0, 0)")
        if self.m != 0 and self.m % 10 == 0:
            raise ValueError(f"Decimal10.m has no trailing zero digit: write {self.m} as a larger exponent")

    def fraction(self) -> Fraction:
        """The exact value."""
        return Fraction(self.m) * (Fraction(10) ** self.e)


RangeUnit = Literal["ohm", "farad", "henry", "volt", "ampere", "hertz", "watt", "second", "kelvin"]
"""The units of a ``ValueRange``: the units of the DSL's ``Quantity`` (``kelvin``: change c0274)."""


@dataclass(frozen=True, slots=True)
class ValueRange:
    """An exact range of an electrical value: unit, low, nominal and high, at least one bound given.

    Stored on ``Component.value_range`` (change c0246); no backend writes or reads it.
    """

    unit: RangeUnit
    low: Decimal10 | None = None
    nominal: Decimal10 | None = None
    high: Decimal10 | None = None

    def __post_init__(self) -> None:
        if self.unit not in get_args(RangeUnit):
            raise ValueError(
                f"unknown range unit {self.unit!r}; use one of: {', '.join(get_args(RangeUnit))}"
            )
        for name, value in (("low", self.low), ("nominal", self.nominal), ("high", self.high)):
            if value is not None and not isinstance(value, Decimal10):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise ValueError(f"ValueRange.{name} must be a Decimal10 or None, not {value!r}")
        if self.low is None and self.high is None:
            raise ValueError("a value range needs at least one bound")
        low = None if self.low is None else self.low.fraction()
        high = None if self.high is None else self.high.fraction()
        if low is not None and high is not None and low > high:
            raise ValueError(f"a value range runs from low to high, not from {low} to {high}")
        if self.nominal is not None:
            nominal = self.nominal.fraction()
            if (low is not None and nominal < low) or (high is not None and nominal > high):
                raise ValueError(f"the nominal {nominal} lies outside the value range {low}..{high}")


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
    #: The exact range of ``value`` when the design gave one (a DSL part value with a tolerance).
    value_range: ValueRange | None = None

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
    #: The width, gap and via gap of a differential pair of the class: defaults of a router, not limits.
    diff_pair_width: Nm | None = None
    diff_pair_gap: Nm | None = None
    diff_pair_via_gap: Nm | None = None


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


BlockParamType = Literal["bool", "int", "str", "length", "quantity", "range", "none"]
BLOCK_PARAM_TYPES: tuple[str, ...] = ("bool", "int", "str", "length", "quantity", "range", "none")
"""The closed set of ``BlockParam.type`` (change c0251)."""


@dataclass(frozen=True, slots=True)
class BlockParam:
    """One parameter of a block instance as recorded: its name, its type and its canonical text
    (``true``, ``3``, ``1000000`` nm, ``3.3V``; empty for ``none``)."""

    name: str
    type: BlockParamType
    text: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a block parameter needs a name")
        if self.type not in BLOCK_PARAM_TYPES:
            raise ValueError(
                f"block parameter {self.name}: type {self.type!r} is not one of "
                f"{', '.join(BLOCK_PARAM_TYPES)}"
            )


@dataclass(frozen=True, slots=True)
class Module(Entity):
    """A node of the design hierarchy (``power/ldo``) and the components it owns. A module made by a
    block (change c0251) names it in ``block`` and records its parameters in ``params``, ordered by name."""

    path: str
    parent: str | None = None
    component_ids: tuple[str, ...] = ()
    block: str = ""
    params: tuple[BlockParam, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        names = [param.name for param in self.params]
        if len(set(names)) != len(names):
            raise ValueError(f"module {self.path}: two block parameters have one name")
        if names != sorted(names):
            raise ValueError(f"module {self.path}: block parameters must be ordered by name")
        if self.params and not self.block:
            raise ValueError(f"module {self.path}: block parameters need a block name")


PortDirection = Literal["in", "out", "inout"]
PORT_DIRECTIONS: tuple[str, ...] = ("in", "out", "inout")


@dataclass(frozen=True, slots=True)
class Port(Entity):
    """A port of a block instance (change c0251): its name, its owner (the id of a module, or of a
    component for a device port), its interface kind (``net``, ``power``, ``i2c``…), its direction, and
    member name → net id; a member without a net is left out."""

    name: str
    owner: str
    kind: str
    direction: PortDirection = "inout"
    members: dict[str, str] = field(default_factory=lambda: {})
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.kind:
            raise ValueError("a port needs a name and a kind")
        if self.direction not in PORT_DIRECTIONS:
            raise ValueError(
                f"port {self.name}: direction {self.direction!r} is not one of {', '.join(PORT_DIRECTIONS)}"
            )


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
    #: The ports of block instances (change c0251).
    ports: tuple[Port, ...] = ()
    #: Buses, indexed vectors of nets; a bus gives no net and no net member.
    buses: tuple[Bus, ...] = ()
    #: Pins the design leaves unconnected on purpose, in the form of net members: ``pin`` holds a
    #: designator as written until a build resolves it, and a pin number afterwards.
    no_connects: tuple[PinRef, ...] = ()


def power_interface_nets(circuit: Circuit) -> frozenset[str]:
    """The ids of the nets that an interface of kind ``power`` names (the DSL's ``Power``): the one set that
    ERC lite, the schematic writer's power flags and ``fenolite ready`` take as the declared supplies."""
    return frozenset(
        net_id
        for interface in circuit.interfaces
        if interface.kind == "power"
        for net_id in interface.members.values()
    )


__all__ = [
    "BLOCK_PARAM_TYPES",
    "PORT_DIRECTIONS",
    "BlockParam",
    "BlockParamType",
    "Bus",
    "BusMember",
    "Circuit",
    "Component",
    "Decimal10",
    "Interface",
    "Module",
    "Net",
    "NetClass",
    "Pin",
    "PinRef",
    "PinType",
    "Port",
    "PortDirection",
    "RangeUnit",
    "ValueRange",
    "normal_pin_pad_map",
    "pin_pad_map_problems",
    "power_interface_nets",
    "with_normal_pin_maps",
]
