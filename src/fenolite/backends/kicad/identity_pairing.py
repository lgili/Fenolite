# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Feature-keyed identity pairing of two boards for the private level-7 proof copy (c0384 2.1).

KiCad's teardrop generation orders neighbouring teardrops of different nets by the identities of their
pads, tracks and vias (native controls, ``tests/kicad/board/test_native_identity_controls.py``), and a
board built from code carries derived identities, never the source's. The level-7 derived-cache proof
therefore rewrites, on the generated side's private native input copy only, the identity of every root
segment, arc and via and every footprint pad to the identity of its source counterpart. The editable
model, the source, every written file and every other level stay untouched.

Each object is keyed by its complete non-identity content, its net named by the board's own declared net
name (net codes may differ; two canonical rules, ``net_keys``), the unique net child of a pad placed last
(its position is native-neutral) and a pad's footprint reference, layer and placement (quarter turns
compared modulo 360). A pairing exists only when both boards hold the same key multiset. Refused, never
first-matched: changed, missing or extra objects, duplicate signatures other than the one proven case,
malformed or duplicated identities, undeclared or contradictory nets, two codes for one name. The one
admitted duplicate is a group of exactly two pads that are identical apart from their identity on both
sides: exchanging their identities leaves every zone and fill byte-identical on native 10.0.6
(``test_fully_identical_pads_exchange_their_identities_without_changing_fills``); they pair in file order
and are listed. An object whose source identity is shared by several source objects keeps its own identity
and is listed, never rewritten.

The same pairing also gives the order preparation: the root segments, arcs and vias of the copy take the
file order of their source counterparts, in the slots they already occupy (one RoyalBlue teardrop outline
depends on track order, c0384 0.2). By c0275's design a build gives copper its own identities and order;
a proof after this preparation measures geometry once identity and order are aligned, and never claims that
Fenolite keeps the source's identities or order.
"""

# evidence: see pcb, schgen

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.kicad.netnames import SLASH, UNCONNECTED_PREFIX, model_name, pin_text
from fenolite.backends.kicad.sexpr import Atom, Node, dumps

IDS = frozenset({"uuid", "tstamp"})
ROOT_KINDS = frozenset({"segment", "arc", "via"})


def declarations(root: Node) -> dict[str, str]:
    """Net code → declared name; refuses malformed or duplicated declarations and two codes for one name."""
    names: dict[str, str] = {}
    for net in root.nodes("net"):
        atoms = net.atoms()
        if len(atoms) != 2 or net.nodes() or atoms[0].value in names:
            raise ValueError("net declaration missing, malformed or duplicated")
        names[atoms[0].value] = atoms[1].value
    if len(set(names.values())) != len(names):
        raise ValueError("two netcodes declare one net name; pairing refused")
    return names


SLASH_RULE = "slash"
UNCONNECTED_RULE = "unconnected-single-pad"


@dataclass(frozen=True, slots=True)
class NetKeys:
    """A board's declared net names and the name each net is paired under."""

    names: dict[str, str]
    """Net code → declared name."""
    keys: dict[str, str]
    """Net code → pairing key: the declared name, or its canonical name under one of the two rules."""
    canonical: tuple[tuple[str, str, str], ...]
    """``(rule, declared name, key)`` of every net whose key is not its declared name, in file order."""


def _single_pad_name(name: str, ref: str, number: str, pin: str | None) -> bool:
    """Whether ``name`` is KiCad's derived name of a pin on no net for this pad
    (``unconnected-(<ref>-Pad<number>)``, or ``unconnected-(<ref>[unit]-<pin name>-Pad<number>)`` with the
    pad's own pin name; ``netnames.unconnected_name``, ``H-K-SCH-UNCONNECTED``)."""
    if name == f"{UNCONNECTED_PREFIX}{ref}-Pad{number})":
        return True
    pattern = re.escape(UNCONNECTED_PREFIX + ref) + "[A-Z]?-" + re.escape(pin_text(pin or "")) + "-Pad"
    return bool(pin) and re.fullmatch(pattern + re.escape(number) + r"\)", name) is not None


