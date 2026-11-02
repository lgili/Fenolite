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

# evidence: see mod, pcb

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import teardrops as tdlib
from fenolite.backends.kicad import zones as zonelib
from fenolite.backends.kicad._libread import Context, child_locators, leading_atoms
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps
from fenolite.core.coords import Point, Size
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.core.units import format_angle
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import (
    CHAMFER_CORNERS,
    Graphic,
    GraphicKind,
    Pad,
    PadFabProperty,
    PadPrimitive,
    Padstack,
    PadstackLayer,
    ZoneConnection,
)
from fenolite.model.library import FootprintDef, ModelPlacement

FP_GRAPHIC_HEADS: Mapping[str, GraphicKind] = MappingProxyType(
    {"fp_line": "line", "fp_arc": "arc", "fp_circle": "circle", "fp_rect": "rect", "fp_poly": "polygon"}
)
GR_GRAPHIC_HEADS: Mapping[str, GraphicKind] = MappingProxyType(
    {"gr_line": "line", "gr_arc": "arc", "gr_circle": "circle", "gr_rect": "rect", "gr_poly": "polygon"}
)
PAD_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "at": "position",
        "size": "size",
        "layers": "layers",
        "uuid": "native_ids",
        "drill": "drill",
        "zone_connect": "zone_connection",
        "property": "fab_property",
    }
)
PAD_POSITIONAL = ("number", "kind", "shape")
PAD_CANONICAL: tuple[str, ...] = (
    *PAD_POSITIONAL, "position", "size", "trapezoid_delta", "drill", "fab_property", "layers", "corner_ratio",
    "chamfer_ratio", "chamfer_corners", "mask_margin", "paste_margin", "zone_connection", "anchor_shape",
    "primitives", "native_ids",
)  # fmt: skip
"""Where a library pad gains a child it did not have: ``zone_connect`` goes before ``uuid``, the
fabrication ``property`` after ``drill`` (or ``size``) and before ``layers``, and the two margins (change
c0223) after ``layers`` and before ``zone_connect``, in the order of S-0001."""
MARGIN_HEADS: Mapping[str, str] = MappingProxyType(
    {"solder_mask_margin": "mask_margin", "solder_paste_margin": "paste_margin"}
)
"""The margin children of a pad and their fields (change c0223): a reader projects the first child of each
into its field and keeps the child as an opaque slot; a writer writes the field for a pad without one."""
ZONE_CONNECT = "zone_connect"
NET_TIES = "net_tie_pad_groups"
"""The footprint child that lists the net-tie groups, one string per group (``libraries.md``, "Net-tie
groups"; change c0114). It is no field of ``DEF_FIELDS``: a read child stays an opaque slot, projected into
``net_ties``, and only an authored definition writes it from the field."""
FAB_PROPERTY = "property"
FAB_PROPERTY_TOKENS: Mapping[PadFabProperty, str] = MappingProxyType(
    {
        "bga": "pad_prop_bga",
        "fiducial_global": "pad_prop_fiducial_glob",
        "fiducial_local": "pad_prop_fiducial_loc",
        "test_point": "pad_prop_testpoint",
        "heatsink": "pad_prop_heatsink",
        "castellated": "pad_prop_castellated",
        "mechanical": "pad_prop_mechanical",
        "press_fit": "pad_prop_pressfit",
    }
)
"""``Pad.fab_property`` to the token of a pad's ``(property <token>)`` child (``board.md``,
``H-K-PAD-FABPROP``)."""
_FAB_PROPERTIES: Mapping[str, PadFabProperty] = MappingProxyType(
    {token: value for value, token in FAB_PROPERTY_TOKENS.items()}
)
DEF_FIELDS: Mapping[str, str] = MappingProxyType(
    {"descr": "description", "attr": "kind", "pad": "pads", **dict.fromkeys(FP_GRAPHIC_HEADS, "graphics")}
)
"""The field map of a footprint definition (``mod.FOOTPRINT_FIELDS`` is this mapping)."""
DEF_POSITIONAL = ("name",)
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
_FP_KIND_HEADS: Mapping[GraphicKind, str] = MappingProxyType(
    {kind: head for head, kind in FP_GRAPHIC_HEADS.items()}
)
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
    hole_shape, hole_length, hole_turn = "round", None, 0
    layers: tuple[str, ...] = ()
    net_id: str | None = None
    zone_connection: ZoneConnection | None = None
    padstack_at: tuple[int, Node, str] | None = None
    fab_property: PadFabProperty | None = None
    margins: dict[str, int] = {}
    connects = len(node.nodes(ZONE_CONNECT))
    marks = len(node.nodes(FAB_PROPERTY))
    for index, (child_loc, child) in enumerate(child_locators(loc, node)):
        if not isinstance(child, Node):
            continue
        head = child.name
        if head == ZONE_CONNECT:
            # one child with a code from 0 to 3 is modelled; a repeated one is projected from the first
            found = zonelib.read_pad_connect(child)
            if child_loc.endswith("[0]"):
                zone_connection = found
            if found is None or connects > 1:
                slots[index] = ctx.opaque(child, chain)
                why = "is repeated" if found is not None else "is not a code from 0 to 3"
                ctx.kept_opaque(f"zone_connect {why}; kept as written", child_loc)
        elif head == FAB_PROPERTY:
            # one child with a known token is modelled; a repeated one is projected from the first
            mark = read_fab_property(child)
            if child_loc.endswith("[0]"):
                fab_property = mark
            if mark is None or marks > 1:
                slots[index] = ctx.opaque(child, chain)
                why = "is repeated" if mark is not None else "is not a known fabrication property"
                ctx.kept_opaque(f"pad property {why}; kept as written", child_loc)
        elif head in MARGIN_HEADS:
            # projected from the first child (change c0223): the child stays an opaque slot
            value = margin_of(child)
            if value is not None and MARGIN_HEADS[head] not in margins:
                margins[MARGIN_HEADS[head]] = value
        elif head == "at":
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
            drill, hole_shape, hole_length, hole_turn = read_drill(ctx, child, child_loc, slots, index, chain)
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
    elif hole_shape == "slot":
        ident, native_ids = ids.of("pst", "pad", node, ":padstack")
        padstack = Padstack(
            id=ident,
            native_ids=native_ids,
            provenance=ctx.provenance(loc),
            hole_shape="slot",
            hole_length=hole_length,
            hole_rotation=hole_turn,  # in the pad's own frame, for a footprint file and for a board
        )
    ident, native_ids = ids.of("pad", "pad", node)
    shaped = project_shape(node)
    return Pad(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(loc),
        ext={"kicad": slotlib.to_ext(slots)},
        trapezoid_delta=shaped.get("trapezoid_delta"),  # type: ignore[arg-type]
        chamfer_ratio=shaped.get("chamfer_ratio"),  # type: ignore[arg-type]
        chamfer_corners=shaped.get("chamfer_corners", ()),  # type: ignore[arg-type]
        anchor_shape=shaped.get("anchor_shape"),  # type: ignore[arg-type]
        primitives=shaped.get("primitives", ()),  # type: ignore[arg-type]
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
        zone_connection=zone_connection,
        fab_property=fab_property,
        mask_margin=margins.get("mask_margin"),
        paste_margin=margins.get("paste_margin"),
    )


