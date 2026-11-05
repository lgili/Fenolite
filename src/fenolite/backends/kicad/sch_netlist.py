# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own netlist of the schematic sheets it generated (capability ``kicad-schematic``, "Own
netlist of a generated sheet" and "Netlist grammar check"; changes c0063, c0070 and c0406).

On a generated sheet a pin is on the net of the group of points it rests on: straight wires join their two
ends, a junction joins every wire that ends on it, a global label joins the wire it lies on, and a pin of
one of Fenolite's own power symbols names its group like a global label of the instance's Value (change
c0406). A group with no name is a net of its own, named as KiCad names it (``netnames.unconnected_name``).
Labels of one text are one net on every sheet of the tree. So the netlist is read from the sheets alone, by
coincidence of points, with the facts of ``docs/formats/kicad/schematic.md`` ("Generated sheets").
``grammar_issues`` names everything that would make this reading wrong: a bus, a wire that is not one
segment, a wire end on nothing, a pin, junction or wire end inside a wire, a local label, a sheet used
twice or not given, a symbol at another path than its sheet's, two pins on one point, a hidden power pin
of another symbol. Sheets with any of them are refused, and their netlist is KiCad's to tell (plan D9:
Fenolite does not re-implement KiCad's connection graph). Nothing here reads the circuit model, a file or
a tool.
"""

from __future__ import annotations

import posixpath
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import netnames, sch, schlayout, symembed
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.netlist import (
    NO_CONNECT_SUFFIX,
    KicadNetlist,
    NetComponent,
    NetlistNet,
    NetNode,
    build_netlist,
)
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.base import Opaque
from fenolite.model.library import SymbolDef, SymbolPin
from fenolite.model.schematic import SchematicSheet, SheetRef, SymbolInstance

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED, hypotheses=("H-K-NETLIST-OWN", "H-K-SCH-HIER-FILE", "H-K-SCH-WIRE-END")
)
"""``KICAD-VERIFIED``: ``H-K-NETLIST-OWN`` holds on 9.0.9 and 10.0.6 for the sheets ``build`` writes (c0063
task 8.2), and the two rows of c0070 hold for the sheet tree and the wires. It says nothing of a sheet
outside the grammar, which ``own_netlist`` refuses."""
STACKED_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-SCH-STACKED",))
"""What a netlist rests on besides ``EVIDENCE`` when a sheet holds stacked pins: pins of one symbol
instance that have one name and connect at one point (a pin bonded to several pads, change c0123)."""
STACKED_OPEN_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-SCH-STACKED-OPEN",))
"""And when such a stack carries no label: KiCad makes one net of it and names it after one of its pads."""
FRAME_ORDER_EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-SCH-PINFRAME-ORDER",))
"""What a netlist rests on besides ``EVIDENCE`` when a symbol instance is mirrored and turned by 90 or 270
degrees: KiCad turns the symbol first and mirrors the turned symbol, read from the demo sheets of the
corpus and confirmed by ``kicad-cli`` 9.0.9 and 10.0.6 on an authored sheet (change c0137). For 0 and 180
degrees the order does not matter."""
CODE = "kicad.sch.netlist-unsupported"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({CODE: "error"})
"""The one code of this module; the closed set of the reader (``sch.ISSUE_CODES``) is not widened."""
REASONS: tuple[str, ...] = (
    "wire",
    "wire-shape",
    "wire-end",
    "wire-touch",
    "label-kind",
    "sheet",
    "undefined-symbol",
    "label-off-pin",
    "two-names",
    "wire-unlabelled",
    "shared-point",
    "frame",
    "hidden-power",
)
"""Every reason of ``grammar_issues``, in the order they are reported."""
WIRE_HEADS: tuple[str, ...] = ("bus", "bus_entry", "bus_alias")
"""The root children that join points in a way Fenolite does not read. A ``wire`` is read when it is one
straight segment, and a ``junction`` joins the wires that end on it (change c0406)."""
NO_CHILDREN: Mapping[str, SchematicSheet] = MappingProxyType({})
FLAG_LIB_ID = f"{symembed.FLAG_LIBRARY}:{symembed.FLAG_NAME}"
HINT = "kicad-cli reads wires, sheets and power symbols: run `fenolite netlist --source kicad`"
NOT_FIELDS: frozenset[str] = frozenset({"Reference", "Value"})
"""Properties that KiCad's export does not list under ``fields``."""
SHOWN = 3


