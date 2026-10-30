# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rails, grounds and logic lines, and whole interfaces joined by ``connect`` (``docs/dsl.md``, "Connecting
interfaces"; change c0252).

``Rail``, ``Ground``, ``Logic`` and the parameter table ``PARAMETERS`` live in ``fenolite.dsl.interfaces``
and are re-exported here. This module holds the closed compatibility table and the interface form of
``connect``: when every argument is an interface or a port, each member joins the member of the same name
of every other argument, through c0251's port nets. Two UART ports cross ``tx`` and ``rx``. Nothing is
connected when one pair is refused.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import PARAMETERS, Ground, Interface, Logic, Power, Rail
from fenolite.dsl.part import Net
from fenolite.dsl.portnets import MAIN_MEMBERS, PortHandle, PortNet, as_net, join

NET_LIKE: frozenset[str] = frozenset(MAIN_MEMBERS)
"""The kinds a net joins through their main member: ``power``, ``ground`` and ``logic``."""
OPTIONAL_MEMBERS: Mapping[str, frozenset[str]] = MappingProxyType(
    {"power": frozenset({"lv"}), "usb2": frozenset({"vbus", "gnd"})}
)
"""The members that join only where every side has them; any other member is required."""
Item = Interface | PortHandle


def kind_of(value: object) -> str:
    """The kind of a ``connect`` argument: ``net`` for a ``Net``, a port net or a ``net`` port."""
    if isinstance(value, Interface | PortHandle):
        return value.kind
    return "net"


def label(value: object) -> str:
    """How an error names a ``connect`` argument: ``power port `buck1/VIN```, ``ground `GND```."""
    if isinstance(value, PortHandle):
        return f"{value.kind} port `{value.path}`"
    if isinstance(value, Interface):
        return f"{value.kind} `{value.name}`"
    if isinstance(value, PortNet):
        return f"net `{value.path}`"
    if isinstance(value, Net):
        return f"net `{value.name}`"
    return repr(value)


def compatibility(first: str, other: str) -> str | None:
    """The closed compatibility table (``design.md`` of c0252, decision 4): ``yes`` for equal kinds,
    ``main`` for a net and a ``power``, ``ground`` or ``logic`` interface or port, ``None`` otherwise."""
    if first == other:
        return "yes"
    if "net" in (first, other) and ({first, other} - {"net"}) <= NET_LIKE:
        return "main"
    return None


def _refused(first: object, other: object) -> DslError:
    return DslError(f"connect(): cannot connect {label(first)} to {label(other)}")


def _main(value: Item) -> Net:
    if isinstance(value, PortHandle):
        found: Net | None = value.main()
    else:
        found = value.main()
    if found is None:
        raise DslError(f"connect(): {label(value)} has no main member; connect it to one of its kind")
    return found


def check_net_like(first: object, other: Item) -> None:
    """``DslError`` unless ``other`` may join ``first`` in the net form of ``connect``: a compatible kind, and
    ``other`` net-like."""
    mode = compatibility(kind_of(first), other.kind)
    if mode is None:
        if isinstance(other, PortHandle) and other.main() is None:
            as_net(other, what=f"connect(): cannot connect {label(first)} to {label(other)}")
        raise _refused(first, other)
    if mode == "yes" and other.kind != "net" and other.kind not in NET_LIKE:
        raise _refused(first, other)


def _members(value: Item) -> Mapping[str, Net]:
    return value.members


