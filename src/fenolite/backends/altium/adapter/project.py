# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheets and the PCB document of one project as one design (capability altium-import, "Project
import"; change c0043).

The circuit comes from the sheets and the board from the PCB document; neither is corrected by the other.
Footprints link to schematic components by the unique-id path, then by designator; PCB nets to schematic
nets by name. What does not link is added to the circuit and reported.
"""

# evidence: see import_evidence

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.backends.altium.adapter.board import BoardImport, header, import_board, read_board
from fenolite.backends.altium.adapter.circuit import build_circuit
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids, bag
from fenolite.backends.altium.adapter.netlist import DEFAULT_OPTIONS, NetOptions, SheetInput, resolve
from fenolite.backends.altium.adapter.rules import import_rules
from fenolite.backends.altium.read.pcb import PcbDocument
from fenolite.backends.altium.read.rules import Field
from fenolite.core.errors import FormatError, Issue
from fenolite.model.board import Board, FootprintInstance
from fenolite.model.circuit import Circuit, Component, Net, PinRef
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet

KIND = "altium_prjpcb"


@dataclass(frozen=True, slots=True)
class BoardInput:
    """A PCB document: its file name without a folder, its SHA-256 and its document."""

    file: str
    sha256: str
    document: PcbDocument


@dataclass(frozen=True, slots=True)
class RulesInput:
    """The records of an exported rule file: its file name, its SHA-256 and each record's pair list."""

    file: str
    sha256: str
    records: tuple[tuple[Field, ...], ...]


@dataclass(frozen=True, slots=True)
class ProjectInput:
    """One project as records: its name (the project file's stem), its net options, its sheets in document
    order, its first PCB document (``None`` without one) and the rule files the caller wants imported.
    ``file`` and ``sha256`` name the project file; ``extra_boards`` counts further PCB documents."""

    name: str
    options: NetOptions = DEFAULT_OPTIONS
    sheets: tuple[SheetInput, ...] = ()
    board: BoardInput | None = None
    rules: tuple[RulesInput, ...] = ()
    file: str = ""
    sha256: str = "0" * 64
    extra_boards: int = 0


def _retarget(board: Board, components: dict[str, str], nets: dict[str, str]) -> Board:
    """``board`` with the component ids of its footprints and every net id replaced by the maps."""

    def net(value: str | None) -> str | None:
        return None if value is None else nets.get(value, value)

    footprints: list[FootprintInstance] = []
    for footprint in board.footprints:
        pads = tuple(dataclasses.replace(pad, net_id=net(pad.net_id)) for pad in footprint.pads)
        footprints.append(
            dataclasses.replace(
                footprint,
                component_id=components.get(footprint.component_id, footprint.component_id),
                pads=pads,
            )
        )
    return dataclasses.replace(
        board,
        footprints=tuple(footprints),
        tracks=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in board.tracks),
        arcs=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in board.arcs),
        vias=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in board.vias),
        zones=tuple(dataclasses.replace(item, net_id=net(item.net_id)) for item in board.zones),
    )


