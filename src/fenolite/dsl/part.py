# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts, nets, pins and placements of the DSL (``docs/dsl.md``, "API")."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fenolite.core.coords import Point
from fenolite.core.units import Udeg
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.module import Container

Side = Literal["top", "bottom"]
NAME = re.compile(r"[A-Za-z0-9_.+-]+")
"""Module names and refs."""


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


@dataclass(frozen=True)
class PinHandle:
    """One designator of one part, as written (a pin number or a pin name)."""

    part: Part
    designator: str


class Part:
    """A component: reference, symbol lib id, optional footprint lib id and value."""

    def __init__(self, ref: str, lib_id: str, footprint: str | None = None, value: str = "") -> None:
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
        self.parent: Container | None = None
        self.request: Request | None = None
        self.connections: dict[str, Net] = {}

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
        pin.part.connections[pin.designator] = net
        design = pin.part.design
        if design is not None:
            design.register_net(net)
    return net


__all__ = ["NAME", "Net", "Part", "PinHandle", "Placement", "Request", "Side", "check_name", "connect"]
