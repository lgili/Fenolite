# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts, nets, pins and placements of the DSL (``docs/dsl.md``, "API")."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

from fenolite.core.coords import Point
from fenolite.core.units import Nm, Udeg
from fenolite.dsl.errors import DslError
from fenolite.dsl.quantity import RATIO, SIGNED, Quantity, Range
from fenolite.dsl.units import as_nm, as_udeg
from fenolite.model.board import MechanicalIntent
from fenolite.model.library import DeviceDef

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.devices import Origin
    from fenolite.dsl.intents import AnchorRef, PadRef
    from fenolite.dsl.module import Container
    from fenolite.dsl.portnets import Group, PortHandle
    from fenolite.dsl.take import TakenInterface

Side = Literal["top", "bottom"]
NAME = re.compile(r"[A-Za-z0-9_.+-]+")
"""Module names, part names and refs."""
PREFIX = re.compile(r"[A-Z][A-Z_]*")
"""Reference prefixes (``prefix=``)."""
RESERVED_PROPERTIES: frozenset[str] = frozenset(
    {"Reference", "Value", "Footprint", "Datasheet", "Description"}
)
"""Property names a part cannot set (compared after ``str.casefold``): ``ref`` and ``value`` give the first
two, the others are fields of the footprint library (``docs/dsl.md``, "User properties")."""
RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")
"""Property-name prefixes a part cannot use: Fenolite's namespace and KiCad's own names."""
FIELD_NAMES: tuple[str, ...] = ("Reference", "Value")
"""The footprint fields a script can place (``docs/dsl.md``, "Field placement")."""
FIELD_LAYERS: tuple[str, ...] = ("silk", "fab")
FIELD_SIDES: tuple[str, ...] = ("top", "bottom", "left", "right")
FIELD_JUSTIFY: tuple[str, ...] = (
    "left",
    "right",
    "top",
    "bottom",
    "left top",
    "left bottom",
    "right top",
    "right bottom",
)
"""One or two words: ``left`` or ``right`` first, then ``top`` or ``bottom``."""


def _properties(ref: str, properties: object) -> Mapping[str, str]:
    """The user properties of part ``ref``, checked, in code-point order of names."""
    if properties is None:
        return MappingProxyType({})
    if not isinstance(properties, Mapping):
        raise DslError(f"part {ref}: properties must be a mapping of str to str, not {properties!r}")
    folded: dict[str, str] = {}
    for name, value in cast(Mapping[object, object], properties).items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise DslError(f"part {ref}: property {name!r} must map a str name to a str value, not {value!r}")
        if not name or name != name.strip() or not name.isprintable():
            raise DslError(
                f"part {ref}: property name {name!r} must be printable text without surrounding spaces"
            )
        if not value.isprintable():
            raise DslError(f"part {ref}: property {name!r} has a value with a non-printable character")
        key = name.casefold()
        reserved = next((r for r in sorted(RESERVED_PROPERTIES) if r.casefold() == key), None)
        if reserved is not None:
            raise DslError(f"part {ref}: property {name!r} is the reserved name {reserved!r}")
        prefix = next((p for p in RESERVED_PREFIXES if key.startswith(p)), None)
        if prefix is not None:
            raise DslError(f"part {ref}: property {name!r} starts with the reserved prefix {prefix!r}")
        if key in folded:
            raise DslError(f"part {ref}: properties {folded[key]!r} and {name!r} differ only in letter case")
        folded[key] = name
    names = cast(Mapping[str, str], properties)
    return MappingProxyType({name: names[name] for name in sorted(names)})


def catalog_prefix(lib_id: str) -> str | None:
    """The ``reference`` of the ``Fenolite:`` catalog symbol ``lib_id``, or ``None`` for another symbol."""
    if not lib_id.startswith("Fenolite:"):
        return None
    from fenolite.catalog import symbol_reference

    return symbol_reference(lib_id)


