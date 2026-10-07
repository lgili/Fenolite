# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A Specctra design file written from the model (capability specctra-dsn, "Design files are written from
the model"; facts: ``docs/formats/specctra/dsn.md``; change c0023).

``write_dsn`` takes the design, the board-frame pads of ``BoardFrame.board_pads`` and the outline rings, and
gives the file text, the names it wrote and its findings. It reads no file and imports no other backend.

- **Units.** ``(resolution um 10)``: a length becomes ``round_half_even(nm / 100)`` database units and is
  written in micrometres with at most one decimal. Y is negated: the file's frame has Y up.
- **Components.** One image per placed footprint, on the front with rotation 0; each pad's board-frame
  copper is its padstack, so nothing depends on how a reader turns or mirrors an image.
- **Wiring.** Every track, arc and via of the board is written with type ``protect``.
- **Nets outside the job.** With ``others="netless"`` a net that is not selected leaves the network
  section; its pins stay in their images and its copper stays as protected wiring without a net, so a
  router works on the job's nets only and still keeps clear of the rest ("Nets outside the routing job in
  design files"; change c0109, ``H-G-DSN-NETLESS``). A net whose class clearance is larger than the
  default rule stays declared: the router keeps only the default rule from copper without a net, and
  KiCad asks for the larger clearance (measured with Freerouting 2.4.1, outcome ``dsn-netless``).
- **Planes, layers and rules** (change c0107). A layer of ``plane_layers`` is written ``(type power)`` with
  one ``plane`` per zone of a net on it; a net of ``net_layers`` is kept to its layers with ``use_layer``, its
  class split by layer set; the rules of ``design.rules`` that the subset can carry are lowered by the closed
  table of ``_lower_rules`` (class clearances, ``class_class``, widths, ``layer_rule``), and every other rule
  is reported, the edge clearance among them: the format has no clearance from the board edge, and keep-out
  bands along the edges lost a route on the oracle bench (``H-G-DSN-EDGE-2``). A call without the two
  arguments, for a design without a rule, writes what it wrote before.

Every fact behind this module is ``INFERRED`` until the probes of ``H-G-DSN-ACCEPT``, ``H-G-DSN-UNITS`` and
``H-G-DSN-PROTECT`` are recorded; the lists of change c0107 follow ``H-G-DSN-LAYERS``, ``H-G-DSN-PLANE``,
``H-G-DSN-CLEARANCE`` and ``H-G-DSN-EDGE-2``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from fenolite.backends.base import BoardPad, PadCopper
from fenolite.backends.specctra.lexer import SNode, dumps, is_word, writable
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, round_half_even_div
from fenolite.geometry import DEFAULT_TOL, Circle, GeometryError, Polygon, convex_hull
from fenolite.geometry import Arc as GeometryArc
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, Selector

UNIT_NM = 100
"""Nanometres per database unit."""
RESOLUTION = 10
"""Database units per micrometre, the value of ``(resolution um 10)``."""
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-G-DSN-ACCEPT",
        "H-G-DSN-CLEARANCE",
        "H-G-DSN-EDGE-2",
        "H-G-DSN-LAYERS",
        "H-G-DSN-PLANE",
        "H-G-DSN-PROTECT",
        "H-G-DSN-UNITS",
    ),
)
"""Raised when the probes are recorded; a route itself is always ``UNVERIFIED``."""
Others = Literal["declared", "netless"]
"""How ``write_dsn`` writes the nets outside the job."""
ISSUE_CODES: dict[str, Severity] = {
    "specctra.unknown-padstack": "error",
    "specctra.session-moved": "error",
    "specctra.pad-approximated": "warning",
    "specctra.plane-skipped": "warning",
    "specctra.rounded": "info",
    "specctra.renamed": "info",
    "specctra.unknown-list": "info",
    "specctra.rule-not-sent": "info",
    "specctra.rule-widened": "info",
}
"""Every ``specctra.*`` code and its one severity."""
PCB_LAYER = "pcb"
SIGNAL_LAYER = "signal"
RESERVED_LAYERS = frozenset({PCB_LAYER, SIGNAL_LAYER, "power"})
HOST = "fenolite"
UNCONNECTED_PREFIX = "unconnected-("
"""How KiCad names the net of a pin on no net (``docs/formats/kicad/schematic.md``, "Net names")."""
DEFAULT_CLASS = "Default"
"""The class name that selects the nets without a class, as KiCad names it."""
NO_LAYERS: Mapping[str, tuple[str, ...]] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class DsnDefaults:
    """The board defaults for a net without a class, or a class without a value (nanometres)."""

    width: Nm
    clearance: Nm
    via_diameter: Nm
    via_drill: Nm

    def __post_init__(self) -> None:
        for name in ("width", "clearance", "via_diameter", "via_drill"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"default {name} must be a positive integer of nanometres, got {value!r}")
        if self.via_drill >= self.via_diameter:
            raise ValueError("the default via drill must be smaller than the via diameter")


