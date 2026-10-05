# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist that ``kicad-cli sch export netlist --format kicadsexpr`` writes, read as components and
nets (capability ``kicad-schematic``, "Netlist export reading"; change c0063).

Facts: ``docs/formats/kicad/schematic.md``, "Netlist export" (S-0020; observed on 9.0.9 and 10.0.6). Only
``components`` and ``nets`` are read. The sections ``design``, ``libparts``, ``libraries``, ``groups`` and
``variants``, and the children ``code``, ``pinfunction``, ``sheetpath``, ``tstamps`` and ``units``, carry a
date, paths of the run, numbering or a spelling that differs between the majors, so none of them reaches
the result. ``KicadNetlist`` is also the type of Fenolite's own netlist of a generated sheet
(``sch_netlist``), and ``differences`` compares two of them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.backends.kicad.schlayout import natural_key
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-NETLIST-SHAPE",))
"""``KICAD-VERIFIED``: ``H-K-NETLIST-SHAPE`` holds on 9.0.9 and 10.0.6 (c0063 task 8.2)."""
ROOT = "export"
NO_CONNECT_SUFFIX = "+no_connect"
"""What KiCad appends to the ``pintype`` of a pin under a no-connect flag."""
_EMPTY: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class NetNode:
    """A pin on a net: the reference of its component, the pin number and KiCad's ``pintype``."""

    ref: str
    pin: str
    pintype: str = ""

    @property
    def element(self) -> str:
        """``REF-PIN``, the element name of the assignment compare."""
        return f"{self.ref}-{self.pin}"


@dataclass(frozen=True, slots=True)
class NetlistNet:
    """A net: its name, its net class (``""`` when the source does not know it) and its nodes, sorted by
    reference and pin."""

    name: str
    netclass: str = ""
    nodes: tuple[NetNode, ...] = ()


@dataclass(frozen=True, slots=True)
class NetComponent:
    """A component: reference, value, footprint, and its fields by name (``Reference`` and ``Value`` are
    not among them)."""

    ref: str
    value: str = ""
    footprint: str = ""
    properties: Mapping[str, str] = field(default_factory=lambda: _EMPTY, hash=False)
    """Python 3.11 refuses an unhashable default, so the empty mapping comes from a factory."""


@dataclass(frozen=True, slots=True)
class KicadNetlist:
    """Components in the natural order of their references and nets by name."""

    components: tuple[NetComponent, ...]
    nets: tuple[NetlistNet, ...]


def node_key(node: NetNode) -> tuple[object, ...]:
    return (natural_key(node.ref), natural_key(node.pin))


def build_netlist(components: Iterable[NetComponent], nets: Iterable[NetlistNet]) -> KicadNetlist:
    """A netlist in the one order of this module: components by the natural order of the reference, nets
    by name, the nodes of a net by reference and pin. Nets of one name are joined, and a net without a
    node is left out."""
    joined: dict[str, tuple[str, dict[tuple[str, str], NetNode]]] = {}
    for net in nets:
        netclass, nodes = joined.setdefault(net.name, (net.netclass, {}))
        for node in net.nodes:
            nodes.setdefault((node.ref, node.pin), node)
        joined[net.name] = (netclass or net.netclass, nodes)
    return KicadNetlist(
        tuple(sorted(components, key=lambda c: natural_key(c.ref))),
        tuple(
            NetlistNet(name, netclass, tuple(sorted(nodes.values(), key=node_key)))
            for name, (netclass, nodes) in sorted(joined.items())
            if nodes
        ),
    )


def _text(node: Node, head: str) -> str | None:
    child = node.find(head)
    atoms = child.atoms() if child is not None else ()
    return atoms[0].value if atoms else None


def _required(node: Node, head: str, file: str) -> str:
    value = _text(node, head)
    if value is None:
        raise FormatError(f"a {node.name} without a {head}", file=file, locator=f"/{ROOT}/{node.name}")
    return value


