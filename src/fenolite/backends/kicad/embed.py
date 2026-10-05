# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library footprints placed on a board: ``place_footprint`` and ``footprint_extent``.

Facts and Fenolite choices: ``docs/formats/kicad/board.md`` ("Placed footprints"). A placement emits
the definition as a board footprint, gives every uuid a value derived from the caller's key, mirrors
the children for the bottom side, stores child angles absolute, and maps the node with the board
reader, so the instance equals what ``read_board`` gives for the written board. The bottom-side rules
are ``KICAD-VERIFIED`` on 9.0.9 and 10.0.6 (``H-G-BOTTOM-STORE``, ``H-G-FLIP``, ``H-G-PAD-ANGLE-ABS``).
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import get_args

from fenolite.backends.kicad import pcb, versions
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import angle_atom, emit_footprint, node
from fenolite.backends.kicad.layers import flip_layer
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse_fragment, walk
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import FENOLITE_NS
from fenolite.core.units import Udeg
from fenolite.geometry.shapes import Arc, BBox, Circle
from fenolite.geometry.transform import Transform
from fenolite.model.base import Modeled, Opaque
from fenolite.model.board import FootprintAttribute, FootprintInstance, Graphic, Pad, Side
from fenolite.model.circuit import Component
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-G-BOTTOM-STORE", "H-G-FLIP", "H-G-PAD-ANGLE-ABS"))
"""Settled on 9.0.9 and 10.0.6 by DRC library parity (``tests/kicad/board/test_flip_oracle.py``)."""
PLACE_PREFIX = "kicad-place"
MIRROR_HEADS: frozenset[str] = frozenset({"at", "start", "mid", "end", "center", "xy", "offset"})
"""Heads whose Y is negated on the bottom side; ``offset`` only under ``drill``."""
FLIP_UNSUPPORTED: frozenset[str] = frozenset(
    {"rect_delta", "chamfer", "dimension", "image", "fp_text_box", "table", "barcode"}
)
"""Heads with geometry the mirror table does not cover; refused on the bottom side."""
HEADER = frozenset({"version", "generator", "generator_version"})
TEXT_HEADS = frozenset({"property", "fp_text"})
FLIP_CODE = "kicad.board.flip-unsupported"
PATH_PROPERTY = "fenolite.path"
"""The hidden property that names a built footprint's component path (c0011; read by c0019)."""
_ATTRIBUTES = frozenset(get_args(FootprintAttribute))


def placement_uuid(key: str, locator: str) -> str:
    """The uuid of the node at ``locator`` of a definition placed under ``key``."""
    return str(uuid.uuid5(FENOLITE_NS, f"{PLACE_PREFIX}:{key}:{locator}"))


def _source_info(defn: FootprintDef) -> versions.FormatInfo | None:
    bag = defn.ext.get("kicad")
    for key, value in bag.payload if bag is not None else ():
        if key.startswith("slot:.:opaque") and value.startswith("(version "):
            fragment = parse_fragment(value)
            assert isinstance(fragment, Node)
            number = int(fragment.atoms()[0].text)
            kind = versions.FileKind.FOOTPRINT
            return versions.FormatInfo(
                kind, number, versions.major_for(kind, number), versions.classify(kind, number)
            )
    return None


def _negate(atom: Atom) -> Atom:
    if atom.kind != AtomKind.NUMBER or Decimal(atom.text) == 0:
        return atom
    text = atom.text[1:] if atom.text.startswith("-") else "-" + atom.text
    return Atom(text, AtomKind.NUMBER)


def _mirror(child: Node, parent: str) -> Node:
    """``child`` with its Y negated when it is a point the mirror table covers."""
    if child.name not in MIRROR_HEADS or (child.name == "offset" and parent != "drill"):
        return child
    atoms = list(child.children)
    if len(atoms) >= 2 and isinstance(atoms[1], Atom):
        atoms[1] = _negate(atoms[1])
    return child.with_children(atoms)


