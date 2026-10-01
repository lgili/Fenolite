# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad layer names: their kind in the neutral model and wildcard expansion.

Facts and Fenolite choices: ``docs/formats/kicad/board.md``. Canonical names come from S-0001 and
S-0021; the ``*.Adhes`` row and the fallback for names outside the table are Fenolite choices.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fenolite.model.board import LayerKind

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


__all__ = ["COPPER_ROW_TYPES", "LAYER_KINDS", "expand_layers", "has_wildcard", "is_canonical", "layer_kind"]