def check_name(value: object, what: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise DslError(f"{what} {value!r} must match {NAME.pattern}")
    return value


class Net:
    """A net, named globally and literally; a module-local net is named by the script."""

    deferred = False
    """True for a port net (``fenolite.dsl.portnets``), whose name is fixed only by ``to_model``."""

    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name or name != name.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"a net name must be a non-empty string without surrounding spaces, not {name!r}")
        self.name = name
        self.design: Design | None = None
        self.netclass: str | None = None
        self.group: Group | None = None
        """The port nets this net is bound to (change c0251); ``None`` until it is bound to one."""

    def __repr__(self) -> str:
        return f"Net({self.name!r})"


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a part goes: ``at`` in the written frame (``BOARD_ORIGIN`` added), the stored rotation, the
    side and the lock."""

    at: Point
    rotation: Udeg
    side: Side
    locked: bool
    anchor: MechanicalIntent | None = None


@dataclass(frozen=True, slots=True)
class Request:
    """A placement as the script gave it, in the board-relative frame."""

    x: int
    y: int
    rotation: Udeg
    side: Side
    locked: bool
    anchor: MechanicalIntent | None = None


PAD_ZONE_CONNECTIONS = ("solid", "thermal", "none", "thru_hole_only")
"""The values of ``Pad.zone_connection`` (``docs/design-model.md``)."""


@dataclass(frozen=True, slots=True)
class PadZoneRequest:
    """A request for how copper zones connect to pads of a part, as the script gave it: the pad
    ``number``, the ``index`` among the pads that carry it (``None``: every one), the ``connection`` and
    whether the request wins over a setting made in KiCad (``docs/dsl.md``, "Zones")."""

    number: str
    index: int | None
    connection: str
    locked: bool = False


@dataclass(frozen=True, slots=True)
class FieldRequest:
    """A placement request for one footprint field of a part, as the script gave it: lengths in nm, the
    angle in µdeg, and ``None`` for every value that was not given.

    ``dx`` and ``dy`` are measured in the board frame from the part's placement point and ``rotation`` is
    the field's angle on the board; ``layer`` is ``silk`` or ``fab`` on the part's side; ``outside`` names
    a side of the courtyard box, with ``gap`` as the distance from it.
    """

    name: str
    dx: Nm | None = None
    dy: Nm | None = None
    rotation: Udeg | None = None
    layer: str | None = None
    visible: bool | None = None
    size: Nm | None = None
    thickness: Nm | None = None
    justify: str | None = None
    outside: str | None = None
    gap: Nm | None = None
    locked: bool = False


@dataclass(frozen=True)
class PinHandle:
    """One designator of one part, as written (a pin number or a pin name)."""

    part: Part
    designator: str


def pads_of(value: str | Sequence[str]) -> tuple[str, ...]:
    """The pads of one value of ``Part.pad_map``: a string is one pad, a sequence several, in order."""
    return (value,) if isinstance(value, str) else tuple(value)


def pad_pairs(pad_map: Mapping[str, str | Sequence[str]]) -> tuple[tuple[str, str], ...]:
    """``Component.pin_pad_map`` of a ``pad_map``: the pins in sorted order, the pads of one pin as written.
    For a map of one pad per pin this is ``tuple(sorted(pad_map.items()))``."""
    return tuple((pin, pad) for pin in sorted(pad_map) for pad in pads_of(pad_map[pin]))


def _value_range(ref: str, value: Range) -> Range:
    """``value`` when it can be a part value: a unit of ``Quantity``, a nominal, two bounds, no negative
    bound of an unsigned unit, and a model form within the exponent limit; else ``DslError``."""
    from fenolite.dsl.convert import range_to_model

    if value.unit == RATIO:
        raise DslError(f"part {ref}: the value {value.text()} is a ratio; a part value needs a unit")
    if value.low is None or value.high is None:
        raise DslError(f"part {ref}: the value {value.text()} is unbounded; a part value needs two bounds")
    if value.nominal_value is None:
        raise DslError(f"part {ref}: the value {value.text()} has no nominal; a part value needs a nominal")
    if value.low < 0 and value.unit not in SIGNED:
        raise DslError(f"part {ref}: the value {value.text()} has a negative bound in {value.unit}")
    try:
        range_to_model(value)
    except DslError as exc:
        raise DslError(f"part {ref}: {exc}") from exc
    return value


def _device_properties(ref: str, device: DeviceDef, user: Mapping[str, str]) -> Mapping[str, str]:
    """The user properties of a device part merged with ``Manufacturer``, ``MPN`` and the device's own
    properties; a user property of one of those names (after ``str.casefold``) with another value is
    refused (``docs/devices.md``, "Parts from devices")."""
    given = {"Manufacturer": device.manufacturer, "MPN": device.mpn, **device.properties}
    merged = {name: value for name, value in given.items() if value}
    folded = {name.casefold(): name for name in merged}
    out = dict(merged)
    for name, value in user.items():
        own = folded.get(name.casefold())
        if own is None:
            out[name] = value
        elif merged[own] != value:
            raise DslError(
                f"part {ref}: property {name!r} = {value!r} conflicts with the device {device.id}, whose "
                f"{own} is {merged[own]!r}; a different {own} is a different device"
            )
    return MappingProxyType({name: out[name] for name in sorted(out)})


class Part:
    """A component: reference, symbol lib id, optional footprint lib id, value and user properties; or a
    reference and a device id, which gives the rest (``docs/devices.md``)."""

    device: DeviceDef | None
    """The device of a part made with ``device=``; ``None`` for any other part."""
    device_origin: Origin | None
    """Where the device came from: ``authored`` (the design or the project) or ``builtin``."""
    device_overrides: bool
    """Whether the part's device is a project device that has the id of a shipped one."""

    def __init__(
        self,
        ref: str | None = None,
        lib_id: str | None = None,
        footprint: str | None = None,
        value: str | Quantity | Range | None = None,
        *,
        name: str | None = None,
        prefix: str | None = None,
        device: str | None = None,
        properties: Mapping[str, str] | None = None,
        pad_map: Mapping[str, str | Sequence[str]] | None = None,
        height: object = None,
    ) -> None:
        self.explicit_ref: str | None = None if ref is None else check_name(ref, "ref")
        """The ref the script wrote, or ``None``: the build then assigns one (``docs/dsl.md``, "Reference
        designators and the design lock")."""
        self.assigned: str | None = None
        """The ref the build assigned to a part without an explicit ref (``to_model``)."""
        self.name: str | None = None if name is None else check_name(name, "part name")
        if prefix is not None and (not isinstance(prefix, str) or not PREFIX.fullmatch(prefix)):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part prefix {prefix!r} must match {PREFIX.pattern}")
        label = ref or name or prefix or lib_id or device
        self.device: DeviceDef | None = None
        self.device_origin: Origin | None = None
        self.device_overrides = False
        if (lib_id is None) == (device is None):
            raise DslError(f"part {label}: give exactly one of lib_id and device")
        if device is not None:
            from fenolite.dsl.devices import resolve

            for field_name, given in (("footprint", footprint), ("pad_map", pad_map)):
                if given is not None:
                    raise DslError(
                        f"part {label}: the device names the {field_name}; do not give {field_name} with "
                        "device="
                    )
            found = resolve(device)
            self.device, self.device_origin, self.device_overrides = (
                found.device,
                found.origin,
                found.overrides,
            )
            lib_id, footprint = found.device.symbol, found.device.footprint
            pad_map = {
                pin: tuple(pad for owner, pad in found.device.pad_map if owner == pin)
                for pin in dict.fromkeys(owner for owner, _ in found.device.pad_map)
            }
            if value is None:
                value = found.device.value
            if prefix is None and found.device.ref_prefix:
                prefix = found.device.ref_prefix  # the device's prefix feeds the lock (change c0249)
        if value is None:
            value = ""
        if not isinstance(lib_id, str) or not lib_id:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {label}: lib_id must be a non-empty string")
        self.prefix: str | None = prefix if prefix is not None else catalog_prefix(lib_id)
        """The reference prefix: ``prefix=``, else the ``reference`` of a ``Fenolite:`` catalog symbol."""
        if self.explicit_ref is None and self.prefix is None:
            raise DslError(
                f"part {label}: give a ref, a prefix or a device; {lib_id} is not a catalog symbol, so its "
                "reference prefix is unknown"
            )
        ref = cast(str, label)
        if footprint is not None and (not isinstance(footprint, str) or not footprint):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: footprint must be a non-empty string or None")
        #: The exact range of the value when it was given as a ``Range`` (change c0246); else ``None``.
        self.value_range: Range | None = None
        if isinstance(value, Range):
            self.value_range = _value_range(ref, value)
            value = Quantity(value.unit, cast(Fraction, value.nominal_value)).text()
        if isinstance(value, Quantity):
            value = value.text()
        if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: value must be a string, a Quantity or a Range")
        self.lib_id = lib_id
        self.footprint = footprint
        self.value = value
        self.properties: Mapping[str, str] = _properties(ref, properties)
        if self.device is not None:
            self.properties = _device_properties(ref, self.device, self.properties)
        if pad_map is None:
            pad_map = {}
        if not isinstance(pad_map, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: pad_map must map symbol pin numbers to footprint pad numbers")
        checked_map: dict[str, str | tuple[str, ...]] = {}
        targets: set[str] = set()
        for source, target in cast(Mapping[object, object], pad_map).items():
            if not isinstance(source, str) or not source:
                raise DslError(f"part {ref}: pad_map keys and values must be non-empty strings")
            # one pad, or a tuple or list of pads for a pin bonded to several (change c0123)
            several = isinstance(target, (tuple, list))
            pads = tuple(cast("Sequence[object]", target)) if several else (target,)
            if not pads:
                raise DslError(f"part {ref}: pad_map gives symbol pin {source!r} no pad")
            for index, pad in enumerate(pads):
                if not isinstance(pad, str) or not pad:
                    raise DslError(f"part {ref}: pad_map keys and values must be non-empty strings")
                if pad in pads[:index]:
                    raise DslError(f"part {ref}: pad_map lists pad {pad!r} twice for symbol pin {source!r}")
                if pad in targets:
                    raise DslError(f"part {ref}: pad_map maps more than one pin to pad {pad!r}")
                targets.add(pad)
            if source in checked_map:
                raise DslError(f"part {ref}: pad_map repeats symbol pin {source!r}")
            names = cast("tuple[str, ...]", pads)
            checked_map[source] = names[0] if len(names) == 1 else names
        self.pad_map: Mapping[str, str | tuple[str, ...]] = MappingProxyType(
            dict(sorted(checked_map.items()))
        )
        self.height: Nm | None = None
        """The top of the part's body above the board surface on its own side, in nm (change c0140); the
        build turns it into a body of the placed footprint, and nothing else reads it."""
        if height is not None:
            self.height = as_nm(height, name=f"part {ref}: height")
            if self.height <= 0:
                raise DslError(f"part {ref}: height must be above 0")
        self.parent: Container | None = None
        self.request: Request | None = None
        self.field_requests: dict[str, FieldRequest] = {}
        """The field placement requests of ``field()``, by field name."""
        self.pad_zone_requests: dict[tuple[str, int | None], PadZoneRequest] = {}
        """The requests of ``zone_connection()``, by pad number and index."""
        self.connections: dict[str, Net] = {}
        self.ports: dict[str, PortHandle] = {}
        """The device ports of this part that the script reached (``port``; change c0252), by name."""
        self.no_connects: set[str] = set()
        """Designators marked as intentionally unconnected, as written (``no_connect``)."""
        self.two_terminal = False
        """Set when the part is used through its ends ``a`` and ``b`` (or a connection helper): the build
        then checks that its symbol has exactly two pins (``build.not-two-terminal``; change c0247)."""
        self.unused_request: frozenset[str] | None = None
        """The ``keep`` designators of ``unused_no_connect()``, as written; ``None`` without a request."""

    @property
    def ref(self) -> str | None:
        """The explicit ref, or the ref the build assigned (``to_model``); ``None`` before that."""
        return self.explicit_ref if self.explicit_ref is not None else self.assigned

    @ref.setter
    def ref(self, value: str | None) -> None:
        """Setting a ref makes it the part's explicit ref (``None`` removes it)."""
        self.explicit_ref = None if value is None else check_name(value, "ref")

    @property
    def key(self) -> str:
        """The last segment of the path: ``name``, else the explicit ref, else the reference prefix."""
        return cast(str, self.name or self.explicit_ref or self.prefix)

    @property
    def label(self) -> str:
        """The part as messages name it: its ref when known, else its path."""
        return self.ref if self.ref is not None else self.path

    @property
    def path(self) -> str:
        from fenolite.dsl.module import Module

        if isinstance(self.parent, Module):
            return f"{self.parent.path}/{self.key}"
        return self.key

    @property
    def design(self) -> Design | None:
        parent = self.parent
        return None if parent is None else parent.design

    def __getitem__(self, designator: str | int) -> PinHandle:
        if isinstance(designator, bool) or not isinstance(designator, (str, int)):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.label}: a designator is a pin number or name, not {designator!r}")
        text = str(designator)
        if not text:
            raise DslError(f"part {self.label}: empty designator")
        if self.device is not None:
            from fenolite.dsl.devices import designator as checked

            text = checked(self, self.device, text)
        return PinHandle(self, text)

    def _end(self, index: int) -> PinHandle:
        """The pin handle of end ``index`` (0 is ``a``, 1 is ``b``): symbol pins ``1`` and ``2``. This is the
        one lookup of the ends; a catalog device that names its ends (change c0248) gives its functions."""
        from fenolite.dsl.devices import end_handle

        named = end_handle(self, index)
        return named if named is not None else self[str(index + 1)]

    @property
    def a(self) -> PinHandle:
        """The first end of a two-pin part (pin ``1``); using it marks the part ``two_terminal``."""
        self.two_terminal = True
        return self._end(0)

    @property
    def b(self) -> PinHandle:
        """The second end of a two-pin part (pin ``2``); using it marks the part ``two_terminal``."""
        self.two_terminal = True
        return self._end(1)

    def unused_no_connect(self, *, keep: Iterable[str | int] = ()) -> None:
        """Ask the build to mark every pin of this part that is open when it runs as not connected, except
        the designators of ``keep`` (pin numbers or names, as written), pins of type ``no_connect`` and
        must-connect pins: an open ``power_in`` pin stops the build with ``build.must-connect-unconnected``
        (``docs/dsl.md``, "Connection helpers"). Once per part; ``connect`` and ``no_connect`` stay
        allowed after it."""
        if self.unused_request is not None:
            raise DslError(f"part {self.ref}: unused_no_connect() is already requested")
        if isinstance(keep, (str, bytes)) or not isinstance(keep, Iterable):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.ref}: keep is a tuple of designators, not {keep!r}")
        kept: set[str] = set()
        for designator in cast("Iterable[object]", keep):
            if isinstance(designator, bool) or not isinstance(designator, (str, int)) or not str(designator):
                raise DslError(
                    f"part {self.ref}: a keep designator is a pin number or name, not {designator!r}"
                )
            kept.add(str(designator))
        self.unused_request = frozenset(kept)

    def port(self, name: str) -> PortHandle:
        """The interface port ``name`` that the part's device declares (``[[interfaces]]``, change c0252):
        a ``PortHandle`` whose members are the part's pins, through port nets owned by the part's path."""
        from fenolite.dsl.devices import device_port

        return device_port(self, name)

    def take(
        self,
        kind: object,
        *,
        name: str | None = None,
        option: str | None = None,
        pins: Mapping[str, object] | None = None,
    ) -> TakenInterface:
        """Take one interface of ``kind`` (``I2C``, ``SPI``, ``UART``, ``USB2``, ``DiffPair`` or ``"pin"``)
        from the options of the part's device; the build chooses its pins (``docs/pins.md``; change c0257).
        The take key is ``name``, else ``<kind>#<n>``; ``option`` and ``pins`` narrow the alternatives."""
        from fenolite.dsl.take import take

        return take(self, kind, name=name, option=option, pins=pins)

    def __getattr__(self, name: str) -> PinHandle | PortHandle:
        """A device port (change c0252) or a function of a device part read as an attribute (``u1.vdd``,
        ``u1.VIN``); reached only for names that ``Part`` does not define, so every attribute of the part
        wins."""
        if name.startswith("_"):
            raise AttributeError(name)
        device = self.__dict__.get("device")
        if device is None:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
        if any(found.name == name for found in device.interfaces):
            return self.port(name)
        from fenolite.dsl.devices import designator as checked

        return PinHandle(self, checked(self, device, name))

    def __dir__(self) -> list[str]:
        names = set(super().__dir__())
        if self.device is not None:
            from fenolite.dsl.devices import attribute_names

            names |= set(attribute_names(self.device, set(dir(type(self)))))
        return sorted(names)

    def pad(self, number: str | int, *, index: int | None = None) -> PadRef:
        """The pads of this part numbered ``number``, for a copper intent; ``index`` picks one of several
        pads sharing the number (the build takes the nearest otherwise). On a device part ``number`` may
        also be a function: its first pad in map order, or the ``index``-th."""
        from fenolite.dsl.intents import pad_ref

        if self.device is not None and isinstance(number, str):
            from fenolite.dsl.devices import function_pad

            pad = function_pad(self, self.device, number, index)
            if pad is not None:
                return pad_ref(self, pad, None)
        return pad_ref(self, number, index)

    def at(self, dx: object = None, dy: object = None) -> AnchorRef:
        """The point ``(dx, dy)`` from the origin of this part's footprint, in the footprint's frame as its
        library draws it (X to the right, Y down), for a copper intent; a length left out is 0. The build
        resolves it after placement, so the point turns and moves with the part and is mirrored with it
        on the bottom side. ``part.pad(n).at(dx, dy)`` measures from a pad, which needs no library
        coordinates."""
        from fenolite.dsl.intents import anchor_ref

        return anchor_ref(self, None, None, dx, dy)

    def place(
        self,
        x: object,
        y: object,
        rot: int | str | float = 0,
        side: str = "top",
        locked: bool = False,
        *,
        anchor: MechanicalIntent | None = None,
    ) -> None:
        """Request a placement in the board frame (origin at the outline's top-left corner, Y down)."""
        if self.request is not None:
            raise DslError(f"part {self.label} is already placed")
        if side not in ("top", "bottom"):
            raise DslError(f"part {self.label}: side must be 'top' or 'bottom', not {side!r}")
        if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.label}: locked must be a bool")
        if anchor is not None and not locked:
            raise DslError(f"part {self.label}: an anchor requires locked=True")
        if anchor is not None and not isinstance(anchor, MechanicalIntent):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.label}: anchor must be MechanicalIntent")
        self.request = Request(
            as_nm(x, name="x"), as_nm(y, name="y"), as_udeg(rot, name="rot"), side, locked, anchor
        )

    def field(
        self,
        name: str,
        *,
        dx: object = None,
        dy: object = None,
        rot: int | str | float | None = None,
        layer: str | None = None,
        visible: bool | None = None,
        size: object = None,
        thickness: object = None,
        justify: str | None = None,
        outside: str | None = None,
        gap: object = None,
        locked: bool = False,
    ) -> None:
        """Request a placement of the footprint field ``name`` (``Reference`` or ``Value``), once per name.

        ``dx`` and ``dy`` are lengths in the board frame from the part's placement point and ``rot`` is the
        field's angle on the board, so "2.5 mm above the part, horizontal" stays true when the part
        turns. ``outside`` puts the field beside the courtyard on one side instead; ``gap`` is its
        distance. ``locked`` makes the request win over a field edited in KiCad (``docs/lens.md``).
        """
        what = f"part {self.label}: field {name!r}"
        if name not in FIELD_NAMES:
            raise DslError(f"{what}: only {' and '.join(FIELD_NAMES)} can be placed")
        if name in self.field_requests:
            raise DslError(f"part {self.label}: field {name} already has a placement request")
        for label, flag in (("visible", visible), ("locked", locked)):
            if flag is not None and not isinstance(flag, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"{what}: {label} must be a bool, not {flag!r}")
        if (dx is None) != (dy is None):
            raise DslError(f"{what}: dx and dy must be given together")
        if layer is not None and layer not in FIELD_LAYERS:
            raise DslError(f"{what}: layer must be 'silk' or 'fab', not {layer!r}")
        if justify is not None:
            if not isinstance(justify, str) or " ".join(justify.split()) not in FIELD_JUSTIFY:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(
                    f"{what}: justify is 'left' or 'right', then 'top' or 'bottom', not {justify!r}"
                )
            justify = " ".join(justify.split())
        if outside is not None:
            if outside not in FIELD_SIDES:
                raise DslError(f"{what}: outside must be one of {', '.join(FIELD_SIDES)}, not {outside!r}")
            taken = [
                k for k, v in (("dx", dx), ("dy", dy), ("rot", rot), ("justify", justify)) if v is not None
            ]
            if taken:
                raise DslError(f"{what}: outside decides the position, so {', '.join(taken)} cannot be given")
        elif gap is not None:
            raise DslError(f"{what}: gap is allowed only with outside")
        lengths: dict[str, Nm | None] = {}
        for label, value in (("dx", dx), ("dy", dy), ("size", size), ("thickness", thickness), ("gap", gap)):
            lengths[label] = None if value is None else as_nm(value, name=f"{what}: {label}")
        for label in ("size", "thickness"):
            found = lengths[label]
            if found is not None and found <= 0:
                raise DslError(f"{what}: {label} must be positive")
        if lengths["gap"] is not None and lengths["gap"] < 0:
            raise DslError(f"{what}: gap must be at least 0")
        rotation = None if rot is None else as_udeg(rot, name=f"{what}: rot")
        request = FieldRequest(
            name,
            lengths["dx"],
            lengths["dy"],
            rotation,
            layer,
            visible,
            lengths["size"],
            lengths["thickness"],
            justify,
            outside,
            lengths["gap"],
            locked,
        )
        if request == FieldRequest(name, locked=locked):
            raise DslError(f"{what}: the request sets nothing")
        self.field_requests[name] = request

    def zone_connection(
        self, number: str | int, connection: str, *, index: int | None = None, locked: bool = False
    ) -> None:
        """Request how copper zones connect to the pads of this part numbered ``number``: ``solid``,
        ``thermal``, ``none`` or ``thru_hole_only``. ``index`` names one of several pads that share the
        number, in the footprint's pad order. On a rebuild a setting made in KiCad wins unless the
        request is ``locked`` (``docs/lens.md``)."""
        if isinstance(number, bool) or not isinstance(number, (str, int)) or str(number) == "":  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.label}: a pad number is a non-empty str or an int, not {number!r}")
        text = str(number)
        what = f"part {self.label}: zone connection of pad {text}"
        if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: index is None or a non-negative int, not {index!r}")
        if connection not in PAD_ZONE_CONNECTIONS:
            raise DslError(
                f"{what}: connection must be one of {', '.join(PAD_ZONE_CONNECTIONS)}, not {connection!r}"
            )
        if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: locked must be a bool, not {locked!r}")
        if (text, index) in self.pad_zone_requests:
            where = "" if index is None else f" index {index}"
            raise DslError(f"part {self.label}: pad {text}{where} already has a zone connection request")
        taken = [key for key in self.pad_zone_requests if key[0] == text]
        if taken and (index is None or any(key[1] is None for key in taken)):
            raise DslError(
                f"part {self.label}: pad {text} has a zone connection request with an index and one without: "
                "the two would name the same pad"
            )
        self.pad_zone_requests[(text, index)] = PadZoneRequest(text, index, connection, locked)

    def __repr__(self) -> str:
        return f"Part({self.ref!r}, {self.lib_id!r})"


