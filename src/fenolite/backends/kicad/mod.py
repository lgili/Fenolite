# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint library files (``.kicad_mod``) as ``FootprintDef`` definitions.

Facts, mapping tables and sources: ``docs/formats/kicad/libraries.md``. Each child is modelled,
projected (copied into a field and kept as an opaque slot) or opaque; slot lists persist in
``ext["kicad"]`` of the definition, of every pad and of every graphic.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._libread import (
    Context,
    Loaded,
    Source,
    child_locators,
    leading_atoms,
    load_source,
)
from fenolite.backends.kicad.liberrors import lib_issue
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps
from fenolite.backends.kicad.versions import FileKind
from fenolite.core.coords import Size
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.model.base import Slot
from fenolite.model.board import Graphic, GraphicKind, Pad, Padstack, PadstackLayer
from fenolite.model.library import FootprintDef, FootprintKind

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LIB-READ",))

GRAPHIC_HEADS: Mapping[str, GraphicKind] = MappingProxyType(
    {"fp_line": "line", "fp_arc": "arc", "fp_circle": "circle", "fp_rect": "rect", "fp_poly": "polygon"}
)
FOOTPRINT_FIELDS: Mapping[str, str] = MappingProxyType(
    {"descr": "description", "attr": "kind", "pad": "pads", **dict.fromkeys(GRAPHIC_HEADS, "graphics")}
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
_POINTS: Mapping[GraphicKind, tuple[str, ...]] = MappingProxyType(
    {
        "line": ("start", "end"),
        "arc": ("start", "mid", "end"),
        "circle": ("center", "end"),
        "rect": ("start", "end"),
    }
)
_FILLS = {"yes": True, "solid": True, "no": False, "none": False}
_PLAIN_STROKES = frozenset({"solid", "default"})
_ROOT = ("footprint",)


class _Ids:
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


def _text(node: Node) -> str:
    return " ".join(a.value for a in node.atoms())


def _symbols(node: Node) -> list[str]:
    return [a.value for a in node.atoms()]


def _replace(slots: list[Slot], index: int, slot: Slot) -> None:
    slots[index] = slot


def _size(ctx: Context, node: Node, locator: str) -> Size:
    point = ctx.point(node, locator)
    return Size(point.x, point.y)


def _padstack(
    ctx: Context, pad: Node, node: Node, pad_loc: str, loc: str, shape: str, size: Size, ids: _Ids
) -> Padstack:
    mode = node.find("mode")
    if mode is not None:
        value = " ".join(_symbols(mode))
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
        layer_shape = " ".join(_symbols(shape_node))
        if layer_shape not in PAD_SHAPES:
            raise ctx.error(f"unknown pad shape {layer_shape!r} in padstack layer {name!r}", layer_loc, child)
        layers.append(PadstackLayer(name, layer_shape, _size(ctx, size_node, f"{layer_loc}/size[0]")))  # type: ignore[arg-type]
    ident, native_ids = ids.of("pst", "pad", pad, ":padstack")
    return Padstack(id=ident, native_ids=native_ids, provenance=ctx.provenance(loc), layers=tuple(layers))


def _pad(ctx: Context, node: Node, loc: str, ids: _Ids) -> Pad:
    chain = (*_ROOT, "pad")
    atoms = leading_atoms(node)
    if len(atoms) < 3:
        raise ctx.error("a pad needs a number, a type and a shape", loc, node)
    number, kind, shape = atoms[0].value, atoms[1].value, atoms[2].value
    if kind not in PAD_KINDS:
        raise ctx.error(f"unknown pad type {kind!r}", loc, node)
    if shape not in PAD_SHAPES:
        raise ctx.error(f"unknown pad shape {shape!r}", loc, node)
    slots = ctx.split(node, dict(PAD_FIELDS), chain, PAD_POSITIONAL)
    position, rotation, size, drill = None, 0, None, None
    layers: tuple[str, ...] = ()
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
            size = _size(ctx, child, child_loc)
        elif head == "layers":
            layers = tuple(_symbols(child))
        elif head == "drill":
            drill = _drill(ctx, child, child_loc, slots, index, chain)
        elif head == "padstack":
            padstack_at = (index, child, child_loc)
    if position is None or size is None:
        raise ctx.error(f"pad {number!r} has no {'at' if position is None else 'size'}", loc, node)
    padstack = None
    if padstack_at is not None:
        index, child, child_loc = padstack_at
        padstack = _padstack(ctx, node, child, loc, child_loc, shape, size, ids)
        _replace(slots, index, ctx.opaque(child, chain))
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
        padstack=padstack,
    )


def _drill(
    ctx: Context, node: Node, loc: str, slots: list[Slot], index: int, chain: tuple[str, ...]
) -> int | None:
    """``(drill D)`` is modelled; an offset drill projects D; an oval or other form gives None."""
    atoms = node.atoms()
    numbers = [a for a in atoms if a.kind == AtomKind.NUMBER]
    lists = node.nodes()
    simple = len(atoms) == 1 and len(numbers) == 1
    if simple and not lists:
        return ctx.nm(numbers[0], loc, node)
    _replace(slots, index, ctx.opaque(node, chain))
    if simple and [c.name for c in lists] == ["offset"]:
        ctx.kept_opaque("drill offset is not modelled", loc)
        return ctx.nm(numbers[0], loc, node)
    ctx.kept_opaque("oval or unusual drill: drill is None", loc)
    return None


def _unrepresentable(node: Node, kind: GraphicKind) -> str | None:
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
        missing = [name for name in _POINTS[kind] if node.find(name) is None]
        if missing:
            return f"{kind} without {missing[0]}"
    fill = node.find("fill")
    if fill is not None:
        values = _symbols(fill)
        if fill.nodes() or len(values) != 1 or values[0] not in _FILLS:
            return f"fill {' '.join(values) or '(list)'} is not representable"
    if kind == "rect" and node.find("radius") is not None:
        return "rectangle with a corner radius"
    return None


