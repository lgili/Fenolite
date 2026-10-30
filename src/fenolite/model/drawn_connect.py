# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The connectivity of a drawn schematic and its comparison with the circuit (capability
``drawn-schematic``, "Drawn connectivity resolver", "Drawn connectivity rules", "Drawn bus connectivity",
"Drawn net names", "Drawing compared with the circuit", "Drawn schematic coverage" and "Repeated sheet
values"; change c0276; ``docs/drawn-schematic.md``).

``resolve`` gives the nets of a ``DrawnSchematic`` from its geometry alone: no file, no tool, no float. The
caller gives the connection point of every pin of every drawn symbol and power symbol in the sheet frame
(``pins``), computed from the symbol definitions. The rules are those of ``docs/formats/kicad/schematic.md``
("Drawn schematic connectivity"), each ``INFERRED`` until its hypothesis is measured:

- a wire segment joins its two ends and every label anchor and junction that lies on it; segments join
  where their ends meet; a segment end inside another segment (a T) and a crossing join only through a
  junction on that point, and a pin (of a symbol, a power symbol or a sheet reference) joins a wire at the
  wire's end only, as ``kicad-cli`` 9.0.9 and 10.0.6 read them (``H-K-SCH-WIRE-END``, ``H-K-DRAWN-CONNECT``);
- local labels of one text join on one sheet instance, global labels and power symbols of one text on
  every sheet, a hidden ``power_in`` pin joins the global net of its pin name, and a hierarchical label
  joins the sheet pin of its name on the reference of its instance;
- a bus carries the members of its labels and sheet pins (``NAME[a..b]``, ``{A B}``, aliases); a member
  joins the local labels of its name on the instance, and crosses a sheet through a bus sheet pin and the
  hierarchical label of the same text; a bus entry joins nothing by itself;
- a repeated sheet gives one set of local nets per instance.

``compare`` compares the drawn nets with the circuit as partitions of (component path, pin number), and
``coverage`` checks that every unit of every code component is drawn once per instance. The issue codes are
``ISSUE_CODES``; the build, ``fenolite check`` (stage ``schematic.drawn``) and ``fenolite sync`` report
them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.model.circuit import Circuit, Component
from fenolite.model.drawn import DrawnInstance, DrawnSchematic, DrawnSheet

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "drawn.netlist-differs": "error",
        "drawn.symbol-missing": "error",
        "drawn.part-unknown": "error",
        "drawn.sheet-pin-unmatched": "error",
        "drawn.sheet-unknown": "error",
        "drawn.repeated-value-differs": "error",
        "drawn.net-name-differs": "warning",
        "drawn.unit-missing": "warning",
        "drawn.dangling": "warning",
        "drawn.label-unconnected": "warning",
        "drawn.bus-member-unknown": "warning",
        "drawn.placements-ignored": "warning",
        "drawn.opaque-dropped": "info",
        "drawn.frozen": "info",
        "drawn.altium-repeat-flattened": "info",
    }
)
"""The closed set of the drawn schematic codes and their severities."""
PATH_PROPERTY = "fenolite.path"
"""The component property that holds a component's path (``fenolite.dsl.convert.PATH_PROPERTY``)."""
SPLIT_HINT = "give each instance its own sheet, or give the parts equal values and footprints"
NETLIST_HINT = (
    "change the code (or fenolite edit) so that it means the drawing, or redraw the sheet so that it means "
    "the code: the code is the source of the nets"
)
_VECTOR = re.compile(r"^(.*?)\[(\d+)\.\.(\d+)\]$")
_GROUP = re.compile(r"^([^{}]*)\{([^{}]*)\}$")
_NATURAL = re.compile(r"(\d+)")

Element = tuple[str, str]
"""A pin of a drawn component: (component path, pin number)."""
PinKey = tuple[str, str, int]
"""The pins of one drawn item: (sheet key, ``symbol`` or ``power``, index in its sheet's array)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


@dataclass(frozen=True, slots=True)
class PinPoint:
    """One pin of a drawn item: its number, its connection point in the sheet frame, its electrical type,
    whether it is hidden, and its name."""

    number: str
    at: Point
    etype: str = "passive"
    hidden: bool = False
    name: str = ""


@dataclass(frozen=True, slots=True)
class DrawnNet:
    """One net of a drawing: its name (``""`` for an unnamed net), its members in sorted order and the
    texts of the labels and power symbols that name it."""

    name: str
    members: tuple[Element, ...]
    labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DrawnNetlist:
    """The nets of a drawing (every group with a member: named nets, and unnamed ones of two or more
    pins), every pin of a drawn component, the open pins (alone and unnamed) and the resolver's issues."""

    nets: tuple[DrawnNet, ...]
    pins: tuple[Element, ...]
    open: tuple[Element, ...] = ()
    issues: tuple[Issue, ...] = ()

    def net_of(self, element: Element) -> DrawnNet | None:
        return next((net for net in self.nets if element in net.members), None)


