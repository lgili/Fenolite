# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups of nets (``docs/dsl.md``, "Interfaces"): kept in the model, never lowered to KiCad.

``Harness`` (change c0037) is lowered by the Altium build only. ``I2C``, ``SPI``, ``UART`` and ``USB2``
(change c0073) are buses with fixed roles; ``attach`` joins the pins of one part to them by role.

Change c0252 gives interfaces parameters (``PARAMETERS``: exact c0246 ranges, each ``alias``, ``sum``,
``bound`` or ``link``), a reference rail and the classes ``Rail`` (``Power`` is another name of it),
``Ground`` and ``Logic``; ``fenolite.dsl.rails`` connects whole interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net, Part, PinHandle, connect
from fenolite.dsl.quantity import Quantity, Range

if TYPE_CHECKING:
    from fenolite.dsl.portnets import PortHandle

WHERE: tuple[str, ...] = ("out", "in", "inout", "design")
"""Where a parameter may be set: on a port of each direction, or on the design interface."""


@dataclass(frozen=True, slots=True)
class Parameter:
    """One row of ``PARAMETERS``: its semantics (``alias``, ``sum``, ``bound`` or ``link``), the c0246 unit
    name of its value (empty for a link) and where it may be set (``WHERE``)."""

    semantics: str
    unit: str
    where: frozenset[str]


def _row(semantics: str, unit: str, *where: str) -> Parameter:
    return Parameter(semantics, unit, frozenset(where))


_LOGIC: Mapping[str, Parameter] = {
    "abs_max": _row("bound", "volt", "out", "in", "inout"),
    "input_high_min": _row("bound", "volt", "in", "inout"),
    "input_low_max": _row("bound", "volt", "in", "inout"),
    "output_high_min": _row("bound", "volt", "out", "inout"),
    "output_low_max": _row("bound", "volt", "out", "inout"),
    "output_current_max": _row("bound", "ampere", "out", "inout"),
    "reference": _row("link", "", *WHERE),
}
PARAMETERS: Mapping[str, Mapping[str, Parameter]] = MappingProxyType(
    {
        "power": MappingProxyType(
            {
                "voltage": _row("alias", "volt", *WHERE),
                "current": _row("sum", "ampere", "out", "in"),
            }
        ),
        "ground": MappingProxyType({}),
        "logic": MappingProxyType(_LOGIC),
        "i2c": MappingProxyType({**_LOGIC, "pullup": _row("bound", "ohm", "in", "inout", "design")}),
        "spi": MappingProxyType(_LOGIC),
        "uart": MappingProxyType(_LOGIC),
        "usb2": MappingProxyType(_LOGIC),
    }
)
"""Kind → its closed parameter table (``docs/dsl.md``, "Interface parameters"; change c0252). ``reference`` is
given as its own keyword (``reference=``), never as a value; every other parameter takes a c0246 ``Range``
or ``Quantity`` of its unit."""


def check_param(kind: str, where: str, name: str, value: object, what: str) -> Range:
    """``value`` as the range of parameter ``name`` of ``kind`` set ``where`` (``WHERE``); ``DslError`` naming
    ``what`` and the parameter when the table does not allow it there, or for a value of another unit."""
    table = PARAMETERS.get(kind, {})
    row = table.get(name)
    if row is None or row.semantics == "link":
        taken = ", ".join(key for key, found in table.items() if found.semantics != "link") or "none"
        raise DslError(f"{what}: a {kind} interface has no parameter {name!r}; it takes {taken}")
    if where not in row.where:
        if row.semantics == "sum" and where == "inout":
            raise DslError(
                f"{what}: {name} is stated by a port that draws or sources it; say whether this port draws "
                f'or sources current with direction="in" or direction="out" (a pass-through port states none)'
            )
        if where == "design":
            raise DslError(f"{what}: {name} is set on ports only, not on the design interface")
        raise DslError(f"{what}: {name} is not set on an {where} {kind} port")
    if isinstance(value, Quantity):
        value = value.as_range()
    if not isinstance(value, Range):
        raise DslError(f"{what}: {name} takes a Range or a Quantity in {row.unit}, not {value!r}")
    if value.unit != row.unit:
        raise DslError(f"{what}: {name} is a value in {row.unit}, not in {value.unit} ({value.text()})")
    return value


