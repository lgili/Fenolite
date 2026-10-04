# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint library files (``.kicad_mod``) as ``FootprintDef`` definitions.

Facts, mapping tables and sources: ``docs/formats/kicad/libraries.md``. Each child is modelled,
projected (copied into a field and kept as an opaque slot) or opaque; slot lists persist in
``ext["kicad"]`` of the definition, of every pad and of every graphic. ``write_footprint`` writes a
definition back for KiCad 9 or 10 ("Writing footprints"); ``board_footprints`` reads the footprints
placed in a board as definitions.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from fenolite.backends.kicad import _pcbwrite
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
    emit_footprint,
    padstack_key,
    projected_zone_connect,
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
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    FORMAT_VERSIONS,
    GENERATOR,
    TARGET_MAJORS,
    FileKind,
    FormatInfo,
    LossyWriteError,
    classify,
    major_for,
    require_editable,
)
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef, FootprintKind

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LIB-READ",))
AUTHORING_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DSL-FOOTPRINT",))

GRAPHIC_HEADS = FP_GRAPHIC_HEADS
FOOTPRINT_FIELDS: Mapping[str, str] = DEF_FIELDS
"""The definition field map; it lives in ``_fpmap`` (``DEF_FIELDS``), which the footprint emitter shares."""
_ROOT = ("footprint",)
BOARD_CHAIN = ("kicad_pcb", "footprint")
"""The root chain of a footprint placed in a board (``footprint_from``, ``board_footprints``)."""
HEADER_HEADS = ("version", "generator", "generator_version")
"""Header lists the footprint writer sets for the target, in this order."""
DROPPED_CODE = "kicad.footprint.dropped-too-new"
READ_ONLY_CODE = "kicad.footprint.projection-read-only"
WRITE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {DROPPED_CODE: "warning", READ_ONLY_CODE: "error"}
)
"""The closed table of the footprint writer's codes (libraries.md, "Writing footprints")."""


def _replace(slots: list[Slot], index: int, slot: Slot) -> None:
    slots[index] = slot


def read_footprint(
    source: Source, *, library: str | None = None, file: str = "", issues: list[Issue] | None = None
) -> FootprintDef:
    """One footprint from a ``.kicad_mod`` path, file text or a parsed node (see libraries.md)."""
    return footprint_from(load_source(source, file), library=library, issues=issues)


def footprint_from(
    loaded: Loaded,
    *,
    library: str | None = None,
    issues: list[Issue] | None = None,
    root_chain: tuple[str, ...] = _ROOT,
    index: int = 0,
) -> FootprintDef:
    """``read_footprint`` on an already loaded input (the resolver's parse cache).

    With ``root_chain == BOARD_CHAIN``, ``loaded`` is a board and the ``index``-th footprint placed in
    it is read as a definition (libraries.md, "Writing footprints").
    """
    if root_chain == BOARD_CHAIN:
        return _board_footprint(loaded, library, issues, index)
    if root_chain != _ROOT:
        raise ValueError(f"unsupported root chain {root_chain!r}; expected {_ROOT!r} or {BOARD_CHAIN!r}")
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


def _board_footprint(
    loaded: Loaded, library: str | None, issues: list[Issue] | None, index: int
) -> FootprintDef:
    ctx = Context(loaded, FileKind.BOARD, EVIDENCE, issues if issues is not None else [])
    ctx.check_version("kicad_pcb", FileKind.BOARD)
    footprints = loaded.node.nodes("footprint")
    if not 0 <= index < len(footprints):
        raise IndexError(f"the board has {len(footprints)} footprint(s); index {index} is out of range")
    root = footprints[index]
    base = f"/kicad_pcb/footprint[{index}]"
    header = leading_atoms(root)
    if not header:
        raise ctx.error("footprint has no name", base, root)
    nickname, colon, name = header[0].value.partition(":")
    if not colon:
        nickname, name = "", header[0].value
    library = nickname if library is None else library
    native = f"{library}:{name}" if library else name
    return _definition(ctx, root, name, library, native, BOARD_CHAIN, base)


def board_footprints(
    source: Source, *, file: str = "", issues: list[Issue] | None = None
) -> tuple[FootprintDef, ...]:
    """Every footprint placed in a board, read as a definition, in file order.

    Coordinates and angles are taken as stored, and board-only children stay opaque. The board's
    version issues are reported once.
    """
    loaded = load_source(source, file)
    found: list[FootprintDef] = []
    for index in range(len(loaded.node.nodes("footprint"))):
        own: list[Issue] = []
        found.append(footprint_from(loaded, issues=own, root_chain=BOARD_CHAIN, index=index))
        if issues is not None:
            issues.extend(i for i in own if index == 0 or not i.code.startswith("kicad.version."))
    return tuple(found)


