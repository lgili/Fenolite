# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout preservation: a rebuild keeps the work done in KiCad (``docs/lens.md``).

The existing board is the layout authority; there is no stored base. ``match_footprints`` pairs the
design's parts with the board's footprints (uuid, ``fenolite.path``, then a ``moved()`` alias);
``effective_placements`` applies the precedence locked ``place()`` > board > ``placements.toml`` >
``place()`` > staging; ``merge_layout`` keeps matched footprint nodes (under the new identity for an alias
match), copper on surviving or renamed nets and every other board content;
``drop_stale_fills`` drops fills whose text digests changed; ``merge_rules`` keeps the user's custom
rules after Fenolite's. Geometry is never computed: positions are integers and digests are text.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol, cast

from fenolite.backends.kicad import copper as copper_mod
from fenolite.backends.kicad import dru, pcb, pro, slots
from fenolite.backends.kicad import zones as zones_mod
from fenolite.backends.kicad.embed import PATH_PROPERTY, placement_uuid
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse_fragment
from fenolite.backends.kicad.versions import FileKind, FutureFormatError, load_inventory
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Udeg
from fenolite.lens.moved import resolve_aliases
from fenolite.model import canonical
from fenolite.model.base import Opaque, Slot
from fenolite.model.board import (
    Arc,
    Board,
    FootprintField,
    FootprintInstance,
    Graphic,
    Pad,
    Side,
    Track,
    Via,
    Zone,
)
from fenolite.model.circuit import Component, PinRef
from fenolite.model.design import Design

PRESERVE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "layout.copper-mismatch": "error",
        "layout.source-invalid": "error",
        "layout.orphan": "warning",
        "layout.alias-unused": "warning",
        "layout.net-alias-unused": "warning",
        "layout.source-unknown": "warning",
        "layout.place-forced": "warning",
        "layout.footprint-replaced": "warning",
        "layout.net-removed": "warning",
        "layout.outline-kept": "warning",
        "zone.fill-stale": "warning",
        "layout.place-overridden": "info",
        "layout.alias-used": "info",
        "layout.net-alias-used": "info",
        "layout.source-stale": "info",
        "layout.board-only": "info",
    }
)
EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-K-LENS-KEEP", "H-K-LENS-FILL", "H-K-UUID-KEEP-2", "H-K-BUILD-PATHPROP")
)
"""Joins the ``build`` envelope only when an existing board was read; stays ``INFERRED`` because the oracle
covers the edited blink, not every board."""
OVERRIDE_HINT = (
    "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout"
)
FILE_HINT = "lock the placement in the script, or edit placements.toml"
STALE_HINT = "run fenolite sync --to-source"
BAG = "kicad"


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, PRESERVE_ISSUE_CODES[code], message, where=where, hint=hint)


# --- existing files -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExistingProject:
    """The texts of the triad already in the output folder (``None`` when a file is absent)."""

    board: str | None = None
    project: str | None = None
    rules: str | None = None


def read_existing(out_dir: Path, name: str) -> ExistingProject:
    """The texts of ``<name>.kicad_pcb``, ``.kicad_pro`` and ``.kicad_dru`` in ``out_dir``."""
    texts: list[str | None] = []
    for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
        path = out_dir / f"{name}{suffix}"
        if not path.is_file():
            texts.append(None)
            continue
        try:
            texts.append(path.read_bytes().decode("utf-8"))
        except UnicodeDecodeError as error:
            raise FormatError(f"{name}{suffix} is not UTF-8 text: {error}", file=f"{name}{suffix}") from error
    return ExistingProject(*texts)


def footprint_uuid(path: str) -> str:
    """The KiCad uuid that the build gives the footprint of the part at component path ``path``."""
    return placement_uuid(path, "/footprint")


# --- matching -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FootprintMatch:
    path: str
    footprint: FootprintInstance
    key: Literal["uuid", "path", "alias"]


@dataclass(frozen=True)
class LayoutMatch:
    matches: Mapping[str, FootprintMatch]
    orphans: tuple[FootprintInstance, ...] = ()
    board_only: tuple[FootprintInstance, ...] = ()
    unused_aliases: tuple[tuple[str, str], ...] = ()


def _paths(design: Design) -> dict[str, Component]:
    """Component path → component, for components that carry ``fenolite.path``."""
    out: dict[str, Component] = {}
    for component in design.circuit.components:
        path = component.properties.get(PATH_PROPERTY)
        if path is not None:
            out.setdefault(path, component)
    return dict(sorted(out.items()))


def component_paths(design: Design) -> dict[str, Component]:
    """Component path → component, for the components that carry ``fenolite.path``, in path order."""
    return _paths(design)


def _footprint_paths(board: Design) -> dict[str, str | None]:
    """Footprint id → the ``fenolite.path`` of its component (``None`` without one)."""
    components = {c.id: c for c in board.circuit.components}
    out: dict[str, str | None] = {}
    for fp in board.board.footprints if board.board is not None else ():
        component = components.get(fp.component_id)
        out[fp.id] = component.properties.get(PATH_PROPERTY) if component is not None else None
    return out


