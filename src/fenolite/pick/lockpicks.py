# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``[picks]`` section of the design lock (change c0254, ``docs/picking.md``, "Picks in the lock").

The design lock of change c0249 reads and writes the file (``fenolite.dsl.lock``); this module turns its
tables into ``PickEntry`` values and back. An entry holds the canonical query text, the device a pick names,
its row, the catalog it came from (``fenolite-catalog <CATALOG_VERSION>`` or ``project:<path>``), the SHA-256
of the row's canonical text, what made it (``query`` or a generator's name) and, for a generator's part,
the achieved range in integer micro-units rounded outward.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.errors import FormatError
from fenolite.core.partquery import LOCK_KEYS, LOCK_REQUIRED

KEYS = LOCK_KEYS
"""The keys of an entry in the order of the file."""


@dataclass(frozen=True, slots=True)
class PickEntry:
    """One pick of the lock: the string keys of ``KEYS``; ``achieved`` is ``""`` for a query's pick."""

    query: str
    device: str
    row: str
    catalog: str
    sha256: str
    by: str
    achieved: str = ""

    def table(self) -> Mapping[str, str]:
        """The entry as the lock's table: ``KEYS`` in order, ``achieved`` only when set."""
        values = {
            "query": self.query,
            "device": self.device,
            "row": self.row,
            "catalog": self.catalog,
            "sha256": self.sha256,
            "by": self.by,
        }
        if self.achieved:
            values["achieved"] = self.achieved
        return MappingProxyType(values)


def entry(table: Mapping[str, object], *, path: str = "", file: str = "") -> PickEntry:
    """The ``PickEntry`` of a lock table; ``FormatError`` naming ``file`` and the key when it is malformed."""
    for key, value in table.items():
        if key not in KEYS:
            raise FormatError(
                f"unknown key {key!r} in the pick of {path}", file=file, locator=f"picks.{path}.{key}"
            )
        if not isinstance(value, str):
            raise FormatError(
                f"{key} of the pick of {path} must be a string", file=file, locator=f"picks.{path}.{key}"
            )
    for key in LOCK_REQUIRED:
        if key not in table:
            raise FormatError(f"the pick of {path} has no {key}", file=file, locator=f"picks.{path}.{key}")
    return PickEntry(
        str(table["query"]),
        str(table["device"]),
        str(table["row"]),
        str(table["catalog"]),
        str(table["sha256"]),
        str(table["by"]),
        str(table.get("achieved", "")),
    )


def entries(section: Mapping[str, object], *, file: str = "") -> dict[str, PickEntry]:
    """Every entry of the ``picks`` section, by component path, in code-point order of paths."""
    out: dict[str, PickEntry] = {}
    for path in sorted(section):
        value = section[path]
        if not isinstance(value, Mapping):
            raise FormatError(f"the pick of {path} must be a table", file=file, locator=f"picks.{path}")
        out[path] = entry(value, path=path, file=file)  # pyright: ignore[reportUnknownArgumentType]
    return out


def tables(picks: Mapping[str, PickEntry]) -> dict[str, Mapping[str, str]]:
    """The ``picks`` section of ``picks``, in code-point order of paths."""
    return {path: picks[path].table() for path in sorted(picks)}


def micro_text(name: str, unit: str, low: Fraction, high: Fraction) -> str:
    """``VOUT 3224694uV..3399373uV``: a range in integer micro-units, the minimum rounded down and the
    maximum rounded up, so the lock never claims more than the arithmetic proved."""
    scale = 10**6
    down = (low * scale).__floor__()
    up = (high * scale).__ceil__()
    return f"{name} {down}u{unit}..{up}u{unit}"


__all__ = ["KEYS", "PickEntry", "entries", "entry", "micro_text", "tables"]