def connect(net: object, *pins: object) -> Net:
    """Join each pin to ``net``; one designator of one part on two nets is refused.

    ``net`` is a ``Net``, a port net, a net-like port or a net-like interface (a ``Rail``, a ``Ground`` or a
    ``Logic``, change c0252); a pin argument may also be a port net, a net-like port or a compatible net-like
    interface, which binds it to ``net`` (``docs/dsl.md``, "Port nets"). When every argument is an
    interface or a port, whole interfaces are joined member by member (``fenolite.dsl.rails``)."""
    from fenolite.dsl.interfaces import Interface
    from fenolite.dsl.portnets import PortHandle, PortNet, as_net, join, same_net

    if pins and all(isinstance(item, Interface | PortHandle) for item in (net, *pins)):
        from fenolite.dsl.rails import connect_interfaces

        return connect_interfaces((net, *pins))
    first = as_net(net, what="connect()")
    if first is None:
        raise DslError(f"connect() needs a Net first, not {net!r}")
    if any(isinstance(pin, Interface | PortHandle) for pin in pins):
        from fenolite.dsl.rails import check_net_like

        for pin in pins:
            if isinstance(pin, Interface | PortHandle):
                check_net_like(net, pin)
    for pin in pins:
        if isinstance(pin, (PortNet, PortHandle, Interface)):
            join(first, cast(Net, as_net(pin, what="connect()")))
            continue
        if not isinstance(pin, PinHandle):
            raise DslError(f"connect() takes pins such as part['1'], not {pin!r}")
        current = pin.part.connections.get(pin.designator)
        if isinstance(current, PortNet) and current.port.owner is pin.part and not same_net(current, first):
            join(first, current)  # a pin of a device port (change c0252): the port net joins the net
            current = first
        if current is not None and not same_net(current, first):
            raise DslError(
                f"pin {pin.part.label} {pin.designator} is already on net {current.name}; "
                f"cannot join {first.name}"
            )
        if pin.designator in pin.part.no_connects:
            raise DslError(
                f"pin {pin.part.label} {pin.designator} is marked as not connected; cannot join {first.name}"
            )
        if current is None:
            pin.part.connections[pin.designator] = first
        design = pin.part.design
        if design is not None:
            design.register_net(first)
    return first