def _flip_layers(child: Node) -> Node:
    if child.name not in ("layer", "layers"):
        return child
    out: list[Node | Atom] = []
    for part in child.children:
        if isinstance(part, Atom) and part.kind != AtomKind.NUMBER:
            flipped = flip_layer(part.value)
            out.append(part if flipped == part.value else Atom.string(flipped))
        else:
            out.append(part)
    return child.with_children(out)


def _flip(tree: Node, issues: list[Issue]) -> Node:
    """The bottom side: layers flipped, points mirrored about local X, texts on flipped layers mirrored."""

    def visit(current: Node, loc: str, parent: str) -> Node:
        if current.name == "model":
            return current
        if current.name in FLIP_UNSUPPORTED:
            issues.append(
                Issue(
                    FLIP_CODE,
                    "error",
                    f"'{current.name}' holds geometry that the bottom-side mirror does not cover",
                    where=loc,
                )
            )
        seen: dict[str, int] = {}
        children: list[Node | Atom] = []
        for child in current.children:
            if isinstance(child, Node):
                index = seen.get(child.name, 0)
                seen[child.name] = index + 1
                flipped = _flip_layers(
                    _mirror(visit(child, f"{loc}/{child.name}[{index}]", current.name), current.name)
                )
                children.append(flipped)
            else:
                children.append(child)
        result = current.with_children(children)
        if current.name in TEXT_HEADS and result.find("layer") != current.find("layer"):
            result = _toggle_mirror(result)
        return result

    return visit(tree, f"/{tree.name}", "")


def _toggle_mirror(text: Node) -> Node:
    """A text whose ``justify`` gains ``mirror``, or loses it when it had it."""
    effects = text.find("effects")
    mirror = Atom.symbol("mirror")
    if effects is None:
        return text.with_children([*text.children, node("effects", node("justify", mirror))])
    justify = effects.find("justify")
    if justify is None:
        new_effects = effects.with_children([*effects.children, node("justify", mirror)])
    elif mirror in justify.children:
        kept = [c for c in justify.children if c != mirror]
        rest = [c for c in effects.children if c is not justify]
        new_effects = effects.with_children(
            [justify.with_children(kept) if c is justify else c for c in effects.children] if kept else rest
        )
    else:
        new_effects = effects.with_children(
            [
                justify.with_children([*justify.children, mirror]) if c is justify else c
                for c in effects.children
            ]
        )
    return text.with_children([new_effects if c is effects else c for c in text.children])


def _angles(tree: Node, rotation: Udeg, *, bottom: bool) -> Node:
    """Every child ``at`` angle made absolute: ``((−φ if bottom else φ) + θ) mod 360°``."""
    children: list[Node | Atom] = []
    for child in tree.children:
        at = child.find("at") if isinstance(child, Node) else None
        if isinstance(child, Node) and at is not None:
            atoms = at.atoms()
            local = _udeg(atoms[2]) if len(atoms) > 2 else 0
            angle = pcb.pad_angle_to_board((-local if bottom else local) % pcb.FULL_TURN, rotation)
            values: list[Node | Atom] = list(atoms[:2])
            if len(atoms) > 2 or angle:
                values.append(angle_atom(angle))
            child = child.with_children([at.with_children(values) if c is at else c for c in child.children])
        children.append(child)
    return tree.with_children(children)


def _udeg(atom: Atom) -> int:
    value = Decimal(atom.text) * 1_000_000
    if value != value.to_integral_value():
        raise ValueError(f"angle {atom.text} is not a whole number of microdegrees")
    return int(value)


def _uuids(tree: Node, key: str) -> Node:
    """Every ``uuid`` replaced by its placement uuid; group ``members`` follow the new values."""
    mapping: dict[str, str] = {}
    for loc, current in walk(tree):
        found = current.find("uuid")
        if found is not None and found.atoms():
            mapping[found.atoms()[0].value] = placement_uuid(key, loc)

    def visit(current: Node, loc: str) -> Node:
        seen: dict[str, int] = {}
        children: list[Node | Atom] = []
        for child in current.children:
            if not isinstance(child, Node):
                children.append(child)
                continue
            index = seen.get(child.name, 0)
            seen[child.name] = index + 1
            if child.name == "uuid":
                children.append(node("uuid", Atom.string(placement_uuid(key, loc))))
            elif child.name == "members":
                children.append(
                    child.with_children(
                        [
                            Atom.string(mapping.get(a.value, a.value)) if isinstance(a, Atom) else a
                            for a in child.children
                        ]
                    )
                )
            else:
                children.append(visit(child, f"{loc}/{child.name}[{index}]"))
        return current.with_children(children)

    return visit(tree, f"/{tree.name}")


