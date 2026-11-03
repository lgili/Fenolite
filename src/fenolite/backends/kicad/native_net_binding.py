# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Existing exact numbered physical net bindings, shared without an API-layer dependency."""

from __future__ import annotations

from collections import defaultdict

from fenolite.backends.kicad.derived_teardrops import native_net
from fenolite.backends.kicad.sexpr import AtomKind, Node
from fenolite.model.design import Design


def bindings(design: Design) -> dict[str, tuple[str, ...]]:
    refs = {component.id: component.ref for component in design.circuit.components}
    assignments = (
        (refs.get(footprint.component_id, "") + "-" + pad.number, pad.net_id or "")
        for footprint in (design.board.footprints if design.board is not None else ())
        for pad in footprint.pads
        if pad.number
    )
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    for element, net in assignments:
        if element in seen:
            if seen[element] != net:
                raise ValueError("ambiguous numbered-pad binding")
            continue
        seen[element] = net
        members[net].append(element)
    names = {net.id: net.name for net in design.circuit.nets}
    result: dict[str, tuple[str, ...]] = {}
    for net, elements in members.items():
        name = names.get(net)
        if name is None:
            continue
        if name in result:
            raise ValueError("ambiguous native net name")
        result[name] = tuple(sorted(elements))
    return result


def raw_bindings(root: Node, expected: frozenset[tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Bind complete electrical terminal signatures; retain all physical copies outside this set view."""
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    identities: dict[str, tuple[str, str]] = {}
    signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    for footprint in root.nodes("footprint"):
        terminals: dict[str, str] = {}
        for pad in footprint.nodes("pad"):
            atoms = pad.atoms()
            if not atoms or atoms[0].kind != AtomKind.STRING:
                raise ValueError("native pad number malformed")
            if not atoms[0].value or not pad.nodes("net"):
                continue
            net = native_net(pad, root)
            if not net:
                continue
            number = atoms[0].value
            if number in terminals and terminals[number] != net:
                raise ValueError("native numbered-pad identity ambiguous")
            terminals[number] = net
        if not terminals:
            continue  # No numbered electrical terminal to bind; no physical object is removed.
        references = [
            p.atoms()[1].value
            for p in footprint.nodes("property")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "Reference"
        ]
        references += [
            p.atoms()[1].value
            for p in footprint.nodes("fp_text")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "reference"
        ]
        if len(references) != 1 or not references[0]:
            raise ValueError("native electrical footprint has no unique reference")
        reference = references[0]
        signature = tuple(sorted(terminals.items()))
        if reference in signatures and signatures[reference] != signature:
            raise ValueError("native repeated reference has ambiguous terminal decomposition")
        signatures[reference] = signature
        for number, net in signature:
            element = reference + "-" + number
            identity = (reference, number)
            if element in identities and identities[element] != identity:
                raise ValueError("native terminal spelling is ambiguous")
            identities[element] = identity
            if element in seen:
                if seen[element] != net:
                    raise ValueError("native numbered-pad identity ambiguous")
                continue
            seen[element] = net
            members[net].append(element)
    result = {name: tuple(sorted(elements)) for name, elements in members.items()}
    if frozenset(result.values()) != expected:
        raise ValueError("native named-pad partitions changed")
    return result