def check_params(kind: str, where: str, params: Mapping[str, object], what: str) -> dict[str, Range]:
    """Every parameter of ``params`` checked by ``check_param``, by name; ``None`` values left out."""
    return {
        name: check_param(kind, where, name, value, what)
        for name, value in sorted(params.items())
        if value is not None
    }


def check_reference(value: object, what: str) -> Interface | PortHandle | None:
    """``value`` as a reference rail: ``None``, a ``Rail`` (a ``power`` interface) or a ``power`` port
    handle; anything else raises ``DslError``."""
    from fenolite.dsl.portnets import PortHandle

    if value is None:
        return None
    if isinstance(value, Interface | PortHandle) and value.kind == "power":
        return value
    raise DslError(f"{what}: reference is a Rail or a power port handle, not {value!r}")


class Interface:
    """A typed bundle of nets: role → net; with the parameters, the reference rail and the sharing flag of
    change c0252."""

    def __init__(self, name: str, kind: str, members: Mapping[str, Net]) -> None:
        if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"an interface name must be a non-empty string, not {name!r}")
        if not isinstance(kind, str) or not kind:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"interface {name}: kind must be a non-empty string")
        for role, net in members.items():
            if not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"interface {name}: member {role!r} is not a Net")
        self.name = name
        self.kind = kind
        self.members = dict(members)
        self.params: dict[str, Range] = {}
        self.reference: Interface | PortHandle | None = None
        self.shared = False

    def main(self) -> Net | None:
        """The member a net-like interface stands for (``hv``, ``gnd``, ``io``), or ``None``."""
        from fenolite.dsl.portnets import MAIN_MEMBERS

        found = MAIN_MEMBERS.get(self.kind)
        return None if found is None else self.members.get(found)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class Rail(Interface):
    """A supply rail (change c0252): the ``hv`` net and, when given, the ``lv`` net; the default name is
    ``<hv>/<lv>``, or ``<hv>``. ``voltage`` is the declared operating range (a c0246 range or quantity of
    volts), ``shared`` lets several sources drive the rail. ``Power`` is another name of this class, and a
    rail without parameters gives the model of ``Power`` byte for byte."""

    def __init__(
        self,
        hv: Net,
        lv: Net | None = None,
        *,
        name: str | None = None,
        voltage: Range | Quantity | None = None,
        shared: bool = False,
        **params: object,
    ) -> None:
        members = {"hv": hv} if lv is None else {"hv": hv, "lv": lv}
        default = ""
        if isinstance(hv, Net) and (lv is None or isinstance(lv, Net)):  # pyright: ignore[reportUnnecessaryIsInstance]
            default = hv.name if lv is None else f"{hv.name}/{lv.name}"
        super().__init__(name or default, "power", members)
        if not isinstance(shared, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"rail {self.name}: shared must be a bool, not {shared!r}")
        self.params = check_params("power", "design", {**params, "voltage": voltage}, f"rail {self.name}")
        self.shared = shared


Power = Rail
"""The name of ``Rail`` before change c0252, kept: ``Power(vin, gnd)`` gives the same model."""


class Ground(Interface):
    """A ground (change c0252): the member ``gnd``; the default name is the net's name."""

    def __init__(self, gnd: Net, *, name: str | None = None) -> None:
        default = gnd.name if isinstance(gnd, Net) else ""  # pyright: ignore[reportUnnecessaryIsInstance]
        super().__init__(name or default, "ground", {"gnd": gnd})


class Logic(Interface):
    """A logic line (change c0252): the member ``io`` and the rail its levels refer to (``reference``, a
    ``Rail`` or a power port handle); the default name is the net's name. Thresholds are stated on ports."""

    def __init__(self, io: Net, *, name: str | None = None, reference: object = None) -> None:
        default = io.name if isinstance(io, Net) else ""  # pyright: ignore[reportUnnecessaryIsInstance]
        super().__init__(name or default, "logic", {"io": io})
        self.reference = check_reference(reference, f"logic {self.name}")


class DiffPair(Interface):
    """A differential pair: ``p`` and ``n`` nets; the default name is ``<p>/<n>``."""

    def __init__(self, p: Net, n: Net, *, name: str | None = None) -> None:
        super().__init__(name or f"{p.name}/{n.name}", "diff_pair", {"p": p, "n": n})