def margin_of(child: Node) -> int | None:
    """The margin in nm of a pad's ``solder_mask_margin`` or ``solder_paste_margin`` child, or ``None`` when
    it holds no single exact number."""
    atoms = child.atoms()
    if len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER:
        return None
    try:
        return atoms[0].to_nm()
    except ValueError:
        return None


def read_fab_property(child: Node) -> PadFabProperty | None:
    """The mark of a pad's ``(property <token>)`` child, or ``None`` for a token outside the table."""
    atoms = child.atoms()
    if len(atoms) != 1 or child.nodes():
        return None
    return _FAB_PROPERTIES.get(atoms[0].value)


def fab_property_node(value: PadFabProperty) -> Node:
    """``(property <token>)`` for a pad's mark."""
    return node(FAB_PROPERTY, Atom.symbol(FAB_PROPERTY_TOKENS[value]))


def read_drill(
    ctx: Context, node: Node, loc: str, slots: list[Slot], index: int, chain: tuple[str, ...]
) -> tuple[int | None, str, int | None, int]:
    """Round and oval drills are modelled; offsets and unusual forms stay opaque."""
    atoms = node.atoms()
    numbers = [a for a in atoms if a.kind == AtomKind.NUMBER]
    lists = node.nodes()
    simple = len(atoms) == 1 and len(numbers) == 1
    if simple and not lists:
        return ctx.nm(numbers[0], loc, node), "round", None, 0
    if len(atoms) == 3 and atoms[0].value == "oval" and len(numbers) == 2 and not lists:
        x_size, y_size = (ctx.nm(value, loc, node) for value in numbers)
        slots[index] = Modeled("drill")
        if x_size == y_size:
            return x_size, "round", None, 0
        return min(x_size, y_size), "slot", max(x_size, y_size), 90_000_000 if y_size > x_size else 0
    slots[index] = ctx.opaque(node, chain)
    if simple and [c.name for c in lists] == ["offset"]:
        ctx.kept_opaque("drill offset is not modelled", loc)
        return ctx.nm(numbers[0], loc, node), "round", None, 0
    ctx.kept_opaque("oval or unusual drill: drill is None", loc)
    return None, "round", None, 0