class NetlistUnsupportedError(FenoliteError):
    """The sheet is outside the grammar of the own netlist; ``issues`` holds one per reason (FEN-7001)."""

    cli_code = "FEN-7001"

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        self.hint = HINT
        reasons = ", ".join(issue.message.split(":", 1)[0] for issue in self.issues)
        super().__init__(f"Fenolite does not read the nets of this sheet itself ({reasons})")


@dataclass(frozen=True, slots=True)
class _Pin:
    """A pin of a placed unit: where it connects, and what the netlist says of it."""

    instance: SymbolInstance
    definition: SymbolDef
    pin: SymbolPin
    ref: str
    point: Point


def _definitions(sheet: SchematicSheet) -> dict[str, SymbolDef]:
    return {definition.lib_id: definition for definition in sheet.lib_symbols}


def _definition(instance: SymbolInstance, known: dict[str, SymbolDef]) -> SymbolDef | None:
    found = known.get(instance.lib_name or instance.lib_ref)
    return None if found is None or found.extends else found


def _ref(instance: SymbolInstance, project: str | None) -> str:
    """The reference of ``instance`` in ``project``: that of its use there, else of its only use, else its
    ``Reference`` property."""
    uses = [use for use in instance.uses if project is None or use.project == project]
    return uses[0].ref if uses else instance.ref


