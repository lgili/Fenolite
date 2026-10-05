# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The DSL design: its tree of modules and parts, its nets, classes, interfaces and board."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, get_args

from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.module import Container, Module
from fenolite.dsl.part import NAME, Net, Part
from fenolite.dsl.select import ALL, Select
from fenolite.dsl.units import as_nm, as_nm2
from fenolite.model.board import IslandRemoval, ZoneConnection, ZoneSettings
from fenolite.model.rules import RuleKind, RuleSeverity, Selector

if TYPE_CHECKING:
    from fenolite.dsl.intents import Recorded

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


@dataclass(frozen=True)
class ZoneSpec:
    """One ``zone()`` call: the net name (``None`` for a zone without a net), the copper layers, the
    outline as board-relative ``(x, y)`` nanometres (``None`` for the board rectangle), and the settings."""

    name: str
    net: str | None
    layers: tuple[str, ...]
    outline: tuple[tuple[Nm, Nm], ...] | None
    priority: int
    settings: ZoneSettings
    locked: bool


ZONE_CONNECTIONS: tuple[str, ...] = get_args(ZoneConnection)
ZONE_ISLANDS: tuple[str, ...] = get_args(IslandRemoval)


MINIMUM_KINDS: tuple[RuleKind, ...] = (
    "clearance",
    "track_width",
    "via_diameter",
    "via_drill",
    "hole_size",
    "edge_clearance",
)
"""The keywords of ``design.rules.minimum()``: the first six rule kinds of the model. The other kinds are
declared with ``design.rules.rule()``."""


@dataclass(frozen=True)
class MinimumSpec:
    """One minimum of ``design.rules.minimum()``: a rule kind, the net class it holds for (``None`` for
    the whole board) and the least value in nanometres."""

    kind: RuleKind
    netclass: str | None
    min: Nm


RULE_KINDS: tuple[str, ...] = get_args(RuleKind)
RULE_SEVERITIES: tuple[str, ...] = get_args(RuleSeverity)
BINARY_KINDS: frozenset[str] = frozenset({"clearance", "creepage"})
"""The rule kinds that take a second selector (``between``)."""


@dataclass(frozen=True)
class RuleSpec:
    """One ``design.rules.rule()`` call: a rule of any model kind, with its selectors as model selectors
    and its limits in nanometres."""

    name: str
    kind: RuleKind
    where: Selector
    between: Selector | None
    layers: tuple[str, ...]
    min: Nm | None
    opt: Nm | None
    max: Nm | None
    severity: RuleSeverity
    priority: int


def _leaf_values(selector: Selector | None, op: str) -> list[str]:
    if selector is None:
        return []
    if selector.items:
        return [value for item in selector.items for value in _leaf_values(item, op)]
    return [selector.value] if selector.op == op else []


