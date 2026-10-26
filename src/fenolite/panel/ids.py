# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ids of a panel's items (change c0173, design Decision 2): ``derived_id(prefix, "panel", key)``.

Ids depend on the keys alone, never on ``--seed``: a panel laid out twice gives the same ids. Rows count
from 1 at the top, columns from 1 at the left, and copy ``k = (row - 1) * cols + col``. An item of copy
``k`` keeps its source id inside its key: ``derived_id(<its prefix>, "panel", "<copy key>/<source id>")``.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.ids import FENOLITE_NS, derived_id

BACKEND = "panel"
KEYS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "panel": ("pnl", "panel"),
        "copy": ("pcy", "copy:<row>.<col>"),
        "tab": ("ptb", "tab:<edge>:<k>"),
        "vscore": ("pvs", "vscore:<x|y>:<k>"),
        "fiducial": ("pfd", "fiducial:<ref>"),
        "tooling": ("ptl", "tooling:<ref>"),
    }
)
"""Object → (id prefix, key form)."""


def panel_id() -> str:
    return derived_id("pnl", BACKEND, "panel")


def copy_key(row: int, col: int) -> str:
    return f"copy:{row}.{col}"


def copy_id(row: int, col: int) -> str:
    return derived_id("pcy", BACKEND, copy_key(row, col))


def tab_id(edge: str, k: int) -> str:
    return derived_id("ptb", BACKEND, f"tab:{edge}:{k}")


def vscore_id(axis: str, k: int) -> str:
    return derived_id("pvs", BACKEND, f"vscore:{axis}:{k}")


def fiducial_id(ref: str) -> str:
    return derived_id("pfd", BACKEND, f"fiducial:{ref}")


def tooling_id(ref: str) -> str:
    return derived_id("ptl", BACKEND, f"tooling:{ref}")


def item_id(prefix: str, row: int, col: int, source_id: str) -> str:
    """The id of an item of copy ``(row, col)`` whose source id is ``source_id``."""
    return derived_id(prefix, BACKEND, f"{copy_key(row, col)}/{source_id}")


def item_uuid(key: str, source_uuid: str) -> str:
    """The native uuid written for an item of a panel: ``uuid5`` of the item's key and its source uuid, so
    each copy's items keep distinct, stable uuids."""
    return str(uuid.uuid5(FENOLITE_NS, f"{BACKEND}:{key}/{source_uuid}"))


__all__ = [
    "BACKEND",
    "KEYS",
    "copy_id",
    "copy_key",
    "fiducial_id",
    "item_id",
    "item_uuid",
    "panel_id",
    "tab_id",
    "tooling_id",
    "vscore_id",
]