def padstack_key(pad: Pad, child: Node) -> tuple[tuple[str, str, int, int], ...] | None:
    """The padstack layers a ``padstack`` child stands for, as ``read_padstack`` reads them."""
    layers = [("F.Cu", str(pad.shape), pad.size.w, pad.size.h)]
    for row in child.nodes("layer"):
        names, shape, size = row.atoms(), row.find("shape"), row.find("size")
        if not names or shape is None or size is None or len(size.atoms()) != 2:
            return None
        try:
            w, h = (a.to_nm() for a in size.atoms())
        except ValueError:
            return None
        layers.append((names[0].value, " ".join(symbols(shape)), w, h))
    return tuple(layers)


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


MODEL_HEAD = "model"


def placement_node(placement: ModelPlacement) -> Node:
    """``(model "path" (offset (xyz X Y Z)) (scale (xyz …)) (rotate (xyz …)))`` of a placement (change c0223;
    ``libraries.md``, "Model placement"). KiCad's offset has Y up and its turn about Z is clockwise seen from
    above (``H-K-MODEL-PLACE``), so the writer negates the model's Y and its angles."""
    x, y, z = placement.offset
    rx, ry, rz = placement.rotation

    def xyz(head: str, *values: Atom) -> Node:
        return node(head, node("xyz", *values))

    return node(
        MODEL_HEAD,
        Atom.string(placement.path),
        xyz("offset", Atom.from_nm(x), Atom.from_nm(-y), Atom.from_nm(z)),
        xyz("scale", *(Atom.from_nm(value) for value in placement.scale)),
        xyz("rotate", *(angle_atom(-angle if angle else 0) for angle in (rx, ry, rz))),
    )


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


def aligned_slot_pad(pad: Pad) -> Pad:
    """Rotate a circular pad to an arbitrary slot axis without changing its copper (c0161)."""
    stack = pad.padstack
    if stack is None or stack.hole_shape != "slot" or stack.hole_rotation % 90000000 == 0:
        return pad
    if pad.shape not in ("circle", "oval") or pad.size.w != pad.size.h:
        raise ValueError(f"pad {pad.number}: KiCad writer cannot represent this slot rotation")
    if any(row.shape not in ("circle", "oval") or row.size.w != row.size.h for row in stack.layers):
        raise ValueError(f"pad {pad.number}: KiCad writer cannot represent this slot rotation")
    if any(row.offset != Point(0, 0) for row in stack.layers):
        raise ValueError(f"pad {pad.number}: KiCad writer cannot represent this slot rotation")
    turn = stack.hole_rotation
    return dataclasses.replace(
        pad,
        rotation=(pad.rotation + turn) % 360000000,
        padstack=dataclasses.replace(stack, hole_rotation=0),
    )


SHAPE_HEADS: Mapping[str, str] = MappingProxyType(
    {
        "rect_delta": "trapezoid_delta",
        "roundrect_rratio": "corner_ratio",
        "chamfer_ratio": "chamfer_ratio",
        "chamfer": "chamfer_corners",
        "options": "anchor_shape",
        "primitives": "primitives",
    }
)
"""The shape children of a pad and the fields they hold (change c0277): a reader projects them and keeps the
children as read; a created pad writes them from the fields, in the order of the demo boards (S-0058)."""
PRIMITIVE_HEADS: Mapping[str, str] = MappingProxyType(
    {"poly": "gr_poly", "segment": "gr_line", "circle": "gr_circle", "arc": "gr_arc"}
)
_PRIMITIVE_POINTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"gr_line": ("start", "end"), "gr_circle": ("center", "end"), "gr_arc": ("start", "mid", "end")}
)