def _component(comp: Node, file: str) -> NetComponent:
    fields: dict[str, str] = {}
    listed = comp.find("fields")
    for item in listed.nodes("field") if listed is not None else ():
        name = _text(item, "name")
        if name is None:
            continue
        atoms = item.atoms()
        fields.setdefault(name, atoms[0].value if atoms else "")
    return NetComponent(
        _required(comp, "ref", file),
        _text(comp, "value") or "",
        _text(comp, "footprint") or "",
        MappingProxyType(fields),
    )


def _net(net: Node, file: str) -> NetlistNet:
    nodes = tuple(
        NetNode(_required(node, "ref", file), _required(node, "pin", file), _text(node, "pintype") or "")
        for node in net.nodes("node")
    )
    return NetlistNet(_required(net, "name", file), _text(net, "class") or "", nodes)


def read_netlist(text: str, *, file: str = "") -> KicadNetlist:
    """The components and nets of a KiCad netlist export. ``FormatError`` for a text that is no
    S-expression, for a root other than ``export`` and for a missing ``components`` or ``nets``."""
    root = parse(text, file=file)
    if root.name != ROOT:
        raise FormatError(f"not a KiCad netlist: the root is {root.name!r}, not {ROOT!r}", file=file)
    components, nets = root.find("components"), root.find("nets")
    for head, found in (("components", components), ("nets", nets)):
        if found is None:
            raise FormatError(f"a KiCad netlist without {head!r}", file=file, locator=f"/{ROOT}")
    assert components is not None and nets is not None
    return build_netlist(
        (_component(comp, file) for comp in components.nodes("comp")),
        (_net(net, file) for net in nets.nodes("net")),
    )


def differences(
    a: KicadNetlist, b: KicadNetlist, *, pintypes: bool = True, netclasses: bool = False
) -> tuple[str, ...]:
    """What differs between two netlists, one line each, sorted; ``()`` when they are equal.

    A component or a net on one side only, a value or a footprint that differs, a node on one side only
    and, with ``pintypes``, a node whose ``pintype`` differs; with ``netclasses`` also a net class that
    differs. The fields of a component are not compared. ``a`` is "the first" and ``b`` "the second".
    """
    found: list[str] = []
    comps_a, comps_b = ({c.ref: c for c in side.components} for side in (a, b))
    for ref in comps_a.keys() | comps_b.keys():
        first, second = comps_a.get(ref), comps_b.get(ref)
        if first is None or second is None:
            found.append(f"component {ref}: only in the {'first' if second is None else 'second'}")
            continue
        for what, one, other in (
            ("value", first.value, second.value),
            ("footprint", first.footprint, second.footprint),
        ):
            if one != other:
                found.append(f"component {ref}: {what} {one!r} in the first and {other!r} in the second")
    nets_a, nets_b = ({n.name: n for n in side.nets} for side in (a, b))
    for name in nets_a.keys() | nets_b.keys():
        first_net, second_net = nets_a.get(name), nets_b.get(name)
        if first_net is None or second_net is None:
            found.append(f"net {name}: only in the {'first' if second_net is None else 'second'}")
            continue
        if netclasses and first_net.netclass != second_net.netclass:
            found.append(
                f"net {name}: class {first_net.netclass!r} in the first and {second_net.netclass!r} in the "
                "second"
            )
        nodes_a, nodes_b = ({n.element: n for n in net.nodes} for net in (first_net, second_net))
        for element in nodes_a.keys() | nodes_b.keys():
            one_node, other_node = nodes_a.get(element), nodes_b.get(element)
            if one_node is None or other_node is None:
                side = "first" if other_node is None else "second"
                found.append(f"net {name}: {element} only in the {side}")
            elif pintypes and one_node.pintype != other_node.pintype:
                found.append(
                    f"net {name}: {element} is {one_node.pintype!r} in the first and "
                    f"{other_node.pintype!r} in the second"
                )
    return tuple(sorted(found))


__all__ = [
    "EVIDENCE",
    "NO_CONNECT_SUFFIX",
    "KicadNetlist",
    "NetComponent",
    "NetNode",
    "NetlistNet",
    "build_netlist",
    "differences",
    "node_key",
    "read_netlist",
]
