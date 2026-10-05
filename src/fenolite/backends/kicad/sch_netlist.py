# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own netlist of a schematic sheet it generated (capability ``kicad-schematic``, "Own netlist
of a generated sheet" and "Netlist grammar check"; change c0063).

A generated sheet holds no wire: a pin is on the net whose global label lies on its connection point, and
a pin without a label is on a net of its own, named as KiCad names it (``netnames.unconnected_name``). So
the netlist is read from the sheet alone, by coincidence of points, with the facts of
``docs/formats/kicad/schematic.md`` ("Generated sheets"). ``grammar_issues`` names everything that would
make this reading wrong: a wire, a local label, a sub-sheet, two pins on one point, a hidden power pin.
A sheet with any of them is refused, and its netlist is KiCad's to tell (plan D9: Fenolite does not
re-implement KiCad's connection graph). Nothing here reads the circuit model, a file or a tool.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import netnames, sch, schlayout, symembed
from fenolite.backends.kicad.netlist import (
    NO_CONNECT_SUFFIX,
    KicadNetlist,
    NetComponent,
    NetlistNet,
    NetNode,
    build_netlist,
)
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.library import SymbolDef, SymbolPin
from fenolite.model.schematic import SchematicSheet, SymbolInstance

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-NETLIST-OWN",))
"""``KICAD-VERIFIED``: ``H-K-NETLIST-OWN`` holds on 9.0.9 and 10.0.6 for the sheets ``build`` writes (c0063
task 8.2). It says nothing of a sheet outside the grammar, which ``own_netlist`` refuses."""
CODE = "kicad.sch.netlist-unsupported"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({CODE: "error"})
"""The one code of this module; the closed set of the reader (``sch.ISSUE_CODES``) is not widened."""
REASONS: tuple[str, ...] = (
    "wire",
    "label-kind",
    "sheet",
    "undefined-symbol",
    "label-off-pin",
    "two-names",
    "shared-point",
    "frame",
    "hidden-power",
)
"""Every reason of ``grammar_issues``, in the order they are reported."""
WIRE_HEADS: tuple[str, ...] = ("wire", "junction", "bus", "bus_entry", "bus_alias")
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


def grammar_issues(sheet: SchematicSheet) -> tuple[Issue, ...]:
    """One ``kicad.sch.netlist-unsupported`` error per reason that keeps Fenolite from reading the nets of
    ``sheet``, the reason first in the message; ``()`` for a sheet it can read."""
    found: dict[str, str] = {}
    heads = sch.opaque_heads(sheet)
    wires = {head: heads[head] for head in WIRE_HEADS if heads[head]}
    if wires:
        listed = ", ".join(f"{count} {head}" for head, count in wires.items())
        found["wire"] = f"the sheet holds {listed}; Fenolite reads no wire and no bus"
    other = [label.name for label in sheet.labels if label.kind != "global"]
    if other:
        found["label-kind"] = f"{len(other)} label(s) are not global labels: {_shown(other)}"
    several = [instance.ref for instance in sheet.symbols if len(instance.uses) > 1]
    if sheet.sheets or several:
        parts = [f"{len(sheet.sheets)} sheet reference(s)"] if sheet.sheets else []
        parts += [f"symbol(s) with more than one use: {_shown(several)}"] if several else []
        found["sheet"] = f"{'; '.join(parts)}; Fenolite reads one flat sheet"
    known = _definitions(sheet)
    undefined = [i.lib_name or i.lib_ref for i in sheet.symbols if _definition(i, known) is None]
    if undefined:
        found["undefined-symbol"] = (
            f"the sheet embeds no flat definition of {_shown(undefined)}, so the pins are not known"
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
        found["label-off-pin"] = f"{len(off)} label(s) lie on no pin: {_shown(off)}"
    double = sorted((point for point, texts in names.items() if len(texts) > 1), key=lambda p: (p.x, p.y))
    if double:
        texts = " and ".join(sorted(names[double[0]]))
        found["two-names"] = f"labels of different names lie on one point: {texts} at {_at(double[0])}"
    shared: list[str] = []
    for point, group in sorted(at.items(), key=lambda item: (item[0].x, item[0].y)):
        instances = {id(pin.instance) for pin in group}
        if len(instances) > 1 or (len(group) > 1 and not names.get(point)):
            shared.append(" and ".join(sorted({f"{pin.ref}-{pin.pin.number}" for pin in group})))
    if shared:
        found["shared-point"] = f"several pins connect at one point without a label of their own: {shared[0]}"
    frames = [i.ref for i in sheet.symbols if _frame(i) not in schlayout.PROVED_FRAMES]
    if frames:
        found["frame"] = f"the rotation and mirror of {_shown(frames)} were not measured"
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
        found["hidden-power"] = f"{'; '.join(parts)}: KiCad joins such pins by name, not by label"
    return tuple(
        Issue(CODE, ISSUE_CODES[CODE], f"{reason}: {found[reason]}", where=sheet.name, hint=HINT)
        for reason in REASONS
        if reason in found
    )


def _components(sheet: SchematicSheet, project: str) -> tuple[NetComponent, ...]:
    """``sch.components`` of the sheet, each with the properties of its symbol of the lowest unit."""
    properties: dict[str, tuple[int, dict[str, str]]] = {}
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
        for c in sch.components((sheet,), project=project)
    )


def own_netlist(sheet: SchematicSheet, *, project: str) -> KicadNetlist:
    """The netlist of ``sheet`` for the uses of ``project``, read from the sheet alone.

    Every pin of a placed unit whose reference does not start with ``#`` is a node. The nodes whose
    points carry a global label of one text are the net of that name (``netnames.stored_name`` of the
    text); a node without a label is a net of its own, named by ``netnames.unconnected_name``. The
    ``pintype`` is the electrical type of the pin, followed by ``+no_connect`` under a no-connect flag.
    A sheet outside the grammar raises ``NetlistUnsupportedError`` with the issues of ``grammar_issues``.
    """
    issues = grammar_issues(sheet)
    if issues:
        raise NetlistUnsupportedError(issues)
    labels = {label.position: netnames.stored_name(label.name) for label in sheet.labels}
    flagged = {flag.position for flag in sheet.no_connects}
    nets: dict[str, dict[tuple[str, str], NetNode]] = defaultdict(dict)
    placed: set[tuple[str, str]] = set()
    for pin in _pins(sheet, project):
        key = (pin.ref, pin.pin.number)
        if not pin.ref or pin.ref.startswith("#") or key in placed:
            continue
        if not any(use.project == project for use in pin.instance.uses):
            continue
        placed.add(key)
        name = labels.get(pin.point)
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
        _components(sheet, project),
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