def _definition(
    ctx: Context,
    root: Node,
    name: str,
    library: str,
    native: str,
    chain: tuple[str, ...] = _ROOT,
    base: str = "/footprint",
) -> FootprintDef:
    ids = Ids(native)
    slots = ctx.split(root, dict(FOOTPRINT_FIELDS), chain, DEF_POSITIONAL)
    description, kind = "", "unspecified"
    flags: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    properties: dict[str, str] = {}
    models: list[str] = []
    pads: list[Pad] = []
    graphics: list[Graphic] = []
    for index, (loc, child) in enumerate(child_locators(base, root)):
        if not isinstance(child, Node):
            continue
        head = child.name
        if head == "descr":
            if len(child.children) == 1 and isinstance(child.children[0], Atom):
                description = child.children[0].value
            else:
                _replace(slots, index, ctx.opaque(child, chain))
        elif head == "attr":
            kind, flags = _attr(ctx, child, loc, slots, index, chain)
        elif head == "tags":
            keywords = tuple(text_of(child).split())
            _replace(slots, index, ctx.opaque(child, chain))
        elif head == "property":
            atoms = leading_atoms(child)
            if len(atoms) >= 2:
                properties[atoms[0].value] = atoms[1].value
        elif head == "model":
            atoms = child.atoms()
            if atoms:
                models.append(atoms[0].value)
        elif head == "pad":
            pads.append(read_pad(ctx, child, loc, ids, root=chain))
        elif head in GRAPHIC_HEADS:
            graphic_kind = GRAPHIC_HEADS[head]
            reason = unrepresentable(child, graphic_kind)
            if reason is None:
                graphics.append(read_graphic(ctx, child, loc, graphic_kind, ids, root=chain))
            else:
                _replace(slots, index, ctx.opaque(child, chain))
                ctx.kept_opaque(f"{head}: {reason}; kept opaque", loc)
    return FootprintDef(
        id=derived_id("fpd", "kicad", native),
        native_ids={"kicad": native},
        provenance=ctx.provenance(base),
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
    ctx: Context, node: Node, loc: str, slots: list[Slot], index: int, chain: tuple[str, ...]
) -> tuple[FootprintKind, tuple[str, ...]]:
    values = [a.value for a in node.atoms()]
    if node.nodes() or any(a.kind != AtomKind.SYMBOL for a in node.atoms()):
        _replace(slots, index, ctx.opaque(node, chain))
        ctx.kept_opaque("attr with lists or quoted values: only its symbols are projected", loc)
    if values and values[0] in ("smd", "through_hole"):
        return values[0], tuple(values[1:])  # type: ignore[return-value]
    return "unspecified", tuple(values)


# --- the footprint writer -------------------------------------------------------------------------


def _slots(entity: FootprintDef | Pad | Graphic) -> list[Slot]:
    bag = entity.ext.get("kicad")
    return list(slotlib.from_ext(bag)) if bag is not None else []


def prepare_authored_definition(defn: FootprintDef) -> FootprintDef:
    """Give a slotless DSL definition the deterministic child order of a newly-authored file."""
    if _slots(defn):
        return defn
    root: list[Slot] = [Modeled("name"), Modeled("description"), Modeled("kind")]
    root.extend(Modeled("pads") for _ in defn.pads)
    root.extend(Modeled("graphics") for _ in defn.graphics)
    root.extend(Modeled("models") for _ in defn.models)
    pads = tuple(
        dataclasses.replace(
            pad,
            ext={
                **pad.ext,
                "kicad": slotlib.to_ext(
                    [
                        Modeled("number"),
                        Modeled("kind"),
                        Modeled("shape"),
                        Modeled("position"),
                        Modeled("size"),
                        Modeled("drill"),
                        Modeled("layers"),
                        Modeled("native_ids"),
                    ]
                ),
            },
        )
        for pad in defn.pads
    )
    graphics = tuple(
        dataclasses.replace(
            graphic,
            ext={
                **graphic.ext,
                "kicad": slotlib.to_ext(
                    [
                        Modeled("points"),
                        Modeled("layer"),
                        Modeled("width"),
                        Modeled("filled"),
                        Modeled("native_ids"),
                    ]
                ),
            },
        )
        for graphic in defn.graphics
    )
    return dataclasses.replace(
        defn, pads=pads, graphics=graphics, ext={**defn.ext, "kicad": slotlib.to_ext(root)}
    )


def _locator(entity: FootprintDef | Pad | Graphic, default: str) -> str:
    return entity.provenance.locator if entity.provenance is not None else default


