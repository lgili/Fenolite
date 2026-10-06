# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist of a set of schematic sheets (capability altium-import, "Net identifier scope", "Net
names", "Buses" and "Harnesses"; ``docs/formats/altium/connectivity.md``; change c0043).

The local nets of each sheet (``connectivity.local_nets``) are joined across the sheet instances by the
net identifier scope, then by the buses and the harnesses, and each net gets one name. Identifiers of
different kinds never join by name; names are compared without letter case.
"""

# evidence: see import_evidence

from __future__ import annotations

import re
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from pathlib import PureWindowsPath
from typing import Literal

from fenolite.backends.altium.adapter import connectivity as geo
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.connectivity import Ident, LocalNet, Union, bus_range
from fenolite.backends.altium.adapter.parts import PartGroup, locator, part_groups
from fenolite.backends.altium.read.sch import (
    HarnessConnector,
    HarnessEntry,
    HarnessType,
    SchDocument,
    SheetEntry,
    SheetFileName,
    SheetName,
    SheetSymbol,
)
from fenolite.core.errors import Issue

Scope = Literal["automatic", "flat", "hierarchical", "strict_hierarchical", "global"]
SCOPES: tuple[Scope, ...] = ("automatic", "flat", "hierarchical", "strict_hierarchical", "global")
HIERARCHICAL: tuple[str, ...] = ("hierarchical", "strict_hierarchical")
REPEAT = "repeat("
_DIGITS = re.compile(r"(\d+)")


def natural(text: str) -> tuple[tuple[int, int | str], ...]:
    """A sort key in natural order: digit runs compare as numbers (``R2`` before ``R10``)."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in _DIGITS.split(text) if part)


@dataclass(frozen=True, slots=True)
class SheetInput:
    """One schematic sheet: its file name without a folder, its SHA-256 and its document."""

    file: str
    sha256: str
    document: SchDocument


@dataclass(frozen=True, slots=True)
class NetOptions:
    """The options of a netlist. ``scope_unknown`` says that the project's hierarchy mode has no known
    meaning: the automatic scope is used and ``altium.import.scope-unknown`` is given."""

    scope: Scope = "automatic"
    power_port_names_first: bool = False
    allow_port_names: bool = False
    allow_sheet_entry_names: bool = True
    higher_level_names_first: bool = False
    append_sheet_numbers: bool = False
    scope_unknown: bool = False
    channel_format: str = ""
    """The designator format of repeated sheets (``channels.channel_designator``); ``""`` when the
    project states none: the components of a repeated sheet then keep the designators of the sheet."""
    room_style: int | None = None
    room_separator: str = "_"

    @classmethod
    def from_project(cls, project: object) -> NetOptions:
        """The options of a project: an ``AltiumProject``, a ``ProjectFile`` or its ``ProjectOptions``
        (``read.project``, c0042). A flag the project does not state keeps its default."""
        holder = getattr(project, "project", project)
        options = getattr(holder, "options", holder)
        scope = getattr(options, "net_scope", None)
        mode = getattr(options, "hierarchy_mode", None)
        default = cls()

        def flag(name: str, fallback: bool) -> bool:
            value = getattr(options, name, None)
            return fallback if value is None else bool(value)

        chosen = str(scope).replace("-", "_") if scope is not None else "automatic"
        return cls(
            scope=chosen if chosen in SCOPES else "automatic",  # type: ignore[arg-type]
            power_port_names_first=flag("power_port_names_take_priority", default.power_port_names_first),
            allow_port_names=flag("allow_port_net_names", default.allow_port_names),
            allow_sheet_entry_names=flag("allow_sheet_entry_net_names", default.allow_sheet_entry_names),
            higher_level_names_first=default.higher_level_names_first,
            append_sheet_numbers=flag("append_sheet_number_to_local_nets", default.append_sheet_numbers),
            scope_unknown=(scope is None and mode is not None) or chosen not in SCOPES,
            channel_format=getattr(options, "channel_designator_format", None) or "",
            room_style=getattr(options, "channel_room_naming_style", None),
            room_separator=getattr(options, "channel_room_level_separator", None) or "_",
        )


DEFAULT_OPTIONS = NetOptions()


@dataclass(frozen=True, slots=True, order=True)
class PinKey:
    """A pin of the netlist: the native id of its component (``cmp:<unique-id path>``) and its designator."""

    component: str
    designator: str


