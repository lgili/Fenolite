# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Port nets of blocks and their binding (``docs/dsl.md``, "Port nets"; change c0251).

A port net is a ``Net`` without a name of its own. ``connect`` binds nets and port nets into groups; a
group holds at most one script-named net (a ``Net`` or a block-local net), whose name it takes. A group
without one takes the path of its preferred port member: an ``out`` port first, then the smallest path in
code-point order, so the name does not depend on the order of the calls. Joining two script-named nets
raises ``DslError``: Fenolite never merges named nets.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net
from fenolite.dsl.quantity import Range

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.module import Container
    from fenolite.dsl.part import Part

DIRECTIONS: tuple[str, ...] = ("in", "out", "inout")
"""The directions of a port."""


class Group:
    """Nets and port nets bound together by ``connect``: they are one net of the model."""

    __slots__ = ("members", "named")

    def __init__(self) -> None:
        self.members: list[Net] = []
        self.named: Net | None = None
        """The one script-named net of the group, or ``None``."""

    def preferred(self) -> PortNet:
        """The port member that names a group without a script-named net."""
        ports = [member for member in self.members if isinstance(member, PortNet)]
        return min(ports, key=lambda p: (p.port.direction != "out", p.path))

    def name(self) -> str:
        return self.named.name if self.named is not None else self.preferred().path


class PortNet(Net):
    """One member of a port: a net that takes the name of its group (``Group.name``)."""

    deferred = True

    def __init__(self, port: PortHandle, member: str) -> None:  # pyright: ignore[reportMissingSuperCall]
        # Net.__init__ is not called: the name is the group's, and it is not fixed yet
        self.port = port
        self.member = member
        self.design: Design | None = None
        self.netclass: str | None = None
        self.group: Group | None = Group()
        self.group.members.append(self)

    @property
    def path(self) -> str:
        """``<owner path>/<port>`` for a port of one member, ``<owner path>/<port>.<member>`` otherwise."""
        base = f"{self.port.owner_path}/{self.port.name}"
        return base if len(self.port.members) == 1 else f"{base}.{self.member}"

    @property
    def name(self) -> str:  # pyright: ignore[reportIncompatibleVariableOverride]
        return cast(Group, self.group).name()

    def __repr__(self) -> str:
        return f"PortNet({self.path!r})"


def group_of(net: Net) -> Group:
    """The group of ``net``; a script-named net without one gets a group of its own."""
    if net.group is None:
        net.group = Group()
        net.group.members.append(net)
        net.group.named = net
    return net.group


def same_net(a: Net, b: Net) -> bool:
    """Whether ``a`` and ``b`` are one net: the same object, or bound into one group."""
    return a is b or (a.group is not None and a.group is b.group)


def join(a: Net, b: Net) -> None:
    """Bind ``a`` and ``b`` into one group; two script-named nets in one group raise ``DslError``."""
    first, second = group_of(a), group_of(b)
    if first is second:
        return
    if first.named is not None and second.named is not None:
        port = next((m.path for m in (b, a, *first.members, *second.members) if isinstance(m, PortNet)), "?")
        raise DslError(
            f"connect(): the nets {first.named.name} and {second.named.name} would be joined through the "
            f"port {port}; Fenolite never merges two named nets"
        )
    if len(first.members) < len(second.members):
        first, second = second, first
    for member in second.members:
        member.group = first
        first.members.append(member)
    first.named = first.named or second.named


