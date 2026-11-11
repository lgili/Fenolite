# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Physical incidences of the resolved circuit, independent of schematic drawing geometry."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Circuit, PinRef


@dataclass(frozen=True, slots=True, order=True)
class PadIdentity:
    footprint_id: str
    pad_id: str


@dataclass(frozen=True, slots=True)
class Incidence:
    terminal: PinRef
    net_id: str
    pads: tuple[PadIdentity, ...]
    problem: (
        Literal["multiple_nets", "unknown_terminal", "missing_footprint", "missing_pad", "pad_net_mismatch"]
        | None
    ) = None


def resolved_incidences(circuit: Circuit, footprints: tuple[FootprintInstance, ...]) -> tuple[Incidence, ...]:
    """Bind resolved net members by component and pin identities, without joining nets or guessing pads."""
    components = {component.id: component for component in circuit.components}
    by_component: dict[str, list[FootprintInstance]] = defaultdict(list)
    for footprint in footprints:
        by_component[footprint.component_id].append(footprint)
    memberships: dict[PinRef, set[str]] = defaultdict(set)
    for net in circuit.nets:
        for member in net.members:
            memberships[member].add(net.id)

    rows: list[Incidence] = []
    for terminal, net_ids in sorted(memberships.items()):
        for net_id in sorted(net_ids):
            if len(net_ids) != 1:
                rows.append(Incidence(terminal, net_id, (), "multiple_nets"))
                continue
            component = components.get(terminal.component_id)
            if component is None or not any(pin.number == terminal.pin for pin in component.pins):
                rows.append(Incidence(terminal, net_id, (), "unknown_terminal"))
                continue
            owned = by_component.get(component.id)
            if not owned:
                rows.append(Incidence(terminal, net_id, (), "missing_footprint"))
                continue
            numbers = set(component.pads_of(terminal.pin))
            matching = [
                (PadIdentity(footprint.id, pad.id), pad)
                for footprint in owned
                for pad in footprint.pads
                if pad.number in numbers and pad.kind != "np_thru_hole"
            ]
            if any(pad.net_id != net_id for _, pad in matching):
                rows.append(Incidence(terminal, net_id, (), "pad_net_mismatch"))
            elif {pad.number for _, pad in matching} != numbers:
                rows.append(Incidence(terminal, net_id, (), "missing_pad"))
            else:
                rows.append(Incidence(terminal, net_id, tuple(sorted(key for key, _ in matching))))
    return tuple(rows)