def uuid_locators(defn: FootprintDef) -> tuple[str, ...]:
    """The locators of every node of a placed copy of ``defn`` that holds a ``uuid``: the footprint itself
    and each node that ``place_footprint`` gives ``placement_uuid(key, locator)``. With them a caller can
    tell the uuids of the same definition placed under another key (``lens.moved.identity_map``)."""
    tree = emit_footprint(defn)
    tree = tree.with_children([c for c in tree.children if not (isinstance(c, Node) and c.name in HEADER)])
    found = ["/footprint"]
    for loc, current in walk(tree):
        if loc != "/footprint" and current.find("uuid") is not None:
            found.append(loc)
    return tuple(found)


def _header(tree: Node, defn: FootprintDef, component: Component, at: Point, rotation: Udeg, side: Side,
            locked: bool, key: str) -> Node:  # fmt: skip
    """Name, ``locked``, ``layer``, ``uuid`` and ``at`` in canonical position; Reference and Value set."""
    values = {"Reference": component.ref, "Value": component.value}
    body: list[Node | Atom] = []
    for child in tree.children[1:]:
        if isinstance(child, Node) and child.name in HEADER | {"layer", "locked", "uuid", "at"}:
            continue
        if isinstance(child, Node) and child.name == "property" and len(child.children) >= 2:
            name = child.children[0]
            if isinstance(name, Atom) and name.value in values:
                child = child.with_children([name, Atom.string(values[name.value]), *child.children[2:]])
        body.append(child)
    head: list[Node | Atom] = [Atom.string(defn.lib_id)]
    if locked:
        head.append(node("locked", Atom.symbol("yes")))
    head += [
        node("layer", Atom.string("B.Cu" if side == "bottom" else "F.Cu")),
        node("uuid", Atom.string(placement_uuid(key, "/footprint"))),
        node("at", Atom.from_nm(at.x), Atom.from_nm(at.y), *((angle_atom(rotation),) if rotation else ())),
    ]
    return tree.with_children([*head, *body])


def _copper_rows(copper: Sequence[str]) -> Node:
    rows: list[Node | Atom] = []
    for name in copper:
        number = 0 if name == "F.Cu" else 2 if name == "B.Cu" else 2 * int(name[2:].split(".")[0]) + 2
        rows.append(Node(Atom.integer(number), (Atom.string(name), Atom.symbol("signal"))))
    return node("layers", *rows)


def place_footprint(
    defn: FootprintDef,
    *,
    component: Component,
    at: Point,
    rotation: Udeg = 0,
    side: Side = "top",
    locked: bool = False,
    key: str,
    copper: Sequence[str] = ("F.Cu", "B.Cu"),
) -> FootprintInstance:
    """``defn`` placed at ``at`` with stored angle ``rotation`` on ``side`` (``board.md``).

    ``key`` names the placement stably (c0011 passes the component path); every uuid and id of the copy
    derives from it. ``copper`` lists the target board's copper layers, for wildcard pad layers.
    """
    info = _source_info(defn)
    if info is not None:
        versions.require_editable(info)
    tree = emit_footprint(defn)
    tree = tree.with_children([c for c in tree.children if not (isinstance(c, Node) and c.name in HEADER)])
    tree = _uuids(tree, key)
    if side == "bottom":
        issues: list[Issue] = []
        tree = _flip(tree, issues)
        if issues:
            raise versions.LossyWriteError(issues, droppable=False)
    tree = _angles(tree, rotation % pcb.FULL_TURN, bottom=side == "bottom")
    tree = _header(tree, defn, component, at, rotation % pcb.FULL_TURN, side, locked, key)
    major = info.major if info is not None and info.major is not None else versions.DEFAULT_TARGET
    version = versions.FORMAT_VERSIONS[versions.FileKind.BOARD][max(major, min(versions.TARGET_MAJORS))]
    board = node(
        "kicad_pcb",
        node("version", Atom.integer(version)),
        node("generator", Atom.string(versions.GENERATOR)),
        _copper_rows(copper),
        tree,
    )
    design = pcb.read_board(board)
    assert design.board is not None
    (instance,) = design.board.footprints
    attributes = tuple(a for a in (defn.kind, *defn.flags) if a in _ATTRIBUTES)
    return dataclasses.replace(instance, provenance=None, component_id=component.id, attributes=attributes)  # type: ignore[arg-type]