def link(circuit: Circuit, by_path: dict[str, str], repeated: set[str], parts: BoardImport,
         issues: list[Issue], unlinkable: dict[str, str] | None = None) -> tuple[Circuit, Board]:  # fmt: skip
    """Merge the board ``parts`` into ``circuit``: link footprints to components and PCB nets to nets; add
    what does not link. ``unlinkable`` holds the components of ``Repeat`` channels with the designator of
    their sheet: no form of their unique-id path is recorded, so a board component links to one only when
    its own designator is the channel's and its source designator the sheet's."""
    components = {component.id: component for component in circuit.components}
    channel_refs = unlinkable or {}
    linked_channels: set[str] = set()
    renamed: list[tuple[str, str]] = []
    by_ref: dict[str, list[str]] = {}
    for component in circuit.components:
        by_ref.setdefault(component.ref, []).append(component.id)
    synthesised = {component.id: component for component in parts.components}
    component_map: dict[str, str] = {}
    added: list[Component] = []
    by_designator = 0
    for footprint in parts.board.footprints:
        record = parts.links.get(footprint.id)
        own = synthesised[footprint.component_id]
        if record is None:
            added.append(own)
            continue
        target = by_path.get(record.source_unique_id or "")
        if target is None:
            candidates = by_ref.get(record.source_designator or "", []) if record.source_designator else []
            if len(candidates) == 1 and candidates[0] not in channel_refs:
                target = candidates[0]
                by_designator += 1
        if target is None and own.ref and record.source_designator:
            candidates = [
                found
                for found in by_ref.get(own.ref, [])
                if channel_refs.get(found) == record.source_designator and found not in linked_channels
            ]
            if len(candidates) == 1:
                target = candidates[0]
                linked_channels.add(target)
                by_designator += 1
        if target is None:
            added.append(own)
            issues.append(
                issue(
                    "altium.import.pcb-only-component",
                    "the component of the PCB document links to no schematic component; it is added to the "
                    "circuit",
                    own.ref or (footprint.provenance.locator if footprint.provenance else ""),
                )
            )
            continue
        component_map[footprint.component_id] = target
        # a component of a repeated sheet takes the designator its board gives it: the board is what the
        # project was annotated to (``source_designator`` is the sheet's own designator, the same for
        # every channel)
        if target in repeated and own.ref:
            linked = components[target]
            if linked.ref != own.ref:
                if "@" not in linked.ref and linked.ref != (record.source_designator or ""):
                    renamed.append((linked.ref, own.ref))  # the format named it otherwise
                path = "/".join((*linked.path.split("/")[:-1], own.ref))
                components[target] = dataclasses.replace(linked, ref=own.ref, path=path)
    if by_designator:
        issues.append(
            issue(
                "altium.import.linked-by-designator",
                f"{by_designator} component(s) of the PCB document are linked by designator, not by their "
                "unique-id path",
                parts.board.provenance.file if parts.board.provenance else "",
            )
        )

    if renamed:
        issues.append(
            issue(
                "altium.import.channel-naming",
                f"{len(renamed)} channel component(s) are named otherwise by the PCB document than by the "
                f"designator format (the first: {renamed[0][1]} against {renamed[0][0]}); the designators "
                "of the PCB document are taken",
                parts.board.provenance.file if parts.board.provenance else "",
            )
        )
    if len(channel_refs) > len(linked_channels):
        issues.append(
            issue(
                "altium.import.channel-naming",
                f"{len(channel_refs) - len(linked_channels)} component(s) of Repeat channels are linked to "
                "no component of the PCB document: the form of their unique-id path is not recorded, and "
                "no board component has their channel designator; they keep the designators of the "
                "designator format",
                parts.board.provenance.file if parts.board.provenance else "",
            )
        )

    exact = {net.name: net for net in circuit.nets}
    folded: dict[str, list[Net]] = {}
    for net in circuit.nets:
        folded.setdefault(net.name.casefold(), []).append(net)
    class_ids = {c.id for c in parts.netclasses}
    net_map: dict[str, str] = {}
    merged: dict[str, Net] = {net.id: net for net in circuit.nets}
    extra_nets: list[Net] = []
    pins_of = {cid: {pin.number for pin in component.pins} for cid, component in components.items()}
    pin_of_pad = {
        cid: {pad: pin for pin, pad in component.pin_pad_map} for cid, component in components.items()
    }
    for net in parts.nets:
        match = exact.get(net.name)
        if match is None and len(folded.get(net.name.casefold(), [])) == 1:
            match = folded[net.name.casefold()][0]
        if match is not None:
            net_map[net.id] = match.id
            if net.netclass_id in class_ids:
                current = merged[match.id]
                pairs = [*(current.ext["altium"].payload if current.ext else ()), *(
                    net.ext["altium"].payload if net.ext else ()
                )]  # fmt: skip
                merged[match.id] = dataclasses.replace(current, netclass_id=net.netclass_id, ext=bag(pairs))
            continue
        members: list[PinRef] = []
        for member in net.members:
            target = component_map.get(member.component_id, member.component_id)
            pin = pin_of_pad.get(target, {}).get(member.pin, member.pin)  # a pad stands for its pin
            if target in pins_of and pin not in pins_of[target]:
                continue  # the sheets do not hold this pin; the pad keeps its net on the board
            ref = PinRef(target, pin)
            if ref not in members:
                members.append(ref)
        extra_nets.append(dataclasses.replace(net, members=tuple(members)))
    if extra_nets:
        issues.append(
            issue(
                "altium.import.pcb-only-net",
                f"{len(extra_nets)} net(s) of the PCB document are no net of the sheets; they are added to "
                "the circuit",
                parts.board.provenance.file if parts.board.provenance else "",
            )
        )
    result = dataclasses.replace(
        circuit,
        components=(*(components[c.id] for c in circuit.components), *added),
        nets=(*(merged[net.id] for net in circuit.nets), *extra_nets),
        netclasses=(*circuit.netclasses, *parts.netclasses),
    )
    return result, _retarget(parts.board, component_map, net_map)