def _same_kind_pairs(items: Sequence[Item]) -> list[tuple[Net, Net]]:
    kind = items[0].kind
    if kind == "uart":
        if len(items) != 2 or not all(isinstance(item, PortHandle) for item in items):
            bus = next((item for item in items if not isinstance(item, PortHandle)), None)
            if bus is not None:
                raise DslError(
                    f"connect(): the UART interface {bus.name} is named from device A, so its side is not "
                    "known; join each part with attach(part, side='a' or 'b', tx=..., rx=...)"
                )
            raise DslError("connect(): UART ports cross tx and rx, so connect() joins exactly two of them")
        first, second = (_members(item) for item in items)
        return [(first["tx"], second["rx"]), (first["rx"], second["tx"])]
    optional = OPTIONAL_MEMBERS.get(kind, frozenset())
    names: list[str] = []
    for item in items:
        names += [name for name in _members(item) if name not in names]
    pairs: list[tuple[Net, Net]] = []
    for name in names:
        holders = [item for item in items if name in _members(item)]
        if len(holders) < len(items) and name not in optional:
            lacking = next(item for item in items if name not in _members(item))
            more = " (an SPI joins SPIs with the same chip selects)" if kind == "spi" else ""
            raise DslError(
                f"connect(): {label(lacking)} has no member {name}, which {label(holders[0])} has{more}"
            )
        base = _members(holders[0])[name]
        pairs += [(base, _members(item)[name]) for item in holders[1:]]
    return pairs


def _check_groups(pairs: Sequence[tuple[Net, Net]]) -> None:
    """Refuse, before any join, a set of joins that would put two script-named nets into one group."""
    parent: dict[int, int] = {}
    named: dict[int, Net] = {}

    def key(net: Net) -> int:
        found = id(net.group) if net.group is not None else id(net)
        if found not in parent:
            parent[found] = found
            if net.group is not None and net.group.named is not None:
                named[found] = net.group.named
            elif net.group is None and not net.deferred:
                named[found] = net
        return found

    def root(found: int) -> int:
        while parent[found] != found:
            found = parent[found]
        return found

    for a, b in pairs:
        ra, rb = root(key(a)), root(key(b))
        if ra == rb:
            continue
        na, nb = named.get(ra), named.get(rb)
        if na is not None and nb is not None and na is not nb:
            raise DslError(
                f"connect(): the nets {na.name} and {nb.name} would be joined; Fenolite never merges two "
                "named nets"
            )
        parent[rb] = ra
        if na is None and nb is not None:
            named[ra] = nb


def connect_interfaces(items: Sequence[object]) -> Net:
    """The interface form of ``connect``: every item an ``Interface`` or a ``PortHandle``. Equal kinds join
    member by member (an optional member where every side has it), a net with a ``power``, ``ground`` or
    ``logic`` item through its main member; any other pair raises ``DslError`` and nothing is connected.
    Returns the first item's main member, or its first member."""
    found: list[Item] = []
    for item in items:
        if not isinstance(item, Interface | PortHandle):
            raise DslError(f"connect(): {item!r} is not an interface or a port")
        found.append(item)
    first = found[0]
    for other in found[1:]:
        if compatibility(first.kind, other.kind) is None:
            raise _refused(first, other)
    pairs: list[tuple[Net, Net]] = []
    if all(item.kind == first.kind for item in found):
        pairs = _same_kind_pairs(found)
    else:
        for other in found[1:]:
            if compatibility(first.kind, other.kind) == "main" or first.kind == "net":
                pairs.append((_main(first), _main(other)))
            else:
                pairs += _same_kind_pairs((first, other))
        if first.kind == "net":
            for left in found[1:]:
                for right in found[1:]:
                    if left is not right and compatibility(left.kind, right.kind) is None:
                        raise _refused(left, right)
    _check_groups(pairs)
    for a, b in pairs:
        join(a, b)
    main = first.main() if first.kind in NET_LIKE or len(first.members) == 1 else None
    if isinstance(first, PortHandle) and main is None and len(first.members) == 1:
        main = next(iter(first.members.values()))
    return main if main is not None else next(iter(_members(first).values()))


__all__ = [
    "NET_LIKE",
    "OPTIONAL_MEMBERS",
    "PARAMETERS",
    "Ground",
    "Logic",
    "Power",
    "Rail",
    "check_net_like",
    "compatibility",
    "connect_interfaces",
    "kind_of",
    "label",
]
