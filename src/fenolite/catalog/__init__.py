# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Offline, Fenolite-authored reusable schematic symbols and footprint definitions.

Every definition is a record file under ``fenolite/catalog/data/`` (change c0259,
``docs/library-records.md``): a pins record gives a symbol, a package record a footprint. This module
keeps the catalog's names and results: ``ENTRIES`` and the two tuples of polarity are computed from the
records when first read.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from fenolite.model.library import FootprintDef, SymbolDef

if TYPE_CHECKING:
    from fenolite.catalog.records import PackageRecord, PinsRecord
FAMILIES_VERSION = "2026.10"
"""The version of the shipped families of ``families/`` (change c0254). It changes whenever a family's
canonical text changes (``families/VERSIONS.toml`` records the digests of each version), so a pick names the
data it was made from, independently of the package version. It is not ``CATALOG_VERSION``, the version of
the library records of ``data/`` (change c0259)."""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Stable metadata for one catalog definition. ``version``, ``licence`` and ``uid`` come from its record
    (change c0259)."""

    lib_id: str
    kind: str
    category: str
    summary: str
    evidence: str
    sources: tuple[str, ...]
    version: str = ""
    licence: str = ""
    uid: str = ""


CATHODE_FIRST_PAD_MAP: tuple[tuple[str, str], ...] = (("1", "2"), ("2", "1"))
"""The pin-to-pad map of an anode-first symbol on a cathode-first land: pin 1 ``A`` on pad 2 (the anode),
pin 2 ``K`` on pad 1 (the cathode). Pairs in the form of ``Component.pin_pad_map`` (change c0147)."""


def _sources(record: PinsRecord | PackageRecord) -> tuple[str, ...]:
    header = record.header
    return header.sources or tuple(sorted({source for ids in header.sources_by.values() for source in ids}))


@cache
def _entries() -> tuple[CatalogEntry, ...]:
    from fenolite.catalog.records import PackageRecord, PinsRecord, kind_of, record_uid, shipped_tree

    found: list[CatalogEntry] = []
    for record in shipped_tree().records:
        if not isinstance(record, PinsRecord | PackageRecord):
            continue
        header = record.header
        found.append(
            CatalogEntry(
                header.id,
                "symbol" if isinstance(record, PinsRecord) else "footprint",
                header.category,
                header.summary,
                header.evidence,
                _sources(record),
                header.version,
                header.licence,
                record_uid(kind_of(record), header.id),
            )
        )
    return tuple(sorted(found, key=lambda entry: entry.lib_id))


@cache
def _anode_first() -> tuple[str, ...]:
    from fenolite.catalog.records import PinsRecord, shipped_tree

    return tuple(
        sorted(r.header.id for r in shipped_tree().records if isinstance(r, PinsRecord) and r.polarity)
    )


@cache
def _cathode_first() -> tuple[str, ...]:
    from fenolite.catalog.records import PackageRecord, shipped_tree

    return tuple(
        sorted(r.header.id for r in shipped_tree().records if isinstance(r, PackageRecord) and r.pad1)
    )


def __getattr__(name: str) -> object:
    """``ENTRIES``, ``ANODE_FIRST_SYMBOLS``, ``CATHODE_FIRST_LANDS`` and ``CATALOG_VERSION``, computed
    from the records."""
    if name == "ENTRIES":
        return _entries()
    if name == "ANODE_FIRST_SYMBOLS":
        return _anode_first()
    if name == "CATHODE_FIRST_LANDS":
        return _cathode_first()
    if name == "CATALOG_VERSION":
        from fenolite.catalog.records import catalog_version

        return catalog_version()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    ENTRIES: tuple[CatalogEntry, ...]
    """Every catalog entry in lib id order."""
    ANODE_FIRST_SYMBOLS: tuple[str, ...]
    """The two-pin symbols with pin 1 ``A`` (anode) and pin 2 ``K`` (cathode), the pins records with
    ``polarity = "anode-first"``."""
    CATALOG_VERSION: str
    """The version of the shipped catalog (``data/VERSIONS.toml``): it changes whenever an entry does."""
    CATHODE_FIRST_LANDS: tuple[str, ...]
    """The two-pad lands that keep the manufacturer's numbering with pad 1 at the cathode
    (``pad1 = "cathode"``; change c0144)."""


def list_entries(*, kind: str | None = None, query: str | None = None) -> tuple[CatalogEntry, ...]:
    """List entries in stable ID order, optionally filtering by kind and case-insensitive text."""
    found = _entries()
    if kind is not None:
        found = tuple(entry for entry in found if entry.kind == kind)
    if query:
        needle = query.casefold()
        found = tuple(
            entry
            for entry in found
            if needle in (entry.lib_id + " " + entry.category + " " + entry.summary).casefold()
        )
    return tuple(sorted(found, key=lambda entry: entry.lib_id))


def default_pad_map(symbol_id: str, footprint_id: str) -> tuple[tuple[str, str], ...]:
    """The pin-to-pad map the catalog applies to a part of ``symbol_id`` on ``footprint_id`` that gives no
    map of its own: ``CATHODE_FIRST_PAD_MAP`` for an anode-first symbol on a cathode-first land, else ``()``
    (capability fenolite-component-catalog, "Default pin-to-pad map of the cathode-first lands")."""
    if symbol_id in _anode_first() and footprint_id in _cathode_first():
        return CATHODE_FIRST_PAD_MAP
    return ()


@cache
def get_symbol(lib_id: str) -> SymbolDef:
    """Return a built-in generic symbol by stable ``library:name`` ID."""
    from fenolite.catalog.records import PinsRecord, shipped_tree, symbol_def

    record = shipped_tree().get("pins", lib_id) if lib_id.startswith("Fenolite:") else None
    if not isinstance(record, PinsRecord):
        raise KeyError(lib_id)
    return symbol_def(record)


def symbol_reference(lib_id: str) -> str | None:
    """The reference prefix of the built-in symbol ``lib_id`` (``Fenolite:Inductor`` gives ``L``), or ``None``
    when it is no catalog symbol (change c0249); read from the shipped pins record (change c0259)."""
    if not lib_id.startswith("Fenolite:"):
        return None
    try:
        return get_symbol(lib_id).reference
    except KeyError:
        return None


@cache
def get_footprint(lib_id: str) -> FootprintDef:
    """Return a built-in generic footprint by stable ``library:name`` ID."""
    from fenolite.catalog.records import PackageRecord, footprint_def, shipped_tree

    record = shipped_tree().get("package", lib_id) if lib_id.startswith("Fenolite:") else None
    if not isinstance(record, PackageRecord):
        raise KeyError(lib_id)
    return footprint_def(record)


__all__ = [
    "ANODE_FIRST_SYMBOLS",
    "CATALOG_VERSION",
    "CATHODE_FIRST_LANDS",
    "CATHODE_FIRST_PAD_MAP",
    "ENTRIES",
    "FAMILIES_VERSION",
    "CatalogEntry",
    "default_pad_map",
    "get_footprint",
    "get_symbol",
    "list_entries",
    "symbol_reference",
]
