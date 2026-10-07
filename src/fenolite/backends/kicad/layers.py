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
from collections.abc import Collection, Mapping, Sequence
from types import MappingProxyType

from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.board import Layer, LayerKind
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


__all__ = [
    "COPPER_ROW_TYPES",
    "CREATED_COPPER_COUNTS",
    "CREATED_ROWS",
    "FLIP_SUFFIXES",
    "LAYER_KINDS",
    "PLANE_ROW_TYPE",
    "created_count",
    "created_layers",
    "expand_layers",
    "flip_layer",
    "has_wildcard",
    "inner_rows",
    "is_canonical",
    "layer_kind",
    "plane_layers",
    "with_plane_types",
]
