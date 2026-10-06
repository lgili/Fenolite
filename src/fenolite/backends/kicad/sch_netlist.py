# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own netlist of the schematic sheets it generated (capability ``kicad-schematic``, "Own
netlist of a generated sheet" and "Netlist grammar check"; changes c0063 and c0070).

On a generated sheet a pin is on the net whose global label lies on its connection point, or on the far
end of the one straight wire that starts there; a pin without either is on a net of its own, named as
KiCad names it (``netnames.unconnected_name``). Labels of one text are one net on every sheet of the
tree. So the netlist is read from the sheets alone, by coincidence of points, with the facts of
``docs/formats/kicad/schematic.md`` ("Generated sheets"). ``grammar_issues`` names everything that would
make this reading wrong: a junction or a bus, a wire that is not one segment from pin end to pin end, a
local label, a sheet used twice or not given, a symbol at another path than its sheet's, two pins on one
point, a hidden power pin. Sheets with any of them are refused, and their netlist is KiCad's to tell
(plan D9: Fenolite does not re-implement KiCad's connection graph). Nothing here reads the circuit model,
a file or a tool.
"""

from __future__ import annotations

import posixpath
from collections import defaultdict
from collections.abc import Mapping, Sequence
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
WIRE_HEADS: tuple[str, ...] = ("junction", "bus", "bus_entry", "bus_alias")
"""The root children that join points in a way Fenolite does not read. A ``wire`` is read, when it is one
straight segment from pin end to pin end."""
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


def _meet(first: Segment, second: Segment) -> bool:
    """Whether two straight wires have a point in common."""
    (a, b), (c, d) = first, second
    return max(min(a.x, b.x), min(c.x, d.x)) <= min(max(a.x, b.x), max(c.x, d.x)) and max(
        min(a.y, b.y), min(c.y, d.y)
    ) <= min(max(a.y, b.y), max(c.y, d.y))


class _Groups:
    """The points of one sheet joined by its wires: a point without a wire is a group of its own."""

    def __init__(self, wires: Sequence[Segment]) -> None:
        self._parent: dict[Point, Point] = {}
        self.wired: set[Point] = set()
        for start, end in wires:
            self._parent[self.of(end)] = self.of(start)
        self.wired = {self.of(point) for wire in wires for point in wire}

    def of(self, point: Point) -> Point:
        """The group of ``point``, named by one of its points."""
        parent = self._parent.setdefault(point, point)
        while parent != self._parent[parent]:
            parent = self._parent[parent]
        self._parent[point] = parent
        return parent


def _ref_pins(ref: SheetRef) -> int:
    """The number of pins of a sheet reference: a read reference keeps them as opaque ``pin`` slots, and a
    created one has none."""
    bag = ref.ext.get("kicad")
    slots = slotlib.from_ext(bag, ".") if bag is not None else ()
    return sum(1 for slot in slots if isinstance(slot, Opaque) and slot.fragment.startswith("(pin"))


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


def _tree(root: SchematicSheet, children: Mapping[str, SchematicSheet]) -> _Tree:
    found: list[tuple[str, SchematicSheet, str]] = [("", root, f"/{kicad_uuid(root)}")]
    problems: list[str] = []
    reached: dict[str, int] = {}
    index = 0
    while index < len(found):
        holder, sheet, path = found[index]
        index += 1
        for ref in sheet.sheets:
            key = _child_key(holder, ref.file)
            if _ref_pins(ref):
                problems.append(f"sheet reference {ref.name!r} has pins")
            if key not in children:
                problems.append(f"sheet reference {ref.name!r} names {key}, which is no sheet given")
                continue
            reached[key] = reached.get(key, 0) + 1
            if reached[key] > 1:
                problems.append(f"{key} is named by {reached[key]} sheet references")
                continue
            found.append((key, children[key], f"{path}/{kicad_uuid(ref)}"))
    problems += [f"no sheet reference names {key}" for key in children if key not in reached]
    return _Tree(tuple(found), tuple(problems))


def _sheet_issues(sheet: SchematicSheet, path: str, found: dict[str, tuple[str, str]]) -> None:
    """The reasons of one sheet, added to ``found`` (reason → message and sheet name) unless an earlier
    sheet gave them."""

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
    kinds = [label.name for label in sheet.labels if label.kind != "global"]
    if kinds:
        add("label-kind", f"{len(kinds)} label(s) are not global labels: {_shown(kinds)}")
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
    off = [label.name for label in sheet.labels if label.position not in at]
    if off and not undefined:  # the pins of an undefined symbol are not known, so neither is this
        add("label-off-pin", f"{len(off)} label(s) lie on no pin: {_shown(off)}")
    if not undefined:
        loose = sorted((end for wire in wires for end in wire if end not in at), key=_key)
        if loose:
            add("wire-end", f"{len(loose)} wire end(s) lie on no pin, the first at {_at(loose[0])}")
    touched: list[Point] = []
    for index, wire in enumerate(wires):
        inner = [p for p in (*at, *names) if _on(p, wire) and p not in wire]
        crossing = [other for other in wires[index + 1 :] if _meet(wire, other)]
        if inner or crossing:
            touched.append(min((*inner, *(end for other in crossing for end in other)), key=_key))
    if touched:
        add(
            "wire-touch",
            f"{len(touched)} wire(s) meet a pin, a label or another wire elsewhere than at their own two "
            f"ends, the first near {_at(min(touched, key=_key))}",
        )
    groups = _Groups(wires)
    texts: dict[Point, set[str]] = defaultdict(set)
    for point, found_names in names.items():
        texts[groups.of(point)] |= found_names
    double = sorted((point for point, found_names in texts.items() if len(found_names) > 1), key=_key)
    if double:
        listed = " and ".join(sorted(texts[double[0]]))
        add("two-names", f"labels of different names lie on one group: {listed} at {_at(double[0])}")
    bare = sorted((point for point in groups.wired if not texts.get(point)), key=_key)
    if bare:
        add("wire-unlabelled", f"{len(bare)} wired group(s) carry no label, the first at {_at(bare[0])}")
    shared: list[str] = []
    for point, group in sorted(at.items(), key=lambda item: _key(item[0])):
        instances = {id(pin.instance) for pin in group}
        if len(instances) > 1 or (len(group) > 1 and not names.get(point)):
            shared.append(" and ".join(sorted({f"{pin.ref}-{pin.pin.number}" for pin in group})))
    if shared:
        add("shared-point", f"several pins connect at one point without a label of their own: {shared[0]}")
    frames = [i.ref for i in sheet.symbols if _frame(i) not in schlayout.PROVED_FRAMES]
    if frames:
        add("frame", f"the rotation and mirror of {_shown(frames)} were not measured")
    used = {id(pin.definition): pin.definition for pin in pins}.values()
    power = [d.lib_id for d in used if d.power and d.lib_id != FLAG_LIB_ID]
    hidden = [
        f"{d.lib_id} pin {pin.number}"
        for d in used
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
    for _, member, path in tree.sheets:
        _sheet_issues(member, path, found)
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
    nets: dict[str, dict[tuple[str, str], NetNode]] = defaultdict(dict)
    placed: set[tuple[str, str]] = set()
    for member in sheets:
        groups = _Groups(_wires(member)[0])
        labels = {groups.of(label.position): netnames.stored_name(label.name) for label in member.labels}
        flagged = {flag.position for flag in member.no_connects}
        for pin in _pins(member, project):
            key = (pin.ref, pin.pin.number)
            if not pin.ref or pin.ref.startswith("#") or key in placed:
                continue
            if not any(use.project == project for use in pin.instance.uses):
                continue
            placed.add(key)
            name = labels.get(groups.of(pin.point))
            if name is None:
                name = netnames.unconnected_name(
                    pin.ref,
                    unit=pin.instance.unit,
                    unit_count=pin.definition.unit_count,
                    pin_name=pin.pin.name,
                    pad_number=pin.pin.number,
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
    "HINT",
    "ISSUE_CODES",
    "REASONS",
    "WIRE_HEADS",
    "NetlistUnsupportedError",
    "grammar_issues",
    "own_netlist",
]