def ppm_text(ppm: int) -> Atom:
    """A ratio in parts per million as the decimal KiCad writes (``250000`` → ``0.25``)."""
    whole, frac = divmod(abs(ppm), 1_000_000)
    text = ("-" if ppm < 0 else "") + str(whole) + (f".{frac:06d}".rstrip("0") if frac else "")
    return Atom(text, AtomKind.NUMBER)


def _ppm_of(child: Node) -> int | None:
    atoms = child.atoms()
    if len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER or child.nodes():
        return None
    try:
        scaled = Decimal(atoms[0].text).scaleb(6)
    except ArithmeticError:
        return None
    return int(scaled) if scaled == scaled.to_integral_value() and 0 <= scaled <= 500_000 else None


def _primitive_nodes(pad: Pad) -> list[Node | Atom]:
    out: list[Node | Atom] = []
    for shape in pad.primitives:
        head = PRIMITIVE_HEADS[shape.kind]
        if head == "gr_poly":
            children: list[Node | Atom] = [node("pts", *(point_node("xy", p) for p in shape.points))]
        else:
            children = [
                point_node(name, p) for name, p in zip(_PRIMITIVE_POINTS[head], shape.points, strict=True)
            ]
        children.append(node("width", Atom.from_nm(shape.width)))
        if head != "gr_line":
            children.append(node("fill", Atom.symbol("yes" if shape.filled else "no")))
        out.append(node(head, *children))
    return out


def shape_items(pad: Pad) -> Items:
    """The shape children of a created pad (change c0277): ``rect_delta``, ``roundrect_rratio``,
    ``chamfer_ratio`` with ``chamfer``, and a custom pad's ``options`` and ``primitives``; nothing for a field
    the pad does not set."""
    items: Items = {name: [] for name in SHAPE_HEADS.values()}
    if pad.trapezoid_delta is not None:
        delta = pad.trapezoid_delta
        items["trapezoid_delta"] = [node("rect_delta", Atom.from_nm(delta.x), Atom.from_nm(delta.y))]
    if pad.corner_ratio is not None and pad.shape == "roundrect":
        items["corner_ratio"] = [node("roundrect_rratio", ppm_text(pad.corner_ratio))]
    if pad.chamfer_ratio is not None:
        items["chamfer_ratio"] = [node("chamfer_ratio", ppm_text(pad.chamfer_ratio))]
        items["chamfer_corners"] = [node("chamfer", *(Atom.symbol(c) for c in pad.chamfer_corners))]
    if pad.shape == "custom" and pad.anchor_shape is not None:
        options = (node("clearance", Atom.symbol("outline")), node("anchor", Atom.symbol(pad.anchor_shape)))
        items["anchor_shape"] = [node("options", *options)]
        items["primitives"] = [node("primitives", *_primitive_nodes(pad))]
    return items


def project_shape(node_: Node) -> dict[str, object]:
    """The shape fields of a read pad from its children (change c0277); a child of another form gives no
    field. The children stay in their slots."""
    found: dict[str, object] = {}
    for child in node_.nodes():
        head = child.name
        if head == "rect_delta" and len(child.atoms()) == 2 and not child.nodes():
            try:
                found["trapezoid_delta"] = Point(child.atoms()[0].to_nm(), child.atoms()[1].to_nm())
            except ValueError:
                continue
        elif head == "chamfer_ratio":
            ratio = _ppm_of(child)
            if ratio is not None:
                found["chamfer_ratio"] = ratio
        elif head == "chamfer":
            names = [a.value for a in child.atoms()]
            if names and all(n in CHAMFER_CORNERS for n in names) and not child.nodes():
                found["chamfer_corners"] = tuple(c for c in CHAMFER_CORNERS if c in names)
        elif head == "options":
            anchor = child.find("anchor")
            shapes = [a.value for a in anchor.atoms()] if anchor is not None else []
            if len(shapes) == 1 and shapes[0] in ("circle", "rect"):
                found["anchor_shape"] = shapes[0]
        elif head == "primitives":
            shapes = _read_primitives(child)
            if shapes is not None:
                found["primitives"] = shapes
    if "chamfer_ratio" not in found or "chamfer_corners" not in found:
        found.pop("chamfer_ratio", None)
        found.pop("chamfer_corners", None)
    return found