def no_connect(*pins: PinHandle) -> None:
    """Mark each pin as intentionally unconnected; a designator that is on a net is refused.

    The designators are kept as written in ``Part.no_connects``; a build resolves them to pin numbers.
    Nothing is marked when one argument is refused. ``Part.unused_no_connect()`` asks the build to mark the
    open pins of a part; the marks it resolves are marks of this kind, and no mark can be removed.
    """
    for pin in pins:
        if not isinstance(pin, PinHandle):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"no_connect() takes pins such as part['1'], not {pin!r}")
        net = pin.part.connections.get(pin.designator)
        if net is not None:
            raise DslError(
                f"pin {pin.part.label} {pin.designator} is on net {net.name}; cannot mark it as not connected"
            )
    for pin in pins:
        pin.part.no_connects.add(pin.designator)


__all__ = [
    "FIELD_JUSTIFY",
    "FIELD_LAYERS",
    "FIELD_NAMES",
    "FIELD_SIDES",
    "NAME",
    "PREFIX",
    "FieldRequest",
    "PAD_ZONE_CONNECTIONS",
    "PadZoneRequest",
    "Net",
    "Part",
    "PinHandle",
    "Placement",
    "Request",
    "Side",
    "catalog_prefix",
    "check_name",
    "connect",
    "no_connect",
]