@dataclass(frozen=True, slots=True)
class NetGroup:
    """One net: its name, its other names (sorted), its pins (sorted) and the locators of its members as
    ``<file>:<locator>``, the first in sheet and stream order first."""

    name: str
    aliases: tuple[str, ...]
    pins: tuple[PinKey, ...]
    locators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BusGroup:
    """One bus: its name without the range, the text of its identifier, and its members that have a net
    as ``(index, net name)`` in identifier order."""

    name: str
    label: str
    members: tuple[tuple[int, str], ...]
    file: str = ""
    sha256: str = ""
    locator: str = ""


@dataclass(frozen=True, slots=True)
class HarnessGroup:
    """One harness: its type, and its entries that have a net as ``(entry name, net name)``."""

    type: str
    members: tuple[tuple[str, str], ...]
    file: str = ""
    sha256: str = ""
    locator: str = ""


@dataclass(frozen=True, slots=True)
class Netlist:
    """The nets of a set of sheets, sorted by name, with the scope that was used, the pins left open on
    purpose, the buses and the harnesses."""

    scope: str
    nets: tuple[NetGroup, ...]
    no_connects: tuple[PinKey, ...] = ()
    buses: tuple[BusGroup, ...] = ()
    harnesses: tuple[HarnessGroup, ...] = ()


# --- sheets and instances -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """A sheet symbol of a sheet: its record, its designator and the file names it lists."""

    record: SheetSymbol
    name: str
    files: tuple[str, ...]
    repeat: bool


@dataclass(frozen=True, slots=True)
class BusIdent:
    """A bus identifier of a sheet: ``kind`` is ``label``, ``port`` or ``entry``."""

    kind: str
    text: str
    name: str
    indexes: tuple[int, ...]
    index: int
    group: int
    locator: str
    owner: int = -1


@dataclass(frozen=True, slots=True)
class ConnectorInfo:
    index: int
    type: str
    locator: str
    entries: tuple[tuple[str, tuple[str, int]], ...]
    """Entry name and the key (stream, record index) of its harness identifier."""


@dataclass
class SheetData:
    """What is computed once per sheet, whatever the number of its instances."""

    input: SheetInput
    groups: tuple[PartGroup, ...]
    nets: tuple[LocalNet, ...]
    symbols: tuple[SymbolInfo, ...]
    has_port: bool
    has_entry: bool
    ident_net: dict[tuple[str, str, int], int] = field(default_factory=lambda: {})
    labels: dict[str, int] = field(default_factory=lambda: {})
    bus_idents: tuple[BusIdent, ...] = ()
    connectors: tuple[ConnectorInfo, ...] = ()
    harness_links: tuple[tuple[Hashable, Hashable], ...] = ()
    """Pairs of harness nodes of this sheet that one group holds (without the instance)."""
    harness_ports: tuple[tuple[int, str, str, str], ...] = ()
    """Record index, name, harness type and locator of each port with a harness type."""
    harness_entries: tuple[tuple[int, str, str, int, str], ...] = ()
    """Record index, name, harness type, owner symbol index and locator of each such sheet entry."""
    nested: tuple[str, ...] = ()
    harness_labels: tuple[tuple[tuple[str, int], str], ...] = ()
    """Per name that a harness of this sheet goes by (the net label on its line, the name of its port or
    of its sheet entry): the harness node (without the instance) and the name."""
    line_groups: int = 0

    @property
    def base(self) -> str:
        return PureWindowsPath(self.input.file).name.casefold()


@dataclass(frozen=True, slots=True)
class Instance:
    """One instance of a sheet in the hierarchy: ``uids`` are the unique ids of the sheet symbols from the
    top, ``names`` their designators (the module path), ``symbol`` the record index of its sheet symbol in
    the parent's sheet."""

    index: int
    sheet: int
    parent: int | None
    symbol: int
    uids: tuple[str, ...]
    names: tuple[str, ...]

    @property
    def depth(self) -> int:
        return len(self.names)


@dataclass(frozen=True, slots=True)
class ResolvedNet:
    """A net with what the circuit needs beside its ``NetGroup``: where its first member is."""

    group: NetGroup
    file: str
    sha256: str
    locator: str