def _read_primitives(child: Node) -> tuple[PadPrimitive, ...] | None:
    shapes: list[PadPrimitive] = []
    kinds = {head: kind for kind, head in PRIMITIVE_HEADS.items()}
    for item in child.nodes():
        kind = kinds.get(item.name)
        if kind is None:
            return None
        try:
            if item.name == "gr_poly":
                pts = item.find("pts")
                if pts is None or any(p.name != "xy" for p in pts.nodes()):
                    return None
                points = tuple(Point(p.atoms()[0].to_nm(), p.atoms()[1].to_nm()) for p in pts.nodes())
            else:
                found = [item.find(name) for name in _PRIMITIVE_POINTS[item.name]]
                if any(f is None or len(f.atoms()) != 2 for f in found):
                    return None
                points = tuple(Point(f.atoms()[0].to_nm(), f.atoms()[1].to_nm()) for f in found)  # type: ignore[union-attr]
            width_node = item.find("width")
            width = width_node.atoms()[0].to_nm() if width_node is not None and width_node.atoms() else 0
        except (ValueError, IndexError):
            return None
        fill = item.find("fill")
        filled = fill is not None and [a.value for a in fill.atoms()] == ["yes"]
        shapes.append(PadPrimitive(kind, points, width, filled))  # type: ignore[arg-type]
    return tuple(shapes)