def _source_version(defn: FootprintDef, slots: list[Slot]) -> int | None:
    """The format version the definition was read at: its header, or the newest opaque minimum."""
    for slot in slots:
        if isinstance(slot, Opaque) and slot.fragment.startswith("(version "):
            child = slotlib.opaque_child(slot)
            atoms = child.atoms() if isinstance(child, Node) else ()
            if atoms and atoms[0].text.isdigit():
                return int(atoms[0].text)
    bag = defn.ext.get("kicad")
    return int(bag.min_version) if bag is not None and bag.min_version else None


class _Projections:
    """Compares the opaque children that project a field with the definition (Decision 15 of c0018)."""

    def __init__(self) -> None:
        self.errors: list[Issue] = []

    def read_only(self, field: str, where: str, message: str) -> None:
        self.errors.append(
            Issue(
                READ_ONLY_CODE,
                "error",
                f"{field}: {message}",
                where=where,
                hint="the writer keeps this child as read; edit it in KiCad or keep the field unchanged",
            )
        )

    @staticmethod
    def children(slots: list[Slot], base: str) -> list[tuple[int, str, Node]]:
        """``(slot index, locator, child)`` for each opaque list child; heads are counted among them."""
        seen: dict[str, int] = {}
        out: list[tuple[int, str, Node]] = []
        for i, slot in enumerate(slots):
            if not isinstance(slot, Opaque):
                continue
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node):
                k = seen.get(child.name, 0)
                seen[child.name] = k + 1
                out.append((i, f"{base}/{child.name}[{k}]", child))
        return out

    def definition(self, defn: FootprintDef, slots: list[Slot]) -> None:
        base = _locator(defn, "/footprint")
        found: dict[str, tuple[str, str]] = {}
        keywords: tuple[str, ...] | None = None
        models: list[str] = []
        for i, loc, child in self.children(slots, base):
            if child.name == "property":
                atoms = leading_atoms(child)
                if len(atoms) < 2:
                    continue
                key, value = atoms[0].value, atoms[1].value
                wanted = defn.properties.get(key)
                if key in ("Reference", "Value") and wanted is not None and wanted != value:
                    renamed = child.with_children(
                        [child.children[0], Atom.string(wanted), *child.children[2:]]
                    )
                    slot = slots[i]
                    assert isinstance(slot, Opaque)
                    slots[i] = Opaque(dumps(renamed, style="compact"), slot.min_version)
                    value = wanted
                found[key] = (value, loc)
            elif child.name == "tags":
                keywords = tuple(text_of(child).split())
                if keywords != defn.keywords:
                    self.read_only("keywords", loc, "the tags are written as read")
            elif child.name == "model":
                atoms = child.atoms()
                if atoms:
                    models.append(atoms[0].value)
        if keywords is None and defn.keywords:
            self.read_only("keywords", base, "the footprint has no tags to hold them")
        if tuple(models) != defn.models:
            self.read_only("models", base, "3D model references are written as read")
        for key in sorted(set(found) | set(defn.properties)):
            value, loc = found.get(key, (None, base))
            if value != defn.properties.get(key):
                self.read_only("properties", loc, f"property {key!r} is written as read")

    def pad(self, pad: Pad, slots: list[Slot]) -> None:
        base = _locator(pad, "/footprint/pad")
        if pad.padstack is not None and pad.padstack.hole_shape == "slot":
            relative = pad.padstack.hole_rotation % 180_000_000
            if pad.padstack.hole_length is None or relative not in (0, 90_000_000):
                self.read_only(
                    "drill",
                    base,
                    "KiCad oval drills can encode only horizontal or vertical slot axes",
                )
        stack = [(loc, child) for _, loc, child in self.children(slots, base) if child.name == "padstack"]
        expected = (
            tuple((ps.layer, str(ps.shape), ps.size.w, ps.size.h) for ps in pad.padstack.layers)
            if pad.padstack is not None and pad.padstack.layers
            else None
        )
        found = padstack_key(pad, stack[0][1]) if stack else None
        if found != expected:
            self.read_only(
                "padstack", stack[0][0] if stack else base, "per-layer pad shapes are written as read"
            )
        connects = [loc for _, loc, child in self.children(slots, base) if child.name == "zone_connect"]
        if connects and projected_zone_connect(slots) != pad.zone_connection:
            self.read_only("zone_connection", connects[0], "the zone connection is written as read")

    def graphic(self, graphic: Graphic, slots: list[Slot]) -> None:
        base = _locator(graphic, "/footprint")
        for _, loc, child in self.children(slots, base):
            width = child.find("width") if child.name == "stroke" else None
            atoms = width.atoms() if width is not None else ()
            if atoms and atoms[0].kind == AtomKind.NUMBER and atoms[0].to_nm() != graphic.width:
                self.read_only("width", loc, "the stroke is written as read")