@dataclass
class Resolved:
    """The netlist with the hierarchy it was computed on (``circuit.import_circuit`` builds entities from
    it)."""

    netlist: Netlist
    sheets: list[SheetData]
    instances: list[Instance]
    nets: list[ResolvedNet]
    component_ids: dict[tuple[int, int], str]
    """(instance index, component index in the sheet) → component native id."""
    options: NetOptions = DEFAULT_OPTIONS
    """The options the netlist was computed under; the circuit names channels with them."""


def _symbols(document: SchDocument) -> tuple[SymbolInfo, ...]:
    found: list[SymbolInfo] = []
    for record in document.sheet_symbols():
        kids = [document.get(ref) for ref in record.children]
        names = [k.text for k in kids if isinstance(k, SheetName)]
        files = [k.text for k in kids if isinstance(k, SheetFileName)]
        listed = tuple(part.strip() for part in (files[0] if files else "").split(";") if part.strip())
        name = names[0] if names and names[0] else (PureWindowsPath(listed[0]).stem if listed else "")
        found.append(SymbolInfo(record, name, listed, REPEAT in name.casefold()))
    return tuple(found)


def _bus_idents(document: SchDocument) -> tuple[BusIdent, ...]:
    buses = geo.bus_lines(document)
    groups = buses.groups()
    found: list[BusIdent] = []

    def add(kind: str, text: str, index: int, where: str, points: Sequence[geo.Pt], owner: int = -1) -> None:
        parsed = bus_range(text)
        if parsed is None:
            return
        lines = [line for point in points for line in buses.at(point)]
        if lines:
            found.append(BusIdent(kind, text, parsed[0], parsed[1], index, groups[lines[0]], where, owner))

    for label in document.net_labels():
        if label.owner is None:
            add("label", label.text, label.ref.index, locator(label), [geo.pt(label.location)])
    for port in document.ports():
        add("port", port.name, port.ref.index, locator(port), geo.port_ends(port))
    for entry in document.of_type(SheetEntry):
        point = geo.entry_point(document, entry)
        owner = document.owner_of(entry)
        if point is not None and owner is not None:
            add("entry", entry.name, entry.ref.index, locator(entry), [point], owner.ref.index)
    return tuple(found)


def _harness(document: SchDocument, data: SheetData) -> None:
    lines = geo.harness_lines(document)
    groups = lines.groups()
    links: list[tuple[Hashable, Hashable]] = []
    connectors: list[ConnectorInfo] = []
    hot: dict[geo.Pt, list[int]] = {}
    nested: list[str] = []
    for record in document.of_type(HarnessConnector):
        kids = [document.get(ref) for ref in record.children]
        kind = next((k.text for k in kids if isinstance(k, HarnessType)), "")
        entries: list[tuple[str, tuple[str, int]]] = []
        for kid in kids:
            if isinstance(kid, HarnessEntry):
                entries.append((kid.name, (kid.ref.stream, kid.ref.index)))
                point = geo.entry_point(document, kid)
                if point is not None and lines.at(point):
                    nested.append(locator(kid))
        number = len(connectors)
        connectors.append(ConnectorInfo(number, kind, locator(record), tuple(entries)))
        point = geo.connector_point(record)
        hot.setdefault(point, []).append(number)
        for line in lines.at(point):
            links.append((("hc", number), ("hl", groups[line])))
    ports: list[tuple[int, str, str, str]] = []
    for port in document.ports():
        ends = geo.port_ends(port)
        touching = any(lines.at(end) or end in hot for end in ends)
        if not port.harness_type and not touching:
            continue  # a port carries a harness by its type, or by lying on a harness line or connector
        ports.append((port.ref.index, port.name, port.harness_type, locator(port)))
        for end in geo.port_ends(port):
            for line in lines.at(end):
                links.append((("hp", port.ref.index), ("hl", groups[line])))
            for number in hot.get(end, []):
                links.append((("hp", port.ref.index), ("hc", number)))
    entries_found: list[tuple[int, str, str, int, str]] = []
    for entry in document.of_type(SheetEntry):
        owner = document.owner_of(entry)
        point = geo.entry_point(document, entry)
        if owner is None or point is None:
            continue
        if not entry.harness_type and not lines.at(point) and point not in hot:
            continue  # as a port: by its type, or by lying on a harness line or connector
        entries_found.append(
            (entry.ref.index, entry.name, entry.harness_type, owner.ref.index, locator(entry))
        )
        for line in lines.at(point):
            links.append((("he", entry.ref.index), ("hl", groups[line])))
        for number in hot.get(point, []):
            links.append((("he", entry.ref.index), ("hc", number)))
    names: list[tuple[tuple[str, int], str]] = []
    for label in document.net_labels():
        if label.owner is None and label.text:
            names += [(("hl", groups[line]), label.text) for line in lines.at(geo.pt(label.location))]
    names += [(("hp", index), name) for index, name, _kind, _where in ports]
    names += [(("he", index), name) for index, name, _kind, _owner, _where in entries_found]
    data.harness_labels = tuple(names)
    data.line_groups = len(set(groups))
    data.connectors = tuple(connectors)
    data.harness_links = tuple(links)
    data.harness_ports = tuple(ports)
    data.harness_entries = tuple(entries_found)
    data.nested = tuple(nested)