def net_keys(root: Node) -> NetKeys:
    """The pairing key of every declared net (approved by the coordinator 2026-11-05, c0384).

    ``slash``: a ``{slash}`` in a stored name is the ``/`` of its label text (``netnames.model_name``; KiCad's
    parity test reads both as one, ``docs/formats/kicad/drc.md``). ``unconnected-single-pad``: a net whose
    name starts with ``unconnected-(`` must carry exactly one pad and be KiCad's derived name for that pad;
    it is keyed by that pad's reference and number. Refused: an ``unconnected-(`` net on no pad or several
    pads, or whose name does not derive from its pad, and two nets under one key."""
    names = declarations(root)
    pads: dict[str, list[tuple[str, str, str | None]]] = {}
    for footprint in root.nodes("footprint"):
        ref = parent(footprint).split("|", 1)[0]
        for pad in footprint.nodes("pad"):
            nets = pad.nodes("net")
            if len(nets) == 1 and nets[0].atoms():
                pin = [p.atoms()[0].value for p in pad.nodes("pinfunction") if p.atoms()]
                number = pad.atoms()[0].value if pad.atoms() else ""
                pads.setdefault(nets[0].atoms()[0].value, []).append((ref, number, pin[0] if pin else None))
    keys: dict[str, str] = {}
    canonical: list[tuple[str, str, str]] = []
    for code, name in names.items():
        key = name
        if name.startswith(UNCONNECTED_PREFIX):
            carried = pads.get(code, [])
            if len(carried) != 1:
                raise ValueError("unconnected net does not carry exactly one pad; pairing refused")
            ref, number, pin = carried[0]
            if not _single_pad_name(name, ref, number, pin):
                raise ValueError("unconnected net name does not derive from its pad; pairing refused")
            key = f"{UNCONNECTED_RULE}:{ref}:{number}"
            canonical.append((UNCONNECTED_RULE, name, key))
        elif SLASH in name:
            key = model_name(name)
            canonical.append((SLASH_RULE, name, key))
        keys[code] = key
    if len(set(keys.values())) != len(keys):
        raise ValueError("two nets share one canonical net name; pairing refused")
    return NetKeys(names, keys, tuple(canonical))


def content(node: Node, names: dict[str, str] | None = None, keys: dict[str, str] | None = None) -> str:
    """The object's complete content without its own identity; nets by declared name when ``names``, written
    under their ``keys`` when given (checked against ``names``)."""

    def named(child: Node | Atom) -> Node | Atom:
        if names is None or not isinstance(child, Node) or child.name != "net":
            return child
        atoms = child.atoms()
        if child.nodes() or not 1 <= len(atoms) <= 2 or atoms[0].value not in names:
            raise ValueError("object net is not a declared netcode")
        if len(atoms) == 2 and atoms[1].value != names[atoms[0].value]:
            raise ValueError("object net name contradicts its declaration")
        return child.with_children((Atom.string((keys or names)[atoms[0].value]),))

    kept = [named(c) for c in node.children if not (isinstance(c, Node) and c.name in IDS)]
    if node.name == "pad":
        # The unique pad net child's position is native-neutral (c0355 field-order control); a second net
        # child is never moved and keeps both apart.
        nets = [c for c in kept if isinstance(c, Node) and c.name == "net"]
        if len(nets) == 1:
            kept = [c for c in kept if c is not nets[0]] + nets
    return dumps(node.with_children(tuple(kept)), style="compact")


