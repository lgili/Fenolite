# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identifiers, provenance and extension bags of imported entities (capability altium-import,
"Identifiers and provenance" and "Extension bags"; change c0043).

An entity with a native id gets ``derived_id(prefix, "altium", <native id>)``; any other gets a content id
from its model fields and an occurrence counter, so equal objects get different ids and an edit of another
object changes none. A file hash never enters an id.
"""

# evidence: see import_evidence

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import Census
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence
from fenolite.core.ids import content_hash, content_id, derived_id
from fenolite.core.provenance import Provenance
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import ExtBag

BACKEND = "altium"
EXT_KEYS: tuple[str, ...] = (
    "u",
    "deg",
    "layer_id",
    "altium_name",
    "plane_net",
    "origin",
    "stack_mode",
    "corner_percent",
    "shape",
    "paste",
    "mask",
    "plated",
    "via_layers",
    "net",
    "pour_index",
    "hatch_style",
    "component_kind",
    "part_ids",
    "pin_pads",
    "sheet_symbol",
    "channel_index",
    "source_designator",
    "source_lib_reference",
    "electrical",
    "pin_symbols",
    "alias",
    "classes",
    "label",
    "harness_type",
    "scope1",
    "scope2",
    "rule_kind",
)
"""The closed table of extension-bag keys, in bag order; each is a row of
``docs/formats/altium/import.md``, "Extension-bag keys"."""
_ORDER = {key: position for position, key in enumerate(EXT_KEYS)}


def bag(pairs: Iterable[tuple[str, str]]) -> dict[str, ExtBag]:
    """The ``ext`` of an entity: ``{"altium": ExtBag}`` with ``pairs`` in the order of ``EXT_KEYS`` (pairs
    of one key keep their order), or ``{}`` without pairs. ``KeyError`` for a key outside the table."""
    items = sorted(pairs, key=lambda pair: _ORDER[pair[0]])
    return {BACKEND: ExtBag(min_version=None, payload=tuple(items))} if items else {}


class Ids:
    """The ids of one import: ``kind`` is what was read (``altium_pcbdoc``, ``altium_schdoc`` or
    ``altium_prjpcb``) and enters every content id."""

    def __init__(self, kind: str, evidence: Evidence) -> None:
        self.kind = kind
        self.evidence = evidence
        self._seen: Counter[tuple[str, str, str]] = Counter()
        self._native: Counter[tuple[str, str]] = Counter()

    def native(self, prefix: str, native_id: str) -> tuple[str, dict[str, str]]:
        """The id and the ``native_ids`` of an entity with a native id. A native id that repeats within one
        import gets the suffix ``#<k>`` from the second on, so that no two entities share an id."""
        seen = self._native[(prefix, native_id)]
        self._native[(prefix, native_id)] += 1
        if seen:
            native_id = f"{native_id}#{seen + 1}"
        return derived_id(prefix, BACKEND, native_id), {BACKEND: native_id}

    def content(self, prefix: str, section: str, *fields: object) -> str:
        """The id of an entity without a native id, from its model fields (ints, strings, lists) and the
        number of earlier entities of equal content in ``section``."""
        digest = content_hash(*fields)
        occurrence = self._seen[(prefix, section, digest)]
        self._seen[(prefix, section, digest)] += 1
        return content_id(prefix, BACKEND, self.kind, section, content_hash(digest, occurrence))

    def provenance(self, file: str, sha256: str, locator: str) -> Provenance:
        return Provenance(BACKEND, file, sha256, locator, self.evidence)


def provenance(file: str, sha256: str, locator: str, evidence: Evidence) -> Provenance:
    """The provenance of an entity read from ``file`` at ``locator``."""
    return Provenance(BACKEND, file, sha256, locator, evidence)


class Exact:
    """Converts the lengths and angles of one entity and remembers the original value of each inexact
    conversion, for the pairs ``u`` and ``deg`` of its bag."""

    def __init__(self, census: Census | None = None) -> None:
        self.census = census
        self._u: list[str] = []
        self._deg: list[str] = []

    def length(self, field: str, u: int) -> Nm:
        if not units.exact_length(u):
            self._u.append(f"{field}={u}")
            if self.census is not None:
                self.census.inexact_lengths += 1
        return units.pcb_length(u)

    def point(self, field: str, x: int, y: int) -> Point:
        return Point(self.length(f"{field}.x", x), -self.length(f"{field}.y", y))

    def angle(self, field: str, degrees: float) -> Udeg:
        value, exact = units.angle(degrees)
        if not exact:
            self._deg.append(f"{field}={float(degrees).hex()}")
            if self.census is not None:
                self.census.inexact_angles += 1
        return value

    def inexact(self, field: str, text: str) -> None:
        """Record an inexact length whose original is text (a mil text or a fraction of units)."""
        self._u.append(f"{field}={text}")
        if self.census is not None:
            self.census.inexact_lengths += 1

    def pairs(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if self._u:
            out.append(("u", ",".join(self._u)))
        if self._deg:
            out.append(("deg", ",".join(self._deg)))
        return out


def point_fields(point: Point) -> list[int]:
    return [point.x, point.y]


__all__ = ["BACKEND", "EXT_KEYS", "Exact", "Ids", "bag", "point_fields", "provenance"]
