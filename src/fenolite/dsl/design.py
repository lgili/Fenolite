# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The DSL design: its tree of modules and parts, its nets, classes, interfaces and board."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.module import Container, Module
from fenolite.dsl.part import NAME, Net, Part
from fenolite.dsl.units import as_nm

DESIGN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
"""A design name becomes the stem of the KiCad files."""
INNER_LAYERS: tuple[str, ...] = ("In1.Cu", "In2.Cu")
"""The inner copper layers of a four-layer board, top to bottom: the layers a plane can take."""


@dataclass(frozen=True)
class NetClassSpec:
    name: str
    clearance: Nm | None
    track_width: Nm | None
    via_diameter: Nm | None
    via_drill: Nm | None
    nets: tuple[Net, ...]


class Rules:
    """``design.rules``: net classes only (no custom-rule constructor in v0.1)."""

    def __init__(self, design: Design) -> None:
        self._design = design
        self.netclasses: dict[str, NetClassSpec] = {}

    def netclass(
        self,
        name: str,
        *,
        clearance: object = None,
        track_width: object = None,
        via_diameter: object = None,
        via_drill: object = None,
        nets: Iterable[Net] = (),
    ) -> None:
        """Declare one net class with lengths and its member nets."""
        if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"a net-class name must be a non-empty string, not {name!r}")
        if name in self.netclasses:
            raise DslError(f"net class {name!r} is declared twice")

        def length(value: object, what: str) -> Nm | None:
            return None if value is None else as_nm(value, name=f"{name}.{what}")

        members = tuple(nets)
        for net in members:
            if not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"net class {name}: {net!r} is not a Net")
            if net.netclass is not None and net.netclass != name:
                raise DslError(f"net {net.name} is already in class {net.netclass}; cannot join {name}")
        spec = NetClassSpec(
            name,
            length(clearance, "clearance"),
            length(track_width, "track_width"),
            length(via_diameter, "via_diameter"),
            length(via_drill, "via_drill"),
            members,
        )
        for net in members:
            self._design.register_net(net)
            net.netclass = name
        self.netclasses[name] = spec


class Design(Container):
    """A design; its name becomes the KiCad file stem."""

    def __init__(self, name: str) -> None:
        super().__init__()
        if not isinstance(name, str) or not DESIGN_NAME.fullmatch(name):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"design name {name!r} must match {DESIGN_NAME.pattern}")
        self.name = name
        self.rules = Rules(self)
        self.copper = 2
        self.planes: dict[str, str] = {}
        """``board(planes=…)``: inner layer name → net name, in layer order; empty by default."""
        self.size: tuple[Nm, Nm] | None = None
        self.parts: dict[str, Part] = {}
        self.modules: dict[str, Module] = {}
        self.nets: dict[str, Net] = {}
        self.interfaces: dict[str, Interface] = {}
        self.aliases: dict[str, str] = {}
        """``moved()`` aliases: new component path → old component path."""

    @property
    def design(self) -> Design:
        return self

    def board(
        self,
        width: object,
        height: object,
        copper: int = 2,
        planes: Mapping[str, Net | str] | None = None,
    ) -> None:
        """A rectangular board of ``width`` × ``height`` with 2 or 4 copper layers. An inner layer is a
        signal layer unless ``planes`` names it: ``planes={"In1.Cu": gnd}`` makes that layer an internal
        plane on that net (a ``Net`` or a net name). A plane holds one net; it is a build parameter, as
        ``copper`` is, and what a target does with it is its build's rule (``docs/dsl.md``)."""
        if self.size is not None:
            raise DslError("board() is called once")
        if copper not in (2, 4):
            raise DslError(f"copper must be 2 or 4, not {copper!r}")
        w, h = as_nm(width, name="width"), as_nm(height, name="height")
        if w <= 0 or h <= 0:
            raise DslError("the board width and height must be positive")
        declared = self._planes(copper, planes)
        self.size = (w, h)
        self.copper = copper
        self.planes = declared

    @staticmethod
    def _planes(copper: int, planes: object) -> dict[str, str]:
        if planes is None:
            return {}
        if not isinstance(planes, Mapping):
            raise DslError(f"planes must map an inner layer name to a net, not {planes!r}")
        found: dict[str, str] = {}
        for layer, net in planes.items():  # pyright: ignore[reportUnknownVariableType]
            if copper != 4:
                raise DslError(f"planes need copper=4: a board of {copper} copper layers has no inner layer")
            if layer not in INNER_LAYERS:
                names = " or ".join(INNER_LAYERS)
                raise DslError(f"a plane lies on an inner layer ({names}), not on {layer!r}")
            if isinstance(net, Net):
                found[layer] = net.name
            elif isinstance(net, str) and net and net == net.strip():
                found[layer] = net
            else:
                raise DslError(f"the plane on {layer} needs a Net or a net name, not {net!r}")
        return {layer: found[layer] for layer in INNER_LAYERS if layer in found}

    def moved(self, old: str, new: str) -> None:
        """Record that the part at component path ``new`` was at ``old`` in an earlier build, so a rebuild
        keeps its layout (``docs/lens.md``, "moved()")."""
        for what, path in (("old", old), ("new", new)):
            if not isinstance(path, str) or not all(NAME.fullmatch(p) for p in path.split("/")):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"moved(): {what} path {path!r} is not a component path")
        if old == new:
            raise DslError(f"moved(): old and new are both {old!r}")
        if new in self.aliases:
            raise DslError(f"moved(): {new!r} already has an alias ({self.aliases[new]!r})")
        if old in self.aliases.values():
            raise DslError(f"moved(): {old!r} is already the old path of an alias")
        self.aliases[new] = old

    # -- registration (called by add(), connect() and netclass())

    def register_net(self, net: Net) -> None:
        known = self.nets.get(net.name)
        if known is not None and known is not net:
            raise DslError(f"two distinct nets are named {net.name!r}")
        net.design = self
        self.nets[net.name] = net

    def register_interface(self, interface: Interface) -> None:
        known = self.interfaces.get(interface.name)
        if known is not None and known is not interface:
            raise DslError(f"interface {interface.name!r} is declared twice")
        for net in interface.members.values():
            self.register_net(net)
        self.interfaces[interface.name] = interface

    def register_tree(self, obj: Part | Module) -> None:
        if isinstance(obj, Part):
            if obj.path in self.parts:
                raise DslError(f"two components have the path {obj.path!r}")
            self.parts[obj.path] = obj
            for net in obj.connections.values():
                self.register_net(net)
            return
        if obj.path in self.modules:
            raise DslError(f"two modules have the path {obj.path!r}")
        self.modules[obj.path] = obj
        for child in obj.children:
            self.register_tree(child)
        for net in obj.pending_nets:
            self.register_net(net)
        for interface in obj.pending_interfaces:
            self.register_interface(interface)

    def __repr__(self) -> str:
        return f"Design({self.name!r})"


__all__ = ["DESIGN_NAME", "INNER_LAYERS", "Design", "NetClassSpec", "Rules"]