def natural(text: str) -> tuple[tuple[int, int | str], ...]:
    """A sort key that orders ``R2`` before ``R10``."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in _NATURAL.split(text) if p)


# --- instances ------------------------------------------------------------------------------------


def instances(drawn: DrawnSchematic) -> tuple[tuple[DrawnInstance, ...], tuple[Issue, ...]]:
    """The instances of ``drawn`` in page order, and one ``drawn.sheet-unknown`` error per reference that
    names no sheet, per cycle of references (naming its sheets) and per sheet other than the root that no
    reference reaches."""
    found, cycles, unknown = drawn.walk()
    issues: list[Issue] = []
    for where in unknown:
        if drawn.sheet(drawn.root) is None:
            issues.append(
                issue("drawn.sheet-unknown", f"the root names the sheet {where!r}, which is none", where)
            )
            continue
        holder, _, key = where.partition(":")
        sheet = drawn.sheet(holder)
        target = next((r.sheet for r in sheet.sheet_refs if r.key == key), "") if sheet is not None else ""
        issues.append(
            issue(
                "drawn.sheet-unknown",
                f"the reference {key} of sheet {holder} names the sheet {target!r}, which the file "
                "does not hold",
                where,
            )
        )
    for cycle in cycles:
        shown = ", ".join(sorted(set(cycle)))
        issues.append(
            issue(
                "drawn.sheet-unknown",
                f"the sheets {shown} reference each other in a cycle: {' -> '.join(cycle)}",
                cycle[0],
                "a sheet may not contain itself",
            )
        )
    reached = {instance.sheet for instance in found}
    in_cycle = {key for cycle in cycles for key in cycle}
    for sheet in drawn.sheets:
        if sheet.key not in reached and sheet.key not in in_cycle:
            issues.append(
                issue(
                    "drawn.sheet-unknown",
                    f"no sheet reference reaches the sheet {sheet.key}",
                    sheet.key,
                    "reference the sheet from the root, or remove it",
                )
            )
    return found, tuple(issues)


# --- bus names ------------------------------------------------------------------------------------


def expand(text: str, aliases: Mapping[str, Sequence[str]], depth: int = 0) -> tuple[str, ...] | None:
    """The member names of a bus text: ``NAME[a..b]`` gives ``NAMEa`` to ``NAMEb``, ``{A B}`` gives its
    items expanded, ``P{A B}`` gives ``P.A`` and ``P.B``, and an alias name its members expanded. ``None``
    for a text that is no bus (a plain net name)."""
    if depth > 8:
        return None
    if text in aliases:
        members: list[str] = []
        for member in aliases[text]:
            members += expand(member, aliases, depth + 1) or (member,)
        return tuple(members)
    vector = _VECTOR.match(text)
    if vector is not None:
        prefix, first, last = vector.group(1), int(vector.group(2)), int(vector.group(3))
        step = 1 if last >= first else -1
        return tuple(f"{prefix}{k}" for k in range(first, last + step, step))
    group = _GROUP.match(text)
    if group is not None:
        prefix = group.group(1)
        members = []
        for item in group.group(2).replace(",", " ").split():
            inner = expand(item, aliases, depth + 1) or (item,)
            members += [f"{prefix}.{m}" if prefix else m for m in inner]
        return tuple(members)
    return None


# --- the resolver ---------------------------------------------------------------------------------


class _Union:
    def __init__(self) -> None:
        self.parent: dict[object, object] = {}

    def find(self, key: object) -> object:
        parent = self.parent.setdefault(key, key)
        while parent != key:
            grand = self.parent.setdefault(parent, parent)
            self.parent[key] = grand
            key, parent = parent, grand
        return key

    def join(self, first: object, second: object) -> None:
        a, b = self.find(first), self.find(second)
        if a != b:
            self.parent[a] = b


def _on_segment(point: Point, start: Point, end: Point) -> bool:
    """Whether ``point`` lies on the closed segment from ``start`` to ``end`` (integer arithmetic)."""
    cross = (end.x - start.x) * (point.y - start.y) - (end.y - start.y) * (point.x - start.x)
    if cross:
        return False
    return min(start.x, end.x) <= point.x <= max(start.x, end.x) and min(start.y, end.y) <= point.y <= max(
        start.y, end.y
    )


class _Segments:
    """Segments indexed by their line, so that a point finds the segments it lies on quickly."""

    def __init__(self, segments: Iterable[tuple[Point, Point]]) -> None:
        self.rows: dict[int, list[tuple[Point, Point]]] = defaultdict(list)
        self.columns: dict[int, list[tuple[Point, Point]]] = defaultdict(list)
        self.slanted: list[tuple[Point, Point]] = []
        self.all: list[tuple[Point, Point]] = []
        for segment in segments:
            start, end = segment
            self.all.append(segment)
            if start.y == end.y:
                self.rows[start.y].append(segment)
            elif start.x == end.x:
                self.columns[start.x].append(segment)
            else:
                self.slanted.append(segment)

    def under(self, point: Point) -> list[tuple[Point, Point]]:
        found = [s for s in self.rows.get(point.y, ()) if _on_segment(point, *s)]
        found += [s for s in self.columns.get(point.x, ()) if _on_segment(point, *s)]
        found += [s for s in self.slanted if _on_segment(point, *s)]
        return found


@dataclass
class _Groups:
    """What the resolver records per group key while it joins."""

    union: _Union = field(default_factory=_Union)
    names: dict[object, list[tuple[int, int, str, str]]] = field(default_factory=lambda: defaultdict(list))
    """Node → (class, depth, full name, label text): class 0 for a global label or power net, 1 else."""


def _aliases(drawn: DrawnSchematic, sheet: DrawnSheet) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    for other in drawn.sheets:
        for alias in other.bus_aliases:
            found.setdefault(alias.name, alias.members)
    for alias in sheet.bus_aliases:
        found[alias.name] = alias.members
    return found


def resolve(
    drawn: DrawnSchematic,
    pins: Mapping[PinKey, Sequence[PinPoint]],
    *,
    design_name: str = "",
) -> DrawnNetlist:
    """The nets of ``drawn``. ``pins`` gives, per drawn symbol and power symbol (``PinKey``), the pins of its
    unit in the sheet frame; a power symbol without an entry connects at its own position. ``design_name``
    names the root in messages."""
    found, issues = instances(drawn)
    out = list(issues)
    groups = _Groups()
    union = groups.union
    elements: set[Element] = set()
    child_of = {(i.parent, i.ref.key): index for index, i in enumerate(found) if i.ref is not None}
    hier_labels: dict[int, set[str]] = defaultdict(set)
    sheet_pins: dict[int, set[str]] = defaultdict(set)
    shown_root = design_name or drawn.root
    for index, instance in enumerate(found):
        sheet = drawn.sheet(instance.sheet)
        if sheet is None or sheet.generated:
            continue
        where = f"{shown_root}/{instance.path}" if instance.path else shown_root
        depth = len(instance.keys)
        prefix = "/" + "".join(f"{name}/" for name in instance.names)
        aliases = _aliases(drawn, sheet)
        wires = _Segments(sheet.segments())
        buses = _Segments(sheet.bus_segments())
        touched: defaultdict[Point, int] = defaultdict(int)
        """How many items other than a segment end lie at each point of the wire layer."""

        def point(at: Point) -> tuple[object, ...]:
            return ("P", index, at.x, at.y)  # noqa: B023

        def bus_point(at: Point) -> tuple[object, ...]:
            return ("B", index, at.x, at.y)  # noqa: B023

        def name(node: object, klass: int, full: str, text: str) -> None:
            groups.names[node].append((klass, depth if klass else 0, full, text))  # noqa: B023

        # wire segments: each joins its ends, and the junctions and label anchors on it
        interest: list[Point] = []
        for start, end in wires.all:
            union.join(point(start), point(end))
        for k, symbol in enumerate(sheet.symbols):
            component = instance.component(symbol.part)
            for pin in pins.get((sheet.key, "symbol", k), ()):
                element = (component, pin.number)
                elements.add(element)
                union.join(("E", element), point(pin.at))
                touched[pin.at] += 1  # a pin joins a wire at the wire's end only (H-K-SCH-WIRE-END)
                if pin.hidden and pin.etype == "power_in" and pin.name and pin.name != "~":
                    union.join(("E", element), ("G", pin.name))
                    name(("G", pin.name), 0, pin.name, pin.name)
        for k, power in enumerate(sheet.powers):
            given = pins.get((sheet.key, "power", k))
            points = [p.at for p in given] if given else [power.at]
            global_net = not given or any(p.etype == "power_in" for p in given)
            for at in points:
                touched[at] += 1
                if global_net:
                    union.join(point(at), ("G", power.net))
            if global_net:
                name(("G", power.net), 0, power.net, power.net)
        for junction in sheet.junctions:
            touched[junction.at] += 1
            interest.append(junction.at)
        for flag in sheet.no_connects:
            touched[flag] += 1
        for entry in sheet.bus_entries:
            touched[entry.at] += 1
            touched[entry.end] += 1
        for ref in sheet.sheet_refs:  # a label on a sheet pin joins it, as on a symbol pin
            if child_of.get((index, ref.key)) is not None:
                for pin in ref.pins:
                    if wires.under(pin.at) or not buses.under(pin.at):
                        touched[pin.at] += 1
        bus_labels: list[tuple[str, str, Point]] = []
        for label in sheet.labels:
            on_wire = bool(wires.under(label.at)) or touched[label.at] > 0
            on_bus = bool(buses.under(label.at))
            if on_bus and not on_wire and expand(label.text, aliases) is not None:
                bus_labels.append((label.kind, label.text, label.at))
                continue
            if on_bus and not on_wire:
                bus_labels.append((label.kind, label.text, label.at))
                continue
            if not on_wire:
                out.append(
                    issue(
                        "drawn.label-unconnected",
                        f"the {label.kind} label {label.text!r} at {_mm(label.at)} on {where} touches "
                        "no wire "
                        "and no pin",
                        f"{where}:{label.text}",
                    )
                )
                continue
            touched[label.at] += 1
            interest.append(label.at)
            if label.kind == "local":
                node: tuple[object, ...] = ("L", index, label.text)
                name(node, 1, f"{prefix}{label.text}", label.text)
            elif label.kind == "global":
                node = ("G", label.text)
                name(node, 0, label.text, label.text)
            else:
                node = ("H", index, label.text)
                hier_labels[index].add(label.text)
                name(node, 1, f"{prefix}{label.text}", label.text)
            union.join(point(label.at), node)
        bus_pins: list[tuple[int, str, Point]] = []
        for ref in sheet.sheet_refs:
            child = child_of.get((index, ref.key))
            if child is None:
                continue
            for pin in ref.pins:
                sheet_pins[child].add(pin.name)
                if buses.under(pin.at) and not wires.under(pin.at):
                    bus_pins.append((child, pin.name, pin.at))
                    continue
                union.join(point(pin.at), ("H", child, pin.name))
        for at in interest:
            for start, _end in wires.under(at):
                union.join(point(at), point(start))
        # dangling segment ends: an end that no other segment and no item touches
        ends: defaultdict[Point, int] = defaultdict(int)
        for start, end in wires.all:
            ends[start] += 1
            ends[end] += 1
        for at, count in sorted(ends.items(), key=lambda pair: (pair[0].x, pair[0].y)):
            inside = sum(1 for s in wires.under(at) if at not in s)
            if count == 1 and not inside and not touched[at]:
                out.append(
                    issue(
                        "drawn.dangling",
                        f"a wire end at {_mm(at)} on {where} joins nothing",
                        f"{where}:{_mm(at)}",
                    )
                )
        # buses: groups of segments, their members, and the members' local nets
        for start, end in buses.all:
            union.join(bus_point(start), bus_point(end))
        for junction in sheet.junctions:
            for start, _end in buses.under(junction.at):
                union.join(bus_point(junction.at), bus_point(start))
        members: dict[object, set[str]] = defaultdict(set)
        unknown: dict[object, set[str]] = defaultdict(set)

        def bus_group(at: Point) -> object | None:
            under = buses.under(at)  # noqa: B023
            return union.find(bus_point(under[0][0])) if under else None

        for kind, text, at in bus_labels:
            group = bus_group(at)
            names = expand(text, aliases)
            if group is None:
                continue
            if names is None:
                unknown[group].add(text)
                continue
            members[group].update(names)
            if kind == "hierarchical":
                hier_labels[index].add(text)
                for member in names:
                    union.join(("HB", index, text, member), ("BM", index, group, member))
            elif kind == "global":
                for member in names:
                    union.join(("GB", text, member), ("BM", index, group, member))
        for child, text, at in bus_pins:
            group = bus_group(at)
            names = expand(text, aliases)
            if group is None or names is None:
                continue
            members[group].update(names)
            for member in names:
                union.join(("HB", child, text, member), ("BM", index, group, member))
        local_texts = {label.text for label in sheet.labels if label.kind in ("local", "global")}
        for group, names in sorted(members.items(), key=lambda pair: str(pair[0])):
            for member in sorted(names):
                union.join(("BM", index, group, member), ("L", index, member))
                if member not in local_texts:
                    unknown[group].add(member)
        for _group, names in sorted(unknown.items(), key=lambda pair: str(pair[0])):
            for member in sorted(names):
                out.append(
                    issue(
                        "drawn.bus-member-unknown",
                        f"the bus member {member} on {where} is carried by no label of that name, and "
                        "no alias "
                        "or vector defines it",
                        f"{where}:{member}",
                    )
                )
    for child, names in sorted(sheet_pins.items()):
        labels = hier_labels.get(child, set())
        instance = found[child]
        shown = instance.path
        for missing in sorted(names - labels):
            out.append(
                issue(
                    "drawn.sheet-pin-unmatched",
                    f"the sheet pin {missing} of {shown} has no hierarchical label of that name on sheet "
                    f"{instance.sheet}",
                    f"{shown}:{missing}",
                )
            )
    for index, labels in sorted(hier_labels.items()):
        if index == 0 or found[index].ref is None:
            for text in sorted(labels):
                out.append(
                    issue(
                        "drawn.sheet-pin-unmatched",
                        f"the hierarchical label {text} on the root sheet has no sheet pin to join",
                        f"{shown_root}:{text}",
                    )
                )
            continue
        for extra in sorted(labels - sheet_pins.get(index, set())):
            out.append(
                issue(
                    "drawn.sheet-pin-unmatched",
                    f"the hierarchical label {extra} on {found[index].path} has no sheet pin of that "
                    "name on its "
                    "reference",
                    f"{found[index].path}:{extra}",
                )
            )
    return _netlist(groups, elements, out)


def _netlist(groups: _Groups, elements: set[Element], issues: list[Issue]) -> DrawnNetlist:
    union = groups.union
    by_root: dict[object, list[Element]] = defaultdict(list)
    for element in elements:
        by_root[union.find(("E", element))].append(element)
    named: dict[object, list[tuple[int, int, str, str]]] = defaultdict(list)
    for node, names in groups.names.items():
        named[union.find(node)] += names
    nets: list[DrawnNet] = []
    open_pins: list[Element] = []
    for root, members in by_root.items():
        ordered = tuple(sorted(members, key=lambda e: (natural(e[0]), natural(e[1]))))
        names = named.get(root, [])
        if not names and len(ordered) == 1:
            open_pins.append(ordered[0])
            continue
        best = min(names) if names else None
        texts = tuple(sorted({text for _, _, _, text in names}))
        nets.append(DrawnNet(best[2] if best is not None else "", ordered, texts))
    nets.sort(key=lambda n: (natural(n.members[0][0]), natural(n.members[0][1])))
    pins = tuple(sorted(elements, key=lambda e: (natural(e[0]), natural(e[1]))))
    open_pins.sort(key=lambda e: (natural(e[0]), natural(e[1])))
    return DrawnNetlist(tuple(nets), pins, tuple(open_pins), tuple(issues))


def _mm(at: Point) -> str:
    def one(nm: int) -> str:
        sign = "-" if nm < 0 else ""
        whole, frac = divmod(abs(nm), 1_000_000)
        return f"{sign}{whole}" + (f".{f'{frac:06d}'.rstrip('0')}" if frac else "")

    return f"({one(at.x)}, {one(at.y)}) mm"


# --- comparison with the circuit ------------------------------------------------------------------


def component_path(component: Component) -> str:
    """The path of a component: its ``fenolite.path`` property, else its reference."""
    return component.properties.get(PATH_PROPERTY, component.ref)


def compare(netlist: DrawnNetlist, circuit: Circuit) -> tuple[Issue, ...]:
    """``drawn.netlist-differs`` for the first pin, in sorted ``REF-PIN`` order, whose group in the drawing
    differs from its group in the circuit (over the pins of drawn components; the reason is ``open``,
    ``split`` or ``merged``), and one ``drawn.net-name-differs`` per drawn net that equals a circuit net,
    carries labels and has no label of the circuit net's name."""
    components = {c.id: c for c in circuit.components}
    paths = {component_path(c): c for c in circuit.components}
    drawn_pins = set(netlist.pins)
    code_group: dict[Element, frozenset[Element]] = {}
    code_name: dict[Element, str] = {}
    for net in circuit.nets:
        members: set[Element] = set()
        for member in net.members:
            component = components.get(member.component_id)
            if component is None:
                continue
            path = component_path(component)
            for pad in component.pads_of(member.pin):
                if (path, pad) in drawn_pins:
                    members.add((path, pad))
        frozen = frozenset(members)
        for element in members:
            code_group[element] = frozen
            code_name[element] = net.name
    drawn_group: dict[Element, frozenset[Element]] = {}
    drawn_name: dict[Element, DrawnNet] = {}
    for net in netlist.nets:
        frozen = frozenset(net.members)
        for element in net.members:
            drawn_group[element] = frozen
            drawn_name[element] = net

    def ref_pin(element: Element) -> str:
        component = paths.get(element[0])
        return f"{component.ref if component is not None else element[0]}-{element[1]}"

    def shown(element: Element, groups: Mapping[Element, frozenset[Element]], name: str) -> str:
        group = groups.get(element)
        if group is None or len(group) <= 1:
            return "no net (open)" if group is None or not name else f"the net {name} alone"
        return f"the net {name or '(unnamed)'}"

    differences: list[tuple[tuple[object, ...], Issue]] = []
    for element in drawn_pins:
        theirs = code_group.get(element, frozenset({element}))
        ours = drawn_group.get(element, frozenset({element}))
        if theirs == ours:
            continue
        if len(ours) <= 1 < len(theirs):
            reason = "open"
        elif ours < theirs:
            reason = "split"
        elif ours > theirs:
            reason = "merged"
        else:
            reason = "merged" if ours - theirs else "split"
        drawn_net = drawn_name.get(element)
        text = (
            f"{ref_pin(element)} is on {shown(element, code_group, code_name.get(element, ''))} in "
            "code and on "
            f"{shown(element, drawn_group, drawn_net.name if drawn_net is not None else '')} in the drawing "
            f"({reason})"
        )
        key = (natural(ref_pin(element)),)
        differences.append((key, issue("drawn.netlist-differs", text, ref_pin(element), NETLIST_HINT)))
    found: list[Issue] = []
    if differences:
        differences.sort(key=lambda pair: pair[0])
        first = differences[0][1]
        more = f" (and {len(differences) - 1} more)" if len(differences) > 1 else ""
        found.append(
            issue(
                first.code,
                f"the drawing does not mean the code: {first.message}{more}",
                first.where,
                first.hint,
            )
        )
    seen: set[str] = set()
    for net in netlist.nets:
        if not net.labels or len(net.members) < 1:
            continue
        element = net.members[0]
        theirs = code_group.get(element)
        if theirs is None or theirs != frozenset(net.members):
            continue
        wanted = code_name.get(element, "")
        # a sheet written for KiCad stores a / of a label text as {slash} (``netnames.stored_name``)
        escaped = wanted.replace("/", "{slash}")
        if not wanted or wanted in net.labels or escaped in net.labels or wanted in seen:
            continue
        seen.add(wanted)
        found.append(
            issue(
                "drawn.net-name-differs",
                f"the net {wanted} of the code is named {', '.join(net.labels)} in the drawing; the "
                "board keeps "
                f"the code's name {wanted}",
                wanted,
                "rename the label, or the net in the code",
            )
        )
    return tuple(found)


