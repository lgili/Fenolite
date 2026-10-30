# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Taking an interface from a part whose device offers it on several pin sets (change c0257,
``docs/pins.md``).

``part.take(I2C)`` returns a ``TakenInterface``: a port of the part (a ``PortHandle``) whose role nets exist
at once, so ``connect`` and ``pull_up`` work before the solve; only the part pins are pending. The build
gives every take one alternative of the device's ``[[options]]`` (``fenolite.lens.pins.solve``), records it
in the ``[pins]`` section of the design lock, and ``apply_choices`` joins the chosen pins to the role nets
before the design is lowered. ``to_model`` solves takes never applied against an empty lock.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from fenolite.catalog.devices import OPTION_ROLES
from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Part, PinHandle, check_name
from fenolite.dsl.portnets import PortHandle, PortNet
from fenolite.model.library import DeviceDef
from fenolite.model.pins import PinSolution, TakeRequest, read_locked, solve

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

KIND_CLASSES: Mapping[str, str] = MappingProxyType(
    {"I2C": "i2c", "SPI": "spi", "UART": "uart", "USB2": "usb2", "DiffPair": "diff_pair"}
)
"""Interface class name → the option kind ``take`` reads; ``"pin"`` (a single-pin function) is given as
text."""


class TakenNet(PortNet):
    """A role net of a take, named ``<part path>/<take key>/<role>`` unless joined to a named net."""

    @property
    def path(self) -> str:
        return f"{self.port.path}/{self.member}"


class TakenInterface(PortHandle):
    """An interface taken from a part (``part.take``): a port of the part whose ``kind`` is the option kind,
    whose members are the roles of the kind and whose pins the build chooses. ``take_key`` is the take key,
    ``key`` the lock key ``<part path>/<take key>``, ``option`` and ``pins`` the filters, and ``choice``
    (role → function) the applied choice, ``None`` before the solve or when it gave none."""

    def __init__(
        self, part: Part, take_key: str, kind: str, option: str | None, pins: Mapping[str, str]
    ) -> None:
        roles = OPTION_ROLES[kind]
        super().__init__(part, take_key, kind, "inout", False, roles)
        self.members = MappingProxyType({role: TakenNet(self, role) for role in roles})
        self.part = part
        self.take_key = take_key
        self.option = option
        self.pins: Mapping[str, str] = MappingProxyType(dict(sorted(pins.items())))
        self.choice: Mapping[str, str] | None = None
        self.applied = False

    @property
    def key(self) -> str:
        return f"{self.part.path}/{self.take_key}"

    def __repr__(self) -> str:
        return f"TakenInterface({self.key!r}, {self.kind!r})"


def _kind(kind: object) -> str:
    if isinstance(kind, str):
        if kind in OPTION_ROLES:
            return kind
    elif isinstance(kind, type):
        found = KIND_CLASSES.get(kind.__name__)
        if found is not None:
            return found
    raise DslError(
        "take() takes an interface class (I2C, SPI, UART, USB2, DiffPair) or a kind "
        f"({', '.join(OPTION_ROLES)}),"
        f" not {kind!r}"
    )