def match_footprints(design: Design, board: Design, *, moves: Mapping[str, str] | None = None) -> LayoutMatch:
    """Each part of ``design`` paired with at most one footprint of ``board`` (``docs/lens.md``, "Keys")."""
    aliases = dict(moves or {})
    footprints = board.board.footprints if board.board is not None else ()
    fp_paths = _footprint_paths(board)
    by_uuid = {fp.native_ids.get(BAG): fp for fp in footprints if fp.native_ids.get(BAG)}
    used: set[str] = set()
    matches: dict[str, FootprintMatch] = {}
    paths = list(_paths(design))

    def by_property(path: str) -> FootprintInstance | None:
        return next((fp for fp in footprints if fp.id not in used and fp_paths.get(fp.id) == path), None)

    def take(path: str, fp: FootprintInstance | None, key: Literal["uuid", "path", "alias"]) -> None:
        if fp is not None and fp.id not in used:
            used.add(fp.id)
            matches[path] = FootprintMatch(path, fp, key)

    for path in paths:
        take(path, by_uuid.get(footprint_uuid(path)), "uuid")
    for path in paths:
        if path not in matches:
            take(path, by_property(path), "path")
    for path in paths:
        old = aliases.get(path)
        if path in matches or old is None:
            continue
        fp = by_uuid.get(footprint_uuid(old))
        take(path, fp if fp is not None and fp.id not in used else by_property(old), "alias")
    unused = tuple(
        (new, old)
        for new, old in sorted(aliases.items())
        if new not in matches or matches[new].key != "alias"
    )
    rest = [fp for fp in footprints if fp.id not in used]
    return LayoutMatch(
        dict(sorted(matches.items())),
        tuple(fp for fp in rest if fp_paths.get(fp.id) is not None),
        tuple(fp for fp in rest if fp_paths.get(fp.id) is None),
        unused,
    )


# --- placement precedence -------------------------------------------------------------------------


