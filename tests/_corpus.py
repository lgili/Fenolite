# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fetched public corpus as test items (manifest rows plus their cached files)."""

from __future__ import annotations

import os
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import pytest
from _resources import CORPUS_HINT, corpus_cache_dir, required_resources

MANIFEST = Path(__file__).resolve().parent / "corpus" / "manifest.toml"
HEAVY_HINT = "heavy corpus item: set FENOLITE_HEAVY=1 to include it"


@dataclass(frozen=True)
class CorpusItem:
    id: str
    path: Path
    license: str
    uses: tuple[str, ...]
    origin: str
    heavy: bool


def _origin(uses: tuple[str, ...]) -> str:
    values = [u.removeprefix("origin:") for u in uses if u.startswith("origin:")]
    return values[0] if len(values) == 1 else "unknown"


def manifest_items(use: str) -> list[CorpusItem]:
    """Every manifest row with ``use``, whether or not it is cached."""
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    cache = corpus_cache_dir()
    items: list[CorpusItem] = []
    for row in rows:
        uses = tuple(row.get("uses", []))
        if use not in uses:
            continue
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(row["url"]).path).name) or row["id"]
        items.append(CorpusItem(row["id"], cache / row["id"] / name, row["license"], uses, _origin(uses),
                                "heavy" in uses))  # fmt: skip
    return items


def heavy_enabled() -> bool:
    return os.environ.get("FENOLITE_HEAVY") == "1"


def corpus_items(use: str, *, heavy: bool = False) -> list[CorpusItem]:
    """Cached items with ``use``; heavy ones only when ``heavy`` or ``FENOLITE_HEAVY=1``."""
    return [i for i in manifest_items(use) if i.path.is_file() and (heavy or heavy_enabled() or not i.heavy)]


def require(item: CorpusItem) -> Path:
    """The cached file of ``item``; skip (or fail in required-resource mode) when it is unavailable."""
    if item.heavy and not heavy_enabled():
        pytest.skip(HEAVY_HINT)
    if not item.path.is_file():
        message = f"corpus item {item.id} is missing from the cache ({CORPUS_HINT})"
        if "corpus" in required_resources():
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    return item.path
