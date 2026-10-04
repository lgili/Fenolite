# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts, nets, pins and placements of the DSL (``docs/dsl.md``, "API")."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

from fenolite.core.coords import Point
from fenolite.core.units import Nm, Udeg
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.intents import PadRef
    from fenolite.dsl.module import Container

Side = Literal["top", "bottom"]
NAME = re.compile(r"[A-Za-z0-9_.+-]+")
"""Module names and refs."""
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


def check_name(value: object, what: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise DslError(f"{what} {value!r} must match {NAME.pattern}")
    return value


class Net:
    """A net, named globally and literally; a module-local net is named by the script."""

    def __init__(self, name: str) -> None:
        if not isinstance(name, str) or not name or name != name.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"a net name must be a non-empty string without surrounding spaces, not {name!r}")
        self.name = name
        self.design: Design | None = None
        self.netclass: str | None = None

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


@dataclass(frozen=True, slots=True)
class Request:
    """A placement as the script gave it, in the board-relative frame."""

    x: int
    y: int
    rotation: Udeg
    side: Side
    locked: bool


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


class Part:
    """A component: reference, symbol lib id, optional footprint lib id, value and user properties."""

    def __init__(
        self,
        ref: str,
        lib_id: str,
        footprint: str | None = None,
        value: str = "",
        *,
        properties: Mapping[str, str] | None = None,
    ) -> None:
        self.ref = check_name(ref, "ref")
        if not isinstance(lib_id, str) or not lib_id:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: lib_id must be a non-empty string")
        if footprint is not None and (not isinstance(footprint, str) or not footprint):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: footprint must be a non-empty string or None")
        if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {ref}: value must be a string")
        self.lib_id = lib_id
        self.footprint = footprint
        self.value = value
        self.properties: Mapping[str, str] = _properties(ref, properties)
        self.parent: Container | None = None
        self.request: Request | None = None
        self.field_requests: dict[str, FieldRequest] = {}
        """The field placement requests of ``field()``, by field name."""
        self.connections: dict[str, Net] = {}
        self.no_connects: set[str] = set()
        """Designators marked as intentionally unconnected, as written (``no_connect``)."""

    @property
    def path(self) -> str:
        from fenolite.dsl.module import Module

        if isinstance(self.parent, Module):
            return f"{self.parent.path}/{self.ref}"
        return self.ref

    @property
    def design(self) -> Design | None:
        parent = self.parent
        return None if parent is None else parent.design

    def __getitem__(self, designator: str | int) -> PinHandle:
        if isinstance(designator, bool) or not isinstance(designator, (str, int)):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.ref}: a designator is a pin number or name, not {designator!r}")
        text = str(designator)
        if not text:
            raise DslError(f"part {self.ref}: empty designator")
        return PinHandle(self, text)

    def pad(self, number: str | int, *, index: int | None = None) -> PadRef:
        """The pads of this part numbered ``number``, for a copper intent; ``index`` picks one of several
        pads sharing the number (the build takes the nearest otherwise)."""
        from fenolite.dsl.intents import pad_ref

        return pad_ref(self, number, index)

    def place(
        self,
        x: object,
        y: object,
        rot: int | str | float = 0,
        side: str = "top",
        locked: bool = False,
    ) -> None:
        """Request a placement in the board frame (origin at the outline's top-left corner, Y down)."""
        if self.request is not None:
            raise DslError(f"part {self.ref} is already placed")
        if side not in ("top", "bottom"):
            raise DslError(f"part {self.ref}: side must be 'top' or 'bottom', not {side!r}")
        if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"part {self.ref}: locked must be a bool")
        self.request = Request(as_nm(x, name="x"), as_nm(y, name="y"), as_udeg(rot, name="rot"), side, locked)

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
        what = f"part {self.ref}: field {name!r}"
        if name not in FIELD_NAMES:
            raise DslError(f"{what}: only {' and '.join(FIELD_NAMES)} can be placed")
        if name in self.field_requests:
            raise DslError(f"part {self.ref}: field {name} already has a placement request")
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

    def __repr__(self) -> str:
        return f"Part({self.ref!r}, {self.lib_id!r})"


def connect(net: Net, *pins: PinHandle) -> Net:
    """Join each pin to ``net``; one designator of one part on two nets is refused."""
    if not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"connect() needs a Net first, not {net!r}")
    for pin in pins:
        if not isinstance(pin, PinHandle):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"connect() takes pins such as part['1'], not {pin!r}")
        current = pin.part.connections.get(pin.designator)
        if current is not None and current is not net:
            raise DslError(
                f"pin {pin.part.ref} {pin.designator} is already on net {current.name}; "
                f"cannot join {net.name}"
            )
        if pin.designator in pin.part.no_connects:
            raise DslError(
                f"pin {pin.part.ref} {pin.designator} is marked as not connected; cannot join {net.name}"
            )
        pin.part.connections[pin.designator] = net
        design = pin.part.design
        if design is not None:
            design.register_net(net)
    return net


def no_connect(*pins: PinHandle) -> None:
    """Mark each pin as intentionally unconnected; a designator that is on a net is refused.

    The designators are kept as written in ``Part.no_connects``; a build resolves them to pin numbers.
    Nothing is marked when one argument is refused.
    """
    for pin in pins:
        if not isinstance(pin, PinHandle):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"no_connect() takes pins such as part['1'], not {pin!r}")
        net = pin.part.connections.get(pin.designator)
        if net is not None:
            raise DslError(
                f"pin {pin.part.ref} {pin.designator} is on net {net.name}; cannot mark it as not connected"
            )
    for pin in pins:
        pin.part.no_connects.add(pin.designator)


__all__ = [
    "FIELD_JUSTIFY",
    "FIELD_LAYERS",
    "FIELD_NAMES",
    "FIELD_SIDES",
    "NAME",
    "FieldRequest",
    "Net",
    "Part",
    "PinHandle",
    "Placement",
    "Request",
    "Side",
    "check_name",
    "connect",
    "no_connect",
]