class Rules:
    """``design.rules``: net classes, design-rule minimums and rules (``docs/dsl.md``, "Design rules")."""

    def __init__(self, design: Design) -> None:
        self._design = design
        self.named: dict[str, RuleSpec] = {}
        """The rules of ``rule()`` by name, in call order."""
        self.netclasses: dict[str, NetClassSpec] = {}
        self.minimums: dict[tuple[RuleKind, str | None], MinimumSpec] = {}
        """Minimums by ``(kind, net class name or None)``, as declared by ``minimum()``."""

    def minimum(
        self,
        *,
        clearance: object = None,
        track_width: object = None,
        via_diameter: object = None,
        via_drill: object = None,
        hole_size: object = None,
        edge_clearance: object = None,
        netclass: str | None = None,
    ) -> None:
        """Declare design-rule minimums: one rule per given length, for the whole board, or for the nets
        of the declared class ``netclass``. The build writes them where the design-rule check of the
        target reads them; a class minimum governs over the board minimum of its kind."""
        if netclass is not None and netclass not in self.netclasses:
            raise DslError(
                f"minimum(): netclass {netclass!r} is not a declared net class; "
                "call design.rules.netclass() first"
            )
        scope = "the board" if netclass is None else f"net class {netclass}"
        given = (clearance, track_width, via_diameter, via_drill, hole_size, edge_clearance)
        found: list[MinimumSpec] = []
        for kind, value in zip(MINIMUM_KINDS, given, strict=True):
            if value is None:
                continue
            length = as_nm(value, name=f"minimum(): {kind}")
            if length <= 0:
                raise DslError(f"minimum(): {kind} must be above 0")
            if (kind, netclass) in self.minimums:
                raise DslError(f"minimum(): {kind} is declared twice for {scope}")
            found.append(MinimumSpec(kind, netclass, length))
        if not found:
            raise DslError("minimum(): give at least one length, for example clearance=mm(0.2)")
        for spec in found:
            self.minimums[(spec.kind, spec.netclass)] = spec

    def rule(
        self,
        name: str,
        kind: str,
        *,
        where: Select = ALL,
        between: Select | None = None,
        layers: tuple[str, ...] = (),
        min: object = None,  # noqa: A002  (the model's field name)
        opt: object = None,
        max: object = None,  # noqa: A002
        severity: str = "error",
        priority: int = 0,
    ) -> None:
        """Declare one design rule of any model kind. ``where`` selects the items (``fenolite.dsl.select``),
        ``between`` the second item of a ``clearance`` or ``creepage`` rule. Priority 0 is written first and
        governs least; among the others, 1 governs most. What depends on the target (the limits a kind
        takes, the majors that check it, globs, layer names) is judged when the rules are lowered."""
        if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"rule(): a rule name must be a non-empty string, not {name!r}")
        if name in self.named:
            raise DslError(f"rule(): the rule {name!r} is declared twice")
        if kind not in RULE_KINDS:
            raise DslError(f"rule() {name!r}: kind {kind!r} is not one of {', '.join(RULE_KINDS)}")
        if not isinstance(where, Select):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"rule() {name!r}: where must be a selector of fenolite.dsl.select, not {where!r}")
        if between is not None and not isinstance(between, Select):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"rule() {name!r}: between must be a selector of fenolite.dsl.select")
        if between is not None and kind not in BINARY_KINDS:
            raise DslError(
                f"rule() {name!r}: between is taken by clearance and creepage rules, not by {kind}"
            )
        if not isinstance(layers, tuple) or not all(isinstance(x, str) and x for x in layers):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"rule() {name!r}: layers must be a tuple of layer names, not {layers!r}")
        if severity not in RULE_SEVERITIES:
            raise DslError(
                f"rule() {name!r}: severity {severity!r} is not one of {', '.join(RULE_SEVERITIES)}"
            )
        if type(priority) is not int or priority < 0:
            raise DslError(f"rule() {name!r}: priority must be an integer of 0 or more, not {priority!r}")
        limits: dict[str, Nm | None] = {}
        for label, value in (("min", min), ("opt", opt), ("max", max)):
            limits[label] = None if value is None else as_nm(value, name=f"rule() {name!r}: {label}")
        given = [(label, value) for label, value in limits.items() if value is not None]
        if not given:
            raise DslError(f"rule() {name!r}: give at least one limit, for example min=mm(0.2)")
        if limits["min"] is not None and limits["min"] < 0:
            raise DslError(f"rule() {name!r}: min must not be negative")
        for label in ("opt", "max"):
            value = limits[label]
            if value is not None and value <= 0:
                raise DslError(f"rule() {name!r}: {label} must be above 0")
        if any(a > b for (_, a), (_, b) in zip(given, given[1:], strict=False)):
            raise DslError(f"rule() {name!r}: the limits must rise from min through opt to max")
        selector_a = where.to_model()
        selector_b = None if between is None else between.to_model()
        for class_name in (*_leaf_values(selector_a, "netclass"), *_leaf_values(selector_b, "netclass")):
            if "*" not in class_name and class_name != "Default" and class_name not in self.netclasses:
                raise DslError(
                    f"rule() {name!r}: netclass {class_name!r} is not a declared net class; "
                    "call design.rules.netclass() first"
                )
        self.named[name] = RuleSpec(
            name,
            cast(RuleKind, kind),
            selector_a,
            selector_b,
            layers,
            limits["min"],
            limits["opt"],
            limits["max"],
            cast(RuleSeverity, severity),
            priority,
        )

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
        self.footprints: dict[str, Footprint] = {}
        self.symbols: dict[str, object] = {}
        self.modules: dict[str, Module] = {}
        self.nets: dict[str, Net] = {}
        self.interfaces: dict[str, Interface] = {}
        self.aliases: dict[str, str] = {}
        """``moved()`` aliases: new component path → old component path."""
        self.copper_intents: dict[str, Recorded] = {}
        """Copper intents by key, as recorded by ``track()``, ``via()`` and ``stitch()``."""
        self.zones: dict[str, ZoneSpec] = {}
        """Copper zones by name, as declared by ``zone()``."""

    def add_footprint(self, footprint: Footprint) -> None:
        """Register a project-authored library footprint for backend builds (not model persistence)."""
        if not isinstance(footprint, Footprint):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"add_footprint() takes a Footprint, not {footprint!r}")
        if footprint.lib_id in self.footprints:
            raise DslError(f"footprint {footprint.lib_id!r} is registered twice")
        self.footprints[footprint.lib_id] = footprint

    def add(self, *objs: object) -> None:
        """Attach authored symbols explicitly, or attach ordinary design objects as usual."""
        from fenolite.dsl.symbol import Symbol

        regular: list[object] = []
        for obj in objs:
            if isinstance(obj, Symbol):
                if obj.lib_id in self.symbols:
                    raise DslError(f"symbol {obj.lib_id!r} is registered twice")
                self.symbols[obj.lib_id] = obj
            else:
                regular.append(obj)
        if regular:
            super().add(*regular)  # type: ignore[arg-type]

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

    def zone(
        self,
        net: Net | None,
        *,
        layers: Sequence[str],
        name: str | None = None,
        outline: Sequence[tuple[object, object]] | None = None,
        priority: int = 0,
        clearance: object = None,
        min_thickness: object = None,
        connection: str | None = None,
        thermal_gap: object = None,
        thermal_spoke_width: object = None,
        islands: str | None = None,
        min_island_area: str | None = None,
        locked: bool = False,
    ) -> None:
        """One copper zone (pour) on ``layers`` for ``net`` (``None`` for a zone without a net).

        The name defaults to the net's name and names the zone across builds. The outline is the board
        rectangle unless ``outline`` gives at least three ``(x, y)`` points in the frame of ``place()``. A
        setting left at ``None`` takes KiCad's new-zone value (``docs/dsl.md``, "Zones"). ``locked=True``
        makes the script win over an edit of the zone in KiCad, and locks the zone there.
        """
        if self.size is None:
            raise DslError("zone(): call board() first")
        if net is not None and not isinstance(net, Net):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"zone(): net must be a Net or None, not {net!r}")
        if name is None:
            if net is None:
                raise DslError("zone(): a zone without a net needs a name")
            name = net.name
        if not isinstance(name, str) or not name or name != name.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(
                f"zone(): name must be a non-empty string without surrounding spaces, not {name!r}"
            )
        if name in self.zones:
            raise DslError(f"zone(): the name {name!r} is already used; pass another name=")
        what = f"zone {name}"
        found_layers = self._zone_layers(layers, what)
        points = self._zone_outline(outline, what)
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: priority must be an int of at least 0, not {priority!r}")
        if not isinstance(locked, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{what}: locked must be a bool, not {locked!r}")
        changes: dict[str, object] = {}
        if clearance is not None:
            changes["clearance"] = as_nm(clearance, name=f"{what}: clearance")
            if changes["clearance"] < 0:  # type: ignore[operator]
                raise DslError(f"{what}: clearance must be at least 0")
        for argument, value in (
            ("min_thickness", min_thickness),
            ("thermal_gap", thermal_gap),
            ("thermal_spoke_width", thermal_spoke_width),
        ):
            if value is None:
                continue
            length = as_nm(value, name=f"{what}: {argument}")
            if length <= 0:
                raise DslError(f"{what}: {argument} must be above 0")
            changes[argument] = length
        if connection is not None:
            if connection not in ZONE_CONNECTIONS:
                raise DslError(
                    f"{what}: connection must be one of {', '.join(ZONE_CONNECTIONS)}, not {connection!r}"
                )
            changes["connection"] = connection
        if islands is not None:
            if islands not in ZONE_ISLANDS:
                raise DslError(f"{what}: islands must be one of {', '.join(ZONE_ISLANDS)}, not {islands!r}")
            changes["island_removal"] = islands
        if min_island_area is not None:
            if islands != "below_area":
                raise DslError(f'{what}: min_island_area is accepted only with islands="below_area"')
            changes["min_island_area"] = as_nm2(min_island_area, name=f"{what}: min_island_area")
        if net is not None:
            self.register_net(net)
        self.zones[name] = ZoneSpec(
            name,
            net.name if net is not None else None,
            found_layers,
            points,
            priority,
            ZoneSettings(**changes),  # type: ignore[arg-type]
            locked,
        )

    def _zone_layers(self, layers: object, what: str) -> tuple[str, ...]:
        allowed = ("F.Cu", *(INNER_LAYERS if self.copper == 4 else ()), "B.Cu")
        if isinstance(layers, str) or not isinstance(layers, Sequence) or not layers:
            raise DslError(
                f"{what}: layers must be a non-empty sequence of copper layer names, not {layers!r}"
            )
        found: list[str] = []
        for layer in cast("Sequence[object]", layers):
            if not isinstance(layer, str) or layer not in allowed:
                raise DslError(
                    f"{what}: layers: {layer!r} is not a copper layer of this board ({', '.join(allowed)})"
                )
            if layer in found:
                raise DslError(f"{what}: layers: {layer!r} is listed twice")
            found.append(layer)
        return tuple(found)

    @staticmethod
    def _zone_outline(outline: object, what: str) -> tuple[tuple[Nm, Nm], ...] | None:
        if outline is None:
            return None
        if isinstance(outline, str) or not isinstance(outline, Sequence):
            raise DslError(f"{what}: outline must hold at least three (x, y) points")
        pairs = cast("Sequence[object]", outline)
        if len(pairs) < 3:
            raise DslError(f"{what}: outline must hold at least three (x, y) points")
        points: list[tuple[Nm, Nm]] = []
        for index, pair in enumerate(pairs):
            if isinstance(pair, str) or not isinstance(pair, Sequence):
                raise DslError(f"{what}: outline[{index}] must be an (x, y) pair of lengths, not {pair!r}")
            xy = cast("Sequence[object]", pair)
            if len(xy) != 2:
                raise DslError(f"{what}: outline[{index}] must be an (x, y) pair of lengths, not {pair!r}")
            points.append(
                (
                    as_nm(xy[0], name=f"{what}: outline[{index}].x"),
                    as_nm(xy[1], name=f"{what}: outline[{index}].y"),
                )
            )
        return tuple(points)

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

    # -- copper intents (resolved by the build after placement; ``docs/dsl.md``, "Copper")

    def track(
        self, key: str, *path: object, layer: str = "F.Cu", width: object = None, net: Net | None = None
    ) -> None:
        """A track along ``path``: ``part.pad(…)`` ends, ``(x, y)`` points in the frame of ``place()``,
        ``arc_to(…)`` bends and ``via_step(…)`` layer changes. The net comes from the pads; the width from
        ``width`` or the net's class. ``key`` names the intent, so its copper keeps its ids across builds."""
        from fenolite.dsl import intents

        intents.record_track(self, key, path, layer, width, net)

    def via(
        self,
        key: str,
        x: object,
        y: object,
        *,
        net: Net,
        diameter: object = None,
        drill: object = None,
        kind: str = "through",
        layers: object = None,
    ) -> None:
        """One via at ``(x, y)`` on ``net``; sizes from the arguments or the net's class. ``kind`` is
        ``through``, ``blind``, ``buried`` or ``micro``; a via that is not a through via names its two
        copper layers in ``layers``."""
        from fenolite.dsl import intents

        intents.record_via(self, key, x, y, net, diameter, drill, kind, layers)

    def stitch(
        self,
        key: str,
        *,
        net: Net,
        pitch: object,
        along: Sequence[object] = (),
        region: Sequence[object] = (),
        origin: object = None,
        diameter: object = None,
        drill: object = None,
        clearance: object = None,
        margin: object = None,
    ) -> None:
        """Through vias of ``net`` every ``pitch`` along a polyline, or on a grid inside a region (the grid
        starts at ``origin``, the board corner by default), kept ``clearance`` from other copper."""
        from fenolite.dsl import intents

        intents.record_stitch(
            self,
            key,
            net=net,
            pitch=pitch,
            along=along,
            region=region,
            origin=origin,
            diameter=diameter,
            drill=drill,
            clearance=clearance,
            margin=margin,
        )

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


__all__ = [
    "DESIGN_NAME",
    "INNER_LAYERS",
    "MINIMUM_KINDS",
    "Design",
    "MinimumSpec",
    "NetClassSpec",
    "Rules",
    "ZoneSpec",
]