class Harness(Interface):
    """A named group of nets with different names, such as SPI with MOSI, MISO and SCK (change c0037).

    ``name`` is the harness type name and has no default; ``members`` maps an entry name to its net. The
    order of the entries carries no meaning: a backend that needs one sorts the entry names. The KiCad
    build keeps a harness in the model only; the Altium build draws it as a signal harness."""

    def __init__(self, name: str, members: Mapping[str, Net]) -> None:
        if isinstance(name, str) and name and not members:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"harness {name}: a harness needs at least one entry")
        for entry in members:
            if not isinstance(entry, str) or not entry:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"harness {name}: an entry name must be a non-empty string, not {entry!r}")
        super().__init__(name, "harness", members)


Pin = PinHandle | str | int
"""A pin argument of ``attach``: a pin handle of the part, or a designator of it."""


class Bus(Interface):
    """The base of the buses with fixed roles: distinct nets, a default name, and ``attach`` by role."""

    def __init__(
        self, kind: str, members: Mapping[str, Net], name: str | None, reference: object = None
    ) -> None:
        seen: dict[str, str] = {}
        for role, net in members.items():
            if not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"{kind} interface: {role} must be a Net, not {net!r}")
            if net.name in seen:
                raise DslError(
                    f"{kind} interface: net {net.name} is given for {seen[net.name]} and for {role}"
                )
            seen[net.name] = role
        first, second = list(members.values())[:2]
        super().__init__(name or f"{first.name}/{second.name}", kind, members)
        self.reference = check_reference(reference, f"{kind} interface {self.name}")

    def _join(self, part: Part, pins: Sequence[tuple[str, Pin]]) -> None:
        """Connect each ``(role, pin)`` to the net of the role; nothing is connected when one is refused."""
        if not isinstance(part, Part):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"interface {self.name}: attach() takes a Part first, not {part!r}")
        resolved: list[tuple[Net, PinHandle]] = []
        taken: dict[str, Net] = {}
        for role, pin in pins:
            net = self.members.get(role)
            if net is None:
                raise DslError(f"interface {self.name} has no {role} net; it cannot take a {role} pin")
            if isinstance(pin, PinHandle):
                if pin.part is not part:
                    raise DslError(
                        f"interface {self.name}: the {role} pin belongs to {pin.part.ref}, not {part.ref}"
                    )
                handle = pin
            else:
                handle = part[pin]
            current = part.connections.get(handle.designator, net)
            if current is not net or handle.designator in part.no_connects:
                connect(net, handle)  # refused: connect raises with its own message
            if taken.setdefault(handle.designator, net) is not net:
                raise DslError(
                    f"interface {self.name}: pin {part.ref} {handle.designator} is given for two nets"
                )
            resolved.append((net, handle))
        for net, handle in resolved:
            connect(net, handle)


class I2C(Bus):
    """An I2C bus: ``sda`` and ``scl`` nets; the default name is ``<sda>/<scl>``."""

    def __init__(
        self,
        sda: Net,
        scl: Net,
        *,
        name: str | None = None,
        reference: object = None,
        pullup: Range | Quantity | None = None,
    ) -> None:
        super().__init__("i2c", {"sda": sda, "scl": scl}, name, reference)
        self.params = check_params("i2c", "design", {"pullup": pullup}, f"i2c interface {self.name}")

    def attach(self, part: Part, *, sda: Pin, scl: Pin) -> None:
        """Join the SDA and SCL pins of ``part`` to the bus."""
        self._join(part, (("sda", sda), ("scl", scl)))