def sheet_data(sheet: SheetInput) -> SheetData:
    """Everything of one sheet that does not depend on where it is instantiated."""
    document = sheet.document
    groups = part_groups(document)
    nets = geo.local_nets(document, groups)
    data = SheetData(
        input=sheet,
        groups=groups,
        nets=nets,
        symbols=_symbols(document),
        has_port=bool(document.ports()),
        has_entry=bool(document.of_type(SheetEntry)),
    )
    for number, net in enumerate(nets):
        for ident in net.idents:
            data.ident_net[(ident.kind, ident.stream, ident.index)] = number
            if ident.kind == "label":
                data.labels.setdefault(ident.text.casefold(), number)
    data.bus_idents = _bus_idents(document)
    _harness(document, data)
    return data


def choose_scope(sheets: Sequence[SheetData], tops: Sequence[int]) -> Scope:
    """The automatic scope: hierarchical when a top sheet holds a sheet entry, else flat when any sheet
    holds a port, else global."""
    if any(sheets[top].has_entry for top in tops):
        return "hierarchical"
    if any(sheet.has_port for sheet in sheets):
        return "flat"
    return "global"


def _instances(sheets: Sequence[SheetData], issues: list[Issue]) -> tuple[list[Instance], list[int]]:
    by_name: dict[str, int] = {}
    for number, sheet in enumerate(sheets):
        by_name.setdefault(sheet.base, number)
    named: dict[int, int] = {}
    for sheet in sheets:
        for symbol in sheet.symbols:
            for file in symbol.files:
                child = by_name.get(PureWindowsPath(file).name.casefold())
                if child is not None:
                    named[child] = named.get(child, 0) + 1
    tops = [number for number in range(len(sheets)) if number not in named] or ([0] if sheets else [])
    for child, count in sorted(named.items()):
        if count > 1:
            issues.append(
                issue(
                    "altium.import.channels",
                    f"the sheet is named by {count} sheet symbols: it is instantiated once per symbol, and "
                    "each instance is a channel",
                    sheets[child].input.file,
                )
            )
    instances: list[Instance] = []

    def descend(sheet: int, parent: int | None, symbol: int, uids: tuple[str, ...], names: tuple[str, ...],
                chain: tuple[int, ...]) -> None:  # fmt: skip
        me = len(instances)
        instances.append(Instance(me, sheet, parent, symbol, uids, names))
        seen: dict[str, int] = {}
        for info in sheets[sheet].symbols:
            where = f"{sheets[sheet].input.file}:{locator(info.record)}"
            if info.repeat:
                issues.append(
                    issue(
                        "altium.import.repeated-sheet",
                        "the sheet symbol's designator holds a Repeat statement: one instance is read",
                        where,
                    )
                )
            count = seen.get(info.name, 0) + 1
            seen[info.name] = count
            name = info.name
            if count > 1:
                issues.append(
                    issue(
                        "altium.import.duplicate-sheet-name",
                        f"two sheet symbols of one sheet have one designator; the module path gets #{count}",
                        where,
                    )
                )
                name = f"{info.name}#{count}"
            for file in info.files:
                child = by_name.get(PureWindowsPath(file).name.casefold())
                if child is None:
                    issues.append(
                        issue(
                            "altium.import.sheet-missing",
                            f"the sheet symbol names {PureWindowsPath(file).name}, which is not among the "
                            "sheets; its entries stay named points",
                            where,
                        )
                    )
                    continue
                if child in chain or child == sheet:
                    issues.append(
                        issue(
                            "altium.import.sheet-loop",
                            "the sheet symbol names one of its own ancestors; the import does not descend",
                            where,
                        )
                    )
                    continue
                descend(
                    child, me, info.record.ref.index, (*uids, info.record.unique_id), (*names, name),
                    (*chain, sheet),
                )  # fmt: skip

    for top in tops:
        descend(top, None, -1, (), (), ())
    return instances, tops


