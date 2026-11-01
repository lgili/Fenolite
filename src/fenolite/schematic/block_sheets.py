# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic of a block, as the backends read it (change c0269, ``docs/schematic.md``, "Block sheets").

``SheetGroup`` and ``BlockSchematic`` are the block-local groups that ``fenolite.dsl.block_schematics``
gives for each block instance: plain component paths, so a backend needs no DSL object. ``port_pins`` reads
the ports of the block instances of a circuit (change c0251) and gives each bound port member its **sheet
name**: ``<port>`` for a port of kind ``net`` and ``<port>_<member>`` otherwise. The same name is a KiCad
hierarchical label and sheet pin, and an Altium port and sheet entry. Nothing here reads a file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol


class _Module(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def path(self) -> str: ...
    @property
    def block(self) -> str: ...


class _Port(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def owner(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def direction(self) -> str: ...
    @property
    def members(self) -> Mapping[str, str]: ...


class _Circuit(Protocol):
    """What ``port_pins`` reads of a ``fenolite.model.circuit.Circuit`` (``schematic`` imports no model)."""

    @property
    def modules(self) -> Sequence[_Module]: ...
    @property
    def ports(self) -> Sequence[_Port]: ...


Flow = Literal["left-to-right", "top-to-bottom"]
FLOWS: tuple[str, ...] = ("left-to-right", "top-to-bottom")
SHAPES: Mapping[str, str] = MappingProxyType({"in": "input", "out": "output", "inout": "bidirectional"})
"""Port direction → the shape of its hierarchical label and sheet pin."""


@dataclass(frozen=True, slots=True)
class SheetGroup:
    """One block-local group of one instance: its key, its members (component paths, the anchor first),
    its title, its anchor, the key it follows and its flow."""

    key: str
    members: tuple[str, ...]
    title: str
    anchor: str | None = None
    after: str | None = None
    flow: Flow = "left-to-right"


@dataclass(frozen=True, slots=True)
class BlockSchematic:
    """The groups of one block instance, in their resolved order; empty when the block declares none."""

    path: str
    block: str
    groups: tuple[SheetGroup, ...] = ()


@dataclass(frozen=True, slots=True)
class PortPin:
    """One bound member of a port of a block instance: the instance path, the sheet name, the port, the
    member, the direction and the net id."""

    module: str
    name: str
    port: str
    member: str
    direction: str
    net: str

    @property
    def shape(self) -> str:
        return SHAPES.get(self.direction, "bidirectional")


def sheet_name(port: str, member: str, kind: str) -> str:
    """The sheet name of a port member: ``<port>`` for a port of kind ``net``, else ``<port>_<member>``."""
    return port if kind == "net" else f"{port}_{member}"


def port_pins(circuit: _Circuit) -> dict[str, tuple[PortPin, ...]]:
    """Per block instance path, its bound port members in port order (the model's, by name) and member
    order (by name). A port owned by a component (a device port) is not a block port."""
    paths = {module.id: module.path for module in circuit.modules if module.block}
    found: dict[str, list[PortPin]] = {}
    for port in circuit.ports:
        module = paths.get(port.owner)
        if module is None:
            continue
        for member, net in sorted(port.members.items()):
            found.setdefault(module, []).append(
                PortPin(
                    module, sheet_name(port.name, member, port.kind), port.name, member, port.direction, net
                )
            )
    return {module: tuple(pins) for module, pins in found.items()}


def split_merged(pins: Sequence[PortPin]) -> tuple[dict[str, PortPin], dict[str, tuple[PortPin, ...]]]:
    """The members of one instance whose net no other member binds (net id → member), and the nets that
    two members or more bind (net id → those members)."""
    by_net: dict[str, list[PortPin]] = {}
    for pin in pins:
        by_net.setdefault(pin.net, []).append(pin)
    single = {net: found[0] for net, found in by_net.items() if len(found) == 1}
    merged = {net: tuple(found) for net, found in by_net.items() if len(found) > 1}
    return single, merged


__all__ = [
    "FLOWS",
    "SHAPES",
    "BlockSchematic",
    "Flow",
    "PortPin",
    "SheetGroup",
    "port_pins",
    "sheet_name",
    "split_merged",
]
