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

Every fact behind this module is ``INFERRED`` until the probes of ``H-G-DSN-ACCEPT``, ``H-G-DSN-UNITS`` and
``H-G-DSN-PROTECT`` are recorded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.base import BoardPad, PadCopper
from fenolite.backends.specctra.lexer import SNode, dumps, is_word, writable
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, round_half_even_div
from fenolite.geometry import DEFAULT_TOL, Circle, GeometryError, Polygon, convex_hull
from fenolite.geometry import Arc as GeometryArc
from fenolite.model.design import Design

UNIT_NM = 100
"""Nanometres per database unit."""
RESOLUTION = 10
"""Database units per micrometre, the value of ``(resolution um 10)``."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-DSN-ACCEPT", "H-G-DSN-PROTECT", "H-G-DSN-UNITS"))
"""Raised when the three probes are recorded; a route itself is always ``UNVERIFIED``."""
ISSUE_CODES: dict[str, Severity] = {
    "specctra.unknown-padstack": "error",
    "specctra.session-moved": "error",
    "specctra.pad-approximated": "warning",
    "specctra.rounded": "info",
    "specctra.renamed": "info",
    "specctra.unknown-list": "info",
}
"""Every ``specctra.*`` code and its one severity."""
PCB_LAYER = "pcb"
SIGNAL_LAYER = "signal"
RESERVED_LAYERS = frozenset({PCB_LAYER, SIGNAL_LAYER, "power"})
HOST = "fenolite"


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


class _Writer:
    def __init__(
        self,
        design: Design,
        pads: Sequence[BoardPad],
        outline: Sequence[Sequence[Point]],
        selected: Sequence[str],
        defaults: DsnDefaults,
    ) -> None:
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

    # --- the file -------------------------------------------------------------------------------

    def build(self) -> DsnResult:
        design, board = self.design, self.board
        self.name_layers()

        # nets that have pads, by name
        net_ids: dict[str, str] = {}
        for pad in self.pads:
            if pad.net is not None and pad.net_id is not None:
                net_ids.setdefault(pad.net, pad.net_id)
        net_namer = _Namer("NET", self.issues, kind="net")
        net_out = {name: net_namer.name(name) for name in sorted(net_ids)}
        out_of_id = {net_ids[name]: out for name, out in net_out.items()}

        # classes and their values
        classes = {c.id: c for c in design.circuit.netclasses}
        class_of = {n.name: classes.get(n.netclass_id or "") for n in design.circuit.nets}
        d = self.defaults

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
        for cls in sorted(design.circuit.netclasses, key=lambda c: (c.name, c.id)):
            members = sorted(name for name in declared if class_of.get(name) is cls)
            if not members:
                continue
            width, clearance, diameter, drill = values(members[0])
            items: list[SNode | str] = [class_namer.name(cls.name), *(net_out[name] for name in members)]
            if any(name in routed for name in members):
                use = self.via_padstack(diameter, drill, top, bottom)
                items.append(SNode("circuit", (SNode("use_via", (use,)),)))
            rule = SNode(
                "rule", (SNode("width", (self.length(width),)), SNode("clearance", (self.length(clearance),)))
            )
            class_nodes.append(SNode("class", (*items, rule)))

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
            SNode("layer", (self.layer_out[name], SNode("type", ("signal",)))) for name in self.copper
        ]
        structure.append(SNode("boundary", (SNode("rect", (PCB_LAYER, *box)),)))
        structure.append(SNode("boundary", (SNode("path", (SIGNAL_LAYER, "0", *self.flat(ring))),)))
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
                (SNode("width", (self.length(d.width),)), SNode("clearance", (self.length(d.clearance),))),
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
) -> DsnResult:
    """The Specctra design file of ``design``'s board.

    ``pads`` are the board-frame pads of ``BoardFrame.board_pads``; ``outline`` holds the board ring first
    and its cut-outs after it; ``selected`` names the nets to route, which decides the vias the router may
    use; ``defaults`` serve nets without a class. Equal inputs give equal text.

    Raises ``ValueError`` for a design without a board, without a copper layer or without an outline ring.
    """
    return _Writer(design, pads, outline, selected, defaults).build()


__all__ = [
    "EVIDENCE",
    "ISSUE_CODES",
    "RESOLUTION",
    "UNIT_NM",
    "DsnDefaults",
    "DsnResult",
    "Names",
    "ViaKey",
    "ViaStack",
    "WireKey",
    "format_units",
    "rounded_point",
    "to_units",
    "write_dsn",
]