def with_property(defn: FootprintDef, *, name: str, value: str) -> FootprintDef:
    """A copy of ``defn`` with one hidden property appended after its last ``property`` child.

    The property has the form of the ``Datasheet`` property of the mini library and of boards written
    by 10.0.6 (``board.md``); its uuid is a placeholder that ``place_footprint`` replaces. ``defn`` is
    unchanged.
    """
    bag = defn.ext.get("kicad")
    slots = list(slotlib.from_ext(bag)) if bag is not None else []
    if not slots:
        raise ValueError(f"{defn.lib_id!r} has no KiCad slot list; only definitions read from a file")
    prop = node(
        "property",
        Atom.string(name),
        Atom.string(value),
        node("at", Atom.integer(0), Atom.integer(0), Atom.integer(0)),
        node("layer", Atom.string("F.Fab")),
        node("hide", Atom.symbol("yes")),
        node("uuid", Atom.string(str(uuid.uuid5(FENOLITE_NS, f"{PLACE_PREFIX}-property:{name}")))),
        node(
            "effects",
            node(
                "font",
                node("size", Atom.integer(1), Atom.integer(1)),
                node("thickness", Atom("0.15", AtomKind.NUMBER)),
            ),
        ),
    )
    last = max(
        (i for i, s in enumerate(slots) if isinstance(s, Opaque) and s.fragment.startswith("(property ")),
        default=-1,
    )
    if last < 0:
        last = max(
            (i for i, s in enumerate(slots) if isinstance(s, Modeled) and s.field == "name"), default=0
        )
    slots.insert(last + 1, Opaque(dumps(prop, style="compact"), bag.min_version if bag is not None else None))
    return dataclasses.replace(
        defn,
        ext={**defn.ext, "kicad": slotlib.to_ext(slots, base=bag)},
        properties={**defn.properties, name: value},
    )


def footprint_extent(defn: FootprintDef) -> BBox:
    """The courtyard box of ``defn`` in its own frame, else the union of its pad boxes, else empty."""
    boxes = [_graphic_box(g) for g in defn.graphics_on("F.CrtYd")]
    if not boxes:
        boxes = [_pad_box(pad) for pad in defn.pads]
    if not boxes:
        return BBox(0, 0, 0, 0)
    box = boxes[0]
    for other in boxes[1:]:
        box = box.union(other)
    return box


def _graphic_box(graphic: Graphic) -> BBox:
    if graphic.kind == "arc":
        return Arc(*graphic.points).bbox()
    if graphic.kind == "circle":
        return Circle.from_kicad(*graphic.points).bbox()
    return BBox.of_points(graphic.points)


def _pad_box(pad: Pad) -> BBox:
    w, h = pad.size.w, pad.size.h
    local = BBox(-(w - w // 2), -(h - h // 2), (w + 1) // 2, (h + 1) // 2)
    return Transform.placement(pad.position, pad.rotation).apply_bbox(local)


__all__ = [
    "EVIDENCE",
    "FLIP_UNSUPPORTED",
    "MIRROR_HEADS",
    "PATH_PROPERTY",
    "PLACE_PREFIX",
    "footprint_extent",
    "place_footprint",
    "placement_uuid",
    "with_property",
]
