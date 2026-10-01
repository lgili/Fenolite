# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The footprint mapping shared by footprint files (``mod``) and boards (``pcb``): pads, drills,
padstacks and graphics, their scoped ids, and the field emitters that write them back.

Facts: ``docs/formats/kicad/libraries.md`` (footprints) and ``docs/formats/kicad/board.md``
(boards). Readers are parameterised by the root chain (``("footprint",)`` in a footprint file,
``("kicad_pcb", "footprint")`` for pads of a board, ``("kicad_pcb",)`` for board graphics), so that
anchored inventory rows match, and report kept-opaque children with the context's code. Emitters
return the items of each modelled field; ``pcb.ModelSource`` wraps them, so this module never imports
``pcb``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._libread import Context, child_locators, leading_atoms
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps
from fenolite.core.coords import Point, Size
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.core.units import format_angle
from fenolite.model.base import Slot
from fenolite.model.board import Graphic, GraphicKind, Pad, Padstack, PadstackLayer

FP_GRAPHIC_HEADS: Mapping[str, GraphicKind] = MappingProxyType(
    {"fp_line": "line", "fp_arc": "arc", "fp_circle": "circle", "fp_rect": "rect", "fp_poly": "polygon"}
)
GR_GRAPHIC_HEADS: Mapping[str, GraphicKind] = MappingProxyType(
    {"gr_line": "line", "gr_arc": "arc", "gr_circle": "circle", "gr_rect": "rect", "gr_poly": "polygon"}
)
PAD_FIELDS: Mapping[str, str] = MappingProxyType(
    {"at": "position", "size": "size", "layers": "layers", "uuid": "native_ids", "drill": "drill"}
)
PAD_POSITIONAL = ("number", "kind", "shape")
GRAPHIC_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        **dict.fromkeys(("start", "mid", "end", "center", "pts"), "points"),
        "layer": "layer",
        "uuid": "native_ids",
        "fill": "filled",
        "width": "width",
    }
)
PAD_KINDS: frozenset[str] = frozenset({"smd", "thru_hole", "np_thru_hole", "connect"})
PAD_SHAPES: frozenset[str] = frozenset({"circle", "rect", "oval", "roundrect", "trapezoid", "custom"})
PADSTACK_MODES: frozenset[str] = frozenset({"front_inner_back", "custom"})
POINT_HEADS: Mapping[GraphicKind, tuple[str, ...]] = MappingProxyType(
    {
        "line": ("start", "end"),
        "arc": ("start", "mid", "end"),
        "circle": ("center", "end"),
        "rect": ("start", "end"),
    }
)
_FILLS = {"yes": True, "solid": True, "no": False, "none": False}
_PLAIN_STROKES = frozenset({"solid", "default"})

Items = dict[str, list[Node | Atom]]
"""Field name → the children a modelled field emits, in order."""
LayerExpander = Callable[[tuple[str, ...]], "tuple[str, ...] | None"]
"""Expands wildcard layer names; returns ``None`` when the list has no wildcard."""
NetResolver = Callable[[Node, str], "tuple[str | None, bool]"]
"""Resolves a pad's ``net`` child to ``(net id, modelled)``; ``modelled`` false keeps it opaque."""


class IdSource(Protocol):
    """Gives ``(id, native_ids)`` for a node; ``section`` scopes content ids, ``suffix`` extends uuids."""

    def of(self, prefix: str, section: str, node: Node, suffix: str = "") -> tuple[str, dict[str, str]]: ...


class Ids:
    """Scoped ids of the sub-entities of one definition (see docs/design-model.md, "Library definitions").

    A uuid repeated inside one definition (copied graphics in the official library, S-0018) keeps the
    plain form for its first occurrence; the k-th repetition appends ``:<k>``, so ids stay unique.
    """

    def __init__(self, native: str) -> None:
        self.native = native
        self.seen: dict[tuple[str, str], int] = {}
        self.uuids: dict[tuple[str, str], int] = {}

    def of(self, prefix: str, section: str, node: Node, suffix: str = "") -> tuple[str, dict[str, str]]:
        uuid = node.find("uuid")
        atoms = uuid.atoms() if uuid is not None else ()
        if atoms:
            value = atoms[0].value
            repeat = self.uuids.get((prefix, value), 0)
            self.uuids[(prefix, value)] = repeat + 1
            native = f"{self.native}:{value}{suffix}" + (f":{repeat}" if repeat else "")
            return derived_id(prefix, "kicad", native), {"kicad": value}
        text = dumps(node, style="compact") + suffix
        count = self.seen.get((section, text), 0)
        self.seen[(section, text)] = count + 1
        return content_id(prefix, "kicad", self.native, section, content_hash(text, count)), {}


