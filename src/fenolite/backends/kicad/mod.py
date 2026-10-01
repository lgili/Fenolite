# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint library files (``.kicad_mod``) as ``FootprintDef`` definitions.

Facts, mapping tables and sources: ``docs/formats/kicad/libraries.md``. Each child is modelled,
projected (copied into a field and kept as an opaque slot) or opaque; slot lists persist in
``ext["kicad"]`` of the definition, of every pad and of every graphic.
"""

from __future__ import annotations

from collections.abc import Mapping

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import (
    DEF_FIELDS,
    DEF_POSITIONAL,
    FP_GRAPHIC_HEADS,
    GRAPHIC_FIELDS,
    PAD_FIELDS,
    PAD_KINDS,
    PAD_SHAPES,
    PADSTACK_MODES,
    Ids,
    read_graphic,
    read_pad,
    text_of,
    unrepresentable,
)
from fenolite.backends.kicad._libread import (
    Context,
    Loaded,
    Source,
    child_locators,
    leading_atoms,
    load_source,
)
from fenolite.backends.kicad.liberrors import lib_issue
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.backends.kicad.versions import FileKind
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.base import Slot
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef, FootprintKind

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LIB-READ",))

GRAPHIC_HEADS = FP_GRAPHIC_HEADS
FOOTPRINT_FIELDS: Mapping[str, str] = DEF_FIELDS
"""The definition field map; it lives in ``_fpmap`` (``DEF_FIELDS``), which the footprint emitter shares."""
_ROOT = ("footprint",)


def _replace(slots: list[Slot], index: int, slot: Slot) -> None:
    slots[index] = slot


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
    ids = Ids(native)
    slots = ctx.split(root, dict(FOOTPRINT_FIELDS), _ROOT, DEF_POSITIONAL)
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
            keywords = tuple(text_of(child).split())
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
            pads.append(read_pad(ctx, child, loc, ids, root=_ROOT))
        elif head in GRAPHIC_HEADS:
            graphic_kind = GRAPHIC_HEADS[head]
            reason = unrepresentable(child, graphic_kind)
            if reason is None:
                graphics.append(read_graphic(ctx, child, loc, graphic_kind, ids, root=_ROOT))
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