# --- coverage -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UnitInfo:
    """What coverage needs of one code component with a resolved symbol: its unit count and the units
    with a pin on a net."""

    units: int
    on_net: frozenset[int] = frozenset()


def coverage(
    drawn: DrawnSchematic,
    circuit: Circuit,
    units: Mapping[str, UnitInfo],
) -> tuple[Issue, ...]:
    """The coverage issues of ``drawn`` against the components of ``circuit`` that ``units`` names (by
    path): every unit drawn once per instance (``drawn.symbol-missing``, or ``drawn.unit-missing`` for a
    unit with no pin on a net), every drawn part in code and drawn once (``drawn.part-unknown``), and equal
    values and footprints for the components one symbol of a repeated sheet stands for
    (``drawn.repeated-value-differs``). Parts of a ``generated`` sheet are left to the generator."""
    found_instances, _ = instances(drawn)
    paths = {component_path(c): c for c in circuit.components}
    drawn_units: dict[tuple[str, int], int] = defaultdict(int)
    issues: list[Issue] = []
    by_sheet: dict[str, list[DrawnInstance]] = defaultdict(list)
    generated_modules: list[str] = []
    for instance in found_instances:
        sheet = drawn.sheet(instance.sheet)
        if sheet is None:
            continue
        by_sheet[sheet.key].append(instance)
        if sheet.generated:
            generated_modules.append(instance.module)
            continue
        for symbol in sheet.symbols:
            path = instance.component(symbol.part)
            info = units.get(path)
            if info is None or symbol.unit > info.units:
                why = (
                    "no component of the code"
                    if path not in paths
                    else (
                        "a component without a symbol"
                        if info is None
                        else f"a symbol of {info.units} unit(s)"
                    )
                )
                issues.append(
                    issue(
                        "drawn.part-unknown",
                        f"the drawn symbol {symbol.part} unit {symbol.unit} on sheet {sheet.key} stands for "
                        f"{path}, {why}",
                        path,
                        "add the part to the code, or remove the symbol from the drawing",
                    )
                )
                continue
            drawn_units[(path, symbol.unit)] += 1
    for (path, unit), count in sorted(drawn_units.items()):
        if count > 1:
            issues.append(
                issue(
                    "drawn.part-unknown",
                    f"{path} unit {unit} is drawn {count} times; a unit is drawn once",
                    path,
                    "remove the extra symbols",
                )
            )
    for path in sorted(units, key=natural):
        if any(path == m or path.startswith(f"{m}/") for m in generated_modules if m) or (
            "" in generated_modules and "/" not in path
        ):
            continue
        info = units[path]
        component = paths.get(path)
        ref = component.ref if component is not None else path
        for unit in range(1, info.units + 1):
            if drawn_units.get((path, unit)):
                continue
            if unit in info.on_net:
                issues.append(
                    issue(
                        "drawn.symbol-missing",
                        f"{ref} ({path}) unit {unit} is in the code and not in the drawing",
                        path,
                        "draw the unit (fenolite sync --to-source after placing it in KiCad), or "
                        "remove the part",
                    )
                )
            else:
                issues.append(
                    issue(
                        "drawn.unit-missing",
                        f"{ref} ({path}) unit {unit} is not drawn; it has no pin on a net",
                        path,
                    )
                )
    for key, sheet_instances in by_sheet.items():
        if len(sheet_instances) < 2:
            continue
        sheet = drawn.sheet(key)
        if sheet is None or sheet.generated:
            continue
        for symbol in sheet.symbols:
            shown = [(i, paths.get(i.component(symbol.part))) for i in sheet_instances]
            present = [(i, c) for i, c in shown if c is not None]
            if len(present) < 2:
                continue
            for what in ("value", "footprint"):
                texts = [(i, c.value if what == "value" else c.lib_footprint_ref) for i, c in present]
                if len({t for _, t in texts}) > 1:
                    listing = ", ".join(f"{i.path or 'root'}: {t!r}" for i, t in texts)
                    issues.append(
                        issue(
                            "drawn.repeated-value-differs",
                            f"the symbol {symbol.part} of the repeated sheet {key} stands for "
                            "components whose "
                            f"{what} differs ({listing}); a repeated sheet carries one {what} per symbol",
                            f"{key}:{symbol.part}",
                            SPLIT_HINT,
                        )
                    )
    return tuple(issues)


__all__ = [
    "ISSUE_CODES",
    "DrawnNet",
    "DrawnNetlist",
    "Element",
    "PinKey",
    "PinPoint",
    "UnitInfo",
    "compare",
    "component_path",
    "coverage",
    "expand",
    "instances",
    "issue",
    "natural",
    "resolve",
]