def parent(footprint: Node) -> str:
    """A pad's footprint context: reference, layer and placement (quarter turns modulo 360)."""
    refs = [
        p.atoms()[1].value
        for p in footprint.nodes("property")
        if len(p.atoms()) >= 2 and p.atoms()[0].value == "Reference"
    ]
    if len(refs) != 1:
        raise ValueError("footprint reference missing or duplicated")
    context: list[str] = []
    for child in footprint.nodes():
        if child.name == "layer":
            context.append(dumps(child, style="compact"))
        elif child.name == "at":
            atoms = child.atoms()
            if len(atoms) == 3 and Fraction(atoms[2].text) % 90 == 0:
                # Quarter turns written as -90 or 270 are the same pose (c0355 measured noncausal).
                context.append(f"(at {atoms[0].text} {atoms[1].text} {Fraction(atoms[2].text) % 360})")
            else:
                context.append(dumps(child, style="compact"))
    return "|".join((refs[0], *context))


def identity(node: Node) -> Node:
    """The object's own single identity field."""
    found = [c for c in node.children if isinstance(c, Node) and c.name in IDS]
    if len(found) != 1 or len(found[0].atoms()) != 1:
        raise ValueError("electrical object identity is missing, duplicated or malformed")
    return found[0]


def objects(
    root: Node, names: dict[str, str] | None, keys: dict[str, str] | None = None
) -> dict[str, list[Node]]:
    """Every root segment/arc/via and footprint pad under its key, in file order."""
    keyed: dict[str, list[Node]] = {}
    for child in root.nodes():
        if child.name in ROOT_KINDS:
            keyed.setdefault(child.name + "|" + content(child, names, keys), []).append(child)
        elif child.name == "footprint":
            context = parent(child)
            for pad in child.nodes("pad"):
                keyed.setdefault("pad|" + context + "|" + content(pad, names, keys), []).append(pad)
    return keyed


@dataclass(frozen=True, slots=True)
class Pairing:
    """Target identity → source identity for every rewritten object, with what was admitted or kept."""

    rewritten: tuple[tuple[str, str, str], ...]
    """``(kind, target identity, source identity)`` in target file order; only differing identities."""
    identical_pairs: tuple[tuple[str, str], ...]
    """Target identities of each admitted group of two fully identical pads."""
    source_aliases_kept: tuple[str, ...]
    """Target identities left unrewritten because their source identity names several source objects."""
    moved: tuple[tuple[str, str, int, int], ...] = ()
    """``(kind, target identity, old position, new position)`` of every root segment, arc and via whose
    position among the root segments, arcs and vias (0-based, file order) changes to its source
    counterpart's; the slots of all other root children stay as they are."""
    canonical_nets: tuple[tuple[str, str, str, str], ...] = ()
    """``(side, rule, declared name, key)`` of every net paired under a canonical name, ``a`` (source) then
    ``b`` (target), each in file order."""


def pair(source: Node, target: Node) -> Pairing:
    """The complete feature-keyed pairing of ``target`` onto ``source``; ``ValueError`` when refused."""
    na, nb = net_keys(source), net_keys(target)
    a, b = objects(source, na.names, na.keys), objects(target, nb.names, nb.keys)
    if {k: len(v) for k, v in a.items()} != {k: len(v) for k, v in b.items()}:
        raise ValueError("electrical objects differ; pairing refused")
    target_ids = Counter(identity(node).atoms()[0].value for nodes in b.values() for node in nodes)
    if any(n > 1 for n in target_ids.values()):
        raise ValueError("target identity aliases several objects; pairing refused")
    source_ids = Counter(identity(node).atoms()[0].value for nodes in a.values() for node in nodes)
    by_target: dict[str, tuple[str, str]] = {}
    identical: list[tuple[str, str]] = []
    kept: list[str] = []
    counterpart: dict[int, Node] = {}
    for key, mine in b.items():
        theirs = a[key]
        counterpart.update((id(node), other) for node, other in zip(mine, theirs, strict=True))
        if len(mine) > 1:
            if len(mine) != 2 or not key.startswith("pad|"):
                raise ValueError("duplicate electrical object signature; pairing refused")
            identical.append((identity(mine[0]).atoms()[0].value, identity(mine[1]).atoms()[0].value))
        for node, other in zip(mine, theirs, strict=True):
            old, new = identity(node).atoms()[0].value, identity(other).atoms()[0].value
            if source_ids[new] > 1:
                kept.append(old)
            elif old != new:
                by_target[old] = (key.split("|", 1)[0], new)
    order: list[tuple[str, str, str]] = []
    for child in target.nodes():
        nodes = (
            [child] if child.name in ROOT_KINDS else child.nodes("pad") if child.name == "footprint" else ()
        )
        for node in nodes:
            old = identity(node).atoms()[0].value
            if old in by_target:
                order.append((by_target[old][0], old, by_target[old][1]))
    rank = {id(node): k for k, node in enumerate(_roots(source))}
    roots = _roots(target)
    ordered = sorted(range(len(roots)), key=lambda k: rank[id(counterpart[id(roots[k])])])
    moved = tuple(
        (roots[old].name, identity(roots[old]).atoms()[0].value, old, new)
        for new, old in enumerate(ordered)
        if old != new
    )
    return Pairing(
        tuple(order),
        tuple(sorted(identical)),
        tuple(sorted(kept)),
        tuple(sorted(moved, key=lambda r: r[2])),
        tuple(("a", *row) for row in na.canonical) + tuple(("b", *row) for row in nb.canonical),
    )