class PlacementLike(Protocol):
    """A requested placement, read by attribute (the structural twin of ``lens.build.PlacementRequest``)."""

    @property
    def at(self) -> Point: ...

    @property
    def rotation(self) -> Udeg: ...

    @property
    def side(self) -> Side: ...

    @property
    def locked(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class KeptPlacement:
    """A footprint's placement taken from the existing board."""

    at: Point
    rotation: Udeg
    side: Side
    locked: bool


def _edge_graphics(design: Design) -> list[Graphic]:
    board = design.board
    if board is None:
        return []
    edge = {layer.name for layer in board.layers if layer.kind == "edge"} or {"Edge.Cuts"}
    return [g for g in board.graphics if g.layer in edge]


def _outline_edges(points: Sequence[Point]) -> set[frozenset[Point]]:
    return {frozenset((points[i], points[(i + 1) % len(points)])) for i in range(len(points))}


def _edges_are_outline(design: Design, board: Design) -> bool:
    """The board's edge content is absent or exactly the lines of ``design``'s outline."""
    graphics = _edge_graphics(board)
    if not graphics:
        return True
    outline = design.board.outline if design.board is not None else None
    if outline is None or any(g.kind != "line" or len(g.points) != 2 for g in graphics):
        return False
    lines = [frozenset(g.points) for g in graphics]
    return len(lines) == len(set(lines)) == len(outline.points) and set(lines) == _outline_edges(
        outline.points
    )


def _off_board(fp: FootprintInstance, design: Design, board: Design) -> bool:
    outline = design.board.outline if design.board is not None else None
    if outline is None or not outline.points or not _edges_are_outline(design, board):
        return False
    xs, ys = [p.x for p in outline.points], [p.y for p in outline.points]
    return not (min(xs) <= fp.position.x <= max(xs) and min(ys) <= fp.position.y <= max(ys))


def off_board(fp: FootprintInstance, design: Design, board: Design) -> bool:
    """Whether ``fp`` lies outside the design's outline, so a build stages or re-places its part
    (``docs/lens.md``, "Placement precedence")."""
    return _off_board(fp, design, board)


def _same(a: PlacementLike, fp: FootprintInstance, *, lock: bool) -> bool:
    same = (a.at, a.rotation, a.side) == (fp.position, fp.rotation, fp.side)
    return same and (not lock or a.locked == fp.locked)


def _describe(at: Point, rotation: Udeg, side: Side) -> str:
    return f"({at.x / 1e6:g} mm, {at.y / 1e6:g} mm, {rotation / 1e6:g}°, {side})"


@dataclass(frozen=True, slots=True)
class FilePlacement(KeptPlacement):
    """A placement taken from the placements file: a ``KeptPlacement``, so the build writes the entry's
    lock, which gives the entry no precedence."""


def _same_place(a: PlacementLike, b: PlacementLike) -> bool:
    return (a.at, a.rotation, a.side) == (b.at, b.rotation, b.side)


def effective_placements(
    placements: Mapping[str, PlacementLike],
    match: LayoutMatch,
    *,
    design: Design,
    board: Design | None,
    source: Mapping[str, PlacementLike] | None = None,
) -> tuple[Mapping[str, PlacementLike], tuple[Issue, ...]]:
    """Each part's placement: locked ``place()`` > existing board > the placements file (``source``) >
    ``place()`` > staging (omitted). An entry of ``source`` that wins is given as a ``FilePlacement``."""
    entries = source or {}
    out: dict[str, PlacementLike] = {}
    issues: list[Issue] = []
    paths = _paths(design)
    for path in paths:
        request = placements.get(path)
        found = match.matches.get(path)
        entry = entries.get(path)
        fp = found.footprint if found is not None else None
        if request is not None and request.locked:
            out[path] = request
            if fp is not None and not _same(request, fp, lock=True):
                issues.append(
                    issue(
                        "layout.place-forced",
                        f"{path}: the locked place() {_describe(request.at, request.rotation, request.side)} "
                        f"re-places the footprint from {_describe(fp.position, fp.rotation, fp.side)}",
                        path,
                    )
                )
            continue
        if fp is not None and not (board is not None and _off_board(fp, design, board)):
            out[path] = KeptPlacement(fp.position, fp.rotation, fp.side, fp.locked)
            if request is not None and not _same(request, fp, lock=False):
                issues.append(
                    issue(
                        "layout.place-overridden",
                        f"{path}: place() {_describe(request.at, request.rotation, request.side)} is "
                        f"overridden by the board's {_describe(fp.position, fp.rotation, fp.side)}",
                        path,
                        OVERRIDE_HINT,
                    )
                )
            if entry is not None and not _same(entry, fp, lock=True):
                issues.append(
                    issue(
                        "layout.source-stale",
                        f"{path}: placements.toml has {_describe(entry.at, entry.rotation, entry.side)}"
                        f"{', locked' if entry.locked else ''} and the board keeps "
                        f"{_describe(fp.position, fp.rotation, fp.side)}{', locked' if fp.locked else ''}",
                        path,
                        STALE_HINT,
                    )
                )
            continue
        if entry is not None:
            out[path] = FilePlacement(entry.at, entry.rotation, entry.side, entry.locked)
            if request is not None and not _same_place(request, entry):
                issues.append(
                    issue(
                        "layout.place-overridden",
                        f"{path}: place() {_describe(request.at, request.rotation, request.side)} is "
                        f"overridden by placements.toml's {_describe(entry.at, entry.rotation, entry.side)}",
                        path,
                        FILE_HINT,
                    )
                )
            continue
        if request is not None:
            out[path] = request
    for path in sorted(set(entries) - set(paths)):
        issues.append(
            issue(
                "layout.source-unknown",
                f"placements.toml places {path!r}, which is not a part of the design",
                path,
                "remove the table, or run fenolite sync --to-source",
            )
        )
    return MappingProxyType(out), tuple(issues)


@dataclass(frozen=True)
class Prepared:
    """What ``build_design`` needs to merge with an existing project. ``aliases`` are the part aliases;
    ``net_aliases`` and ``module_aliases`` are the resolved net and module aliases (new → old)."""

    existing: ExistingProject
    board: Design | None
    match: LayoutMatch | None
    placements: Mapping[str, PlacementLike]
    issues: tuple[Issue, ...] = ()
    reader_infos: int = 0
    aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    net_aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    module_aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


def prepare(
    design: Design,
    placements: Mapping[str, PlacementLike],
    existing: ExistingProject,
    *,
    name: str,
    moves: Mapping[str, str] | None = None,
    module_moves: Mapping[str, str] | None = None,
    net_moves: Mapping[str, str] | None = None,
    source: Mapping[str, PlacementLike] | None = None,
) -> Prepared:
    """Read the existing board, resolve the aliases, match its footprints and decide the effective
    placements. Without a board, only the placements file (``source``) changes the placements."""
    if existing.board is None:
        aliases, _ = resolve_aliases(
            design, None, moves=moves, module_moves=module_moves, net_moves=net_moves
        )
        if not source:
            return Prepared(
                existing, None, None, placements, aliases=aliases.parts, module_aliases=aliases.modules
            )
        effective, more = effective_placements(
            placements, LayoutMatch(MappingProxyType({})), design=design, board=None, source=source
        )
        return Prepared(
            existing, None, None, effective, more, aliases=aliases.parts, module_aliases=aliases.modules
        )
    found: list[Issue] = []
    board = pcb.read_board(existing.board, file=f"{name}.kicad_pcb", issues=found)
    issues = [i for i in found if i.severity != "info"]
    aliases, alias_issues = resolve_aliases(
        design, board, moves=moves, module_moves=module_moves, net_moves=net_moves
    )
    issues += alias_issues
    match = match_footprints(design, board, moves=aliases.parts)
    for new, old in match.unused_aliases:
        issues.append(
            issue(
                "layout.alias-unused",
                f"moved({old!r}, {new!r}) matched nothing to keep; remove the alias",
                new,
            )
        )
    effective, more = effective_placements(placements, match, design=design, board=board, source=source)
    infos = sum(1 for i in found if i.severity == "info")
    return Prepared(
        existing,
        board,
        match,
        effective,
        (*issues, *more),
        infos,
        aliases.parts,
        aliases.nets,
        aliases.modules,
    )


# --- merging --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Merged:
    design: Design
    issues: tuple[Issue, ...]
    summary: Mapping[str, object]


def _slots(entity: FootprintInstance) -> tuple[Slot, ...]:
    bag = entity.ext.get(BAG)
    return slots.from_ext(bag) if bag is not None else ()


def _property_name(slot: Slot) -> str | None:
    if not isinstance(slot, Opaque) or not slot.fragment.startswith("(property"):
        return None
    node = parse_fragment(slot.fragment)
    if not isinstance(node, Node):
        return None
    atoms = node.atoms()
    return atoms[0].value if atoms else None


def _user_fields(built: FootprintInstance) -> list[tuple[str, str, FootprintField]]:
    """``(name, value, field)`` of the fields that the built copy holds after its ``fenolite.path`` field:
    the script's user properties (c0027 appends them as hidden properties, which read as fields)."""
    out: list[tuple[str, str, FootprintField]] = []
    seen_path = False
    for found in built.fields:
        if found.name == PATH_PROPERTY:
            seen_path = True
        elif seen_path:
            value = pcb.field_value(found)
            if value is not None:
                out.append((found.name, value, found))
    return out


def _with_name_and_value(fragment: str, name: str, value: str) -> str:
    node = parse_fragment(fragment)
    assert isinstance(node, Node)
    children = list(node.children)
    atoms = [i for i, c in enumerate(children) if isinstance(c, Atom)]
    children[atoms[0]] = Atom.string(name)
    children[atoms[1]] = Atom.string(value)
    return dumps(node.with_children(children), style="compact")


def _field_with_value(kept: FootprintField, name: str, value: str) -> FootprintField:
    """``kept`` with the script's spelling of its name and the script's value in its value-atom slot; every
    other value and slot stays the board's."""
    bag = kept.ext.get(BAG)
    current = list(slots.from_ext(bag)) if bag is not None else []
    index = pcb.field_value_slot(current)
    if index is None:
        return kept
    old = current[index]
    assert isinstance(old, Opaque)
    fragment = dumps(Atom.string(value), style="compact")
    if old.fragment == fragment and kept.name == name:
        return kept
    current[index] = Opaque(fragment, old.min_version)
    return dataclasses.replace(kept, name=name, ext={**kept.ext, BAG: slots.to_ext(current, bag)})


def _apply_user_properties(
    kept: FootprintInstance, built: FootprintInstance, path: str
) -> tuple[FootprintInstance, dict[str, str]]:
    """``kept`` with the script's user properties (c0019 Decision 22, carried to fields by c0030).

    A field of the same name, after ``str.casefold``, takes the script's value and spelling and keeps its
    placement, appearance, uuid and other slots. A property node of that name that is not a field takes
    name and value in its fragment. A missing one is added after the last field as the built copy's field,
    with a name-derived uuid. Returns the footprint and the user properties written.
    """
    wanted = _user_fields(built)
    current = list(_slots(kept))
    opaque_names = {i: _property_name(s) for i, s in enumerate(current)}
    held = {f.name for f in kept.fields} | {n for n in opaque_names.values() if n is not None}
    if PATH_PROPERTY not in held or not wanted:
        return kept, {}
    fields = list(kept.fields)
    key = kept.native_ids.get(BAG, kept.id)
    written: dict[str, str] = {}
    for name, value, built_field in wanted:
        written[name] = value
        folded = name.casefold()
        at = next(
            (i for i, f in enumerate(fields) if f.name.casefold() == folded and f.name != PATH_PROPERTY), None
        )
        if at is not None:
            fields[at] = _field_with_value(fields[at], name, value)
            continue
        index = next(
            (
                i
                for i, n in opaque_names.items()
                if n is not None and n.casefold() == folded and n != PATH_PROPERTY
            ),
            None,
        )
        if index is not None:
            old = current[index]
            assert isinstance(old, Opaque)
            current[index] = Opaque(_with_name_and_value(old.fragment, name, value), old.min_version)
            opaque_names[index] = name
            continue
        fields.append(
            dataclasses.replace(
                built_field,
                id=derived_id("fld", BAG, f"{key}:field:{name}"),
                native_ids={BAG: placement_uuid(path, f"/footprint/property:{name}")},
                provenance=None,
            )
        )
    bag = slots.to_ext(current, kept.ext.get(BAG))
    return dataclasses.replace(kept, fields=tuple(fields), ext={**kept.ext, BAG: bag}), written


def _net_names(design: Design) -> dict[str, str]:
    return {n.id: n.name for n in design.circuit.nets}


_NOT_REKEYED = frozenset({"id", "component_id", "net_id", "provenance"})
"""Entity fields that hold model ids or provenance, never a KiCad uuid."""


def _rekey(value: object, mapping: Mapping[str, str]) -> object:
    """``value`` with every KiCad uuid that is a key of ``mapping`` replaced, in native ids and in the
    verbatim fragments of the extension bags; every other text stays."""
    if isinstance(value, str):
        if len(value) < 36:
            return value
        if value in mapping:
            return mapping[value]
        for old, new in mapping.items():
            if old in value:
                value = value.replace(old, new)
        return value
    if isinstance(value, tuple):
        old_items = cast(tuple[object, ...], value)
        items = tuple(_rekey(item, mapping) for item in old_items)
        return items if any(a is not b for a, b in zip(items, old_items, strict=True)) else old_items
    if isinstance(value, Mapping):
        return {key: _rekey(item, mapping) for key, item in cast(Mapping[object, object], value).items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes: dict[str, object] = {}
        for found in dataclasses.fields(value):
            if found.name in _NOT_REKEYED:
                continue
            current = getattr(value, found.name)
            renamed = _rekey(current, mapping)
            if renamed is not current and renamed != current:
                changes[found.name] = renamed
        return dataclasses.replace(value, **changes) if changes else value
    return value


def _with_path(kept: FootprintInstance, path: str) -> FootprintInstance:
    """``kept`` with its ``fenolite.path`` property set to ``path``, as a field or as an opaque node."""
    fields = tuple(
        _field_with_value(f, PATH_PROPERTY, path) if f.name == PATH_PROPERTY else f for f in kept.fields
    )
    current = list(_slots(kept))
    changed = False
    for index, slot in enumerate(current):
        if _property_name(slot) == PATH_PROPERTY:
            assert isinstance(slot, Opaque)
            current[index] = Opaque(
                _with_name_and_value(slot.fragment, PATH_PROPERTY, path), slot.min_version
            )
            changed = True
    ext = {**kept.ext, BAG: slots.to_ext(current, kept.ext.get(BAG))} if changed else kept.ext
    return dataclasses.replace(kept, fields=fields, ext=ext)


def _group_members(fragment: str, mapping: Mapping[str, str]) -> str:
    """A root ``group`` fragment whose ``members`` atoms follow ``mapping``; anything else unchanged."""
    if not fragment.startswith("(group") or not any(old in fragment for old in mapping):
        return fragment
    node = parse_fragment(fragment)
    if not isinstance(node, Node) or node.name != "group":
        return fragment
    children: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node) and child.name == "members":
            child = child.with_children(
                [
                    Atom.string(mapping[a.value]) if isinstance(a, Atom) and a.value in mapping else a
                    for a in child.children
                ]
            )
        children.append(child)
    return dumps(node.with_children(children), style="compact")


def _with_groups(board: Board, mapping: Mapping[str, str]) -> Board:
    """``board`` whose root groups name the renamed footprints by their new uuids."""
    bag = board.ext.get(BAG)
    if bag is None or not mapping:
        return board
    current = list(slots.from_ext(bag))
    changed = False
    for index, slot in enumerate(current):
        if isinstance(slot, Opaque):
            fragment = _group_members(slot.fragment, mapping)
            if fragment != slot.fragment:
                current[index] = Opaque(fragment, slot.min_version)
                changed = True
    if not changed:
        return board
    return dataclasses.replace(board, ext={**board.ext, BAG: slots.to_ext(current, bag)})


def merge_layout(
    built: Design,
    board: Design,
    match: LayoutMatch,
    *,
    net_aliases: Mapping[str, str] | None = None,
    identities: Mapping[str, Mapping[str, str]] | None = None,
) -> Merged:
    """The layout to write: the existing board with the built design's circuit and footprints merged.

    ``net_aliases`` (new name → old) lets copper follow a renamed net. ``identities`` maps the component
    path of an alias match to its identity map (``lens.moved.identity_map``): with it the footprint is
    kept under its new path, and without it an alias match is re-placed."""
    assert built.board is not None and board.board is not None
    issues: list[Issue] = []
    copper = [layer.name for layer in board.board.layers if layer.kind == "copper"]
    wanted_copper = [layer.name for layer in built.board.layers if layer.kind == "copper"]
    if copper != wanted_copper:
        issues.append(
            issue(
                "layout.copper-mismatch",
                f"the board's copper layers {copper} differ from the design's {wanted_copper}",
                "board",
                "rebuild with --discard-layout to create the board on the new stack-up",
            )
        )
        return Merged(built, tuple(issues), {})
    components = {c.id: c for c in built.circuit.components}
    by_path = {p: c for p, c in _paths(built).items()}
    built_fps = {fp.component_id: fp for fp in built.board.footprints}
    board_components = {c.id: c for c in board.circuit.components}
    board_nets = _net_names(board)
    nets_by_name = {n.name: n for n in built.circuit.nets}
    matched_ids = {m.footprint.id: m for m in match.matches.values()}
    orphan_ids = {fp.id for fp in match.orphans}
    old_nets = {old: new for new, old in (net_aliases or {}).items()}
    alias_used: dict[str, Counter[str]] = {}
    renamed_uuids: dict[str, str] = {}
    kept_paths: list[str] = []
    replaced: list[str] = []
    placed: list[FootprintInstance] = []
    new_components: dict[str, Component] = {}
    board_only_components: list[Component] = []
    extra_members: dict[str, list[PinRef]] = {}
    lost_pads: Counter[str] = Counter()
    board_only_refs: list[str] = []
    orphans: list[str] = []
    for fp in board.board.footprints:
        found = matched_ids.get(fp.id)
        if found is not None:
            component = by_path[found.path]
            copy = built_fps.get(component.id)
            same = copy is not None and (copy.position, copy.rotation, copy.side, copy.locked) == (
                fp.position,
                fp.rotation,
                fp.side,
                fp.locked,
            )
            read = board_components.get(fp.component_id)
            was = read.properties.get(PATH_PROPERTY) if read is not None else None
            identity = (identities or {}).get(found.path) if found.key == "alias" else None
            if (
                (found.key != "alias" or identity is not None)
                and fp.lib_ref == component.lib_footprint_ref
                and same
                and copy is not None
            ):
                kept_fp = fp
                if identity is not None:
                    renamed = _rekey(fp, identity)
                    assert isinstance(renamed, FootprintInstance)
                    kept_fp = _with_path(renamed, found.path)
                    renamed_uuids.update(identity)
                    issues.append(
                        issue(
                            "layout.alias-used",
                            f"{found.path} takes the layout of {was or fp.native_ids.get(BAG)}: its "
                            "footprint is kept under the new path",
                            found.path,
                        )
                    )
                node, written = _apply_user_properties(kept_fp, copy, found.path)
                pad_nets = {p.number: p.net_id for p in copy.pads}
                kept_pads = tuple(dataclasses.replace(p, net_id=pad_nets.get(p.number)) for p in node.pads)
                placed.append(dataclasses.replace(node, component_id=component.id, pads=kept_pads))
                props = dict(read.properties) if read is not None else {}
                if identity is not None and PATH_PROPERTY in props:
                    props[PATH_PROPERTY] = found.path
                for name in [k for k in props if k.casefold() in {w.casefold() for w in written}]:
                    del props[name]
                props.update(written)
                props.update({"Reference": component.ref, "Value": component.value})
                new_components[component.id] = dataclasses.replace(
                    component, properties=dict(sorted(props.items()))
                )
                kept_paths.append(found.path)
                continue
            replaced.append(found.path)
            if found.key == "alias":
                issues.append(
                    issue(
                        "layout.alias-used",
                        f"{found.path} takes the layout of {was or fp.native_ids.get(BAG)}: its "
                        "footprint is replaced by the built copy at that placement",
                        found.path,
                    )
                )
            if fp.lib_ref != component.lib_footprint_ref:
                issues.append(
                    issue(
                        "layout.footprint-replaced",
                        f"{found.path}: footprint {fp.lib_ref} replaced by {component.lib_footprint_ref}",
                        found.path,
                    )
                )
            continue
        read = board_components.get(fp.component_id)
        ref = read.ref if read is not None else "?"
        if fp.id in orphan_ids:
            path = read.properties.get(PATH_PROPERTY, "") if read is not None else ""
            orphans.append(ref)
            issues.append(
                issue(
                    "layout.orphan",
                    f"{ref} ({path}, uuid {fp.native_ids.get(BAG)}) at "
                    f"{_describe(fp.position, fp.rotation, fp.side)} is no longer in the design "
                    "and is removed",
                    path,
                )
            )
            continue
        pads: list[Pad] = []
        for pad in fp.pads:
            name = board_nets.get(pad.net_id or "")
            net = nets_by_name.get(name or "")
            if name and net is None and name in old_nets:
                net = nets_by_name.get(old_nets[name])
                if net is not None:
                    alias_used.setdefault(net.name, Counter())["pads"] += 1
            if name and net is None:
                lost_pads[name] += 1
            pads.append(dataclasses.replace(pad, net_id=net.id if net is not None else None))
            if net is not None and pad.number:
                extra_members.setdefault(net.id, []).append(PinRef(fp.component_id, pad.number))
        placed.append(dataclasses.replace(fp, pads=tuple(pads)))
        if read is not None:
            board_only_components.append(read)
        board_only_refs.append(ref)
        issues.append(issue("layout.board-only", f"{ref} has no fenolite.path and is kept", ref))
    added = [p for p, c in by_path.items() if p not in kept_paths and c.id in built_fps]
    for path in sorted(added):
        placed.append(built_fps[by_path[path].id])
    added_paths = [p for p in added if p not in replaced]
    # script copper is regenerated (c0028); the copper that stays follows its nets
    script = copper_mod.merge_copper(board, built)
    issues += script.issues
    dropped: dict[str, Counter[str]] = {}

    def keep(item_net: str | None, kind: str) -> tuple[bool, str | None]:
        if item_net is None:
            return True, None
        name = board_nets.get(item_net)
        net = nets_by_name.get(name or "")
        if net is None and name in old_nets:
            net = nets_by_name.get(old_nets[name])
            if net is not None:
                alias_used.setdefault(net.name, Counter())[kind] += 1
        if net is None:
            dropped.setdefault(name or "?", Counter())[kind] += 1
            return False, None
        return True, net.id

    tracks: list[Track] = []
    arcs: list[Arc] = []
    vias: list[Via] = []
    zones: list[Zone] = []
    for track in board.board.tracks:
        if track.id not in script.kept:
            continue
        ok, nid = keep(track.net_id, "tracks")
        if ok:
            tracks.append(dataclasses.replace(track, net_id=nid))
    for arc in board.board.arcs:
        if arc.id not in script.kept:
            continue
        ok, nid = keep(arc.net_id, "arcs")
        if ok:
            arcs.append(dataclasses.replace(arc, net_id=nid))
    for via in board.board.vias:
        if via.id not in script.kept:
            continue
        ok, nid = keep(via.net_id, "vias")
        if ok:
            vias.append(dataclasses.replace(via, net_id=nid))
    tracks += [t for t in built.board.tracks if copper_mod.is_copper_uuid(t.native_ids.get(BAG, ""))]
    arcs += [a for a in built.board.arcs if copper_mod.is_copper_uuid(a.native_ids.get(BAG, ""))]
    vias += [v for v in built.board.vias if copper_mod.is_copper_uuid(v.native_ids.get(BAG, ""))]
    # zones that the script declares are merged by uuid (c0031); the others follow their nets
    script_zones = zones_mod.merge_zones(built, board)
    issues += script_zones.issues
    for zone in script_zones.zones:
        if zone.id in script_zones.decided:
            zones.append(zone)
            continue
        ok, nid = keep(zone.net_id, "zones")
        if ok:
            zones.append(dataclasses.replace(zone, net_id=nid))
    for name in sorted(set(dropped) | set(lost_pads)):
        counts = dropped.get(name, Counter())
        issues.append(
            issue(
                "layout.net-removed",
                f"net {name!r} is no longer in the design: dropped {counts['tracks']} tracks, "
                f"{counts['arcs']} arcs, {counts['vias']} vias and {counts['zones']} zones; "
                f"{lost_pads[name]} board-only pads left without a net",
                name,
            )
        )
    for new in sorted(alias_used):
        counts = alias_used[new]
        issues.append(
            issue(
                "layout.net-alias-used",
                f"net {(net_aliases or {})[new]!r} is now {new!r}: kept {counts['tracks']} tracks, "
                f"{counts['arcs']} arcs, {counts['vias']} vias, {counts['zones']} zones and "
                f"{counts['pads']} board-only pads under the new name",
                new,
            )
        )
    # board content and the outline rule
    edge = _edge_graphics(board)
    outline = None if edge else built.board.outline
    if edge and not _edges_are_outline(built, board):
        issues.append(
            issue(
                "layout.outline-kept",
                "the board's edge content differs from the design's board() outline and is kept",
                "board",
                "change the outline in KiCad, or re-run with --discard-layout",
            )
        )
    # the paper and the title block that the script declares are the script's (c0074); without a call
    # they stay as the board has them
    declared = {
        name: value
        for name, value in (("sheet", built.board.sheet), ("title_block", built.board.title_block))
        if value is not None
    }
    merged_board = dataclasses.replace(
        _with_groups(board.board, renamed_uuids),
        **declared,
        outline=outline,
        footprints=tuple(placed),
        tracks=tuple(tracks),
        arcs=tuple(arcs),
        vias=tuple(vias),
        zones=tuple(zones),
    )
    nets = tuple(
        dataclasses.replace(net, members=tuple(sorted({*net.members, *extra_members.get(net.id, [])})))
        for net in built.circuit.nets
    )
    circuit = dataclasses.replace(
        built.circuit,
        components=(*(new_components.get(c.id, c) for c in built.circuit.components), *board_only_components),
        nets=nets,
    )
    del components
    summary: dict[str, object] = {
        "kept": sorted(kept_paths),
        "replaced": sorted(replaced),
        "added": sorted(added_paths),
        "orphans": orphans,
        "board_only": board_only_refs,
        "dropped": {
            kind: sum(c[kind] for c in dropped.values()) for kind in ("tracks", "arcs", "vias", "zones")
        },
        "copper": {
            "regenerated": script.regenerated,
            "stale": script.stale,
            "duplicates": script.duplicates,
        },
    }
    return Merged(dataclasses.replace(built, circuit=circuit, board=merged_board), tuple(issues), summary)


# --- fill staleness -------------------------------------------------------------------------------


def _digest(lines: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _zone_slots(zone: Zone) -> tuple[Slot, ...]:
    bag = zone.ext.get(BAG)
    return slots.from_ext(bag) if bag is not None else ()


SKIPPED_ZONE_HEADS = frozenset({"net", "net_name", "uuid", "filled_polygon", "fill_segments", "locked"})


def _obsolete(head: str) -> bool:
    """A zone child that some KiCad major no longer writes, so the board's format would change the digest."""
    row = load_inventory().match(FileKind.BOARD, ("kicad_pcb", "zone", head))
    return row is not None and row.until_major is not None


def zone_digest(design: Design, zone: Zone) -> str:
    """SHA-256 of the zone's outline (or opaque polygons), net name, layers, priority, effective settings
    and other opaque slots (among them fill settings that the reader kept opaque); fills, the fill flag,
    the lock, uuids and net forms never enter it."""
    names = _net_names(design)
    opaque: list[str] = []
    polygons: list[str] = []
    for slot in _zone_slots(zone):
        if not isinstance(slot, Opaque):
            continue
        node = parse_fragment(slot.fragment)
        head = node.name if isinstance(node, Node) else ""
        if head in SKIPPED_ZONE_HEADS or _obsolete(head):
            continue
        fragment = slot.fragment
        if head == "fill" and isinstance(node, Node):
            # the fill flag is state, not a setting: an opaque fill child enters without its atoms
            fragment = dumps(node.with_children(node.nodes()), style="compact")
        (polygons if head == "polygon" else opaque).append(fragment)
    outline = [f"{p.x},{p.y}" for p in zone.outline] if zone.outline else polygons
    lines = [
        "outline " + " ".join(outline),
        f"net {names.get(zone.net_id or '', '')}",
        "layers " + " ".join(zone.layers),
        f"priority {zone.priority}",
        "settings " + canonical.dumps(zone.settings.effective()),
        *sorted(opaque),
    ]
    return _digest(lines)


def fill_inputs_digest(
    design: Design,
    *,
    project: str | None,
    rules: str | None,
    net_aliases: Mapping[str, str] | None = None,
) -> str:
    """SHA-256 of what a rebuild can change around a zone: footprints and pads, tracks, arcs, vias, zones,
    rule areas, edge content and outline, the project's classes and patterns, and the rule items.

    ``net_aliases`` (new name → old) are for the existing board of a rebuild: an exact-name pattern or an
    assignment of ``project`` that names the old name of a net enters under the new one, as the nets of
    ``design`` do after ``with_net_names``."""
    renamed = {old: new for new, old in (net_aliases or {}).items()}
    board = design.board
    names = _net_names(design)
    lines: list[str] = []
    if board is not None:
        for fp in board.footprints:
            pads = sorted(
                f"{p.number}|{p.shape}|{p.size.w}x{p.size.h}|{p.position.x},{p.position.y}|{p.kind}|{p.rotation}|"
                f"{p.drill}|{'+'.join(p.layers)}|{names.get(p.net_id or '', '')}"
                for p in fp.pads
            )
            lines.append(
                f"fp {fp.lib_ref} {fp.position.x},{fp.position.y} {fp.rotation} {fp.side} " + ";".join(pads)
            )
        for t in board.tracks:
            lines.append(f"track {t.start} {t.end} {t.width} {t.layer} {names.get(t.net_id or '', '')}")
        for a in board.arcs:
            lines.append(f"arc {a.start} {a.mid} {a.end} {a.width} {a.layer} {names.get(a.net_id or '', '')}")
        for v in board.vias:
            lines.append(
                f"via {v.position} {v.diameter} {v.drill} {'+'.join(v.layers)} {v.via_type} "
                f"{names.get(v.net_id or '', '')}"
            )
        for z in board.zones:
            lines.append(f"zone {zone_digest(design, z)}")
        for k in board.keepouts:
            lines.append(
                f"keepout {k.outline} {'+'.join(k.layers)} {k.no_tracks}{k.no_vias}{k.no_pads}"
                f"{k.no_copper_pour}{k.no_footprints}"
            )
        for g in _edge_graphics(design):
            lines.append(f"edge {g.kind} {g.points} {g.width}")
        if board.outline is not None:
            lines.append(f"outline {board.outline.points} {board.outline.cutouts}")
    if project is not None:
        info = pro.read_project(project, issues=[])
        for cls in info.classes:
            lines.append(f"class {cls}")
        for pattern, cls in info.patterns:
            lines.append(f"pattern {(renamed.get(pattern, pattern), cls)}")
        for net, classes in info.assignments:
            lines.append(f"assignment {(renamed.get(net, net), classes)}")
    if rules is not None:
        for item in dru.parse_rules(rules).items:
            if isinstance(item, dru.RuleItem):
                lines.append(f"rule {item.text}")
    return _digest(sorted(lines))


def with_net_names(board: Design, net_aliases: Mapping[str, str]) -> Design:
    """``board`` with each net named by the old name of an alias renamed to the new one: what the digests
    of the existing board are computed from, so a pure rename keeps the fills."""
    old_nets = {old: new for new, old in net_aliases.items()}
    if not any(net.name in old_nets for net in board.circuit.nets):
        return board
    nets = tuple(
        dataclasses.replace(net, name=old_nets[net.name]) if net.name in old_nets else net
        for net in board.circuit.nets
    )
    return dataclasses.replace(board, circuit=dataclasses.replace(board.circuit, nets=nets))


def drop_stale_fills(
    board: Design,
    layout: Design,
    *,
    existing: ExistingProject,
    project: str,
    rules: str,
    net_aliases: Mapping[str, str] | None = None,
) -> tuple[Design, tuple[Issue, ...]]:
    """``layout`` with the fills of each zone whose digests changed dropped (``zone.fill-stale``). The
    existing board is digested after its net names are mapped through ``net_aliases`` (new → old)."""
    assert layout.board is not None and board.board is not None
    board = with_net_names(board, net_aliases or {})
    assert board.board is not None
    before = {z.native_ids.get(BAG): z for z in board.board.zones}
    same_inputs = fill_inputs_digest(
        board, project=existing.project, rules=existing.rules, net_aliases=net_aliases
    ) == fill_inputs_digest(layout, project=project, rules=rules)
    issues: list[Issue] = []
    zones: list[Zone] = []
    for zone in layout.board.zones:
        old = before.get(zone.native_ids.get(BAG))
        stale = not same_inputs or old is None or zone_digest(board, old) != zone_digest(layout, zone)
        if (zone.fills or zone.filled) and stale:
            label = zone.name or zone.native_ids.get(BAG, zone.id)
            issues.append(
                issue("zone.fill-stale", f"zone {label}: its inputs changed, so its fills are dropped", label)
            )
            zone = dataclasses.replace(zone, fills=(), filled=False)
        zones.append(zone)
    if not issues:
        return layout, ()
    return dataclasses.replace(layout, board=dataclasses.replace(layout.board, zones=tuple(zones))), tuple(
        issues
    )


def fill_counts(before: Design, after: Design) -> dict[str, int]:
    """Zones whose fills were kept and dropped between two layouts."""
    old = {z.native_ids.get(BAG): bool(z.fills) for z in (before.board.zones if before.board else ())}
    kept = dropped = 0
    for zone in after.board.zones if after.board else ():
        if old.get(zone.native_ids.get(BAG)):
            if zone.fills:
                kept += 1
            else:
                dropped += 1
    return {"kept": kept, "dropped": dropped}


# --- rules ----------------------------------------------------------------------------------------

FENOLITE_RULE_PREFIX = "fenolite_"


def _rule_name(item: dru.RuleItem) -> str:
    atoms = item.node.atoms()
    return atoms[0].value if atoms else ""


def merge_rules(
    lowered: str,
    existing: str,
    *,
    target: int,
    file: str = "",
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> str:
    """Fenolite's rules (``lowered``), then the user's rules of ``existing`` in file order, through c0018's
    target gating and self-check (``docs/lens.md``, "Project and rules files")."""
    theirs = dru.parse_rules(existing, file=file)  # refuses a broken file with its line
    if theirs.version > dru.RULES_VERSION:
        raise FutureFormatError(
            f"{file or 'the rules file'} has version {theirs.version}; "
            f"Fenolite writes version {dru.RULES_VERSION}",
            hint="re-save the rules in a KiCad that Fenolite supports, or rebuild with --discard-layout",
        )
    dru.read_rules(existing, file=file, issues=[])
    mine = dru.parse_rules(lowered)
    user = [
        item
        for item in theirs.items
        if not isinstance(item, dru.VersionItem)
        and not (isinstance(item, dru.RuleItem) and _rule_name(item).startswith(FENOLITE_RULE_PREFIX))
    ]
    text = dru.print_rules([*mine.items, *user])
    return dru.write_rules(
        dru.read_rules(text, file=file), target=target, allow_lossy=allow_lossy, issues=issues
    )


__all__ = [
    "EVIDENCE",
    "PATH_PROPERTY",
    "PRESERVE_ISSUE_CODES",
    "ExistingProject",
    "FootprintMatch",
    "KeptPlacement",
    "LayoutMatch",
    "Merged",
    "PlacementLike",
    "Prepared",
    "component_paths",
    "drop_stale_fills",
    "effective_placements",
    "fill_counts",
    "fill_inputs_digest",
    "footprint_uuid",
    "match_footprints",
    "merge_layout",
    "merge_rules",
    "prepare",
    "read_existing",
    "zone_digest",
]