def _graphic(ctx: Context, node: Node, loc: str, kind: GraphicKind, ids: _Ids) -> Graphic:
    chain = (*_ROOT, node.name)
    slots = ctx.split(node, dict(GRAPHIC_FIELDS), chain)
    if kind == "polygon":
        pts = node.find("pts")
        assert pts is not None
        points = tuple(ctx.point(c, f"{loc}/pts[0]/xy[{i}]") for i, c in enumerate(pts.nodes()))
    else:
        points = tuple(ctx.point(node.find(name), f"{loc}/{name}[0]") for name in _POINTS[kind])  # type: ignore[arg-type]
    layer_node = node.find("layer")
    assert layer_node is not None
    layer = _text(layer_node)
    fill = node.find("fill")
    filled = _FILLS[_symbols(fill)[0]] if fill is not None else False
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
            kind_text = _text(stroke_type) if stroke_type is not None else "default"
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


def read_footprint(
    source: Source, *, library: str | None = None, file: str = "", issues: list[Issue] | None = None
) -> FootprintDef:
    """One footprint from a ``.kicad_mod`` path, file text or a parsed node (see libraries.md)."""
    return footprint_from(load_source(source, file), library=library, issues=issues)


def footprint_from(
    loaded: Loaded, *, library: str | None = None, issues: list[Issue] | None = None
) -> FootprintDef:
    """``read_footprint`` on an already loaded input (the resolver's parse cache)."""
    ctx = Context(loaded, FileKind.FOOTPRINT, EVIDENCE, issues if issues is not None else [])
    root = loaded.node
    ctx.check_version("footprint", FileKind.FOOTPRINT)
    header = leading_atoms(root)
    if not header:
        raise ctx.error("footprint has no name", "/footprint", root)
    header_name = header[0].value
    name = header_name
    path = loaded.path
    if path is not None:
        name = path.stem
        if header_name != name:
            ctx.issues.append(
                lib_issue(
                    "kicad.lib.name-mismatch",
                    f"footprint file {path.name!r} declares the name {header_name!r}; "
                    f"the entry is named {name!r} after its file",
                    where=loaded.file,
                )
            )
    if library is None:
        library = path.parent.stem if path is not None and path.parent.suffix == ".pretty" else ""
    native = f"{library}:{name}" if library else name
    return _definition(ctx, root, name, library, native)


def _definition(ctx: Context, root: Node, name: str, library: str, native: str) -> FootprintDef:
    ids = _Ids(native)
    slots = ctx.split(root, dict(FOOTPRINT_FIELDS), _ROOT, ("name",))
    description, kind = "", "unspecified"
    flags: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    properties: dict[str, str] = {}
    models: list[str] = []
    pads: list[Pad] = []
    graphics: list[Graphic] = []
    for index, (loc, child) in enumerate(child_locators("/footprint", root)):
        if not isinstance(child, Node):
            continue
        head = child.name
        if head == "descr":
            if len(child.children) == 1 and isinstance(child.children[0], Atom):
                description = child.children[0].value
            else:
                _replace(slots, index, ctx.opaque(child, _ROOT))
        elif head == "attr":
            kind, flags = _attr(ctx, child, loc, slots, index)
        elif head == "tags":
            keywords = tuple(_text(child).split())
            _replace(slots, index, ctx.opaque(child, _ROOT))
        elif head == "property":
            atoms = leading_atoms(child)
            if len(atoms) >= 2:
                properties[atoms[0].value] = atoms[1].value
        elif head == "model":
            atoms = child.atoms()
            if atoms:
                models.append(atoms[0].value)
        elif head == "pad":
            pads.append(_pad(ctx, child, loc, ids))
        elif head in GRAPHIC_HEADS:
            graphic_kind = GRAPHIC_HEADS[head]
            reason = _unrepresentable(child, graphic_kind)
            if reason is None:
                graphics.append(_graphic(ctx, child, loc, graphic_kind, ids))
            else:
                _replace(slots, index, ctx.opaque(child, _ROOT))
                ctx.kept_opaque(f"{head}: {reason}; kept opaque", loc)
    return FootprintDef(
        id=derived_id("fpd", "kicad", native),
        native_ids={"kicad": native},
        provenance=ctx.provenance("/footprint"),
        ext={"kicad": slotlib.to_ext(slots)},
        name=name,
        library=library,
        description=description,
        keywords=keywords,
        kind=kind,  # type: ignore[arg-type]
        flags=flags,
        properties=properties,
        pads=tuple(pads),
        graphics=tuple(graphics),
        models=tuple(models),
    )


def _attr(
    ctx: Context, node: Node, loc: str, slots: list[Slot], index: int
) -> tuple[FootprintKind, tuple[str, ...]]:
    values = [a.value for a in node.atoms()]
    if node.nodes() or any(a.kind != AtomKind.SYMBOL for a in node.atoms()):
        _replace(slots, index, ctx.opaque(node, _ROOT))
        ctx.kept_opaque("attr with lists or quoted values: only its symbols are projected", loc)
    if values and values[0] in ("smd", "through_hole"):
        return values[0], tuple(values[1:])  # type: ignore[return-value]
    return "unspecified", tuple(values)


__all__ = [
    "EVIDENCE",
    "FOOTPRINT_FIELDS",
    "GRAPHIC_FIELDS",
    "GRAPHIC_HEADS",
    "PADSTACK_MODES",
    "PAD_FIELDS",
    "PAD_KINDS",
    "PAD_SHAPES",
    "read_footprint",
]