def emit_pad(pad: Pad, net: Node | None, *, angle: int | None = None) -> Items:
    """The modelled fields of a pad; ``angle`` replaces ``pad.rotation`` (a board stores it absolute)."""
    original_rotation = pad.rotation
    pad = aligned_slot_pad(pad)
    if angle is not None:
        angle = (angle + pad.rotation - original_rotation) % 360000000
    drill_node: list[Node | Atom] = []
    if pad.drill is not None:
        stack = pad.padstack
        if stack is not None and stack.hole_shape == "slot":
            if stack.hole_length is None:
                raise ValueError(f"pad {pad.number}: KiCad writer cannot represent this slot rotation")
            # The slot's axis is in the pad's own frame, as KiCad stores it: along X or along Y.
            turn = stack.hole_rotation % 180_000_000
            if turn == 0:
                w, h = stack.hole_length, pad.drill
            elif turn == 90_000_000:
                w, h = pad.drill, stack.hole_length
            else:
                raise ValueError(f"pad {pad.number}: KiCad writer cannot represent this slot rotation")
            drill_node.append(node("drill", Atom.symbol("oval"), Atom.from_nm(w), Atom.from_nm(h)))
        else:
            drill_node.append(node("drill", Atom.from_nm(pad.drill)))
    items: Items = {
        "number": [Atom.string(pad.number)],
        "kind": [Atom.symbol(pad.kind)],
        "shape": [Atom.symbol(pad.shape)],
        "position": [at_node(pad.position, pad.rotation if angle is None else angle)],
        "size": [node("size", Atom.from_nm(pad.size.w), Atom.from_nm(pad.size.h))],
        "layers": [layers_node("layers", pad.layers)],
        "native_ids": uuid_items(pad.native_ids),
        "drill": drill_node,
        "zone_connection": (
            [] if pad.zone_connection is None else [zonelib.pad_connect_node(pad.zone_connection)]
        ),
        "fab_property": [] if pad.fab_property is None else [fab_property_node(pad.fab_property)],
        "mask_margin": []
        if pad.mask_margin is None
        else [node("solder_mask_margin", Atom.from_nm(pad.mask_margin))],
        "paste_margin": (
            [] if pad.paste_margin is None else [node("solder_paste_margin", Atom.from_nm(pad.paste_margin))]
        ),
        "teardrop": [] if pad.teardrop is None else [tdlib.emit(pad.teardrop)],
        **shape_items(pad),
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


def net_tie_groups(child: Node) -> tuple[tuple[str, ...], ...]:
    """The groups of one ``net_tie_pad_groups`` child: each string is split at commas, the spaces around a
    number and empty parts are dropped (``"1, 2"`` and ``"1,2"`` both give ``("1", "2")``), and a string
    without a number gives no group."""
    groups: list[tuple[str, ...]] = []
    for atom in child.atoms():
        numbers = tuple(part.strip() for part in atom.value.split(",") if part.strip())
        if numbers:
            groups.append(numbers)
    return tuple(groups)


def net_tie_node(groups: Sequence[Sequence[str]]) -> Node:
    """``(net_tie_pad_groups "1, 2" …)``: one string per group, its numbers joined with ``", "``."""
    return node(NET_TIES, *(Atom.string(", ".join(group)) for group in groups))


def projected_net_ties(slots: Sequence[Slot]) -> tuple[tuple[str, ...], ...] | None:
    """The groups that the opaque ``net_tie_pad_groups`` children of a footprint's slot list stand for, in
    slot order; ``None`` when it has no such child."""
    found: list[tuple[str, ...]] = []
    seen = False
    for slot in slots:
        if isinstance(slot, Opaque) and slot.fragment.startswith(f"({NET_TIES}"):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == NET_TIES:
                seen = True
                found.extend(net_tie_groups(child))
    return tuple(found) if seen else None


def emit_attr(kind: str, flags: Sequence[str]) -> Node:
    """``(attr KIND FLAG …)``; the kind ``unspecified`` is not written."""
    values = ([] if kind == "unspecified" else [kind]) + list(flags)
    return node("attr", *(Atom.symbol(v) for v in values))


class _Items:
    """A ``slots.SlotSource`` over prepared items (``pcb.ModelSource`` without importing ``pcb``)."""

    def __init__(self, items: Mapping[str, Sequence[Node | Atom]], wanted: set[str]) -> None:
        self._items = {k: tuple(v) for k, v in items.items() if k in wanted}

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self._items.get(field, ())

    def fields(self) -> list[str]:
        return [name for name, values in self._items.items() if values]


def _modelled(slots: Sequence[Slot]) -> set[str]:
    return {s.field for s in slots if isinstance(s, Modeled)}


def _entity_slots(entity: Pad | Graphic | FootprintDef) -> tuple[Slot, ...]:
    bag = entity.ext.get("kicad")
    return slotlib.from_ext(bag) if bag is not None else ()


def _graphic_head(graphic: Graphic) -> str:
    locator = graphic.provenance.locator if graphic.provenance is not None else ""
    head = locator.rsplit("/", 1)[-1].split("[", 1)[0]
    return head if head in FP_GRAPHIC_HEADS else _FP_KIND_HEADS[graphic.kind]


def emit_footprint(
    defn: FootprintDef,
    *,
    root_chain: tuple[str, ...] = ("footprint",),
    opaque: Callable[[Opaque], Node | Atom] = slotlib.opaque_child,
) -> Node:
    """A definition read from a file, emitted as a ``footprint`` node from its slots.

    Opaque children come back as read (through ``opaque``, which a writer passes to see each one);
    modelled ones from the definition's current values. Definitions without slots are refused.
    """
    slots = _entity_slots(defn)
    if not slots:
        raise ValueError(
            f"{defn.lib_id!r} has no KiCad slot list; only definitions read from a file are emitted"
        )
    pads = [_rebuild_pad(pad, opaque) for pad in defn.pads]
    graphics = [
        _rebuild(g, emit_graphic(g, _graphic_head(g)), _graphic_head(g), opaque=opaque) for g in defn.graphics
    ]
    items: dict[str, list[Node | Atom]] = {
        "name": [Atom.string(defn.name)],
        "description": [node("descr", Atom.string(defn.description))],
        "kind": [emit_attr(defn.kind, defn.flags)],
        "net_ties": [net_tie_node(defn.net_ties)] if defn.net_ties else [],
        "placements": [placement_node(placement) for placement in defn.placements],
        "pads": list(pads),
        "graphics": list(graphics),
    }
    return slotlib.rebuild(Atom.symbol(root_chain[-1]), slots, _Items(items, _modelled(slots)), opaque=opaque)


def opaque_zone_connects(slots: Sequence[Slot]) -> list[tuple[int, Node]]:
    """``(slot index, child)`` of each opaque ``zone_connect`` child of a pad's slot list."""
    out: list[tuple[int, Node]] = []
    for index, slot in enumerate(slots):
        if isinstance(slot, Opaque) and slot.fragment.startswith(f"({ZONE_CONNECT}"):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == ZONE_CONNECT:
                out.append((index, child))
    return out


def projected_zone_connect(slots: Sequence[Slot]) -> ZoneConnection | None:
    """The connection that the opaque ``zone_connect`` children of a pad stand for (the first one's)."""
    found = opaque_zone_connects(slots)
    return zonelib.read_pad_connect(found[0][1]) if found else None


def opaque_fab_properties(slots: Sequence[Slot]) -> list[tuple[int, Node]]:
    """``(slot index, child)`` of each opaque ``property`` child of a pad's slot list."""
    out: list[tuple[int, Node]] = []
    for index, slot in enumerate(slots):
        if isinstance(slot, Opaque) and slot.fragment.startswith(f"({FAB_PROPERTY}"):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == FAB_PROPERTY:
                out.append((index, child))
    return out


def projected_fab_property(slots: Sequence[Slot]) -> PadFabProperty | None:
    """The mark that the opaque ``property`` children of a pad stand for (the first one's)."""
    found = opaque_fab_properties(slots)
    return read_fab_property(found[0][1]) if found else None


def opaque_margins(slots: Sequence[Slot], head: str) -> list[Node]:
    """The opaque children of a pad's slot list whose head is ``head`` (a key of ``MARGIN_HEADS``)."""
    out: list[Node] = []
    for slot in slots:
        if isinstance(slot, Opaque) and slot.fragment.startswith(f"({head}"):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == head:
                out.append(child)
    return out


def margin_disagrees(pad: Pad, head: str, child: Node) -> bool:
    """Whether the pad's margin field is set and differs from the kept margin ``child`` (change c0223)."""
    value = getattr(pad, MARGIN_HEADS[head])
    return value is not None and margin_of(child) != value


def _rebuild_pad(pad: Pad, opaque: Callable[[Opaque], Node | Atom]) -> Node:
    """A library pad from its slots; a pad without a ``zone_connect`` or a fabrication ``property`` child
    gains one when the model sets ``zone_connection`` or ``fab_property``."""
    slots = _entity_slots(pad)
    wanted = _modelled(slots)
    if not opaque_zone_connects(slots):
        wanted = wanted | {"zone_connection"}
    if not opaque_fab_properties(slots):
        wanted = wanted | {"fab_property"}
    wanted = wanted | {field for head, field in MARGIN_HEADS.items() if not opaque_margins(slots, head)}
    source = _Items(emit_pad(pad, None), wanted)
    return slotlib.rebuild(Atom.symbol("pad"), slots, source, canonical=PAD_CANONICAL, opaque=opaque)


def _rebuild(
    entity: Pad | Graphic,
    items: Mapping[str, Sequence[Node | Atom]],
    head: str = "pad",
    *,
    opaque: Callable[[Opaque], Node | Atom] = slotlib.opaque_child,
) -> Node:
    slots = _entity_slots(entity)
    return slotlib.rebuild(Atom.symbol(head), slots, _Items(items, _modelled(slots)), opaque=opaque)


__all__ = [
    "DEF_FIELDS",
    "DEF_POSITIONAL",
    "FP_GRAPHIC_HEADS",
    "GRAPHIC_FIELDS",
    "GR_GRAPHIC_HEADS",
    "PADSTACK_MODES",
    "PAD_CANONICAL",
    "PAD_FIELDS",
    "PAD_KINDS",
    "PAD_POSITIONAL",
    "PAD_SHAPES",
    "POINT_HEADS",
    "FAB_PROPERTY_TOKENS",
    "IdSource",
    "Ids",
    "MARGIN_HEADS",
    "Items",
    "angle_atom",
    "at_node",
    "emit_attr",
    "emit_footprint",
    "emit_graphic",
    "emit_pad",
    "fab_property_node",
    "layers_node",
    "margin_disagrees",
    "margin_of",
    "net_tie_groups",
    "net_tie_node",
    "node",
    "opaque_fab_properties",
    "opaque_margins",
    "opaque_zone_connects",
    "padstack_key",
    "placement_node",
    "point_node",
    "projected_fab_property",
    "projected_net_ties",
    "projected_zone_connect",
    "read_drill",
    "read_fab_property",
    "read_graphic",
    "read_pad",
    "read_padstack",
    "size_of",
    "symbols",
    "text_of",
    "unrepresentable",
    "uuid_items",
]