def _extra_rules(inputs: Sequence[RulesInput], ids: Ids, issues: list[Issue]) -> tuple[Rule, ...]:
    rules: list[Rule] = []
    for item in inputs:
        found = import_rules(
            item.records, ids, file=item.file, sha256=item.sha256, issues=issues, storage=item.file
        )
        rules += found.rules
    return tuple(rules)


def import_project(project: ProjectInput, *, issues: list[Issue] | None = None) -> Design:
    """The design of one project: the circuit of its sheets (``import_circuit`` with the project's net
    options) and the board, nets and rules of its PCB document, linked. A project without a PCB document
    gives ``board is None``; one without a sheet gives the design of ``import_board``; one with neither
    raises ``FormatError``."""
    found: list[Issue] = [] if issues is None else issues
    if not project.sheets and project.board is None:
        raise FormatError(
            "the project names no readable sheet and no readable PCB document", file=project.file
        )
    if project.extra_boards:
        found.append(
            issue(
                "altium.import.extra-board",
                f"the project lists {project.extra_boards} further PCB document(s); only the first is read",
                project.file,
            )
        )
    if not project.sheets:
        assert project.board is not None
        board = project.board
        design = import_board(board.document, file=board.file, sha256=board.sha256, issues=found)
        return dataclasses.replace(design, header=dataclasses.replace(design.header, name=project.name))
    ids = Ids(KIND, EVIDENCE)
    head = header(ids, project.name, file=project.file or project.sheets[0].file, sha256=project.sha256)
    resolved = resolve(project.sheets, project.options, found)
    built = build_circuit(resolved, ids, found)
    if project.board is None:
        rules = _extra_rules(project.rules, ids, found)
        ruleset = None
        if rules:
            ident, native = ids.native("rst", ids.kind)
            ruleset = RuleSet(id=ident, native_ids=native, rules=rules)
        return Design(header=head, circuit=built.circuit, board=None, rules=ruleset)
    board = project.board
    parts = read_board(board.document, file=board.file, sha256=board.sha256, ids=ids)
    found.extend(parts.issues)
    found.extend(parts.census.issues(board.file))
    circuit, linked = link(built.circuit, built.by_path, built.repeated, parts, found, built.unlinkable)
    rules = (*parts.rules.rules, *_extra_rules(project.rules, ids, found))
    return Design(
        header=head, circuit=circuit, board=linked, rules=dataclasses.replace(parts.rules, rules=rules)
    )


__all__ = ["KIND", "BoardInput", "ProjectInput", "RulesInput", "import_project", "link"]