def take(
    part: Part,
    kind: object,
    *,
    name: str | None = None,
    option: str | None = None,
    pins: Mapping[str, object] | None = None,
) -> TakenInterface:
    """``part.take(kind, name=, option=, pins=)`` (``docs/pins.md``, "Taking an interface")."""
    found = _kind(kind)
    device = part.device
    if device is None:
        raise DslError(f"part {part.label}: take() needs a part placed from a device (device=...)")
    kinds = sorted({o.kind for o in device.options})
    if found not in kinds:
        raise DslError(
            f"part {part.label}: device {device.id} offers no {found} option; it offers "
            f"{', '.join(kinds) or 'no options'}"
        )
    takes = part_takes(part)
    if name is None:
        key = f"{found}#{sum(1 for t in takes if t.kind == found)}"
    else:
        key = check_name(name, f"part {part.label}: the take name")
        if any(t.take_key == key for t in takes):
            raise DslError(f"part {part.label}: a take is already named {key!r}")
        if key in part.ports or any(i.name == key for i in device.interfaces):
            raise DslError(f"part {part.label}: {key!r} is a port of the part; name the take otherwise")
    if option is not None and (not isinstance(option, str) or not option):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"part {part.label}: option is the name of an option, such as 'I2C1', not {option!r}")
    filters: dict[str, str] = {}
    if pins is not None:
        if not isinstance(pins, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(
                f"part {part.label}: pins maps a role to a pin, such as {{'tx': 'PB3'}}, not {pins!r}"
            )
        for role, pin in cast(Mapping[object, object], pins).items():
            if role not in OPTION_ROLES[found]:
                raise DslError(
                    f"part {part.label}: a {found} take has the roles {', '.join(OPTION_ROLES[found])}, "
                    f"not {role!r}"
                )
            if isinstance(pin, PinHandle):
                if pin.part is not part:
                    raise DslError(f"part {part.label}: the pin for {role} belongs to {pin.part.label}")
                pin = pin.designator
            if not isinstance(pin, str) or not pin:
                raise DslError(f"part {part.label}: the pin for {role} is a function name, not {pin!r}")
            filters[cast(str, role)] = pin
    made = TakenInterface(part, key, found, option, filters)
    part.ports[key] = made
    return made


def part_takes(part: Part) -> list[TakenInterface]:
    """The takes of ``part`` in script order."""
    return [port for port in part.ports.values() if isinstance(port, TakenInterface)]


def design_takes(design: Design) -> list[TakenInterface]:
    """The takes of ``design``, by part path then in script order."""
    return [t for path in sorted(design.parts) for t in part_takes(design.parts[path])]


def fixed_functions(part: Part) -> frozenset[str]:
    """The functions of ``part``'s device that a hand connection or a no-connect mark already uses."""
    device = part.device
    if device is None:
        return frozenset()
    used = {
        designator
        for designator, net in part.connections.items()
        if not (isinstance(net, TakenNet) and net.port.owner is part)
    }
    used |= set(part.no_connects)
    return frozenset(
        pin.function
        for pin in device.pins
        if pin.function in used or any(number in used for number in pin.pins)
    )


def apply_choices(design: Design, choices: Mapping[str, Mapping[str, str]]) -> None:
    """Join the chosen functions of each take (lock key → role → function) to its role nets, and mark every
    take of ``design`` applied; a take without a choice keeps its pins open."""
    for found in design_takes(design):
        if found.applied:
            continue
        found.applied = True
        choice = choices.get(found.key)
        if choice is None:
            continue
        found.choice = MappingProxyType(dict(sorted(choice.items())))
        for role, function in sorted(choice.items()):
            found.part.connections[function] = found.members[role]


def requests(design: Design) -> list[TakeRequest]:
    """The takes of ``design`` as requests of the solve (``fenolite.lens.pins``)."""
    return [
        TakeRequest(part=t.part.path, take=t.take_key, kind=t.kind, option=t.option, pins=t.pins)
        for t in design_takes(design)
    ]


def solve_takes(design: Design, locked: Mapping[str, object]) -> PinSolution:
    """The solve of the takes of ``design`` against the ``[pins]`` entries ``locked`` of a design lock."""
    takes = design_takes(design)
    devices = {t.part.path: cast(DeviceDef, t.part.device) for t in takes}
    fixed = {t.part.path: fixed_functions(t.part) for t in takes}
    entries = {
        key: cast(Mapping[str, object], value) for key, value in locked.items() if isinstance(value, Mapping)
    }
    return solve(requests(design), devices, fixed, read_locked(entries))


def apply_pending(design: Design) -> None:
    """Solve the takes not applied yet against an empty lock and apply the choices, as ``to_model``
    assigns refs against an empty lock when it is given none; the issues are the build's to report."""
    if pending(design):
        apply_choices(design, {c.key: c.pins for c in solve_takes(design, {}).choices})


def pending(design: Design) -> list[str]:
    """The lock keys of the takes of ``design`` not applied yet."""
    return [found.key for found in design_takes(design) if not found.applied]


def unused_takes(design: Design) -> list[str]:
    """The lock keys of the applied takes whose role nets reach no pin besides the take's own."""
    counts: dict[int, int] = {}
    for part in design.parts.values():
        for net in part.connections.values():
            counts[id(net.group if net.group is not None else net)] = (
                counts.get(id(net.group if net.group is not None else net), 0) + 1
            )
    found: list[str] = []
    for item in design_takes(design):
        if item.choice is None:
            continue
        if all(
            counts.get(id(net.group if net.group is not None else net), 0) <= 1
            for net in item.members.values()
        ):
            found.append(item.key)
    return found


__all__ = [
    "KIND_CLASSES",
    "TakenInterface",
    "TakenNet",
    "apply_choices",
    "apply_pending",
    "design_takes",
    "fixed_functions",
    "part_takes",
    "pending",
    "requests",
    "solve_takes",
    "take",
    "unused_takes",
]
