# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sources and the report file of the official-library census (``tests/libs/``)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _resources import kicad_install_dir, libs_cache_dir

from fenolite.backends.kicad import libcache
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, find_library_sources

NO_INSTALL = Path("/nonexistent-fenolite-install")


@dataclass(frozen=True)
class CensusSource:
    """One official library source: footprint and symbol folders of one major."""

    id: str
    kind: str
    major: int
    footprints: Path | None
    symbols: Path | None
    install: Path | None = None
    cache: Path | None = None


def census_sources() -> list[CensusSource]:
    found: list[CensusSource] = []
    for major in (10, 9):
        folders = [os.environ.get(f"KICAD{major}_{name}") for name in ("FOOTPRINT_DIR", "SYMBOL_DIR")]
        paths = [Path(f) if f and Path(f).is_dir() else None for f in folders]
        if any(paths):
            found.append(CensusSource(f"env-{major}", "env", major, paths[0], paths[1]))
    install = kicad_install_dir()
    if install is not None:
        for source in find_library_sources(LibraryConfig(env={}, install_dir=install)):
            if source.kind == "install":
                footprints, symbols = install / "footprints", install / "symbols"
                found.append(
                    CensusSource(
                        f"install-{source.major}",
                        "install",
                        source.major,
                        footprints if footprints.is_dir() else None,
                        symbols if symbols.is_dir() else None,
                        install,
                    )
                )
    found += cache_sources()
    return found


def cache_sources() -> list[CensusSource]:
    """One source per fetched tag of the verified library cache: ``cache-<major>`` (c0021)."""
    cache = libs_cache_dir()
    by_tag: dict[str, dict[str, Path]] = {}
    majors: dict[str, int] = {}
    for pin, folder in libcache.verified_folders(cache) if cache.is_dir() else ():
        by_tag.setdefault(pin.tag, {})[pin.repo] = folder
        majors[pin.tag] = pin.major
    return [
        CensusSource(
            f"cache-{majors[tag]}",
            "cache",
            majors[tag],
            folders.get("kicad-footprints"),
            folders.get("kicad-symbols"),
            cache=cache,
        )
        for tag, folders in by_tag.items()
    ]


def source_id(source: CensusSource | None) -> str:
    return "none" if source is None else source.id


def resolver_for(source: CensusSource, tmp_path: Path) -> LibraryResolver:
    """A resolver that sees only this source: an empty configuration folder, so the template applies
    (or the scan, for a cache source)."""
    config = tmp_path / "empty-kicad-config"
    config.mkdir(exist_ok=True)
    env: dict[str, str] = {}
    if source.kind == "env":
        if source.footprints is not None:
            env[f"KICAD{source.major}_FOOTPRINT_DIR"] = str(source.footprints)
        if source.symbols is not None:
            env[f"KICAD{source.major}_SYMBOL_DIR"] = str(source.symbols)
    return LibraryResolver(
        LibraryConfig(
            target_major=source.major,
            env=env,
            config_home=config,
            install_dir=source.install if source.install is not None else NO_INSTALL,
            cache_dir=source.cache,
        )
    )


def report(source: CensusSource, section: str, data: dict[str, Any]) -> None:
    """Merge ``data`` into the JSON file named by ``FENOLITE_CENSUS_OUT`` (nothing without it)."""
    target = os.environ.get("FENOLITE_CENSUS_OUT")
    if not target:
        return
    path = Path(target)
    current: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    entry = current.setdefault("sources", {}).setdefault(source.id, {})
    entry.update({"kind": source.kind, "major": source.major, section: data})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
