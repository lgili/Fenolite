# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block layout adapter: exact level-five positions and copper settled against placed library pads."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.checks.copper import check_copper, frame_edges
from fenolite.cli._blocklayout_merge import CopyMerge
from fenolite.cli.cmd_tidy import clashes_of
from fenolite.cli.errors import CliError
from fenolite.cli.reuse_copper import settle_copper
from fenolite.core.errors import Issue
from fenolite.geometry.transform import Transform
from fenolite.model.board import Arc, FootprintInstance, Track, Via
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse.blocklayout import (
    BlockLayout,
    BlockLayoutError,
    LayoutApplication,
    apply_block_layout,
    component_path,
    pad_contains,
    read_block_layout,
)
from fenolite.reuse.codes import issue
from fenolite.reuse.copper import CopiedItem, Copper, CopperCopy, Dropped


@dataclass(frozen=True)
class LayoutFile:
    path: str
    full: Path
    sha256: str
    layout: BlockLayout
    application: LayoutApplication
    copper: bool

    def summary(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256, "status": self.application.status}


def read_layout(
    path: str,
    full: Path,
    model: Design,
    instance: str,
    definitions: Mapping[str, FootprintDef],
    *,
    copper: bool,
) -> LayoutFile:
    try:
        layout = read_block_layout(full)
    except BlockLayoutError as error:
        raise CliError(error.code, str(error), where=path) from error
    applied = apply_block_layout(layout, model, instance, Transform(), definitions)
    return LayoutFile(path, full, hashlib.sha256(full.read_bytes()).hexdigest(), layout, applied, copper)


def placed_model(
    model: Design, definitions: Mapping[str, FootprintDef], placements: Mapping[str, Any]
) -> Design:
    """An in-memory board with library pads at code-side placements, for the copper guard."""
    board = model.board
    assert board is not None
    nets = {
        (member.component_id, pad): net.id
        for net in model.circuit.nets
        for member in net.members
        for c in model.circuit.components
        if c.id == member.component_id
        for pad in c.pads_of(member.pin)
    }
    footprints: list[FootprintInstance] = []
    for component in model.circuit.components:
        path = component_path(component)
        lib_ref = component.footprint_definition_ref or component.lib_footprint_ref
        definition, placed = definitions.get(lib_ref), placements.get(path)
        if definition is None or placed is None:
            continue
        fp = place_footprint(
            prepare_authored_definition(definition),
            component=component,
            at=placed.at,
            rotation=placed.rotation,
            side=placed.side,
            key=path,
        )
        fp = dataclasses.replace(
            fp,
            pads=tuple(
                dataclasses.replace(pad, net_id=nets.get((component.id, pad.number))) for pad in fp.pads
            ),
        )
        footprints.append(fp)
    return dataclasses.replace(model, board=dataclasses.replace(board, footprints=tuple(footprints)))


def layout_copper(
    file: LayoutFile,
    model: Design,
    instance: str,
    world: Transform,
    definitions: Mapping[str, FootprintDef],
    placements: Mapping[str, Any],
    merge: CopyMerge | None = None,
) -> tuple[list[Copper], list[Issue]]:
    application = apply_block_layout(file.layout, model, instance, world, definitions, copper=file.copper)
    copy = application.copper
    if merge is not None:
        copy = merge.merge(instance, file.layout, copy)
    contacts = dict(file.layout.pads)
    if merge is not None:
        contacts.update(
            {
                source: pads
                for key, pads in merge.contacts.items()
                for owner, separator, source in (key.partition(":"),)
                if separator and owner == instance
            }
        )
    return settle_copy(copy, model, instance, definitions, placements, contacts)


def settle_copy(
    copy: CopperCopy,
    model: Design,
    instance: str,
    definitions: Mapping[str, FootprintDef],
    placements: Mapping[str, Any],
    contact_names: Mapping[str, tuple[str, ...]],
) -> tuple[list[Copper], list[Issue]]:
    if not copy.items and not copy.dropped:
        return [], []
    virtual = placed_model(model, definitions, placements)
    backend = KicadBackend()
    pads = backend.board_pads(virtual)
    assert virtual.board is not None
    components = {c.id: component_path(c) for c in virtual.circuit.components}
    paths = {fp.id: components[fp.component_id] for fp in virtual.board.footprints}
    contacts = {
        f"{paths[p.footprint_id][len(instance) + 1 :]}.{p.number}": p
        for p in pads
        if paths.get(p.footprint_id, "").startswith(f"{instance}/")
    }
    kept: list[CopiedItem] = []
    dropped = list(copy.dropped)
    for found in copy.items:
        item = found.item
        ends = (
            (item.start, item.end)
            if isinstance(item, (Track, Arc))
            else ((item.position,) if isinstance(item, Via) else ())
        )
        wanted = contact_names.get(found.source, ())
        layers = (item.layer,) if isinstance(item, (Track, Arc)) else item.layers
        allowed = {
            name: [
                index
                for index, end in enumerate(ends)
                if contacts.get(name) is not None and pad_contains(contacts[name], end, layers)
            ]
            for name in wanted
        }
        lost = [name for name in wanted if not allowed[name]]
        if len(wanted) == len(ends) == 2 and not any(
            a != b for a in allowed[wanted[0]] for b in allowed[wanted[1]]
        ):
            lost = list(wanted)
        if lost:
            dropped.append(
                Dropped(found.source, type(item).__name__.lower(), found.net, "pad-lost", ", ".join(lost))
            )
        else:
            kept.append(found)
    copy = CopperCopy(tuple(kept), copy.nets, tuple(dropped))

    def check(design: Design):  # type: ignore[no-untyped-def]
        edges, _issues = frame_edges(backend, design)
        return clashes_of(check_copper(design, pads=backend.board_pads(design), edges=edges).findings)

    modules = {module.id: module.path for module in virtual.circuit.modules}
    boundary_nets = frozenset(
        net
        for port in virtual.circuit.ports
        if modules.get(port.owner) == instance
        for net in port.members.values()
    )
    settled = settle_copper(virtual, copy, pads=pads, check=check, boundary_nets=boundary_nets)
    issues = list(settled.issues)
    issues += [
        issue(
            "reuse.copper-dropped",
            f"{instance}: {d.kind} {d.item} dropped as {d.reason}: {d.detail}",
            where=instance,
        )
        for d in settled.dropped
    ]
    items = [
        dataclasses.replace(
            found.item,
            locked=True,
            native_ids={"kicad": copper_uuid(f"block-layout:{instance}", found.source)},
        )
        for found in settled.kept
    ]
    return items, issues