@dataclass(frozen=True, slots=True)
class ViaStack:
    """What a via padstack name stands for: the model's diameter and drill, and the two outermost copper
    layers it spans."""

    diameter: Nm
    drill: Nm
    layers: tuple[str, str]


WireKey = tuple[str, str, int, Point, Point]
"""A protected segment: net name (``""`` for none), model layer, width and its two ends in sorted order,
all rounded to the database unit, in nanometres of the model frame."""
ViaKey = tuple[str, Point]
"""A protected via: net name (``""`` for none) and its rounded position in the model frame."""


@dataclass(frozen=True, slots=True)
class Names:
    """The names a design file was written with, mapped back to the model.

    ``nets`` maps a written net name to the model's name and ``net_ids`` to the net's id; ``components`` a
    written reference to the footprint id; ``pins`` a written ``REF-PIN`` to the pad id; ``layers`` a
    written layer name to the model's; ``vias`` a via padstack name to its ``ViaStack``. ``places`` holds
    each component's written position, rounded, in the model frame, and ``protected_wires`` and
    ``protected_vias`` the wiring that was written as protected.
    """

    nets: Mapping[str, str] = field(default_factory=lambda: {})
    net_ids: Mapping[str, str] = field(default_factory=lambda: {})
    components: Mapping[str, str] = field(default_factory=lambda: {})
    pins: Mapping[str, str] = field(default_factory=lambda: {})
    layers: Mapping[str, str] = field(default_factory=lambda: {})
    vias: Mapping[str, ViaStack] = field(default_factory=lambda: {})
    places: Mapping[str, Point] = field(default_factory=lambda: {})
    protected_wires: frozenset[WireKey] = frozenset()
    protected_vias: frozenset[ViaKey] = frozenset()


@dataclass(frozen=True, slots=True)
class DsnResult:
    """What ``write_dsn`` returns: the file text, the names it wrote and its warnings and infos."""

    text: str
    names: Names
    issues: tuple[Issue, ...] = ()


def to_units(nm: int) -> int:
    """``nm`` in database units, rounded half to even."""
    return round_half_even_div(nm, UNIT_NM)


def format_units(units: int) -> str:
    """Database units as micrometres: at most one decimal, no trailing ``.0``."""
    sign = "-" if units < 0 else ""
    whole, tenth = divmod(abs(units), RESOLUTION)
    return f"{sign}{whole}.{tenth}" if tenth else f"{sign}{whole}"


def rounded_point(point: Point) -> Point:
    """``point`` on the database grid, in nanometres of the model frame (what a reader gets back)."""
    return Point(to_units(point.x) * UNIT_NM, -to_units(-point.y) * UNIT_NM)


class _Namer:
    """Unique writable names for one kind of object."""

    def __init__(self, prefix: str, issues: list[Issue], *, kind: str, no_hyphen: bool = False) -> None:
        self.prefix = prefix
        self.issues = issues
        self.kind = kind
        self.no_hyphen = no_hyphen
        self.used: set[str] = set()
        self.count = 0

    def name(self, wanted: str, *, where: str = "") -> str:
        self.count += 1
        text = wanted.replace("-", "_") if self.no_hyphen else wanted
        if not text or not writable(text):
            text = f"{self.prefix}{self.count}"
        if text in self.used:
            base, serial = text, 2
            while f"{base}@{serial}" in self.used:
                serial += 1
            text = f"{base}@{serial}"
        self.used.add(text)
        if text != wanted:
            self.issues.append(
                Issue(
                    "specctra.renamed",
                    "info",
                    f"the {self.kind} {wanted!r} is written as {text!r}",
                    where=where or wanted,
                )
            )
        return text


def _classes_of(selector: Selector | None) -> frozenset[str] | None:
    """What a rule side selects, for the closed table: ``frozenset()`` for every item (``all`` or no
    selector), the class names of a ``netclass`` leaf or of an ``or`` of such leaves, else ``None``."""
    if selector is None or selector.op == "all":
        return frozenset()
    if selector.op == "netclass" and "*" not in selector.value:
        return frozenset({selector.value})
    if selector.op == "or":
        found: set[str] = set()
        for item in selector.items:
            names = _classes_of(item)
            if not names:
                return None
            found |= names
        return frozenset(found)
    return None


@dataclass
class _Lowered:
    """The rules of a design as the Specctra subset carries them (``docs/formats/specctra/dsn.md``,
    "Routing rules"). Values combine by maximum: the router keeps at least what any rule asks."""

    clearance: int
    width: int
    class_clearance: dict[str, int] = field(default_factory=lambda: {})
    class_width: dict[str, int] = field(default_factory=lambda: {})
    layer_width: dict[str, dict[str, int]] = field(default_factory=lambda: {})
    pairs: dict[tuple[str, str], int] = field(default_factory=lambda: {})


