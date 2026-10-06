# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic side of an Altium project for the parity comparison (``checks.parity``; capability
altium-verification, "Parity on Altium projects"; change c0088; ``docs/formats/altium/import.md``,
"Schematic side of the parity comparison").

The side is built from the imported schematic circuit: one component per designator, its value (the
comment), the name of its current footprint model, and the pads its pins name. A pin names the pad of its
own designator unless the component holds a pin-to-pad map (``Component.pin_pad_map``), which then
decides. The nodes are the members of the imported nets, per pad.

Two spellings differ between the two documents of every project without being a difference of the design,
so the side is given in the board's spelling where the content agrees (``side_of``): the library of a
footprint, and the name of a net whose pads are the pads of one net of the board. Nothing here reads a
file.
"""

# evidence: see import_evidence

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType

from fenolite.backends.base import SchematicSide, SideComponent
from fenolite.model.circuit import Component
from fenolite.model.design import Design

LIBRARY_SEPARATOR = ":"
Key = tuple[str, str]
"""A pad as both sides name it: (designator, pad number)."""


def footprint_name(reference: str) -> str:
    """A footprint reference without its library: the text after the last ``:``. The schematic names the
    library by the file of the footprint model and the PCB document by the library the component was
    placed from, so only the name is common to both."""
    return reference.rsplit(LIBRARY_SEPARATOR, 1)[-1]


def pads_of(component: Component) -> dict[str, tuple[str, ...]]:
    """Pin number → the pad numbers it names: those of ``pin_pad_map`` for a pin the map holds, else the
    pin's own number. A pin without a number names no pad."""
    mapped: dict[str, list[str]] = defaultdict(list)
    for pin, pad in component.pin_pad_map:
        mapped[pin].append(pad)
    return {
        pin.number: tuple(mapped[pin.number]) if pin.number in mapped else (pin.number,)
        for pin in component.pins
        if pin.number
    }


def _board_side(board: Design | None) -> tuple[dict[str, str], dict[Key, set[str]]]:
    """Designator → the footprint reference of its first footprint, and pad → the names of the nets its
    pads of that number are on (``""`` for a pad on no net), for the first footprint of each designator."""
    footprints: dict[str, str] = {}
    nets: dict[Key, set[str]] = defaultdict(set)
    if board is None or board.board is None:
        return footprints, nets
    refs = {component.id: component.ref for component in board.circuit.components}
    names = {net.id: net.name for net in board.circuit.nets}
    for footprint in board.board.footprints:
        ref = refs.get(footprint.component_id, "")
        if ref in footprints:
            continue
        footprints[ref] = footprint.lib_ref
        for pad in footprint.pads:
            if pad.number:
                nets[(ref, pad.number)].add(names.get(pad.net_id, "") if pad.net_id is not None else "")
    return footprints, nets


def board_names(nodes: dict[Key, str], on_board: dict[Key, set[str]]) -> dict[str, str]:
    """Schematic net name → the name of the one board net that holds the same pads, for every net whose
    name differs on the board only.

    Over the pads that both sides hold on a net, a schematic net and a board net are one net when every
    such pad of the first is on the second and every such pad of the second is on the first. Any other net
    keeps its name, so a net that the board splits, joins or leaves off stays a difference."""
    of_schematic: dict[str, set[str]] = defaultdict(set)
    of_board: dict[str, set[str]] = defaultdict(set)
    for key, name in nodes.items():
        placed = on_board.get(key)
        if placed is None or placed == {""}:
            continue
        of_schematic[name] |= placed
        for other in placed:
            of_board[other].add(name)
    renamed: dict[str, str] = {}
    for name, placed in of_schematic.items():
        if len(placed) != 1:
            continue
        (other,) = placed
        if other and other != name and of_board[other] == {name}:
            renamed[name] = other
    return renamed


def side_of(schematic: Design, board: Design | None = None) -> SchematicSide:
    """The side of the imported schematic ``schematic``. The first component of a designator stands for
    it; a component without a designator is left out, as the comparison keys on it.

    With ``board`` (the import of the project's PCB document) the side is given in the board's spelling
    where the content agrees: a footprint whose name equals the name of the footprint of the same
    designator on the board carries the board's reference, library included (``footprint_name``), and a
    net whose pads are those of one board net carries that net's name (``board_names``)."""
    footprints, on_board = _board_side(board)
    components: dict[str, SideComponent] = {}
    pads: dict[str, dict[str, tuple[str, ...]]] = {}
    by_id: dict[str, str] = {}
    for component in schematic.circuit.components:
        if not component.ref or component.ref in components:
            continue
        by_id[component.id] = component.ref
        pads[component.id] = pads_of(component)
        footprint = component.lib_footprint_ref
        placed = footprints.get(component.ref)
        if placed is not None and footprint_name(placed) == footprint_name(footprint):
            footprint = placed
        numbers = frozenset(pad for named in pads[component.id].values() for pad in named)
        components[component.ref] = SideComponent(component.value, footprint, numbers)
    nodes: dict[Key, str] = {}
    for net in schematic.circuit.nets:
        for member in net.members:
            named = pads.get(member.component_id)
            if named is None:
                continue
            for pad in named.get(member.pin, ()):
                nodes.setdefault((by_id[member.component_id], pad), net.name)
    renamed = board_names(nodes, on_board)
    spelled = {key: renamed.get(name, name) for key, name in nodes.items()}
    return SchematicSide(MappingProxyType(components), MappingProxyType(spelled))


__all__ = ["board_names", "footprint_name", "pads_of", "side_of"]