def _roots(root: Node) -> list[Node]:
    return [c for c in root.nodes() if c.name in ROOT_KINDS]


def _reorder(target: Node, moved: tuple[tuple[str, str, int, int], ...]) -> Node:
    roots = _roots(target)
    slots: list[Node | None] = list(roots)
    for kind, ident, old, new in moved:
        if (
            not 0 <= old < len(roots)
            or not 0 <= new < len(roots)
            or roots[old].name != kind
            or identity(roots[old]).atoms()[0].value != ident
        ):
            raise ValueError("pairing does not match the board")
        slots[new] = None
    placed = {new for _, _, _, new in moved}
    if len(placed) != len(moved) or {old for _, _, old, _ in moved} != placed:
        raise ValueError("order preparation is not a permutation")
    for _, _, old, new in moved:
        slots[new] = roots[old]
    filled = [node for node in slots if node is not None]
    if len(filled) != len(roots):
        raise ValueError("order preparation is not a permutation")
    sequence = iter(filled)
    return target.with_children(
        tuple(next(sequence) if isinstance(c, Node) and c.name in ROOT_KINDS else c for c in target.children)
    )


def apply(target: Node, pairing: Pairing, *, order: bool = True) -> Node:
    """``target`` with the moved root objects in their source order (unless ``order`` is false) and the
    rewritten objects' own identity fields changed; nothing else."""
    if order and pairing.moved:
        target = _reorder(target, pairing.moved)
    mapping = {old: new for _, old, new in pairing.rewritten}
    seen: set[str] = set()

    def rewrite(node: Node | Atom, parent_name: str | None) -> Node | Atom:
        if isinstance(node, Atom):
            return node
        children = tuple(rewrite(c, node.name) for c in node.children)
        own = (node.name in ROOT_KINDS and parent_name == "kicad_pcb") or (
            node.name == "pad" and parent_name == "footprint"
        )
        if not own:
            return node.with_children(children)
        field = identity(node)
        old = field.atoms()[0].value
        if old not in mapping:
            return node.with_children(children)
        seen.add(old)
        new = field.with_children((Atom.string(mapping[old]),))
        return node.with_children(tuple(new if c is field else c for c in node.children))

    result = rewrite(target, None)
    if seen != set(mapping):
        raise ValueError("pairing does not match the board")
    assert isinstance(result, Node)
    return result


__all__ = [
    "SLASH_RULE",
    "UNCONNECTED_RULE",
    "NetKeys",
    "Pairing",
    "apply",
    "content",
    "declarations",
    "identity",
    "net_keys",
    "objects",
    "pair",
    "parent",
]
