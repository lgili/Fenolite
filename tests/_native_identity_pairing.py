# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Test-only strict feature-keyed identity pairing for native controls (c0384 1.1).

The keys come from ``fenolite.backends.kicad.identity_pairing``, the private level-7 proof preparation;
this helper is stricter: it refuses every duplicate signature and every source alias.

Every root segment/arc/via and footprint pad is keyed by its complete non-identity content (all children
except its own ``uuid``/``tstamp``); a pad also carries its footprint's reference, placement and layer.
A pairing exists only when both boards hold the same key set with every key unique. Missing, extra,
changed or duplicated objects refuse; no first match, no pad-number or position fallback.
"""

from __future__ import annotations

from collections import Counter

from fenolite.backends.kicad.identity_pairing import ROOT_KINDS as _ROOT_KINDS
from fenolite.backends.kicad.identity_pairing import content as _content
from fenolite.backends.kicad.identity_pairing import declarations as _declarations
from fenolite.backends.kicad.identity_pairing import identity as _identity
from fenolite.backends.kicad.identity_pairing import parent as _parent
from fenolite.backends.kicad.sexpr import Atom, Node


def _objects(root: Node, by_name: bool = False) -> dict[str, Node]:
    names = _declarations(root) if by_name else None
    keyed: dict[str, Node] = {}
    counts: Counter[str] = Counter()
    for child in root.nodes():
        if child.name in _ROOT_KINDS:
            keys = [(child.name + "|" + _content(child, names), child)]
        elif child.name == "footprint":
            parent = _parent(child)
            keys = [("pad|" + parent + "|" + _content(pad, names), pad) for pad in child.nodes("pad")]
        else:
            continue
        for key, node in keys:
            counts[key] += 1
            keyed[key] = node
    if any(n > 1 for n in counts.values()):
        raise ValueError("duplicate electrical object signature; pairing refused")
    return keyed


def pair_identities(source: Node, target: Node, *, by_net_name: bool = False) -> dict[str, str]:
    """Target identity text -> source identity text for a complete, unique, feature-equal bijection.

    ``by_net_name`` keys each object's net by its declared name instead of its numeric code; the
    declarations must be complete and one-to-one on each board. Names are compared literally.
    """
    a, b = _objects(source, by_net_name), _objects(target, by_net_name)
    if set(a) != set(b):
        raise ValueError("electrical objects differ; pairing refused")
    mapping = {_identity(b[k]).atoms()[0].value: _identity(a[k]).atoms()[0].value for k in a}
    if len(mapping) != len(a):
        raise ValueError("target identity aliases several objects; pairing refused")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("source identity aliases several objects; pairing refused")
    return mapping


def apply_identities(target: Node, mapping: dict[str, str]) -> Node:
    """Rewrite only the paired objects' own identity fields; every other child is kept as it is."""
    seen: set[str] = set()

    def rewrite(node: Node | Atom, parent: str | None) -> Node | Atom:
        if isinstance(node, Atom):
            return node
        children = tuple(rewrite(c, node.name) for c in node.children)
        own = (node.name in _ROOT_KINDS and parent == "kicad_pcb") or (
            node.name == "pad" and parent == "footprint"
        )
        if not own:
            return node.with_children(children)
        field = _identity(node)
        old = field.atoms()[0].value
        if old not in mapping:
            raise ValueError("unpaired electrical identity")
        seen.add(old)
        new = field.with_children((Atom.string(mapping[old]),))
        return node.with_children(tuple(new if c is field else c for c in node.children))

    result = rewrite(target, None)
    if seen != set(mapping):
        raise ValueError("pairing does not cover the board")
    assert isinstance(result, Node)
    return result