def text_of(node: Node) -> str:
    return " ".join(a.value for a in node.atoms())


def symbols(node: Node) -> list[str]:
    return [a.value for a in node.atoms()]


def size_of(ctx: Context, node: Node, locator: str) -> Size:
    point = ctx.point(node, locator)
    return Size(point.x, point.y)


def read_padstack(
    ctx: Context, pad: Node, node: Node, pad_loc: str, loc: str, shape: str, size: Size, ids: IdSource
) -> Padstack:
    mode = node.find("mode")
    if mode is not None:
        value = " ".join(symbols(mode))
        if value not in PADSTACK_MODES:
            raise ctx.error(f"unknown padstack mode {value!r}", pad_loc, pad)
    layers = [PadstackLayer("F.Cu", shape, size)]  # type: ignore[arg-type]
    for layer_loc, child in child_locators(loc, node):
        if not isinstance(child, Node) or child.name != "layer":
            continue
        names = child.atoms()
        name = names[0].value if names else ""
        shape_node, size_node = child.find("shape"), child.find("size")
        if shape_node is None or size_node is None:
            missing = "shape" if shape_node is None else "size"
            raise ctx.error(f"padstack layer {name!r} has no {missing}", layer_loc, child)
        layer_shape = " ".join(symbols(shape_node))
        if layer_shape not in PAD_SHAPES:
            raise ctx.error(f"unknown pad shape {layer_shape!r} in padstack layer {name!r}", layer_loc, child)
        layers.append(PadstackLayer(name, layer_shape, size_of(ctx, size_node, f"{layer_loc}/size[0]")))  # type: ignore[arg-type]
    ident, native_ids = ids.of("pst", "pad", pad, ":padstack")
    return Padstack(id=ident, native_ids=native_ids, provenance=ctx.provenance(loc), layers=tuple(layers))


def read_pad(
    ctx: Context,
    node: Node,
    loc: str,
    ids: IdSource,
    *,
    root: tuple[str, ...],
    fields: Mapping[str, str] = PAD_FIELDS,
    expand: LayerExpander | None = None,
    net: NetResolver | None = None,
) -> Pad:
    """One pad. ``expand`` and ``net`` are given for board pads (wildcard layers, net references)."""
    chain = (*root, "pad")
    atoms = leading_atoms(node)
    if len(atoms) < 3:
        raise ctx.error("a pad needs a number, a type and a shape", loc, node)
    number, kind, shape = atoms[0].value, atoms[1].value, atoms[2].value
    if kind not in PAD_KINDS:
        raise ctx.error(f"unknown pad type {kind!r}", loc, node)
    if shape not in PAD_SHAPES:
        raise ctx.error(f"unknown pad shape {shape!r}", loc, node)
    slots = ctx.split(node, dict(fields), chain, PAD_POSITIONAL)
    position, rotation, size, drill = None, 0, None, None
    layers: tuple[str, ...] = ()
    net_id: str | None = None
    padstack_at: tuple[int, Node, str] | None = None
    for index, (child_loc, child) in enumerate(child_locators(loc, node)):
        if not isinstance(child, Node):
            continue
        head = child.name
        if head == "at":
            position = ctx.point(child, child_loc)
            values = child.atoms()
            if len(values) > 2:
                rotation = ctx.udeg(values[2], child_loc, child)
        elif head == "size":
            size = size_of(ctx, child, child_loc)
        elif head == "layers":
            layers = tuple(symbols(child))
            expanded = expand(layers) if expand is not None else None
            if expanded is not None:
                layers = expanded
                slots[index] = ctx.opaque(child, chain)
        elif head == "drill":
            drill = read_drill(ctx, child, child_loc, slots, index, chain)
        elif head == "padstack":
            padstack_at = (index, child, child_loc)
        elif head == "net" and net is not None:
            net_id, modelled = net(child, child_loc)
            if not modelled:
                slots[index] = ctx.opaque(child, chain)
    if position is None or size is None:
        raise ctx.error(f"pad {number!r} has no {'at' if position is None else 'size'}", loc, node)
    padstack = None
    if padstack_at is not None:
        index, child, child_loc = padstack_at
        padstack = read_padstack(ctx, node, child, loc, child_loc, shape, size, ids)
        slots[index] = ctx.opaque(child, chain)
        ctx.kept_opaque("padstack: per-layer extras are not modelled", child_loc)
    ident, native_ids = ids.of("pad", "pad", node)
    return Pad(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(loc),
        ext={"kicad": slotlib.to_ext(slots)},
        number=number,
        shape=shape,  # type: ignore[arg-type]
        size=size,
        position=position,
        kind=kind,  # type: ignore[arg-type]
        rotation=rotation,
        drill=drill,
        layers=layers,
        net_id=net_id,
        padstack=padstack,
    )