def _lower_rules(
    rules: Sequence[Rule],
    classes: Mapping[str, NetClass],
    defaults: DsnDefaults,
    copper: Sequence[str],
    issues: list[Issue],
) -> _Lowered:
    """Lower ``rules`` over the written ``classes`` (name → model class) by the closed table; a rule the
    subset cannot carry gives ``specctra.rule-not-sent``, a dropped layer clause ``specctra.rule-widened``."""
    low = _Lowered(defaults.clearance, defaults.width)
    for name, cls in classes.items():
        low.class_clearance[name] = cls.clearance or defaults.clearance
        low.class_width[name] = cls.track_width or defaults.width
    opt_set: set[str] = set()

    def not_sent(rule: Rule, why: str) -> None:
        issues.append(
            Issue(
                "specctra.rule-not-sent",
                "info",
                f"the {rule.kind} rule {rule.name!r} is not in the design file: {why}",
                where=rule.name,
            )
        )

    def widened(rule: Rule) -> None:
        issues.append(
            Issue(
                "specctra.rule-widened",
                "info",
                f"the {rule.kind} rule {rule.name!r} names the layers {', '.join(rule.layers)}; the design "
                "file has no clearance per layer, so the rule is written for every layer",
                where=rule.name,
            )
        )

    def raise_clearance(names: frozenset[str], value: int) -> None:
        """Raise the clearance of the named classes (``Default`` without such a class: the default rule;
        no name: every class and the default rule)."""
        if not names:
            low.clearance = max(low.clearance, value)
        for name in sorted(names or low.class_clearance):
            if name in low.class_clearance:
                low.class_clearance[name] = max(low.class_clearance[name], value)
            elif name == DEFAULT_CLASS:
                low.clearance = max(low.clearance, value)

    for rule in rules:
        if rule.severity == "ignore" or rule.kind == "no_tracks":
            continue  # a track layer rule travels as net_layers
        side_a, side_b = _classes_of(rule.selector_a), _classes_of(rule.selector_b)
        if rule.kind not in ("clearance", "track_width", "edge_clearance"):
            not_sent(rule, f"the Specctra subset has no list for a {rule.kind} rule")
            continue
        if side_a is None or side_b is None:
            not_sent(rule, "its selector is not 'all', a net class or an 'or' of net classes")
            continue
        if rule.kind == "clearance":
            if rule.min is None:
                not_sent(rule, "it has no min")
                continue
            if rule.layers:
                widened(rule)
            if not side_a or not side_b:
                raise_clearance(side_a or side_b, rule.min)
                continue
            lost = False
            for a in sorted(side_a):
                for b in sorted(side_b):
                    if a == b:
                        raise_clearance(frozenset({a}), rule.min)
                    elif a in low.class_clearance and b in low.class_clearance:
                        key = (a, b) if a < b else (b, a)
                        low.pairs[key] = max(low.pairs.get(key, 0), rule.min)
                    elif DEFAULT_CLASS in (a, b):
                        lost = True
            if lost:
                not_sent(rule, "the nets without a class have no class to pair in the design file")
        elif rule.kind == "edge_clearance":
            # Decision 11's fallback (change c0107): keep-out bands along the edges removed the edge
            # findings of the oracle bench but lost its route in a 2 mm passage (H-G-DSN-EDGE, refuted)
            not_sent(
                rule,
                "the Specctra subset has no clearance from the board edge; check the routed board",
            )
        else:  # track_width
            if rule.selector_b is not None:
                not_sent(rule, "a width rule has one side")
                continue
            names = sorted(side_a or low.class_width)
            if rule.layers:
                unknown = [layer for layer in rule.layers if layer not in copper]
                if rule.opt is None or unknown:
                    why = (
                        f"{', '.join(unknown)} is not a copper layer of the board"
                        if unknown
                        else "a width per layer needs an opt value"
                    )
                    not_sent(rule, why)
                    continue
                for name in names:
                    if name in low.class_width:
                        per_layer = low.layer_width.setdefault(name, {})
                        for layer in rule.layers:
                            per_layer[layer] = max(per_layer.get(layer, 0), rule.opt)
                continue

            def fit(name: str, current: int, rule: Rule = rule) -> int:
                if rule.opt is not None:
                    value = max(current, rule.opt) if name in opt_set else rule.opt
                    opt_set.add(name)
                    return value
                value = current if rule.min is None else max(current, rule.min)
                return value if rule.max is None else min(value, max(rule.max, rule.min or 0))

            for name in names:
                if name in low.class_width:
                    low.class_width[name] = fit(name, low.class_width[name])
                elif name == DEFAULT_CLASS:
                    low.width = fit("", low.width)
            if not side_a:
                low.width = fit("", low.width)
    return low