def _header(slots: list[Slot], target: int) -> list[Slot]:
    """``slots`` with the header lists of ``target`` in place, missing ones inserted after the name."""
    values = {
        "version": Atom(str(FORMAT_VERSIONS[FileKind.FOOTPRINT][target]), AtomKind.NUMBER),
        "generator": Atom.string(GENERATOR),
        "generator_version": Atom.string(f"{target}.0"),
    }
    fragments = {
        head: Opaque(dumps(Node(Atom.symbol(head), (value,)), style="compact"), None)
        for head, value in values.items()
    }
    out = list(slots)
    present: dict[str, int] = {}
    for i, slot in enumerate(out):
        if isinstance(slot, Opaque) and slot.fragment.startswith("("):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name in fragments:
                out[i] = fragments[child.name]
                present.setdefault(child.name, i)
    anchor = next((i for i, s in enumerate(out) if isinstance(s, Modeled) and s.field == "name"), -1)
    for head in HEADER_HEADS:
        if head in present:
            anchor = present[head]
            continue
        anchor += 1
        out.insert(anchor, fragments[head])
        present = {h: (j + 1 if j >= anchor else j) for h, j in present.items()}
    return out


def write_footprint(
    defn: FootprintDef,
    *,
    target: int = DEFAULT_TARGET,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> str:
    """The text of one ``.kicad_mod`` file for KiCad ``target``.0 (libraries.md, "Writing footprints").

    Warnings are appended to ``issues``; errors raise ``LossyWriteError`` or ``FutureFormatError``.
    """
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    defn = prepare_authored_definition(defn)
    slots = _slots(defn)
    version = _source_version(defn, slots)
    if version is not None:
        kind = FileKind.FOOTPRINT
        require_editable(FormatInfo(kind, version, major_for(kind, version), classify(kind, version)))
    checks = _Projections()
    checks.definition(defn, slots)
    for pad in defn.pads:
        checks.pad(pad, _slots(pad))
    for graphic in defn.graphics:
        checks.graphic(graphic, _slots(graphic))
    if checks.errors:
        raise LossyWriteError(checks.errors, droppable=False)
    bag = defn.ext["kicad"]
    edited = dataclasses.replace(
        defn, ext={**defn.ext, "kicad": slotlib.to_ext(_header(slots, target), base=bag)}
    )
    seen: set[int] = set()

    def opaque(slot: Opaque) -> Node | Atom:
        child = slotlib.opaque_child(slot)
        seen.add(id(child))
        return child

    root = emit_footprint(edited, root_chain=_ROOT, opaque=opaque)
    located = _pcbwrite.opaque_locators(root, seen)
    droppable, kept, others = _pcbwrite.gate(root, target, located, FileKind.FOOTPRINT)
    errors = [*checks.errors, *kept]
    found: list[Issue] = []
    if errors or droppable:
        lossy = [issue for group in droppable.values() for issue in group]
        if errors or not allow_lossy:
            raise LossyWriteError([*errors, *lossy], droppable=not errors)
        root = _pcbwrite.remove(root, droppable)
        found += [
            _pcbwrite.dropped(loc, _pcbwrite.head_at(loc), group, DROPPED_CODE)
            for loc, group in droppable.items()
        ]
        again, left, others = _pcbwrite.gate(root, target, located - set(droppable), FileKind.FOOTPRINT)
        if again or left:
            raise LossyWriteError([*left, *(i for g in again.values() for i in g)], droppable=False)
    if issues is not None:
        issues.extend([*found, *others])
    return dumps(root, style="kicad")


def write_pretty(
    defs: Iterable[FootprintDef],
    *,
    target: int = DEFAULT_TARGET,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> dict[str, str]:
    """``"<name>.kicad_mod"`` → text for each definition, sorted by name; nothing is written to disk."""
    chosen: dict[str, FootprintDef] = {}
    for defn in defs:
        if any(c in defn.name for c in "/\\:") or not defn.name:
            raise ValueError(f"footprint name {defn.name!r} cannot be a file name in a .pretty folder")
        if defn.name in chosen:
            raise ValueError(f"two footprints are named {defn.name!r}")
        chosen[defn.name] = defn
    return {
        f"{name}.kicad_mod": write_footprint(
            chosen[name], target=target, allow_lossy=allow_lossy, issues=issues
        )
        for name in sorted(chosen)
    }


__all__ = [
    "BOARD_CHAIN",
    "EVIDENCE",
    "FOOTPRINT_FIELDS",
    "GRAPHIC_FIELDS",
    "GRAPHIC_HEADS",
    "HEADER_HEADS",
    "PADSTACK_MODES",
    "PAD_FIELDS",
    "PAD_KINDS",
    "PAD_SHAPES",
    "WRITE_ISSUE_CODES",
    "board_footprints",
    "footprint_from",
    "read_footprint",
    "write_footprint",
    "write_pretty",
]