def _frame(instance: SymbolInstance) -> tuple[int, str]:
    return ((instance.rotation // 1_000_000) % 360, instance.mirror)


def _pins(sheet: SchematicSheet, project: str | None) -> list[_Pin]:
    """Every pin of every placed unit whose definition the sheet embeds, power flags included."""
    known = _definitions(sheet)
    found: list[_Pin] = []
    for instance in sheet.symbols:
        definition = _definition(instance, known)
        if definition is None:
            continue
        rotation, mirror = _frame(instance)
        ref = _ref(instance, project)
        for pin in definition.pins_of(instance.unit, instance.body_style):
            point = schlayout.pin_point(instance.position, pin.position, rotation, mirror)
            found.append(_Pin(instance, definition, pin, ref, point))
    return found


def _shown(items: Sequence[str]) -> str:
    listed = sorted(set(items), key=schlayout.natural_key)
    return ", ".join(listed[:SHOWN]) + (", …" if len(listed) > SHOWN else "")


def _at(point: Point) -> str:
    return f"({point.x}, {point.y}) nm"


def _key(point: Point) -> tuple[int, int]:
    return (point.x, point.y)


Segment = tuple[Point, Point]


def _wires(sheet: SchematicSheet) -> tuple[list[Segment], int]:
    """The wires of ``sheet`` as two-point segments, and the number of wires that are none: the wires a
    created sheet holds, and for a read sheet the ``wire`` children its reader kept as slots. A wire of
    another shape (more or fewer points, slanted, a point) is counted and left out."""
    found: list[Segment] = [(wire.start, wire.end) for wire in sheet.wires]
    odd = 0
    for points in sch.opaque_wires(sheet):
        if len(points) != 2:
            odd += 1
            continue
        found.append((points[0], points[1]))
    straight = [(a, b) for a, b in found if a != b and (a.x == b.x or a.y == b.y)]
    return straight, odd + len(found) - len(straight)


def _on(point: Point, wire: Segment) -> bool:
    """Whether ``point`` lies on the straight ``wire``, its ends included."""
    a, b = wire
    return min(a.x, b.x) <= point.x <= max(a.x, b.x) and min(a.y, b.y) <= point.y <= max(a.y, b.y)


class _Groups:
    """The points of one sheet joined by its wires: a point without a wire is a group of its own. A
    junction joins every wire it lies on, and each of ``attached`` (the label points) joins the wires on
    whose inside it lies (change c0406); two wires that only cross are not joined."""

    def __init__(
        self, wires: Sequence[Segment], junctions: Iterable[Point] = (), attached: Iterable[Point] = ()
    ) -> None:
        self._parent: dict[Point, Point] = {}
        self.wired: set[Point] = set()
        for start, end in wires:
            self._union(start, end)
        lines = _Lines(wires)
        for point in (*junctions, *attached):
            for wire in lines.through(point):
                self._union(wire[0], point)
        self.wired = {self.of(point) for wire in wires for point in wire}

    def _union(self, first: Point, second: Point) -> None:
        a, b = self.of(first), self.of(second)
        if a != b:
            self._parent[b] = a

    def of(self, point: Point) -> Point:
        """The group of ``point``, named by one of its points."""
        parent = self._parent.setdefault(point, point)
        while parent != self._parent[parent]:
            parent = self._parent[parent]
        self._parent[point] = parent
        return parent


class _Lines:
    """The straight wires of one sheet bucketed by their line, to find the wires through a point."""

    def __init__(self, wires: Sequence[Segment]) -> None:
        self.rows: dict[int, list[Segment]] = defaultdict(list)
        self.columns: dict[int, list[Segment]] = defaultdict(list)
        for wire in wires:
            a, b = wire
            if a.y == b.y:
                self.rows[a.y].append(wire)
            if a.x == b.x:
                self.columns[a.x].append(wire)

    def through(self, point: Point) -> list[Segment]:
        """The wires that ``point`` lies on, their ends included."""
        found = [w for w in self.rows.get(point.y, ()) if _on(point, w)]
        return found + [w for w in self.columns.get(point.x, ()) if _on(point, w) and w not in found]

    def inside(self, point: Point) -> list[Segment]:
        """The wires on whose inside ``point`` lies (not at one of their ends)."""
        return [w for w in self.through(point) if point not in w]


def _junctions(sheet: SchematicSheet) -> set[Point]:
    """The junction points of ``sheet``: those of a created sheet, and for a read sheet the ``junction``
    children its reader kept as slots."""
    return {j.position for j in sheet.junctions} | {at for at, _ in sch.opaque_drawing(sheet).junctions}


def _groups(sheet: SchematicSheet) -> _Groups:
    """The groups of ``sheet``: its wires, its junctions and its labels on the inside of wires."""
    return _Groups(_wires(sheet)[0], _junctions(sheet), (label.position for label in sheet.labels))


def _power_names(sheet: SchematicSheet) -> list[tuple[Point, str]]:
    """(pin point, net name) of each instance of Fenolite's own power symbols on ``sheet``: such a pin joins
    its point like a global label whose text is the instance's Value (change c0406)."""
    known = _definitions(sheet)
    found: list[tuple[Point, str]] = []
    for instance in sheet.symbols:
        if not symembed.is_power_symbol(instance.lib_ref):
            continue
        definition = _definition(instance, known)
        if definition is None:
            continue
        rotation, mirror = _frame(instance)
        for pin in definition.pins_of(instance.unit, instance.body_style):
            point = schlayout.pin_point(instance.position, pin.position, rotation, mirror)
            found.append((point, netnames.stored_name(instance.value)))
    return found


def _ref_pins(ref: SheetRef) -> list[tuple[str, Point]]:
    """(name, point) of each pin of a sheet reference: a created reference holds them in ``pins``, and a
    read one keeps them as opaque ``pin`` slots (``sch.opaque_sheet_pins``, change c0269)."""
    found = [(pin.name, pin.position) for pin in ref.pins]
    found += [(name, point) for name, _, point, _ in sch.opaque_sheet_pins(ref)]
    return found


def _odd_pins(ref: SheetRef) -> int:
    """The opaque ``pin`` slots of a read reference that ``sch.opaque_sheet_pins`` cannot read."""
    bag = ref.ext.get("kicad")
    slots = slotlib.from_ext(bag, ".") if bag is not None else ()
    count = sum(1 for slot in slots if isinstance(slot, Opaque) and slot.fragment.startswith("(pin"))
    return count - len(sch.opaque_sheet_pins(ref))


def _on_edge(point: Point, ref: SheetRef) -> bool:
    """Whether ``point`` lies on an edge of the box of ``ref``."""
    x0, y0 = ref.position.x, ref.position.y
    x1, y1 = x0 + ref.size.w, y0 + ref.size.h
    inside = x0 <= point.x <= x1 and y0 <= point.y <= y1
    return inside and (point.x in (x0, x1) or point.y in (y0, y1))


def _child_key(holder: str, file: str) -> str:
    """The path of a child sheet from the root file's folder: ``file`` as the sheet at ``holder`` names
    it, resolved from that sheet's own folder (``H-K-SCH-HIER-FILE``)."""
    folder = posixpath.dirname(holder)
    return posixpath.normpath(posixpath.join(folder, file.replace("\\", "/")))


@dataclass(frozen=True)
class _Tree:
    """The sheets of a hierarchy, the root first: per sheet its key (``""`` for the root) and the instance
    path of its symbols; and what is wrong with the references."""

    sheets: tuple[tuple[str, SchematicSheet, str], ...]
    problems: tuple[str, ...]
    links: tuple[tuple[int, SheetRef] | None, ...] = ()
    """Per sheet, the index of the sheet that names it and the reference there; ``None`` for the root."""


def _tree(root: SchematicSheet, children: Mapping[str, SchematicSheet]) -> _Tree:
    found: list[tuple[str, SchematicSheet, str]] = [("", root, f"/{kicad_uuid(root)}")]
    links: list[tuple[int, SheetRef] | None] = [None]
    problems: list[str] = []
    reached: dict[str, int] = {}
    index = 0
    while index < len(found):
        holder, sheet, path = found[index]
        index += 1
        for ref in sheet.sheets:
            key = _child_key(holder, ref.file)
            pins = _ref_pins(ref)
            names = [name for name, _ in pins]
            twice = sorted({name for name in names if names.count(name) > 1})
            if twice:
                problems.append(f"sheet reference {ref.name!r} has two sheet pins named {', '.join(twice)}")
            off = sorted(name for name, point in pins if not _on_edge(point, ref))
            if off:
                problems.append(f"sheet pin(s) {', '.join(off)} of {ref.name!r} lie off the edge of its box")
            if _odd_pins(ref):
                problems.append(f"sheet reference {ref.name!r} has a pin Fenolite cannot read")
            if key not in children:
                problems.append(f"sheet reference {ref.name!r} names {key}, which is no sheet given")
                continue
            reached[key] = reached.get(key, 0) + 1
            if reached[key] > 1:
                problems.append(f"{key} is named by {reached[key]} sheet references")
                continue
            found.append((key, children[key], f"{path}/{kicad_uuid(ref)}"))
            links.append((index - 1, ref))
            child = children[key]
            labels = {label.name for label in child.labels if label.kind == "hierarchical"}
            for name in sorted(set(names) - labels):
                problems.append(
                    f"the sheet pin {name} of {ref.name!r} has no hierarchical label of that name on {key}"
                )
            for name in sorted(labels - set(names)):
                problems.append(
                    f"the hierarchical label {name} of {key} has no sheet pin of that name on {ref.name!r}"
                )
    problems += [f"no sheet reference names {key}" for key in children if key not in reached]
    return _Tree(tuple(found), tuple(problems), tuple(links))


def _sheet_issues(
    sheet: SchematicSheet, path: str, found: dict[str, tuple[str, str]], *, root: bool = False
) -> None:
    """The reasons of one sheet, added to ``found`` (reason → message and sheet name) unless an earlier
    sheet gave them; ``root`` tells the root sheet, which holds no hierarchical label."""

    def add(reason: str, message: str) -> None:
        found.setdefault(reason, (message, sheet.name))

    heads = sch.opaque_heads(sheet)
    other = {head: heads[head] for head in WIRE_HEADS if heads[head]}
    if other:
        listed = ", ".join(f"{count} {head}" for head, count in other.items())
        add("wire", f"the sheet holds {listed}; Fenolite reads straight wires from pin to pin only")
    wires, odd = _wires(sheet)
    if odd:
        add("wire-shape", f"{odd} wire(s) are not one horizontal or vertical segment between two points")
    kinds = [label.name for label in sheet.labels if label.kind not in ("global", "hierarchical")]
    if kinds:
        add("label-kind", f"{len(kinds)} label(s) are neither global nor hierarchical: {_shown(kinds)}")
    upper = [label.name for label in sheet.labels if label.kind == "hierarchical" and root]
    if upper:
        add("label-kind", f"{len(upper)} hierarchical label(s) on the root sheet: {_shown(upper)}")
    several = [instance.ref for instance in sheet.symbols if len(instance.uses) > 1]
    if several:
        add("sheet", f"symbol(s) with more than one use: {_shown(several)}; no sheet may be used twice")
    elsewhere = [i.ref for i in sheet.symbols if len(i.uses) == 1 and i.uses[0].path != path]
    if elsewhere:
        add("sheet", f"symbol(s) used at another path than their sheet's ({path}): {_shown(elsewhere)}")
    known = _definitions(sheet)
    undefined = [i.lib_name or i.lib_ref for i in sheet.symbols if _definition(i, known) is None]
    if undefined:
        add(
            "undefined-symbol",
            f"the sheet embeds no flat definition of {_shown(undefined)}, so the pins are not known",
        )
    pins = _pins(sheet, None)
    at: dict[Point, list[_Pin]] = defaultdict(list)
    for pin in pins:
        at[pin.point].append(pin)
    names: dict[Point, set[str]] = defaultdict(set)
    for label in sheet.labels:
        names[label.position].add(label.name)
    powers = _power_names(sheet)
    lines = _Lines(wires)
    junctions = _junctions(sheet)
    sheet_pins = {point for ref in sheet.sheets for _, point in _ref_pins(ref)}
    off = [
        label.name
        for label in sheet.labels
        if label.position not in at and label.position not in sheet_pins and not lines.through(label.position)
    ]
    if off and not undefined:  # the pins of an undefined symbol are not known, so neither is this
        add("label-off-pin", f"{len(off)} label(s) lie on no pin and no wire: {_shown(off)}")
    ends: dict[Point, int] = defaultdict(int)
    for wire in wires:
        for end in wire:
            ends[end] += 1
    if not undefined:
        loose = sorted(
            (end for end, count in ends.items() if end not in at and end not in junctions and count < 2),
            key=_key,
        )
        if loose:
            add(
                "wire-end",
                f"{len(loose)} wire end(s) lie on no pin, no other wire end and no junction, the first at "
                f"{_at(loose[0])}",
            )
    touched: list[Point] = []
    for point in sorted({*at, *junctions, *ends}, key=_key):
        if lines.inside(point):
            touched.append(point)
    for line in (*lines.rows.values(), *lines.columns.values()):
        spans = sorted(((min(a.x, b.x), min(a.y, b.y)), (max(a.x, b.x), max(a.y, b.y))) for a, b in line)
        for (_, high), (low, _) in zip(spans, spans[1:], strict=False):
            if low < high:  # two wires of one line that share a stretch
                touched.append(Point(*low))
    if touched:
        add(
            "wire-touch",
            f"{len(touched)} wire(s) hold a pin, a junction or another wire's end on their inside, or share "
            f"a stretch, the first near {_at(min(touched, key=_key))}",
        )
    groups = _Groups(wires, junctions, names)
    texts: dict[Point, set[str]] = defaultdict(set)
    for point, found_names in names.items():
        texts[groups.of(point)] |= found_names
    for point, power_name in powers:
        texts[groups.of(point)].add(power_name)
    double = sorted((point for point, found_names in texts.items() if len(found_names) > 1), key=_key)
    if double:
        listed = " and ".join(sorted(texts[double[0]]))
        add("two-names", f"labels of different names lie on one group: {listed} at {_at(double[0])}")
    bare = sorted((point for point in groups.wired if not texts.get(point)), key=_key)
    if bare:
        add("wire-unlabelled", f"{len(bare)} wired group(s) carry no label, the first at {_at(bare[0])}")
    shared: list[str] = []
    for point, group in sorted(at.items(), key=lambda item: _key(item[0])):
        if any(symembed.is_power_symbol(pin.definition.lib_id) for pin in group):
            continue  # a power symbol's pin on a pin joins it like a label (change c0406)
        instances = {id(pin.instance) for pin in group}
        stacked = len({pin.pin.name for pin in group}) == 1  # pins of one name: one net (c0123)
        if len(instances) > 1 or (len(group) > 1 and not names.get(point) and not stacked):
            shared.append(" and ".join(sorted({f"{pin.ref}-{pin.pin.number}" for pin in group})))
    if shared:
        add("shared-point", f"several pins connect at one point without a label of their own: {shared[0]}")
    frames = [i.ref for i in sheet.symbols if _frame(i) not in schlayout.PROVED_FRAMES]
    if frames:
        add("frame", f"the rotation and mirror of {_shown(frames)} were not measured")
    used = {id(pin.definition): pin.definition for pin in pins}.values()
    own = [d for d in used if not symembed.is_power_symbol(d.lib_id)]  # read like labels (change c0406)
    power = [d.lib_id for d in own if d.power and not symembed.is_power_flag(d.lib_id)]
    hidden = [
        f"{d.lib_id} pin {pin.number}"
        for d in own
        for pin in d.pins
        if pin.hidden and pin.etype == "power_in"
    ]
    if power or hidden:
        parts = [f"power symbol(s) {_shown(power)}"] if power else []
        parts += [f"hidden power input(s) {_shown(hidden)}"] if hidden else []
        add("hidden-power", f"{'; '.join(parts)}: KiCad joins such pins by name, not by label")


def grammar_issues(
    sheet: SchematicSheet, *, children: Mapping[str, SchematicSheet] = NO_CHILDREN
) -> tuple[Issue, ...]:
    """One ``kicad.sch.netlist-unsupported`` error per reason that keeps Fenolite from reading the nets of
    ``sheet`` and of the child sheets it names, the reason first in the message; ``()`` for sheets it can
    read. ``children`` maps the path of each child sheet, from the root file's folder, to that sheet."""
    found: dict[str, tuple[str, str]] = {}
    tree = _tree(sheet, children)
    if tree.problems:
        listed = "; ".join(tree.problems)
        found["sheet"] = (f"{listed}; Fenolite reads a tree whose every sheet is given once", sheet.name)
    for index, (_, member, path) in enumerate(tree.sheets):
        _sheet_issues(member, path, found, root=index == 0)
    return tuple(
        Issue(CODE, ISSUE_CODES[CODE], f"{reason}: {found[reason][0]}", where=found[reason][1], hint=HINT)
        for reason in REASONS
        if reason in found
    )


def _components(sheets: Sequence[SchematicSheet], project: str) -> tuple[NetComponent, ...]:
    """``sch.components`` of the sheets, each with the properties of its symbol of the lowest unit."""
    properties: dict[str, tuple[int, dict[str, str]]] = {}
    for sheet in sheets:
        for instance in sheet.symbols:
            for use in instance.uses:
                if use.project != project:
                    continue
                known = properties.get(use.ref)
                if known is None or use.unit < known[0]:
                    fields = {k: v for k, v in instance.properties.items() if k not in NOT_FIELDS}
                    properties[use.ref] = (use.unit, fields)
    return tuple(
        NetComponent(c.ref, c.value, c.footprint, MappingProxyType(properties.get(c.ref, (0, {}))[1]))
        for c in sch.components(sheets, project=project)
    )


def stack_evidence(sheets: Iterable[SchematicSheet]) -> tuple[Evidence, ...]:
    """The evidence that the stacked pins of ``sheets`` add to ``EVIDENCE``: ``STACKED_EVIDENCE`` when a
    symbol instance has several pins of one name at one point, and ``STACKED_OPEN_EVIDENCE`` too when such
    a point carries no label. ``()`` for sheets without a stack, so that the evidence of a design whose
    pins have one pad each is ``EVIDENCE`` itself, as before stacked pins were read."""
    stacked = opened = False
    for sheet in sheets:
        groups = _groups(sheet)
        labelled = {groups.of(label.position) for label in sheet.labels}
        labelled |= {groups.of(point) for point, _ in _power_names(sheet)}
        seen: dict[tuple[int, Point, str], str] = {}
        for pin in _pins(sheet, None):
            key = (id(pin.instance), pin.point, pin.pin.name)
            if seen.setdefault(key, pin.pin.number) != pin.pin.number:
                stacked = True
                opened = opened or groups.of(pin.point) not in labelled
    found = (STACKED_EVIDENCE,) if stacked else ()
    return (*found, STACKED_OPEN_EVIDENCE) if opened else found


def frame_evidence(sheets: Iterable[SchematicSheet]) -> tuple[Evidence, ...]:
    """``(FRAME_ORDER_EVIDENCE,)`` when an instance of ``sheets`` is mirrored and turned by 90 or 270
    degrees, the only frames whose pin points depend on the order of the two operations; ``()`` otherwise,
    so that the evidence of a sheet without such an instance is the one it was."""
    for sheet in sheets:
        for instance in sheet.symbols:
            rotation, mirror = _frame(instance)
            if mirror and rotation in (90, 270):
                return (FRAME_ORDER_EVIDENCE,)
    return ()


def evidence_of(sheet: SchematicSheet, children: Mapping[str, SchematicSheet] = NO_CHILDREN) -> Evidence:
    """The evidence of ``own_netlist(sheet, children=children)``: ``EVIDENCE``, combined with
    ``stack_evidence`` of the sheets when they hold stacked pins and ``frame_evidence`` when they hold a
    mirrored and turned instance (lowest level wins, ids listed)."""
    sheets = (sheet, *children.values())
    extra = (*stack_evidence(sheets), *frame_evidence(sheets))
    return Evidence.combine(EVIDENCE, *extra) if extra else EVIDENCE


class _Joined:
    """The groups of every sheet of a tree joined through hierarchical labels and sheet pins (change
    c0269): within a sheet, groups with hierarchical labels of one text are one, and joined to the group of
    the sheet pin of that name on the reference to that sheet. A joined set is named by its global label."""

    def __init__(self) -> None:
        self._parent: dict[tuple[int, Point], tuple[int, Point]] = {}
        self.globals: dict[tuple[int, Point], set[str]] = defaultdict(set)
        self.texts: dict[tuple[int, Point], str] = {}
        self._names: dict[tuple[int, Point], str] | None = None

    def of(self, node: tuple[int, Point]) -> tuple[int, Point]:
        parent = self._parent.setdefault(node, node)
        while parent != self._parent[parent]:
            parent = self._parent[parent]
        self._parent[node] = parent
        return parent

    def join(self, first: tuple[int, Point], second: tuple[int, Point]) -> None:
        a, b = self.of(first), self.of(second)
        if a != b:
            self._parent[b] = a

    def name(self, index: int, group: Point) -> str:
        """The net name of the group ``group`` of the sheet ``index``: the text of a global label of its
        joined set (the least in code-point order when several), else ``/<sheet key>/<label text>``."""
        if self._names is None:
            self._names = {}
            for node, texts in self.globals.items():
                root = self.of(node)
                least = min(texts)
                known = self._names.get(root)
                self._names[root] = least if known is None else min(known, least)
        found = self._names.get(self.of((index, group)))
        return found if found is not None else self.texts.get((index, group), "")


def _joined(tree: _Tree) -> _Joined:
    joined = _Joined()
    hier: dict[tuple[int, str], list[tuple[int, Point]]] = defaultdict(list)
    groups: list[_Groups] = []
    for index, (key, member, _) in enumerate(tree.sheets):
        found = _groups(member)
        groups.append(found)
        for point, power_name in _power_names(member):
            node = (index, found.of(point))
            joined.globals[node].add(power_name)
            joined.texts.setdefault(node, power_name)
        for label in member.labels:
            node = (index, found.of(label.position))
            joined.of(node)
            if label.kind == "hierarchical":
                hier[(index, label.name)].append(node)
                joined.texts.setdefault(node, f"/{key}/{label.name}")
            else:
                joined.globals[node].add(netnames.stored_name(label.name))
                joined.texts.setdefault(node, netnames.stored_name(label.name))
    for nodes in hier.values():
        for node in nodes[1:]:
            joined.join(nodes[0], node)
    for index, link in enumerate(tree.links):
        if link is None:
            continue
        parent, ref = link
        for name, point in _ref_pins(ref):
            for node in hier.get((index, name), ()):
                joined.join((parent, groups[parent].of(point)), node)
    return joined


def own_netlist(
    sheet: SchematicSheet, *, project: str, children: Mapping[str, SchematicSheet] = NO_CHILDREN
) -> KicadNetlist:
    """The netlist of ``sheet`` and of the child sheets it names, for the uses of ``project``, read from
    the sheets alone.

    Every pin of a placed unit whose reference does not start with ``#`` is a node. On one sheet a wire
    joins the points at its two ends; the nodes of every group that carries a global label of one text, on
    any sheet, are the net of that name (``netnames.stored_name`` of the text), and a node whose group
    has no label is a net of its own, named by ``netnames.unconnected_name``. The ``pintype`` is the
    electrical type of the pin, followed by ``+no_connect`` under a no-connect flag. ``children`` maps the
    path of each child sheet, from the root file's folder, to that sheet. Sheets outside the grammar
    raise ``NetlistUnsupportedError`` with the issues of ``grammar_issues``.
    """
    issues = grammar_issues(sheet, children=children)
    if issues:
        raise NetlistUnsupportedError(issues)
    sheets = (sheet, *children.values())
    tree = _tree(sheet, children)
    joined = _joined(tree)
    nets: dict[str, dict[tuple[str, str], NetNode]] = defaultdict(dict)
    placed: set[tuple[str, str]] = set()
    for index, (_, member, _) in enumerate(tree.sheets):
        groups = _groups(member)
        labels = {
            groups.of(label.position): joined.name(index, groups.of(label.position))
            for label in member.labels
        }
        for point, _ in _power_names(member):
            labels[groups.of(point)] = joined.name(index, groups.of(point))
        flagged = {flag.position for flag in member.no_connects}
        pins = _pins(member, project)
        stacks: dict[tuple[int, Point, str], list[str]] = defaultdict(list)
        for pin in pins:
            stacks[(id(pin.instance), pin.point, pin.pin.name)].append(pin.pin.number)
        for pin in pins:
            key = (pin.ref, pin.pin.number)
            if not pin.ref or pin.ref.startswith("#") or key in placed:
                continue
            if not any(use.project == project for use in pin.instance.uses):
                continue
            placed.add(key)
            name = labels.get(groups.of(pin.point))
            if name is None:
                name = netnames.open_name(
                    pin.ref,
                    unit=pin.instance.unit,
                    unit_count=pin.definition.unit_count,
                    pin_name=pin.pin.name,
                    # stacked pins without a label are one net, named after one of them
                    pads=stacks[(id(pin.instance), pin.point, pin.pin.name)],
                    marked=pin.point in flagged,
                )
            suffix = NO_CONNECT_SUFFIX if pin.point in flagged else ""
            nets[name][key] = NetNode(pin.ref, pin.pin.number, f"{pin.pin.etype}{suffix}")
    return build_netlist(
        _components(sheets, project),
        (NetlistNet(name, "", tuple(nodes.values())) for name, nodes in nets.items()),
    )


__all__ = [
    "CODE",
    "EVIDENCE",
    "FRAME_ORDER_EVIDENCE",
    "STACKED_EVIDENCE",
    "STACKED_OPEN_EVIDENCE",
    "HINT",
    "ISSUE_CODES",
    "REASONS",
    "WIRE_HEADS",
    "NetlistUnsupportedError",
    "evidence_of",
    "frame_evidence",
    "grammar_issues",
    "own_netlist",
    "stack_evidence",
]
