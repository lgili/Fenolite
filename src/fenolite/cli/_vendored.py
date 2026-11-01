# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Offline CLI adapters for the data-only catalog.vendored reader (c0266)."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import cast

from fenolite.catalog.vendored import VendoredTree
from fenolite.library.cache import cached_versions, index_path


def hint_namespaces() -> tuple[str, ...]:
    """Newest cached index only, for an error hint; no payload or network lookup."""
    versions = cached_versions()
    if not versions:
        return ()
    try:
        raw: object = json.loads(index_path(versions[-1]).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ()
        value = cast(dict[str, object], raw).get("items")
        if not isinstance(value, list):
            return ()
        names: set[str] = set()
        for entry in cast(list[object], value):
            if isinstance(entry, dict):
                row = cast(dict[str, object], entry)
                ident = row.get("id")
                if row.get("kind") == "device" and isinstance(ident, str):
                    names.add(ident.split(":", 1)[0])
        return tuple(sorted(names))
    except (ValueError, OSError, UnicodeError):
        return ()


def used_items(
    vendored: VendoredTree,
    owners: Mapping[tuple[str, str], str],
    ids: Mapping[str, object],
    authored: Collection[tuple[str, str]] = (),
) -> dict[str, dict[str, str]]:
    """Item metadata of definitions actually used, excluding authored replacements."""
    return {
        f"{ref.kind}/{ref.id}": ref.as_json()
        for key, ref in sorted(vendored.items.items())
        if ref.id in ids and key not in authored and owners.get(key, "").startswith("fenolite_library/")
    }
