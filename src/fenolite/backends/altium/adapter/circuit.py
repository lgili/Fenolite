# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic sheets as a circuit (capability altium-import, "Schematic components and pins", "Hierarchy as
modules", "Buses" and "Harnesses"; change c0043).

``import_circuit`` builds the model entities from the netlist of ``netlist.resolve``: one component per
designator per sheet instance, the nets, one module per sheet-symbol instance, one interface per harness,
one bus per bus group, and the pins left open on purpose.
"""

# evidence: see import_evidence

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids, bag
from fenolite.backends.altium.adapter.netlist import (
    DEFAULT_OPTIONS,
    NetOptions,
    Resolved,
    SheetInput,
    natural,
    resolve,
)
from fenolite.backends.altium.adapter.parts import PartGroup, locator
from fenolite.backends.altium.adapter.pins import pin_etype
from fenolite.core.errors import Issue
from fenolite.model.circuit import Bus, BusMember, Circuit, Component, Interface, Module, Net, Pin, PinRef

KIND = "altium_schdoc"


@dataclass
class CircuitImport:
    """The circuit of a set of sheets with what a project import needs to link a board to it: per unique-id
    path of each part (``\\<sheet symbol id>…\\<part id>``) the component's id, and the netlist."""

    circuit: Circuit
    resolved: Resolved
    by_path: dict[str, str] = field(default_factory=lambda: {})
    repeated: set[str] = field(default_factory=lambda: set())
    """The ids of the components that lie on a sheet instantiated more than once."""
    channel_sources: dict[str, int] = field(default_factory=lambda: {})
    """How many channel components took their designator from each source: ``annotation`` (the project's
    annotation file, change c0083), ``format`` (the project's designator format) or ``unresolved``
    (``<designator>@<channel>``); ``project.link`` adds ``board``."""
    unlinkable: dict[str, str] = field(default_factory=lambda: {})
    """Per component of a ``Repeat`` channel, its id and the designator of its sheet: no unique-id path
    is recorded for such a component, so a board links to it by designator only."""


def pin_pad_map(group: PartGroup) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], int]:
    """The pin-to-pad map of a component as the model holds it, with what it cannot hold.

    A map record names the pads of one pin (``docs/formats/altium/connectivity.md``, "Component link").
    The model's map gives a pin any number of pads and a pad one pin (change c0123), so a record gives one
    pair per pad it lists, in its order. The pins are taken in the order of the pin table; a pin without a
    record, a pin whose record lists its own designator and a pin whose record lists no pad stand for the
    pad of their own designator before any other pin is taken. A pad that another pin stands for gives no
    pair, and a pin none of whose pads gives a pair keeps its own designator. Returns the pairs, every
    record that the pairs do not say in full as ``(pin, pads joined by a comma)`` (a record without a pad,
    and one of which a pad gave no pair), and the count of those records."""
    pins = [pin.designator for pin in group.pins]
    records = {pin: pads for pin, pads in group.pin_pads if pin in pins}
    holder: dict[str, str] = {}
    for pin in pins:
        pads = records.get(pin)
        if not pads or pin in pads:
            holder.setdefault(pin, pin)
    pairs: list[tuple[str, str]] = []
    kept: list[tuple[str, str]] = []
    for pin in pins:
        pads = records.get(pin)
        if pads is None:
            continue
        whole, given = bool(pads), False
        for pad in dict.fromkeys(pads):
            if holder.setdefault(pad, pin) != pin:
                whole = False
                continue
            pairs.append((pin, pad))
            given = True
        if not given:
            holder.setdefault(pin, pin)
        if not whole:
            kept.append((pin, ",".join(pads)))
    return tuple(pairs), tuple(kept), len(kept)


