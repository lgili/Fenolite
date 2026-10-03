# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A local KiCad install compared with the verified cache of its major (capability
kicad-library-resolution, "Install tree compared with its pin"; change c0021).

A measurement: counts only, written to the file named by ``FENOLITE_CENSUS_OUT``, and a difference never
fails the test. Footprint files are compared by bytes. Symbol libraries are compared by their flattened
definitions, because an install packs the repository's folders into files (S-0044); the order of the
definitions does not count, because a folder has none.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _libcensus import CensusSource, census_sources, report

from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.model.canonical import to_data

pytestmark = [pytest.mark.needs_libs, pytest.mark.slow]
FETCH = "uv run python tools/kicad_libs_fetch.py"


def _pair() -> tuple[CensusSource, CensusSource]:
    sources = census_sources()
    install = next((s for s in sources if s.kind == "install"), None)
    if install is None:
        pytest.skip(f"no local KiCad install to compare with the cache ({FETCH} makes the cache)")
    cache = next((s for s in sources if s.kind == "cache" and s.major == install.major), None)
    if cache is None:
        tag = {10: "10.0.6", 9: "9.0.9"}.get(install.major, f"{install.major}.x")
        pytest.skip(f"no verified {tag} cache of the install's major: run {FETCH}")
    return install, cache


def _strip(value: Any) -> Any:
    """``value`` without provenance and ``ext``: where a definition came from is not what it is."""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in ("provenance", "ext")}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_strip(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def _definitions(path: Path, library: str) -> list[str]:
    """The flattened definitions of one library as canonical JSON texts, sorted: a multiset."""
    symbols = resolve_extends(read_symbol_library(path, library=library))
    return sorted(json.dumps(_strip(to_data(s)), sort_keys=True) for s in symbols)


def compare_footprints(install: Path, cache: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    ours = {p.relative_to(install).as_posix(): p for p in install.glob("*.pretty/*.kicad_mod")}
    theirs = {p.relative_to(cache).as_posix(): p for p in cache.glob("*.pretty/*.kicad_mod")}
    for name in sorted(ours.keys() | theirs.keys()):
        if name not in theirs:
            counts["only_in_install"] += 1
        elif name not in ours:
            counts["only_in_cache"] += 1
        elif ours[name].read_bytes() == theirs[name].read_bytes():
            counts["equal"] += 1
        else:
            counts["different"] += 1
    return {k: counts[k] for k in ("equal", "different", "only_in_install", "only_in_cache")}


def _symbol_libraries(folder: Path) -> dict[str, Path]:
    """Stem to library: a ``.kicad_sym`` file, else a ``.kicad_symdir`` folder."""
    found = {p.stem: p for p in sorted(folder.glob("*.kicad_symdir")) if p.is_dir()}
    found.update({p.stem: p for p in sorted(folder.glob("*.kicad_sym")) if p.is_file()})
    return found


def compare_symbols(install: Path, cache: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    ours, theirs = _symbol_libraries(install), _symbol_libraries(cache)
    for name in sorted(ours.keys() | theirs.keys()):
        if name not in theirs:
            counts["only_in_install"] += 1
        elif name not in ours:
            counts["only_in_cache"] += 1
        elif _definitions(ours[name], name) == _definitions(theirs[name], name):
            counts["equal"] += 1
        else:
            counts["different"] += 1
    return {k: counts[k] for k in ("equal", "different", "only_in_install", "only_in_cache")}


def test_install_against_its_pin() -> None:
    install, cache = _pair()
    start = time.perf_counter()
    data: dict[str, Any] = {"cache": cache.id}
    if install.footprints is not None and cache.footprints is not None:
        data["footprints"] = compare_footprints(install.footprints, cache.footprints)
    if install.symbols is not None and cache.symbols is not None:
        data["symbol_libraries"] = compare_symbols(install.symbols, cache.symbols)
    data["seconds"] = round(time.perf_counter() - start, 1)
    report(install, "install_pin", data)
    assert "footprints" in data or "symbol_libraries" in data  # something was compared; counts never fail
