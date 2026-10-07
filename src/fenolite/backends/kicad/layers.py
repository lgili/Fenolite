# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad layer names: their kind in the neutral model and wildcard expansion.

Facts and Fenolite choices: ``docs/formats/kicad/board.md``. Canonical names come from S-0001 and
S-0021; the ``*.Adhes`` row and the fallback for names outside the table are Fenolite choices.
"""

# evidence: see pcb

from __future__ import annotations

import dataclasses
import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.sexpr import Node, dumps, parse_fragment
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import derived_id
from fenolite.model.base import Entity, ExtBag, Opaque
from fenolite.model.board import Board, FootprintInstance, Keepout, Layer, LayerKind, Pad, Via, Zone
from fenolite.model.design import Design

LAYER_KINDS: Mapping[str, LayerKind] = MappingProxyType(
    {
        "F.Cu": "copper",
        "B.Cu": "copper",
        "In<n>.Cu": "copper",
        "*.SilkS": "silkscreen",
        "*.Mask": "soldermask",
        "*.Paste": "solderpaste",
        "*.CrtYd": "courtyard",
        "*.Fab": "fabrication",
        "Edge.Cuts": "edge",
        "Margin": "mechanical",
        "*.Adhes": "mechanical",
        "Dwgs.User": "user",
        "Cmts.User": "user",
        "Eco1.User": "user",
        "Eco2.User": "user",
        "User.<n>": "user",
    }
)
"""Canonical name pattern → kind; ``*`` stands for ``F`` or ``B``, ``<n>`` for a positive number."""

COPPER_ROW_TYPES = frozenset({"signal", "power", "mixed", "jumper"})
_SIDES = ("F", "B")
FLIP_SUFFIXES = ("Cu", "Adhes", "Paste", "SilkS", "Mask", "CrtYd", "Fab")
"""Technical layers that come in a front and a back copy; ``flip_layer`` swaps their side."""

CREATED_ROWS: tuple[tuple[int, str, str, str | None], ...] = (
    (0, "F.Cu", "signal", None),
    (2, "B.Cu", "signal", None),
    (9, "F.Adhes", "user", "F.Adhesive"),
    (11, "B.Adhes", "user", "B.Adhesive"),
    (13, "F.Paste", "user", None),
    (15, "B.Paste", "user", None),
    (5, "F.SilkS", "user", "F.Silkscreen"),
    (7, "B.SilkS", "user", "B.Silkscreen"),
    (1, "F.Mask", "user", None),
    (3, "B.Mask", "user", None),
    (17, "Dwgs.User", "user", "User.Drawings"),
    (19, "Cmts.User", "user", "User.Comments"),
    (21, "Eco1.User", "user", "User.Eco1"),
    (23, "Eco2.User", "user", "User.Eco2"),
    (25, "Edge.Cuts", "user", None),
    (27, "Margin", "user", None),
    (31, "F.CrtYd", "user", "F.Courtyard"),
    (29, "B.CrtYd", "user", "B.Courtyard"),
    (35, "F.Fab", "user", None),
    (33, "B.Fab", "user", None),
)
"""The two-copper layer table KiCad 10.0.6 writes (``board.md``): number, name, type, user name."""
CREATED_COPPER_COUNTS: tuple[int, ...] = (2, 4, 6, 8)
"""The copper layer counts of a created board (change c0100); ``fenolite.dsl.design.COPPER_COUNTS``
holds the same counts, and a unit test keeps the two equal."""


def _compile(pattern: str) -> re.Pattern[str]:
    text = re.escape(pattern).replace(re.escape("<n>"), r"[1-9]\d*").replace(re.escape("*"), "(?:F|B)")
    return re.compile(text)


_PATTERNS: tuple[tuple[re.Pattern[str], LayerKind], ...] = tuple(
    (_compile(pattern), kind) for pattern, kind in LAYER_KINDS.items()
)


def _table_kind(name: str) -> LayerKind | None:
    for pattern, kind in _PATTERNS:
        if pattern.fullmatch(name):
            return kind
    return None


def is_canonical(name: str) -> bool:
    """True for a name of the table (``F.Cu``, ``In3.Cu``, ``User.4``, …), never by the fallback."""
    return _table_kind(name) is not None


def layer_kind(name: str, row_type: str = "user") -> LayerKind:
    """The kind of a layer; names outside the table are copper for copper row types, else user."""
    kind = _table_kind(name)
    if kind is not None:
        return kind
    return "copper" if row_type in COPPER_ROW_TYPES else "user"


def has_wildcard(names: Sequence[str]) -> bool:
    return any(name.startswith(("*.", "F&B.")) for name in names)


def expand_layers(names: Sequence[str], copper: Sequence[str]) -> tuple[str, ...]:
    """Real layer names: ``*.Cu`` → every copper layer in ``copper``; ``*.X`` and ``F&B.X`` → ``F.X``,
    ``B.X``. Order follows ``names``; a name already listed is not repeated."""
    out: list[str] = []
    for name in names:
        if name == "*.Cu":
            expanded: Sequence[str] = copper
        elif name.startswith(("*.", "F&B.")):
            suffix = name.split(".", 1)[1]
            expanded = [f"{side}.{suffix}" for side in _SIDES]
        else:
            expanded = [name]
        out.extend(n for n in expanded if n not in out)
    return tuple(out)


def flip_layer(name: str) -> str:
    """``F.<x>`` ↔ ``B.<x>`` for the paired technical layers; every other name is returned unchanged."""
    side, dot, suffix = name.partition(".")
    if dot and side in _SIDES and suffix in FLIP_SUFFIXES:
        return f"{'B' if side == 'F' else 'F'}.{suffix}"
    return name


def _counts_text() -> str:
    counts = [str(count) for count in CREATED_COPPER_COUNTS]
    return f"{', '.join(counts[:-1])} or {counts[-1]}"


def _check_count(copper: object) -> int:
    if isinstance(copper, bool) or not isinstance(copper, int) or copper not in CREATED_COPPER_COUNTS:
        raise ValueError(f"created boards have {_counts_text()} copper layers, not {copper!r}")
    return copper


def inner_rows(copper: int) -> tuple[tuple[int, str, str, str | None], ...]:
    """The rows a table of ``copper`` layers adds after ``F.Cu``: ``(2k + 2, "In<k>.Cu", "signal")``
    without a user name for k = 1 … copper − 2 (``board.md``, "Created boards"; ``H-K-PCB-LAYERS``)."""
    count = _check_count(copper)
    return tuple((2 * k + 2, f"In{k}.Cu", "signal", None) for k in range(1, count - 1))


def created_count(names: Sequence[str]) -> int | None:
    """The count of ``CREATED_COPPER_COUNTS`` whose created table has exactly the copper layer names
    ``names``, in table order; ``None`` when no count has them."""
    given = tuple(names)
    for count in CREATED_COPPER_COUNTS:
        if given == ("F.Cu", *(row[1] for row in inner_rows(count)), "B.Cu"):
            return count
    return None


def created_layers(copper: int) -> tuple[Layer, ...]:
    """The layers of a created board, with the KiCad number, type and user name in ``ext["kicad"]``.
    ``copper`` is a count of ``CREATED_COPPER_COUNTS``; any other value raises ``ValueError``."""
    rows = CREATED_ROWS[:1] + inner_rows(copper) + CREATED_ROWS[1:]
    layers: list[Layer] = []
    for ordinal, (number, name, row_type, user_name) in enumerate(rows):
        pairs = [("number", str(number)), ("type", row_type)]
        if user_name is not None:
            pairs.append(("user_name", user_name))
        layers.append(
            Layer(
                id=derived_id("lay", "kicad", f"layer:{name}"),
                ext={"kicad": ExtBag(None, tuple(pairs))},
                name=name,
                kind=layer_kind(name, row_type),
                ordinal=ordinal,
            )
        )
    return tuple(layers)


PLANE_ROW_TYPE = "power"
"""The copper row type of a plane layer (``board.md``, "Plane layers"; ``H-K-LAYER-POWER``)."""


def _row_type(layer: Layer) -> str | None:
    bag = layer.ext.get("kicad")
    return None if bag is None else dict(bag.payload).get("type")


def plane_layers(design: Design) -> tuple[str, ...]:
    """The copper layers of the board whose KiCad row type is ``power``, in stack order: the plane layers
    (change c0107). A copper layer without a ``type`` in its ext bag is not a plane layer."""
    if design.board is None:
        return ()
    copper = sorted((x for x in design.board.layers if x.kind == "copper"), key=lambda x: x.ordinal)
    return tuple(layer.name for layer in copper if _row_type(layer) == PLANE_ROW_TYPE)


def with_plane_types(layers: Sequence[Layer], planes: Collection[str]) -> tuple[Layer, ...]:
    """``layers`` with the row type ``power`` on each copper layer named in ``planes``; every other layer
    is returned as it is, so a type the board already holds is never removed. A name that is not a copper
    layer of ``layers`` raises ``ValueError``."""
    copper = {layer.name for layer in layers if layer.kind == "copper"}
    unknown = [name for name in planes if name not in copper]
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a copper layer of the board, so it takes no plane")
    made: list[Layer] = []
    for layer in layers:
        if layer.name not in planes or _row_type(layer) == PLANE_ROW_TYPE:
            made.append(layer)
            continue
        bag = layer.ext.get("kicad", ExtBag())
        pairs = [(key, value) for key, value in bag.payload if key != "type"]
        keys = [key for key, _ in bag.payload]
        index = keys.index("type") if "type" in keys else min(1, len(pairs))
        pairs.insert(index, ("type", PLANE_ROW_TYPE))
        ext = {**layer.ext, "kicad": dataclasses.replace(bag, payload=tuple(pairs))}
        made.append(dataclasses.replace(layer, ext=ext))
    return tuple(made)


# --- a copper count change on a built board (change c0102) -----------------------------------------

MERGE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.layers.removed": "warning",
        "kicad.layers.stackup-reset": "warning",
        "kicad.layers.added": "info",
    }
)
"""The closed table of ``merge_layers``."""
BAG = "kicad"


@dataclass(frozen=True)
class LayerMerge:
    """What ``merge_layers`` did: the adapted board design, the inner layers added and removed, and the
    issues."""

    board: Design
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()


def _opaque_layers(entity: Entity) -> tuple[str, ...] | None:
    """The names of the ``layers`` child that ``entity`` keeps as written, or ``None`` without one."""
    bag = entity.ext.get(BAG)
    if bag is None:
        return None
    for slot in slotlib.from_ext(bag):
        if isinstance(slot, Opaque) and slot.fragment.startswith("(layers"):
            child = parse_fragment(slot.fragment)
            if isinstance(child, Node) and child.name == "layers":
                return tuple(atom.value for atom in child.atoms())
    return None


def _projected(
    entity: Entity, current: Sequence[str], copper: Sequence[str], removed: frozenset[str]
) -> tuple[str, ...]:
    """The layers of ``entity`` on the new table: its wildcard expanded again, copper layers in table
    order, or its own layers without the removed ones."""
    written = _opaque_layers(entity)
    if written is not None and has_wildcard(written):
        return expand_layers(written, copper)
    return tuple(name for name in current if name not in removed)


def _repad(fp: FootprintInstance, copper: Sequence[str], removed: frozenset[str]) -> FootprintInstance:
    pads: list[Pad] = []
    changed = False
    for pad in fp.pads:
        layers = _projected(pad, pad.layers, copper, removed)
        if layers != tuple(pad.layers):
            pad = dataclasses.replace(pad, layers=layers)
            changed = True
        pads.append(pad)
    return dataclasses.replace(fp, pads=tuple(pads)) if changed else fp


def _stackup_copper(node: Node) -> tuple[str, ...]:
    names: list[str] = []
    for layer in node.nodes("layer"):
        atoms = layer.atoms()
        if atoms and atoms[0].value.endswith(".Cu"):
            names.append(atoms[0].value)
    return tuple(names)


def _without_stale_node(board: Board, copper: Sequence[str]) -> tuple[Board, bool]:
    """``board`` without the ``stackup`` child of its kept ``setup`` when that names other copper layers
    than ``copper``."""
    bag = board.ext.get(BAG)
    if bag is None:
        return board, False
    current = list(slotlib.from_ext(bag))
    for index, slot in enumerate(current):
        if not isinstance(slot, Opaque) or not slot.fragment.startswith("(setup"):
            continue
        setup = parse_fragment(slot.fragment)
        if not isinstance(setup, Node) or setup.name != "setup":
            continue
        stale = [child for child in setup.nodes("stackup") if _stackup_copper(child) != tuple(copper)]
        if not stale:
            return board, False
        kept = [child for child in setup.children if not any(child is gone for gone in stale)]
        current[index] = Opaque(dumps(setup.with_children(kept), style="compact"), slot.min_version)
        return dataclasses.replace(board, ext={**board.ext, BAG: slotlib.to_ext(current, bag)}), True
    return board, False


def _without_stale_stackup(board: Board, copper: Sequence[str]) -> tuple[Board, bool]:
    """``board`` without a stack-up that names other copper layers than ``copper``: the ``stackup`` child
    of its kept ``setup`` goes, and so does ``Board.stackup``, the value the reader projected from that
    child (change c0101). The two go together: a model stack-up left over a smaller table is refused by
    ``Design.validate`` (``model.stackup-copper``) and by the writer. KiCad then derives its default
    stack-up for the new count."""
    board, reset = _without_stale_node(board, copper)
    held = board.stackup
    if held is not None and tuple(e.name for e in held.layers if e.kind == "copper") != tuple(copper):
        return dataclasses.replace(board, stackup=None), True
    return board, reset


def _issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, MERGE_ISSUE_CODES[code], message, where, hint)


def merge_layers(board: Design, copper: int) -> LayerMerge:
    """Adapt an existing ``board`` whose copper layers are those of a created table of another count to the
    copper layers of ``created_layers(copper)`` (capability layout-lens, "Copper layer changes across
    rebuilds"; ``H-K-LAYER-CHANGE``).

    The rows of the layers that stay keep their ``kicad`` bags, with the type and user name set in KiCad;
    rows of new inner layers come from ``created_layers``; rows of removed layers go (a smaller count
    removes the deepest inner layers). On a removed layer, tracks and arcs are dropped, a via whose layers
    name it is dropped (a through via stays), zones and rule areas lose the layer and go when none is
    left, and root graphics and texts on it are dropped: one ``kicad.layers.removed`` per layer gives the
    counts. Pads whose ``layers`` child holds a wildcard are projected again on the new table. A
    ``stackup`` of ``setup`` that names other copper layers is removed (``kicad.layers.stackup-reset``).
    A board whose copper names are no created table, or already those of ``copper``, is returned as it
    is, without an issue.
    """
    model = board.board
    wanted = created_layers(copper)
    if model is None:
        return LayerMerge(board)
    names = [layer.name for layer in model.layers if layer.kind == "copper"]
    new_names = [layer.name for layer in wanted if layer.kind == "copper"]
    if created_count(names) is None or names == new_names:
        return LayerMerge(board)
    added = tuple(name for name in new_names if name not in names)
    removed = tuple(name for name in names if name not in new_names)
    gone = frozenset(removed)
    by_name = {layer.name: layer for layer in wanted}
    rows: list[Layer] = []
    for layer in model.layers:
        if layer.name in gone:
            continue
        if layer.name == "B.Cu":
            rows += [by_name[name] for name in added]
        rows.append(layer)
    layers = tuple(dataclasses.replace(layer, ordinal=ordinal) for ordinal, layer in enumerate(rows))
    counts: dict[str, Counter[str]] = {name: Counter() for name in removed}
    tracks = tuple(t for t in model.tracks if t.layer not in gone)
    for track in model.tracks:
        if track.layer in gone:
            counts[track.layer]["tracks"] += 1
    arcs = tuple(a for a in model.arcs if a.layer not in gone)
    for arc in model.arcs:
        if arc.layer in gone:
            counts[arc.layer]["arcs"] += 1
    vias: list[Via] = []
    for via in model.vias:
        hit = [name for name in via.layers if name in gone]
        if hit:
            counts[hit[0]]["vias"] += 1
        else:
            vias.append(via)
    zones: list[Zone] = []
    for zone in model.zones:
        kept = _projected(zone, zone.layers, new_names, gone)
        lost = [name for name in zone.layers if name in gone]
        for name in lost:
            counts[name]["zones"] += 1
        if not kept:
            continue
        if lost:
            fills = tuple(fill for fill in zone.fills if fill.layer not in gone)
            zone = dataclasses.replace(zone, layers=kept, fills=fills)
        zones.append(zone)
    keepouts: list[Keepout] = []
    for area in model.keepouts:
        kept = _projected(area, area.layers, new_names, gone)
        lost = [name for name in area.layers if name in gone]
        for name in lost:
            counts[name]["rule areas"] += 1
        if not kept:
            continue
        keepouts.append(dataclasses.replace(area, layers=kept) if kept != tuple(area.layers) else area)
    graphics = tuple(g for g in model.graphics if g.layer not in gone)
    for graphic in model.graphics:
        if graphic.layer in gone:
            counts[graphic.layer]["graphics"] += 1
    texts = tuple(x for x in model.texts if x.layer not in gone)
    for text in model.texts:
        if text.layer in gone:
            counts[text.layer]["texts"] += 1
    adapted = dataclasses.replace(
        model,
        layers=layers,
        footprints=tuple(_repad(fp, new_names, gone) for fp in model.footprints),
        tracks=tracks,
        arcs=arcs,
        vias=tuple(vias),
        zones=tuple(zones),
        keepouts=tuple(keepouts),
        graphics=graphics,
        texts=texts,
    )
    issues: list[Issue] = []
    if added:
        issues.append(
            _issue(
                "kicad.layers.added",
                f"the board gets the inner copper layers {', '.join(added)} for the script's "
                f"{len(new_names)} copper layers",
                "board",
            )
        )
    kinds = ("tracks", "arcs", "vias", "zones", "rule areas", "graphics", "texts")
    for name in removed:
        found = counts[name]
        listed = ", ".join(_count(found[kind], kind) for kind in kinds)
        issues.append(
            _issue(
                "kicad.layers.removed",
                f"{name} is removed for the script's {len(new_names)} copper layers: dropped {listed}",
                name,
                "run fenolite route to close the connections that reopened",
            )
        )
    adapted, reset = _without_stale_stackup(adapted, new_names)
    if reset:
        issues.append(
            _issue(
                "kicad.layers.stackup-reset",
                "the board's stack-up names other copper layers than the new table and is removed: KiCad "
                "derives its default stack-up",
                "board",
                "set the stack-up again in KiCad's board setup",
            )
        )
    return LayerMerge(dataclasses.replace(board, board=adapted), added, removed, tuple(issues))


def _count(count: int, kind: str) -> str:
    return f"{count} {kind[:-1] if count == 1 else kind}"


__all__ = [
    "COPPER_ROW_TYPES",
    "CREATED_COPPER_COUNTS",
    "CREATED_ROWS",
    "FLIP_SUFFIXES",
    "LAYER_KINDS",
    "MERGE_ISSUE_CODES",
    "LayerMerge",
    "PLANE_ROW_TYPE",
    "created_count",
    "created_layers",
    "expand_layers",
    "flip_layer",
    "has_wildcard",
    "inner_rows",
    "is_canonical",
    "layer_kind",
    "merge_layers",
    "plane_layers",
    "with_plane_types",
]