def build_circuit(resolved: Resolved, ids: Ids, issues: list[Issue]) -> CircuitImport:
    """The model entities of ``resolved`` with the ids of ``ids``."""
    sheets, instances = resolved.sheets, resolved.instances
    counts: dict[int, int] = {}
    for instance in instances:
        counts[instance.sheet] = counts.get(instance.sheet, 0) + 1
    components: list[Component] = []
    by_native: dict[str, str] = {}
    by_path: dict[str, str] = {}
    repeated: set[str] = set()
    unlinkable: dict[str, str] = {}
    of_instance: dict[int, list[Component]] = {}
    options = resolved.options
    sources = dict(resolved.channel_sources)
    maps: dict[tuple[int, int], tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], int]] = {}
    partial = 0
    for instance in instances:
        sheet = sheets[instance.sheet]
        file, sha256 = sheet.input.file, sheet.input.sha256
        for number, group in enumerate(sheet.groups):
            native = resolved.component_ids[(instance.index, number)]
            ident, native_ids = ids.native("cmp", native)
            by_native.setdefault(native, ident)
            if instance.repeated:
                # the unique-id path of a component of a Repeat channel has no recorded form
                unlinkable[ident] = group.ref
            else:
                prefix = "".join(f"\\{uid}" for uid in instance.uids)
                for unique in group.unique_ids:
                    by_path.setdefault(f"{prefix}\\{unique}", ident)
            ref = resolved.refs.get((instance.index, number), group.ref)
            if counts[instance.sheet] > 1:
                repeated.add(ident)
            key = (instance.sheet, number)
            if key not in maps:
                maps[key] = pin_pad_map(group)
            pad_map, kept, count = maps[key]
            partial += count
            if not group.has_designator:
                issues.append(
                    issue(
                        "altium.import.no-designator",
                        "the component has no designator record; its reference is empty",
                        f"{file}:{group.locator}",
                    )
                )
            pins: list[Pin] = []
            for record in group.pins:
                etype, pairs = pin_etype(record)
                pin_id, pin_native = ids.native("pin", f"{native_ids['altium']}:pin:{record.designator}")
                pins.append(
                    Pin(
                        id=pin_id,
                        native_ids=pin_native,
                        provenance=ids.provenance(file, sha256, locator(record)),
                        ext=bag(pairs),
                        number=record.designator,
                        name=record.name,
                        etype=etype,
                    )
                )
            extra: list[tuple[str, str]] = []
            if group.first.component_kind:
                extra.append(("component_kind", str(group.first.component_kind)))
            if len(group.unique_ids) > 1:
                extra.append(("part_ids", ",".join(group.unique_ids)))
            extra += [("pin_pads", f"{pin}={pads}") for pin, pads in kept]
            component = Component(
                id=ident,
                native_ids=native_ids,
                provenance=ids.provenance(file, sha256, group.locator),
                ext=bag(extra),
                ref=ref,
                value=group.value,
                lib_symbol_ref=group.lib_symbol_ref,
                lib_footprint_ref=group.lib_footprint_ref,
                properties=dict(group.properties),
                path="/".join((*instance.names, ref)),
                pins=tuple(pins),
                pin_pad_map=pad_map,
            )
            components.append(component)
            of_instance.setdefault(instance.index, []).append(component)

    nets: list[Net] = []
    net_ids: dict[str, str] = {}
    for net in resolved.nets:
        group = net.group
        ident, native_ids = ids.native("net", f"net:{group.name}")
        net_ids[group.name] = ident
        nets.append(
            Net(
                id=ident,
                native_ids=native_ids,
                provenance=ids.provenance(net.file, net.sha256, net.locator),
                ext=bag([("alias", alias) for alias in group.aliases]),
                name=group.name,
                members=tuple(PinRef(by_native[pin.component], pin.designator) for pin in group.pins),
            )
        )

    modules: list[Module] = []
    module_ids: dict[int, str] = {}
    for instance in instances:
        if instance.parent is None:
            continue
        sheet = sheets[instance.sheet]
        native = "module:" + "".join(f"\\{uid}" for uid in instance.uids)
        ident, native_ids = ids.native("mod", native)
        module_ids[instance.index] = ident
        owned = sorted(of_instance.get(instance.index, []), key=lambda c: (natural(c.ref), c.id))
        channel: list[tuple[str, str]] = []
        if instance.indexes[-1] is not None:
            index = instance.indexes[-1]
            symbol = instance.uids[-1].removesuffix(f"[{index}]")
            channel = [("sheet_symbol", symbol), ("channel_index", str(index))]
        modules.append(
            Module(
                id=ident,
                native_ids=native_ids,
                provenance=ids.provenance(sheet.input.file, sheet.input.sha256, "FileHeader#0"),
                ext=bag(channel),
                path="/".join(instance.names),
                parent=module_ids.get(instance.parent),
                component_ids=tuple(component.id for component in owned),
            )
        )

    interfaces: list[Interface] = []
    for harness in resolved.netlist.harnesses:
        members = {entry: net_ids[name] for entry, name in harness.members}
        interfaces.append(
            Interface(
                id=ids.content("itf", "interfaces", harness.type, sorted(members.items())),
                provenance=ids.provenance(harness.file, harness.sha256, harness.locator),
                ext=bag([("harness_type", harness.type)] if harness.type else []),
                name=harness.type,
                kind="harness",
                members=members,
            )
        )
    buses: list[Bus] = []
    for found in resolved.netlist.buses:
        bus_members = tuple(BusMember(index, net_ids[name]) for index, name in found.members)
        buses.append(
            Bus(
                id=ids.content(
                    "bus", "buses", found.name, found.label, [[m.index, m.net_id] for m in bus_members]
                ),
                provenance=ids.provenance(found.file, found.sha256, found.locator),
                ext=bag([("label", found.label)]),
                name=found.name,
                members=bus_members,
            )
        )
    marks = tuple(PinRef(by_native[pin.component], pin.designator) for pin in resolved.netlist.no_connects)
    circuit = Circuit(
        components=tuple(components),
        nets=tuple(nets),
        interfaces=tuple(interfaces),
        modules=tuple(modules),
        buses=tuple(buses),
        no_connects=marks,
    )
    if sources.get("unresolved"):
        issues.append(
            issue(
                "altium.import.channel-naming",
                f"{sources['unresolved']} component(s) of repeated sheets: the designator format "
                f"{options.channel_format!r} with the room naming style {options.room_style} is not one this "
                "import resolves; they are named <designator>@<channel>",
                sheets[instances[0].sheet].input.file if instances else "",
            )
        )
    if partial:
        issues.append(
            issue(
                "altium.import.pin-map",
                f"{partial} pin map record(s) name no pad, or a pad that another pin holds: the model gives "
                "a pad one pin, so such a pad is left off the pin; the record is kept in the component's "
                "altium bag (pin_pads)",
                sheets[instances[0].sheet].input.file if instances else "",
            )
        )
    return CircuitImport(circuit, resolved, by_path, repeated, sources, unlinkable)


def import_circuit(
    sheets: Sequence[SheetInput],
    *,
    options: NetOptions = DEFAULT_OPTIONS,
    issues: list[Issue] | None = None,
) -> Circuit:
    """The circuit of the schematic sheets ``sheets`` under the net options ``options``: components with
    their pins, nets, modules, harness interfaces, buses and no-connect marks. The adapter's issues are
    added to ``issues``."""
    found: list[Issue] = [] if issues is None else issues
    resolved = resolve(sheets, options, found)
    return build_circuit(resolved, Ids(KIND, EVIDENCE), found).circuit


__all__ = ["KIND", "CircuitImport", "build_circuit", "import_circuit", "pin_pad_map"]