class SPI(Bus):
    """An SPI bus: ``sck``, ``mosi``, ``miso`` and one ``cs<i>`` net per chip select, in the order given."""

    def __init__(
        self,
        sck: Net,
        mosi: Net,
        miso: Net,
        *,
        cs: Sequence[Net] = (),
        name: str | None = None,
        reference: object = None,
    ) -> None:
        if isinstance(cs, Net) or not isinstance(cs, Sequence):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"spi interface: cs is a sequence of nets, not {cs!r}")
        members = {"sck": sck, "mosi": mosi, "miso": miso}
        members.update({f"cs{index}": net for index, net in enumerate(cs)})
        super().__init__("spi", members, name, reference)
        self.selects = len(cs)

    def attach(
        self,
        part: Part,
        *,
        role: str,
        sck: Pin,
        mosi: Pin,
        miso: Pin,
        cs: Pin | Sequence[Pin] | None = None,
        cs_index: int | None = None,
    ) -> None:
        """Join the pins of a ``controller`` (one ``cs`` pin per chip-select net, in order) or of a
        ``peripheral`` (one ``cs`` pin and the index of its chip-select net). MOSI joins MOSI."""
        pins: list[tuple[str, Pin]] = [("sck", sck), ("mosi", mosi), ("miso", miso)]
        if role == "controller":
            given = () if cs is None else cs
            if cs_index is not None or isinstance(given, PinHandle | str | int):
                raise DslError(
                    f"interface {self.name}: a controller takes cs as a sequence of pins and no cs_index"
                )
            chosen = list(cast("Sequence[Pin]", given))
            if len(chosen) != self.selects:
                raise DslError(
                    f"interface {self.name}: a controller takes {self.selects} cs pin(s), not {len(chosen)}"
                )
            pins += [(f"cs{index}", pin) for index, pin in enumerate(chosen)]
        elif role == "peripheral":
            if isinstance(cs, bool) or not isinstance(cs, PinHandle | str | int):
                raise DslError(f"interface {self.name}: a peripheral takes one cs pin, not {cs!r}")
            if isinstance(cs_index, bool) or not isinstance(cs_index, int):
                raise DslError(f"interface {self.name}: a peripheral takes cs_index, the index of its cs net")
            if not 0 <= cs_index < self.selects:
                raise DslError(
                    f"interface {self.name}: cs_index {cs_index} is outside its {self.selects} cs net(s)"
                )
            pins.append((f"cs{cs_index}", cs))
        else:
            raise DslError(f"interface {self.name}: role is 'controller' or 'peripheral', not {role!r}")
        self._join(part, pins)


class UART(Bus):
    """A UART link: ``tx`` and ``rx`` nets, named from device A (side ``a``)."""

    def __init__(self, tx: Net, rx: Net, *, name: str | None = None, reference: object = None) -> None:
        super().__init__("uart", {"tx": tx, "rx": rx}, name, reference)

    def attach(self, part: Part, *, side: str, tx: Pin, rx: Pin) -> None:
        """Join the TX and RX pins of ``part``: straight on side ``a``, crossed on side ``b``."""
        if side == "a":
            self._join(part, (("tx", tx), ("rx", rx)))
        elif side == "b":
            self._join(part, (("rx", tx), ("tx", rx)))
        else:
            raise DslError(f"interface {self.name}: side is 'a' or 'b', not {side!r}")


class USB2(Bus):
    """A USB 2.0 port: ``dp`` and ``dn`` nets, and ``vbus`` and ``gnd`` when given."""

    def __init__(
        self,
        dp: Net,
        dn: Net,
        *,
        vbus: Net | None = None,
        gnd: Net | None = None,
        name: str | None = None,
        reference: object = None,
    ) -> None:
        members = {"dp": dp, "dn": dn}
        if vbus is not None:
            members["vbus"] = vbus
        if gnd is not None:
            members["gnd"] = gnd
        super().__init__("usb2", members, name, reference)

    def attach(
        self, part: Part, *, dp: Pin, dn: Pin, vbus: Pin | None = None, gnd: Pin | None = None
    ) -> None:
        """Join the data pins of ``part``, and its VBUS and GND pins when given."""
        pins: list[tuple[str, Pin]] = [("dp", dp), ("dn", dn)]
        if vbus is not None:
            pins.append(("vbus", vbus))
        if gnd is not None:
            pins.append(("gnd", gnd))
        self._join(part, pins)


__all__ = [
    "I2C",
    "PARAMETERS",
    "SPI",
    "UART",
    "USB2",
    "WHERE",
    "Bus",
    "DiffPair",
    "Ground",
    "Harness",
    "Interface",
    "Logic",
    "Parameter",
    "Power",
    "Rail",
    "check_param",
    "check_params",
    "check_reference",
]