def read_drill(
    ctx: Context, node: Node, loc: str, slots: list[Slot], index: int, chain: tuple[str, ...]
) -> int | None:
    """``(drill D)`` is modelled; an offset drill projects D; an oval or other form gives None."""
    atoms = node.atoms()
    numbers = [a for a in atoms if a.kind == AtomKind.NUMBER]
    lists = node.nodes()
    simple = len(atoms) == 1 and len(numbers) == 1
    if simple and not lists:
        return ctx.nm(numbers[0], loc, node)
    slots[index] = ctx.opaque(node, chain)
    if simple and [c.name for c in lists] == ["offset"]:
        ctx.kept_opaque("drill offset is not modelled", loc)
        return ctx.nm(numbers[0], loc, node)
    ctx.kept_opaque("oval or unusual drill: drill is None", loc)
    return None


def unrepresentable(node: Node, kind: GraphicKind) -> str | None:
    """Why a graphic cannot be represented, or None."""
    if node.find("layer") is None:
        return "graphic without a layer"
    if kind == "polygon":
        pts = node.find("pts")
        if pts is None:
            return "polygon without points"
        if any(c.name != "xy" for c in pts.nodes()):
            return "arc inside the points of a polygon"
    else:
        missing = [name for name in POINT_HEADS[kind] if node.find(name) is None]
        if missing:
            return f"{kind} without {missing[0]}"
    fill = node.find("fill")
    if fill is not None:
        values = symbols(fill)
        if fill.nodes() or len(values) != 1 or values[0] not in _FILLS:
            return f"fill {' '.join(values) or '(list)'} is not representable"
    if kind == "rect" and node.find("radius") is not None:
        return "rectangle with a corner radius"
    return None


def read_graphic(
    ctx: Context, node: Node, loc: str, kind: GraphicKind, ids: IdSource, *, root: tuple[str, ...]
) -> Graphic:
    chain = (*root, node.name)
    slots = ctx.split(node, dict(GRAPHIC_FIELDS), chain)
    if kind == "polygon":
        pts = node.find("pts")
        assert pts is not None
        points = tuple(ctx.point(c, f"{loc}/pts[0]/xy[{i}]") for i, c in enumerate(pts.nodes()))
    else:
        points = tuple(ctx.point(node.find(name), f"{loc}/{name}[0]") for name in POINT_HEADS[kind])  # type: ignore[arg-type]
    layer_node = node.find("layer")
    assert layer_node is not None
    layer = text_of(layer_node)
    fill = node.find("fill")
    filled = _FILLS[symbols(fill)[0]] if fill is not None else False
    width = 0
    for child_loc, child in child_locators(loc, node):
        if not isinstance(child, Node):
            continue
        if child.name == "width" and child.atoms():
            width = ctx.nm(child.atoms()[0], child_loc, child)
        elif child.name == "stroke":
            stroke_width, stroke_type = child.find("width"), child.find("type")
            if stroke_width is not None and stroke_width.atoms():
                width = ctx.nm(stroke_width.atoms()[0], f"{child_loc}/width[0]", stroke_width)
            kind_text = text_of(stroke_type) if stroke_type is not None else "default"
            if kind_text not in _PLAIN_STROKES:
                ctx.kept_opaque(f"stroke type {kind_text!r} is not modelled", child_loc)
    ident, native_ids = ids.of("gfx", "gfx", node)
    return Graphic(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(loc),
        ext={"kicad": slotlib.to_ext(slots)},
        kind=kind,
        layer=layer,
        points=points,
        width=width,
        filled=filled,
    )