class PortHandle:
    """A port of a block instance, or of a device part (change c0252): its name, kind, direction and
    members (``b.port``). A port of one member, or whose kind names a main member, is net-like:
    ``connect`` takes it as that member. ``params``, ``reference``, ``share`` and ``requires`` are the
    parameters of change c0252 (``set``)."""

    _FIELDS = (
        "name",
        "kind",
        "direction",
        "optional",
        "owner",
        "members",
        "params",
        "reference",
        "share",
        "requires",
        "evidence",
    )

    def __init__(
        self,
        owner: Container | Part,
        name: str,
        kind: str,
        direction: str,
        optional: bool,
        members: tuple[str, ...],
    ) -> None:
        self.owner = owner
        self.name = name
        self.kind = kind
        self.direction = direction
        self.optional = optional
        self.members: Mapping[str, PortNet] = MappingProxyType({m: PortNet(self, m) for m in members})
        self.params: dict[str, Range] = {}
        self.reference: object = None
        """A ``Rail``, a power ``PortHandle``, or ``None``."""
        self.share = False
        self.requires: tuple[str, ...] = ()
        self.evidence = ""
        """The evidence label of the device record a device port comes from; empty for a block port."""

    def set(self, *, reference: object = None, share: bool | None = None, **params: object) -> PortHandle:
        """Set parameters of the port (``PARAMETERS`` of its kind, for its direction), its reference rail
        and its ``share`` flag; each parameter is set once. Returns the port."""
        from fenolite.dsl.interfaces import check_params, check_reference

        what = f"port {self.path}"
        for name, value in params.items():
            if name in self.params and value is not None:
                raise DslError(f"{what}: parameter {name} is set twice")
        found = check_params(self.kind, self.direction, params, what)
        if reference is not None:
            if self.reference is not None:
                raise DslError(f"{what}: reference is set twice")
            self.reference = check_reference(reference, what)
        if share is not None:
            if not isinstance(share, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"{what}: share must be a bool, not {share!r}")
            if share and (self.kind != "power" or self.direction != "out"):
                raise DslError(f"{what}: share is stated by an out power port")
            self.share = share
        self.params.update(found)
        return self

    @property
    def owner_path(self) -> str:
        return cast(str, getattr(self.owner, "path", ""))

    @property
    def path(self) -> str:
        return f"{self.owner_path}/{self.name}"

    def main(self) -> PortNet | None:
        """The member ``connect`` acts on: the only one, or the kind's main member (``MAIN_MEMBERS``)."""
        if len(self.members) == 1:
            return next(iter(self.members.values()))
        main = MAIN_MEMBERS.get(self.kind)
        return None if main is None else self.members.get(main)

    def __getitem__(self, member: str) -> PortNet:
        found = self.members.get(member)
        if found is None:
            raise DslError(f"port {self.path} has no member {member!r}; it has {', '.join(self.members)}")
        return found

    def __getattr__(self, member: str) -> PortNet:
        if member.startswith("_") or member in PortHandle._FIELDS:
            raise AttributeError(member)
        return self[member]

    def __repr__(self) -> str:
        return f"PortHandle({self.path!r}, {self.kind!r})"


MAIN_MEMBERS: Mapping[str, str] = MappingProxyType(
    {"power": "hv", "ground": "gnd", "logic": "io", "pin": "io"}
)
"""Kind → the member a net-like port or interface of several members stands for (change c0252); ``pin`` is a
single-pin take (change c0257)."""


def as_net(value: object, *, what: str) -> Net | None:
    """``value`` as a net when it is a ``Net``, a port net, a net-like port or a net-like interface (a
    ``Rail``, a ``Ground`` or a ``Logic``, change c0252); ``None`` for other values. A port or interface of
    several members without a main member raises ``DslError``."""
    from fenolite.dsl.interfaces import Interface

    if isinstance(value, Net):
        return value
    if isinstance(value, Interface):
        main = value.main()
        if main is None:
            raise DslError(
                f"{what}: the {value.kind} interface {value.name} has the members "
                f"{', '.join(value.members)}; connect it to an interface or a port of its kind, or name one "
                "of its nets"
            )
        return main
    if isinstance(value, PortHandle):
        main = value.main()
        if main is None:
            raise DslError(
                f"{what}: the port {value.path} has the members {', '.join(value.members)}; "
                f"name one, such as {value.path.rpartition('/')[2]}.{next(iter(value.members))}"
            )
        return main
    return None


def resolve(design: Design) -> None:
    """Register the name of every group of port nets of ``design``: a group with a script-named net
    registers that net, a group without one that holds a pin registers its preferred port net under
    its path. Called by ``to_model``; calling it again after more ``connect`` calls renames the groups."""
    from fenolite.dsl.block import Block

    for name in sorted(design.port_net_names):
        if isinstance(design.nets.get(name), PortNet):
            del design.nets[name]
    design.port_net_names.clear()
    pinned = {
        id(net.group)
        for part in design.parts.values()
        for net in part.connections.values()
        if net.group is not None
    }
    seen: set[int] = set()
    owners: list[tuple[str, Mapping[str, PortHandle]]] = [
        (path, module.ports) for path, module in design.modules.items() if isinstance(module, Block)
    ]
    owners += [(path, part.ports) for path, part in design.parts.items() if part.ports]  # c0252
    for _, ports in sorted(owners, key=lambda owner: owner[0]):
        for port in ports.values():
            for member in port.members.values():
                group = cast(Group, member.group)
                if id(group) in seen:
                    continue
                seen.add(id(group))
                if group.named is not None:
                    design.register_net(group.named)
                    continue
                if id(group) not in pinned:
                    continue
                preferred = group.preferred()
                name = preferred.path
                known = design.nets.get(name)
                if known is not None and not same_net(known, preferred):
                    raise DslError(
                        f"two distinct nets are named {name!r}: a net of the script and a port net"
                    )
                design.nets[name] = preferred
                design.port_net_names.add(name)


__all__ = [
    "DIRECTIONS",
    "MAIN_MEMBERS",
    "Group",
    "PortHandle",
    "PortNet",
    "as_net",
    "group_of",
    "join",
    "resolve",
    "same_net",
]