class _Writer:
    def __init__(
        self,
        design: Design,
        pads: Sequence[BoardPad],
        outline: Sequence[Sequence[Point]],
        selected: Sequence[str],
        defaults: DsnDefaults,
        others: Others = "declared",
        plane_layers: Sequence[str] = (),
        net_layers: Mapping[str, Sequence[str]] = NO_LAYERS,
    ) -> None:
        if others not in ("declared", "netless"):
            raise ValueError(f"others must be 'declared' or 'netless', got {others!r}")
        self.others = others
        board = design.board
        if board is None:
            raise ValueError("the design has no board to write a Specctra design file for")
        self.design = design
        self.board = board
        self.pads = pads
        self.outline = [tuple(ring) for ring in outline if len(ring) >= 3]
        if not self.outline:
            raise ValueError(
                "a Specctra design file needs the board outline: a ring of at least three points"
            )
        self.selected = tuple(selected)
        self.defaults = defaults
        self.copper = tuple(
            la.name for la in sorted(board.layers, key=lambda la: la.ordinal) if la.kind == "copper"
        )
        if not self.copper:
            raise ValueError("the board has no copper layer")
        unknown = [name for name in plane_layers if name not in self.copper]
        if unknown:
            raise ValueError(f"plane layer {', '.join(unknown)} is not a copper layer of the board")
        self.plane_layers = tuple(name for name in self.copper if name in plane_layers)
        self.net_layers: dict[str, tuple[str, ...]] = {}
        for net, layers in sorted(net_layers.items()):
            given = tuple(layers)
            if not given:
                raise ValueError(f"the net {net} has an empty layer set")
            for layer in given:
                if layer not in self.copper:
                    raise ValueError(f"the net {net} is kept to {layer}, which is not a copper layer")
                if layer in self.plane_layers:
                    raise ValueError(f"the net {net} is kept to {layer}, which is a plane layer")
            self.net_layers[net] = tuple(name for name in self.copper if name in given)
        self.issues: list[Issue] = []
        self.rounded = 0
        self.layer_out: dict[str, str] = {}
        self.padstacks: dict[tuple[tuple[str, ...], ...], str] = {}
        self.via_names: dict[tuple[int, int, int, int], str] = {}
        self.vias: dict[str, ViaStack] = {}

    # --- numbers --------------------------------------------------------------------------------

    def units(self, nm: int) -> int:
        if nm % UNIT_NM:
            self.rounded += 1
        return to_units(nm)

    def length(self, nm: int) -> str:
        return format_units(self.units(nm))

    def xy(self, point: Point) -> tuple[str, str]:
        return format_units(self.units(point.x)), format_units(self.units(-point.y))

    def relative(self, point: Point, origin: Point) -> tuple[str, str]:
        """``point`` relative to ``origin``, both rounded on their own; only ``point`` is counted."""
        return (
            format_units(self.units(point.x) - to_units(origin.x)),
            format_units(self.units(-point.y) - to_units(-origin.y)),
        )

    def flat(self, points: Sequence[Point], origin: Point | None = None) -> tuple[str, ...]:
        out: list[str] = []
        for point in points:
            out.extend(self.xy(point) if origin is None else self.relative(point, origin))
        return tuple(out)

    # --- layers ---------------------------------------------------------------------------------

    def name_layers(self) -> None:
        namer = _Namer("L", self.issues, kind="layer")
        namer.used.update(RESERVED_LAYERS)
        for name in self.copper:
            self.layer_out[name] = namer.name(name)

    # --- padstacks ------------------------------------------------------------------------------

    def entry_shape(self, entry: PadCopper, origin: Point, where: str) -> tuple[str, ...] | None:
        """The shape of one copper entry relative to its pad, or ``None`` for an entry without area."""
        layer = self.layer_out[entry.layer]
        core = entry.core
        if len(core) == 1:
            x, y = self.relative(core[0], origin)
            centre = () if (x, y) == ("0", "0") else (x, y)
            return ("circle", layer, self.length(entry.width), *centre)
        if not entry.filled:
            if entry.width == 0:
                return None
            return ("path", layer, self.length(entry.width), *self.flat(core, origin))
        if entry.width == 0:
            return ("polygon", layer, "0", *self.flat(core, origin))
        radius = -(-entry.width // 2)
        if Polygon(core).is_convex():
            around: list[Point] = []
            for point in core:
                around += Circle.from_radius(point, radius).polygonize(DEFAULT_TOL, outer=True)
            counted = self.rounded  # hull vertices are derived geometry, not lengths of the model
            hull = self.flat(convex_hull(around), origin)
            self.rounded = counted
            return ("polygon", layer, "0", *hull)
        self.approximated(
            where, "a ring with a width that is not convex is written as its bounding rectangle"
        )
        xs, ys = [p.x for p in core], [p.y for p in core]
        low = Point(min(xs) - radius, max(ys) + radius)
        high = Point(max(xs) + radius, min(ys) - radius)
        return ("rect", layer, *self.relative(low, origin), *self.relative(high, origin))

    def approximated(self, where: str, why: str) -> None:
        issue = Issue(
            "specctra.pad-approximated", "warning", f"the copper of {where} is approximate: {why}", where
        )
        if issue not in self.issues:
            self.issues.append(issue)

    def hole_shape(self, pad: BoardPad, layer: str) -> tuple[str, ...]:
        drill = pad.drill or 0
        out = self.layer_out[layer]
        if len(pad.hole) == 1:
            x, y = self.relative(pad.hole[0], pad.position)
            centre = () if (x, y) == ("0", "0") else (x, y)
            return ("circle", out, self.length(drill), *centre)
        return ("path", out, self.length(drill), *self.flat(pad.hole, pad.position))

    def pad_padstack(self, pad: BoardPad, where: str) -> str | None:
        """The name of the padstack of ``pad``, or ``None`` when it has nothing on a copper layer."""
        shapes: list[tuple[str, ...]] = []
        covered: set[str] = set()
        for entry in pad.copper:
            if entry.layer not in self.layer_out:
                continue
            if not entry.exact:
                self.approximated(where, "the pad's copper entry is a conservative superset")
            shape = self.entry_shape(entry, pad.position, where)
            if shape is not None:
                shapes.append(shape)
                covered.add(entry.layer)
        if pad.hole and pad.drill:
            shapes += [self.hole_shape(pad, layer) for layer in self.copper if layer not in covered]
        if not shapes:
            return None
        key = tuple(shapes)
        return self.padstacks.setdefault(key, f"P{len(self.padstacks) + 1}")

    def via_padstack(self, diameter: int, drill: int, first: str, last: str) -> str:
        """The name of the via padstack of this size between two copper layers, defined on first use."""
        start, end = sorted((self.copper.index(first), self.copper.index(last)))
        key = (to_units(diameter), to_units(drill), start, end)
        if key not in self.via_names:
            name = f"Via_{format_units(key[0])}_{format_units(key[1])}"
            if (start, end) != (0, len(self.copper) - 1):
                name += f"_L{start + 1}_L{end + 1}"
            self.via_names[key] = name
            self.vias[name] = ViaStack(diameter, drill, (self.copper[start], self.copper[end]))
        return self.via_names[key]

    def padstack_nodes(self) -> list[SNode]:
        nodes = [
            SNode("padstack", (name, *(SNode("shape", (SNode(s[0], s[1:]),)) for s in shapes)))
            for shapes, name in self.padstacks.items()
        ]
        for (diameter, _drill, start, end), name in self.via_names.items():
            size = format_units(diameter)
            shapes = tuple(
                SNode("shape", (SNode("circle", (self.layer_out[layer], size)),))
                for layer in self.copper[start : end + 1]
            )
            nodes.append(SNode("padstack", (name, *shapes)))
        return nodes

    def plane_zones(self) -> list[tuple[str, str, tuple[Point, ...], str]]:
        """The planes of the board: ``(net name, layer, outline, zone label)`` for each zone with a net,
        in model order, and each of its layers that is a plane layer, in stack order."""
        names = {net.id: net.name for net in self.design.circuit.nets}
        found: list[tuple[str, str, tuple[Point, ...], str]] = []
        for zone in self.board.zones:
            net = names.get(zone.net_id or "")
            if net is None:
                continue
            every = "*.Cu" in zone.layers
            for layer in self.plane_layers:
                if every or layer in zone.layers:
                    found.append((net, layer, tuple(zone.outline), zone.name or net))
        return found

    def plane_nets(self) -> frozenset[str]:
        """The names of the nets of the planes this file holds; they stay declared in every mode, so a
        router counts as joined every pin that reaches the plane (changes c0107 and c0109)."""
        return frozenset(net for net, _layer, outline, _label in self.plane_zones() if len(outline) >= 3)

    # --- the file -------------------------------------------------------------------------------

    def build(self) -> DsnResult:
        design, board = self.design, self.board
        self.name_layers()

        # nets that have pads, by name
        net_ids: dict[str, str] = {}
        pad_count: dict[str, int] = {}
        for pad in self.pads:
            if pad.net is not None and pad.net_id is not None:
                net_ids.setdefault(pad.net, pad.net_id)
                pad_count[pad.net] = pad_count.get(pad.net, 0) + 1
        # The net KiCad gives a pin on no net holds one pad and nothing to route: its pad is written as
        # a pad on no net, so a router gets the same board with and without those names (c0061).
        for name in [n for n in net_ids if n.startswith(UNCONNECTED_PREFIX) and pad_count[n] == 1]:
            del net_ids[name]
        # classes and their values
        classes = {c.id: c for c in design.circuit.netclasses}
        class_of = {n.name: classes.get(n.netclass_id or "") for n in design.circuit.nets}
        d = self.defaults
        ordered = sorted(design.circuit.netclasses, key=lambda c: (c.name, c.id))
        # the classes that hold a net with pads, before any net leaves the file: the rules are lowered
        # over them, and the nets outside the job are decided from the lowered values
        populated = {cls.name: cls for cls in ordered if any(class_of.get(name) is cls for name in net_ids)}
        low = _lower_rules(
            design.rules.rules if design.rules is not None else (), populated, d, self.copper, self.issues
        )
        # the classes that a ``class_class`` list pairs with the class of a selected net
        chosen = {cls.name for cls in (class_of.get(name) for name in self.selected) if cls is not None}
        paired = {other for a, b in low.pairs for own, other in ((a, b), (b, a)) if own in chosen}
        if self.others == "netless":
            # The same for every net outside the job: not declared and in no class, its pads pins on no
            # net and its copper protected wiring without a net (c0109). A router keeps the default rule
            # from such copper and no more, so a net whose class asks for a larger clearance stays
            # declared with its class (measured: ``dsn-netless``).
            kept = set(self.selected) | self.plane_nets()
            for name in [n for n in net_ids if n not in kept]:
                cls = class_of.get(name)
                if cls is not None and (low.class_clearance[cls.name] > low.clearance or cls.name in paired):
                    continue
                del net_ids[name]
        net_namer = _Namer("NET", self.issues, kind="net")
        net_out = {name: net_namer.name(name) for name in sorted(net_ids)}
        out_of_id = {net_ids[name]: out for name, out in net_out.items()}

        def values(name: str) -> tuple[int, int, int, int]:
            cls = class_of.get(name)
            if cls is None:
                return d.width, d.clearance, d.via_diameter, d.via_drill
            return (
                cls.track_width or d.width,
                cls.clearance or d.clearance,
                cls.via_diameter or d.via_diameter,
                cls.via_drill or d.via_drill,
            )

        top, bottom = self.copper[0], self.copper[-1]
        routed = [name for name in sorted(set(self.selected)) if name in net_out]
        via_list: list[str] = []
        for name in routed:
            _w, _c, diameter, drill = values(name)
            stack = self.via_padstack(diameter, drill, top, bottom)
            if stack not in via_list:
                via_list.append(stack)
        if not via_list:
            via_list.append(self.via_padstack(d.via_diameter, d.via_drill, top, bottom))

        # components: one image per footprint that has a pad on copper
        positions = {fp.id: fp.position for fp in board.footprints}
        order = {fp.id: index for index, fp in enumerate(board.footprints)}
        by_footprint: dict[str, list[BoardPad]] = {}
        for pad in self.pads:
            if pad.footprint_id not in positions:
                raise ValueError(f"the pad {pad.ref}-{pad.number} names a footprint the board lacks")
            by_footprint.setdefault(pad.footprint_id, []).append(pad)
        ref_namer = _Namer("FP", self.issues, kind="reference", no_hyphen=True)
        components: dict[str, str] = {}
        pins: dict[str, str] = {}
        places: dict[str, Point] = {}
        net_pins: dict[str, list[str]] = {name: [] for name in net_out}
        images: list[SNode] = []
        placement: list[SNode] = []
        for footprint_id in sorted(by_footprint, key=order.__getitem__):
            members = by_footprint[footprint_id]
            origin = positions[footprint_id]
            ref = ref_namer.name(members[0].ref)
            pin_namer = _Namer("@", self.issues, kind="pin", no_hyphen=True)
            pin_nodes: list[SNode] = []
            for pad in members:
                where = f"{pad.ref}-{pad.number}"
                stack = self.pad_padstack(pad, where)
                if stack is None:
                    continue
                pin = pin_namer.name(pad.number, where=where)
                pin_nodes.append(SNode("pin", (stack, pin, *self.relative(pad.position, origin))))
                pins[f"{ref}-{pin}"] = pad.pad_id
                if pad.net is not None and pad.net in net_pins:
                    net_pins[pad.net].append(f"{ref}-{pin}")
            if not pin_nodes:
                continue
            components[ref] = footprint_id
            places[ref] = rounded_point(origin)
            images.append(SNode("image", (ref, *pin_nodes)))
            place = SNode("place", (ref, *self.xy(origin), "front", "0", SNode("lock_type", ("position",))))
            placement.append(SNode("component", (ref, place)))

        # network
        nets = [
            SNode("net", (net_out[name], SNode("pins", tuple(net_pins[name]))))
            for name in sorted(net_out)
            if net_pins[name]
        ]
        declared = {name for name in net_out if net_pins[name]}
        class_namer = _Namer("CLASS", self.issues, kind="net class")
        class_nodes: list[SNode] = []
        members_of = {
            cls.id: sorted(name for name in declared if class_of.get(name) is cls) for cls in ordered
        }
        groups_of: dict[str, list[str]] = {}

        def class_node(
            label: str, members: Sequence[str], sets: tuple[str, ...] | None, cls: NetClass | None
        ) -> SNode:
            """One written class: its nets, its circuit (via and layers), its rule and its layer rules."""
            _w, _c, diameter, drill = values(members[0])
            width = low.class_width[cls.name] if cls is not None else low.width
            clearance = low.class_clearance[cls.name] if cls is not None else low.clearance
            items: list[SNode | str] = [label, *(net_out[name] for name in members)]
            circuit: list[SNode] = []
            if any(name in routed for name in members):
                circuit.append(SNode("use_via", (self.via_padstack(diameter, drill, top, bottom),)))
            if sets is not None:
                circuit.append(SNode("use_layer", tuple(self.layer_out[layer] for layer in sets)))
            if circuit:
                items.append(SNode("circuit", tuple(circuit)))
            items.append(
                SNode(
                    "rule",
                    (SNode("width", (self.length(width),)), SNode("clearance", (self.length(clearance),))),
                )
            )
            per_layer = low.layer_width.get(cls.name, {}) if cls is not None else {}
            for layer in self.copper:
                if layer in per_layer:
                    layer_rule = SNode("rule", (SNode("width", (self.length(per_layer[layer]),)),))
                    items.append(SNode("layer_rule", (self.layer_out[layer], layer_rule)))
            return SNode("class", tuple(items))

        def by_layer_set(members: Sequence[str]) -> list[tuple[tuple[str, ...] | None, list[str]]]:
            """``members`` grouped by layer set: the group that may use every signal layer first, so it
            keeps the class's name, then the others in the name order of their first net."""
            groups: dict[tuple[str, ...] | None, list[str]] = {}
            for name in members:
                groups.setdefault(self.net_layers.get(name), []).append(name)
            return sorted(groups.items(), key=lambda item: (item[0] is not None, item[1][0]))

        for cls in ordered:
            members = members_of[cls.id]
            if not members:
                continue
            for sets, group in by_layer_set(members):
                label = class_namer.name(cls.name)
                groups_of.setdefault(cls.name, []).append(label)
                class_nodes.append(class_node(label, group, sets, cls))
        classless = sorted(
            name for name in declared if class_of.get(name) is None and name in self.net_layers
        )
        for sets, group in by_layer_set(classless):
            class_nodes.append(class_node(class_namer.name(""), group, sets, None))
        for (a, b), value in sorted(low.pairs.items()):
            rule = SNode("rule", (SNode("clearance", (self.length(value),)),))
            for first in groups_of.get(a, ()):
                for second in groups_of.get(b, ()):
                    class_nodes.append(SNode("class_class", (SNode("classes", (first, second)), rule)))

        # wiring
        wires: list[SNode] = []
        protected_wires: set[WireKey] = set()
        protected_vias: set[ViaKey] = set()

        net_names = {out: name for name, out in net_out.items()}

        def tail(net_id: str | None) -> tuple[tuple[SNode, ...], str]:
            out = out_of_id.get(net_id or "")
            protect = SNode("type", ("protect",))
            if out is None or net_names[out] not in declared:
                return (protect,), ""
            return (SNode("net", (out,)), protect), net_names[out]

        def wire(points: Sequence[Point], width: int, layer: str, net_id: str | None) -> None:
            if layer not in self.layer_out:
                return
            extra, net = tail(net_id)
            path = SNode("path", (self.layer_out[layer], self.length(width), *self.flat(points)))
            wires.append(SNode("wire", (path, *extra)))
            grid = [rounded_point(p) for p in points]
            for a, b in zip(grid, grid[1:], strict=False):
                low, high = sorted((a, b))
                protected_wires.add((net, layer, to_units(width) * UNIT_NM, low, high))

        for track in board.tracks:
            wire((track.start, track.end), track.width, track.layer, track.net_id)
        for arc in board.arcs:
            try:
                points: Sequence[Point] = GeometryArc(arc.start, arc.mid, arc.end).polygonize(DEFAULT_TOL)
            except (GeometryError, ValueError):
                points = (arc.start, arc.end)
            wire(points, arc.width, arc.layer, arc.net_id)
        for via in board.vias:
            span = [layer for layer in via.layers if layer in self.layer_out]
            first, last = (span[0], span[-1]) if span else (top, bottom)
            stack = self.via_padstack(via.diameter, via.drill, first, last)
            extra, net = tail(via.net_id)
            wires.append(SNode("via", (stack, *self.xy(via.position), *extra)))
            protected_vias.add((net, rounded_point(via.position)))

        # structure
        ring = self.outline[0]
        xs = [to_units(p.x) for p in ring]
        ys = [to_units(-p.y) for p in ring]
        box = (format_units(min(xs)), format_units(min(ys)), format_units(max(xs)), format_units(max(ys)))
        structure: list[SNode | str] = [
            SNode(
                "layer",
                (
                    self.layer_out[name],
                    SNode("type", ("power" if name in self.plane_layers else "signal",)),
                ),
            )
            for name in self.copper
        ]
        structure.append(SNode("boundary", (SNode("rect", (PCB_LAYER, *box)),)))
        structure.append(SNode("boundary", (SNode("path", (SIGNAL_LAYER, "0", *self.flat(ring))),)))
        for plane_net, layer, zone_outline, label in self.plane_zones():
            if plane_net not in declared:
                continue  # a net without a pin in the file: no plane and no issue
            if len(zone_outline) < 3:
                self.issues.append(
                    Issue(
                        "specctra.plane-skipped",
                        "warning",
                        f"the zone {label!r} of {plane_net} on {layer} has no outline of three points or "
                        "more, so no plane is written for it",
                        where=f"{label}/{layer}",
                    )
                )
                continue
            shape = SNode("polygon", (self.layer_out[layer], "0", *self.flat(zone_outline)))
            structure.append(SNode("plane", (net_out[plane_net], shape)))
        for cutout in self.outline[1:]:
            structure.append(SNode("keepout", (SNode("polygon", (SIGNAL_LAYER, "0", *self.flat(cutout))),)))
        for keepout in board.keepouts:
            if len(keepout.outline) < 3 or not (keepout.no_tracks or keepout.no_vias):
                continue
            kind = (
                "keepout"
                if keepout.no_tracks and keepout.no_vias
                else "wire_keepout"
                if keepout.no_tracks
                else "via_keepout"
            )
            every = not keepout.layers or "*.Cu" in keepout.layers
            for layer in self.copper:
                if every or layer in keepout.layers:
                    shape = SNode("polygon", (self.layer_out[layer], "0", *self.flat(keepout.outline)))
                    structure.append(SNode(kind, (shape,)))
        structure.append(SNode("via", tuple(via_list)))
        structure.append(
            SNode(
                "rule",
                (
                    SNode("width", (self.length(low.width),)),
                    SNode("clearance", (self.length(low.clearance),)),
                ),
            )
        )

        name = design.header.name.replace(" ", "_")
        tree = SNode(
            "pcb",
            (
                name if is_word(name) else "board",
                SNode(
                    "parser",
                    (
                        SNode("string_quote", ('"',)),
                        SNode("space_in_quoted_tokens", ("on",)),
                        SNode("host_cad", (HOST,)),
                    ),
                ),
                SNode("resolution", ("um", str(RESOLUTION))),
                SNode("unit", ("um",)),
                SNode("structure", tuple(structure)),
                SNode("placement", tuple(placement)),
                SNode("library", (*images, *self.padstack_nodes())),
                SNode("network", (*nets, *class_nodes)),
                SNode("wiring", tuple(wires)),
            ),
        )
        if self.rounded:
            self.issues.append(
                Issue(
                    "specctra.rounded",
                    "info",
                    f"{self.rounded} length(s) were not multiples of {UNIT_NM} nm and were rounded "
                    f"to the file's resolution",
                )
            )
        names = Names(
            nets={out: name for name, out in net_out.items() if name in declared},
            net_ids={out: net_ids[name] for name, out in net_out.items() if name in declared},
            components=components,
            pins=pins,
            layers={out: name for name, out in self.layer_out.items()},
            vias=dict(self.vias),
            places=places,
            protected_wires=frozenset(protected_wires),
            protected_vias=frozenset(protected_vias),
        )
        return DsnResult(dumps(tree), names, tuple(self.issues))


def write_dsn(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    outline: Sequence[Sequence[Point]],
    selected: Sequence[str],
    defaults: DsnDefaults,
    plane_layers: Sequence[str] = (),
    net_layers: Mapping[str, Sequence[str]] = NO_LAYERS,
    others: Others = "declared",
) -> DsnResult:
    """The Specctra design file of ``design``'s board.

    ``pads`` are the board-frame pads of ``BoardFrame.board_pads``; ``outline`` holds the board ring first
    and its cut-outs after it; ``selected`` names the nets to route, which decides the vias the router may
    use; ``defaults`` serve nets without a class. Equal inputs give equal text.

    ``plane_layers`` names the copper layers written ``(type power)``, each with one ``plane`` per zone of a
    net on it; ``net_layers`` maps a net name to the copper layers, none of them a plane layer, that its
    wires may use. The rules of ``design.rules`` are lowered by the closed table of the module. Without
    the two arguments and without a rule, the text is the one the writer gave before change c0107.

    ``others`` says how the nets that are not in ``selected`` are written: ``"declared"`` (the default)
    declares every net that has pads; ``"netless"`` leaves them out of the network section and of every
    class, keeps their pins in the images as pins on no net and writes their copper as protected wiring
    without a net. They are then no key of ``names.nets`` and ``names.net_ids``. Two kinds of nets stay
    declared with their class in both modes: a net of a plane this file holds, so the router counts its
    pins as joined there, and a net whose clearance as the file writes it (its class, raised by the rules,
    or a ``class_class`` pair of its class) is larger than the default rule's, because a router keeps only
    the default rule from copper without a net.

    Raises ``ValueError`` for a design without a board, without a copper layer or without an outline ring,
    for a plane layer that is not a copper layer, for a layer set that is empty or names a plane layer or
    a layer the board lacks, and for a value of ``others`` that is neither of the two.
    """
    return _Writer(design, pads, outline, selected, defaults, others, plane_layers, net_layers).build()


__all__ = [
    "EVIDENCE",
    "ISSUE_CODES",
    "RESOLUTION",
    "UNIT_NM",
    "DsnDefaults",
    "DsnResult",
    "Names",
    "Others",
    "ViaKey",
    "ViaStack",
    "WireKey",
    "format_units",
    "rounded_point",
    "to_units",
    "write_dsn",
]