# --- emitters -------------------------------------------------------------------------------------


def angle_atom(udeg: int) -> Atom:
    """An angle in degrees, the shortest exact decimal (``90``, ``-45``, ``30.5``)."""
    return Atom(format_angle(udeg, "deg")[: -len("deg")], AtomKind.NUMBER)


def node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


def point_node(head: str, point: Point, *extra: Atom) -> Node:
    return node(head, Atom.from_nm(point.x), Atom.from_nm(point.y), *extra)


def at_node(point: Point, udeg: int, *, always: bool = False) -> Node:
    """``(at X Y [ANGLE])``; the angle is omitted when it is zero unless ``always``."""
    return point_node("at", point, *((angle_atom(udeg),) if udeg or always else ()))


def uuid_items(native_ids: Mapping[str, str]) -> list[Node | Atom]:
    value = native_ids.get("kicad")
    return [node("uuid", Atom.string(value))] if value is not None else []


def layers_node(head: str, layers: tuple[str, ...]) -> Node:
    return node(head, *(Atom.string(name) for name in layers))


def emit_pad(pad: Pad, net: Node | None, *, angle: int | None = None) -> Items:
    """The modelled fields of a pad; ``angle`` replaces ``pad.rotation`` (a board stores it absolute)."""
    items: Items = {
        "number": [Atom.string(pad.number)],
        "kind": [Atom.symbol(pad.kind)],
        "shape": [Atom.symbol(pad.shape)],
        "position": [at_node(pad.position, pad.rotation if angle is None else angle)],
        "size": [node("size", Atom.from_nm(pad.size.w), Atom.from_nm(pad.size.h))],
        "layers": [layers_node("layers", pad.layers)],
        "native_ids": uuid_items(pad.native_ids),
        "drill": [] if pad.drill is None else [node("drill", Atom.from_nm(pad.drill))],
    }
    if net is not None:
        items["net_id"] = [net]
    return items


def emit_graphic(graphic: Graphic, head: str) -> Items:
    """The modelled fields of a graphic (``head`` is its ``fp_*`` or ``gr_*`` head)."""
    if graphic.kind == "polygon":
        points: list[Node | Atom] = [node("pts", *(point_node("xy", p) for p in graphic.points))]
    else:
        points = [
            point_node(name, p) for name, p in zip(POINT_HEADS[graphic.kind], graphic.points, strict=True)
        ]
    return {
        "points": points,
        "layer": [node("layer", Atom.string(graphic.layer))],
        "native_ids": uuid_items(graphic.native_ids),
        "filled": [node("fill", Atom.symbol("yes" if graphic.filled else "no"))],
        "width": [node("width", Atom.from_nm(graphic.width))],
    }


__all__ = [
    "FP_GRAPHIC_HEADS",
    "GRAPHIC_FIELDS",
    "GR_GRAPHIC_HEADS",
    "PADSTACK_MODES",
    "PAD_FIELDS",
    "PAD_KINDS",
    "PAD_POSITIONAL",
    "PAD_SHAPES",
    "POINT_HEADS",
    "IdSource",
    "Ids",
    "Items",
    "angle_atom",
    "at_node",
    "emit_graphic",
    "emit_pad",
    "layers_node",
    "node",
    "point_node",
    "read_drill",
    "read_graphic",
    "read_pad",
    "read_padstack",
    "size_of",
    "symbols",
    "text_of",
    "unrepresentable",
    "uuid_items",
]