# --- the netlist ----------------------------------------------------------------------------------------

_KIND_RANK = {"label": 0, "power": 1, "port": 2, "offsheet": 2, "entry": 3}


def _candidates(
    idents: Sequence[tuple[Ident, int]], options: NetOptions
) -> list[tuple[tuple[int, int, str, str], str]]:
    """The naming candidates of a net as (sort key, text); the smallest key names the net."""
    found: list[tuple[tuple[int, int, str, str], str]] = []
    for ident, depth in idents:
        if not ident.text or ident.kind not in _KIND_RANK:
            continue
        if ident.kind == "port" and not options.allow_port_names:
            continue
        if ident.kind == "entry" and not options.allow_sheet_entry_names:
            continue
        rank = _KIND_RANK[ident.kind]
        if options.power_port_names_first and ident.kind in ("label", "power"):
            rank = 1 - rank
        level = depth if options.higher_level_names_first else -depth
        found.append(((rank, level, ident.text.casefold(), ident.text), ident.text))
    return sorted(found)


def resolve(
    sheets: Sequence[SheetInput], options: NetOptions = DEFAULT_OPTIONS, issues: list[Issue] | None = None
) -> Resolved:
    """Join the local nets of ``sheets`` and name them (see ``netlist``)."""
    found: list[Issue] = [] if issues is None else issues
    data = [sheet_data(sheet) for sheet in sheets]
    instances, tops = _instances(data, found)
    where = data[tops[0]].input.file if tops else ""
    if options.scope_unknown:
        found.append(
            issue(
                "altium.import.scope-unknown",
                "the project's hierarchy mode has no known meaning; the automatic scope is used",
                where,
            )
        )
    scope: Scope = options.scope
    if scope == "automatic":
        scope = choose_scope(data, tops)
    found.append(issue("altium.import.scope", f"the net identifier scope is {scope}", where))
    if options.append_sheet_numbers:
        found.append(
            issue(
                "altium.import.option-ignored",
                "AppendSheetNumberToLocalNets is set; the import does not append sheet numbers to net names",
                where,
            )
        )
    for sheet in data:
        for nested in sheet.nested:
            found.append(
                issue(
                    "altium.import.harness-nested",
                    "a harness entry carries a harness of its own; it is not resolved",
                    f"{sheet.input.file}:{nested}",
                )
            )

    union = Union()
    hierarchical = scope in HIERARCHICAL
    for instance in instances:
        sheet = data[instance.sheet]
        for number, net in enumerate(sheet.nets):
            node = ("n", instance.index, number)
            union.find(node)
            has_port = bool(net.of("port"))
            for ident in net.idents:
                key = ident.text.casefold()
                if not key:
                    continue
                if ident.kind == "power":
                    if scope == "strict_hierarchical" or (hierarchical and has_port):
                        continue
                    union.join(node, ("power", key))
                elif ident.kind == "label" and scope == "global":
                    union.join(node, ("label", key))
                elif ident.kind == "port" and not hierarchical:
                    union.join(node, ("port", key))
                elif ident.kind == "offsheet":
                    union.join(node, ("offsheet", instance.parent, key))
        if hierarchical and instance.parent is not None:
            parent = data[instances[instance.parent].sheet]
            entries = {
                ident.text.casefold(): number
                for number, net in enumerate(parent.nets)
                for ident in net.of("entry")
                if ident.owner == instance.symbol
            }
            for number, net in enumerate(sheet.nets):
                for ident in net.of("port"):
                    above = entries.get(ident.text.casefold())
                    if above is not None:
                        union.join(("n", instance.index, number), ("n", instance.parent, above))

    # --- buses ---
    bus_union = Union()
    width_warned: set[tuple[int, int]] = set()

    def join_members(a: tuple[int, BusIdent], b: tuple[int, BusIdent]) -> None:
        (ia, first), (ib, second) = a, b
        if len(first.indexes) != len(second.indexes) and (ia, first.index) not in width_warned:
            width_warned.add((ia, first.index))
            found.append(
                issue(
                    "altium.import.bus-width",
                    f"bus identifiers of {len(first.indexes)} and {len(second.indexes)} members join; "
                    "the common prefix is joined",
                    f"{data[instances[ia].sheet].input.file}:{first.locator}",
                )
            )
        for k in range(min(len(first.indexes), len(second.indexes))):
            union.join(("bm", ia, first.kind, first.index, k), ("bm", ib, second.kind, second.index, k))
        bus_union.join(("bg", ia, first.group), ("bg", ib, second.group))

    for instance in instances:
        sheet = data[instance.sheet]
        for ident in sheet.bus_idents:
            bus_union.find(("bg", instance.index, ident.group))
            for k, index in enumerate(ident.indexes):
                node = ("bm", instance.index, ident.kind, ident.index, k)
                union.find(node)
                labelled = sheet.labels.get(f"{ident.name}{index}".casefold())
                if labelled is not None:
                    union.join(node, ("n", instance.index, labelled))
        for a, first in enumerate(sheet.bus_idents):
            for second in sheet.bus_idents[a + 1 :]:
                if first.group == second.group and (
                    first.name.casefold() != second.name.casefold() or first.indexes == second.indexes
                ):
                    join_members((instance.index, first), (instance.index, second))
        ports = [ident for ident in sheet.bus_idents if ident.kind == "port"]
        if hierarchical and instance.parent is not None:
            above = data[instances[instance.parent].sheet]
            for port in ports:
                for entry in above.bus_idents:
                    if (
                        entry.kind == "entry"
                        and entry.owner == instance.symbol
                        and entry.text.casefold() == port.text.casefold()
                    ):
                        join_members((instance.index, port), (instance.parent, entry))
        elif not hierarchical:
            for port in ports:
                key = ("busport", port.text.casefold())
                for k in range(len(port.indexes)):
                    union.join(("bm", instance.index, "port", port.index, k), (*key, k))
                bus_union.join(("bg", instance.index, port.group), key)

    # --- harnesses ---
    harness = Union()
    for instance in instances:
        sheet = data[instance.sheet]
        for connector in sheet.connectors:
            harness.find(("hc", instance.index, connector.index))
        for group in range(sheet.line_groups):
            harness.find(("hl", instance.index, group))
        for a, b in sheet.harness_links:
            harness.join((a[0], instance.index, a[1]), (b[0], instance.index, b[1]))  # type: ignore[index]
        for index, name, _kind, _where in sheet.harness_ports:
            node = ("hp", instance.index, index)
            harness.find(node)
            if hierarchical and instance.parent is not None:
                above = data[instances[instance.parent].sheet]
                for entry, entry_name, _k, owner, _w in above.harness_entries:
                    if owner == instance.symbol and entry_name.casefold() == name.casefold():
                        harness.join(node, ("he", instance.parent, entry))
            elif not hierarchical:
                harness.join(node, ("hport", name.casefold()))
        for index, _name, _kind, _owner, _where in sheet.harness_entries:
            harness.find(("he", instance.index, index))
    harness_groups: dict[Hashable, list[tuple[int, ConnectorInfo]]] = {}
    dotted: dict[Hashable, list[tuple[str, Hashable, int]]] = {}
    for instance in instances:
        sheet = data[instance.sheet]
        for connector in sheet.connectors:
            root = harness.find(("hc", instance.index, connector.index))
            harness_groups.setdefault(root, []).append((instance.index, connector))
        # A net label ``<harness>.<entry>`` names the member ``<entry>`` of the harness that goes by
        # ``<harness>`` on this sheet (``connectivity.md``, "Buses and harnesses").
        named_here: dict[str, list[tuple[str, int]]] = {}
        for node, name in sheet.harness_labels:
            named_here.setdefault(name.casefold(), []).append(node)
        for text, local in sheet.labels.items():
            prefix, dot, entry = text.rpartition(".")
            if not dot or not entry or prefix not in named_here:
                continue
            for kind, number in named_here[prefix]:
                root = harness.find((kind, instance.index, number))
                dotted.setdefault(root, []).append((entry, ("n", instance.index, local), instance.index))
    for root in dotted:
        harness_groups.setdefault(root, [])
    fallback: dict[Hashable, list[str]] = {}
    harness_members: list[tuple[Hashable, list[tuple[str, Hashable]]]] = []
    harness_names: dict[Hashable, str] = {}
    for root, connectors in harness_groups.items():
        named: list[tuple[tuple[int, int, str, str], str]] = []
        kind = next((c.type for _i, c in connectors if c.type), "")
        for instance in instances:
            sheet = data[instance.sheet]
            for index, name, port_kind, _where in sheet.harness_ports:
                if harness.find(("hp", instance.index, index)) == root:
                    named.append(((0, instance.depth, name.casefold(), name), name))
                    kind = kind or port_kind
            for index, name, entry_kind, _owner, _where in sheet.harness_entries:
                if harness.find(("he", instance.index, index)) == root:
                    named.append(((1, instance.depth, name.casefold(), name), name))
                    kind = kind or entry_kind
        title = min(named)[1] if named else kind
        harness_names[root] = kind
        by_entry: dict[str, tuple[str, Hashable]] = {}
        for entry, node, _inst in dotted.get(root, []):
            known = by_entry.setdefault(entry.casefold(), (entry, node))
            union.join(known[1], node)
        for inst, connector in connectors:
            for entry, (stream, index) in connector.entries:
                local = data[instances[inst].sheet].ident_net.get(("harness", stream, index))
                if local is None:
                    continue
                node = ("n", inst, local)
                known = by_entry.get(entry.casefold())
                if known is None or known[0] != entry:
                    by_entry[entry.casefold()] = (entry, node)  # the connector's spelling wins
                if known is not None:
                    union.join(known[1], node)
        for entry, node in by_entry.values():
            fallback.setdefault(node, []).append(f"{title}.{entry}")
        harness_members.append((root, list(by_entry.values())))

    # --- nets ---
    components: dict[tuple[int, int], str] = {}
    for instance in instances:
        for number, group in enumerate(data[instance.sheet].groups):
            ids = group.unique_ids
            tail = ids[0] if ids else f"#{group.first.ref.index}"
            components[(instance.index, number)] = "cmp:" + "".join(
                f"\\{uid}" for uid in (*instance.uids, tail)
            )
    pins: dict[Hashable, set[PinKey]] = {}
    idents: dict[Hashable, list[tuple[Ident, int]]] = {}
    firsts: dict[Hashable, list[tuple[int, int, str]]] = {}
    refs: dict[PinKey, str] = {}
    open_pins: list[PinKey] = []
    for instance in instances:
        sheet = data[instance.sheet]
        for number, net in enumerate(sheet.nets):
            keys = [PinKey(components[(instance.index, pin.group)], pin.designator) for pin in net.pins]
            for key, pin in zip(keys, net.pins, strict=True):
                refs[key] = sheet.groups[pin.group].ref
            if net.no_connect:
                open_pins += keys
                continue
            root = union.find(("n", instance.index, number))
            pins.setdefault(root, set()).update(keys)
            idents.setdefault(root, []).extend((ident, instance.depth) for ident in net.idents)
            firsts.setdefault(root, []).extend(
                (instance.index, k, where) for k, where in enumerate(net.locators)
            )
    fallbacks: dict[Hashable, str] = {}
    for node, texts in fallback.items():
        root = union.find(node)
        fallbacks[root] = min([*texts, *([fallbacks[root]] if root in fallbacks else [])])

    drafts: list[tuple[str, tuple[str, ...], tuple[PinKey, ...], Hashable]] = []
    for root in pins:
        candidates = _candidates(idents.get(root, []), options)
        net_pins = tuple(sorted(pins[root]))
        if candidates:
            name = candidates[0][1]
        elif root in fallbacks and net_pins:
            name = fallbacks[root]
        elif len(net_pins) > 1:
            lead = min(net_pins, key=lambda key: (natural(refs[key]), natural(key.designator)))
            name = f"Net{refs[lead]}_{lead.designator}"
        else:
            continue
        aliases = tuple(sorted({text for _key, text in candidates} - {name}))
        drafts.append((name, aliases, net_pins, root))
    drafts.sort(key=lambda draft: (draft[0], draft[2], firsts.get(draft[3], [(0, 0, "")])[0]))
    taken: dict[str, int] = {}
    used = {draft[0] for draft in drafts}
    names: dict[Hashable, str] = {}
    resolved: list[ResolvedNet] = []
    for name, aliases, net_pins, root in drafts:
        count = taken.get(name, 0) + 1
        taken[name] = count
        final = name
        if count > 1:
            k = count
            while f"{name}#{k}" in used:
                k += 1
            final = f"{name}#{k}"
            used.add(final)
            found.append(
                issue(
                    "altium.import.duplicate-net-name",
                    f"two nets end with one name; the later one is renamed {final}",
                    name,
                )
            )
        names[root] = final
        first = min(firsts.get(root, [(0, 0, "")]))
        sheet = data[instances[first[0]].sheet].input if instances else None
        listed = tuple(
            f"{data[instances[i].sheet].input.file}:{where}" for i, _k, where in sorted(firsts.get(root, []))
        )
        resolved.append(
            ResolvedNet(
                NetGroup(final, aliases, net_pins, listed),
                sheet.file if sheet else "",
                sheet.sha256 if sheet else "",
                first[2],
            )
        )
    resolved.sort(key=lambda net: net.group.name)

    # --- bus and harness groups ---
    buses: list[BusGroup] = []
    missing_members = 0
    bus_groups: dict[Hashable, list[tuple[int, BusIdent]]] = {}
    for instance in instances:
        for ident in data[instance.sheet].bus_idents:
            root = bus_union.find(("bg", instance.index, ident.group))
            bus_groups.setdefault(root, []).append((instance.index, ident))
    bus_rank = {"label": 0, "port": 1, "entry": 2}
    for group in bus_groups.values():
        inst, chosen = min(
            group,
            key=lambda pair: (
                bus_rank[pair[1].kind],
                instances[pair[0]].depth if options.higher_level_names_first else -instances[pair[0]].depth,
                pair[1].text.casefold(),
                pair[1].text,
                pair[0],
            ),
        )
        members: list[tuple[int, str]] = []
        for k, index in enumerate(chosen.indexes):
            root = union.find(("bm", inst, chosen.kind, chosen.index, k))
            if root in names:
                members.append((index, names[root]))
            else:
                missing_members += 1
        sheet_input = data[instances[inst].sheet].input
        buses.append(
            BusGroup(
                chosen.name, chosen.text, tuple(members), sheet_input.file, sheet_input.sha256, chosen.locator
            )
        )
    if missing_members:
        found.append(
            issue(
                "altium.import.bus-member",
                f"{missing_members} bus member(s) have no net and are left out",
                where,
            )
        )
    harnesses: list[HarnessGroup] = []
    missing_entries = 0
    for root, entries in harness_members:
        members_found: list[tuple[str, str]] = []
        for entry, node in entries:
            net_root = union.find(node)
            if net_root in names:
                members_found.append((entry, names[net_root]))
            else:
                missing_entries += 1
        if harness_groups[root]:
            inst, where_found = harness_groups[root][0][0], harness_groups[root][0][1].locator
        else:
            inst, where_found = dotted[root][0][2], "FileHeader#0"
        sheet_input = data[instances[inst].sheet].input
        harnesses.append(
            HarnessGroup(
                harness_names[root],
                tuple(sorted(members_found)),
                sheet_input.file,
                sheet_input.sha256,
                where_found,
            )  # fmt: skip
        )
    if missing_entries:
        found.append(
            issue(
                "altium.import.harness-entry",
                f"{missing_entries} harness entr(ies) have no net and are left out",
                where,
            )
        )
    result = Netlist(
        scope=scope,
        nets=tuple(net.group for net in resolved),
        no_connects=tuple(sorted(open_pins)),
        buses=tuple(sorted(buses, key=lambda bus: (bus.name, bus.label, bus.file, bus.locator))),
        harnesses=tuple(sorted(harnesses, key=lambda h: (h.type, h.file, h.locator))),
    )
    return Resolved(result, data, instances, resolved, components, options)


def netlist(
    sheets: Sequence[SheetInput], *, options: NetOptions = DEFAULT_OPTIONS, issues: list[Issue] | None = None
) -> Netlist:
    """The nets of ``sheets`` under ``options``: the local nets of each sheet joined by the net identifier
    scope, by the buses and by the harnesses, each with one name. A net without an identifier that holds
    fewer than two pins is no net: an unconnected pin is in no net. A named net of one pin is kept."""
    return resolve(sheets, options, issues).netlist


__all__ = [
    "BusGroup",
    "HarnessGroup",
    "Instance",
    "NetGroup",
    "NetOptions",
    "Netlist",
    "PinKey",
    "Resolved",
    "ResolvedNet",
    "Scope",
    "SheetInput",
    "choose_scope",
    "natural",
    "netlist",
    "resolve",
    "sheet_data",
]
