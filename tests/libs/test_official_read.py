# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census: every official footprint and symbol reads (kicad-library-read, "Reading evidence").

Supporting data for ``H-K-LIB-READ``; counts go only to the file named by ``FENOLITE_CENSUS_OUT``.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import pytest
from _libcensus import CensusSource, census_sources, report, source_id

from fenolite.backends.kicad._libread import load_source
from fenolite.backends.kicad.mod import footprint_from
from fenolite.backends.kicad.sexpr import Node
from fenolite.backends.kicad.sym import resolve_extends, symbols_from
from fenolite.core.errors import Issue
from fenolite.model.library import FootprintDef

pytestmark = [pytest.mark.needs_libs, pytest.mark.slow]
SOURCES: list[CensusSource | None] = [*census_sources()] or [None]


def _source(source: CensusSource | None, folder: str) -> Path:
    if source is None:
        pytest.skip("no official library source with a known major")
    path = source.footprints if folder == "footprints" else source.symbols
    if path is None:
        pytest.skip(f"source {source.id} has no {folder} folder")
    return path


def _pts_arc(node: Node) -> bool:
    """An ``arc`` inside the ``pts`` of an ``fp_poly`` or of a custom pad's ``gr_poly``."""
    polygons = list(node.nodes("fp_poly"))
    for pad in node.nodes("pad"):
        for primitives in pad.nodes("primitives"):
            polygons += primitives.nodes("gr_poly")
    return any(pts.find("arc") is not None for poly in polygons for pts in poly.nodes("pts"))


def _ids(fp: FootprintDef) -> list[str]:
    padstacks = [p.padstack.id for p in fp.pads if p.padstack is not None]
    return [fp.id, *(p.id for p in fp.pads), *(g.id for g in fp.graphics), *padstacks]


@pytest.mark.parametrize("source", SOURCES, ids=source_id)
def test_official_footprints_read(source: CensusSource | None) -> None:
    folder = _source(source, "footprints")
    assert source is not None
    start = time.perf_counter()
    counts: Counter[str] = Counter()
    issues_by_code: Counter[str] = Counter()
    for library in sorted(folder.glob("*.pretty")):
        ids: list[str] = []
        library_repeats = False
        counts["libraries"] += 1
        for path in sorted(library.glob("*.kicad_mod")):
            loaded = load_source(path)
            issues: list[Issue] = []
            fp = footprint_from(loaded, issues=issues)
            assert len(fp.pads) == len(loaded.node.nodes("pad")), path.name
            ids += _ids(fp)
            counts["footprints"] += 1
            counts["pads"] += len(fp.pads)
            counts["graphics"] += len(fp.graphics)
            counts["models"] += len(fp.models)
            counts["pts_arc_footprints"] += _pts_arc(loaded.node)
            uuids = [e.native_ids["kicad"] for e in (*fp.pads, *fp.graphics) if e.native_ids]
            repeated = len(uuids) != len(set(uuids))
            counts["repeated_uuid_footprints"] += repeated
            library_repeats = library_repeats or repeated
            issues_by_code.update(i.code for i in issues)
        counts["repeated_uuid_libraries"] += library_repeats
        assert len(ids) == len(set(ids)), f"duplicate ids in {library.name}"
    assert counts["footprints"] > 0
    report(
        source,
        "footprints",
        {
            **counts,
            "issues": dict(issues_by_code),
            "read_errors": 0,
            "seconds": round(time.perf_counter() - start, 1),
        },
    )


def _symbol_files(folder: Path) -> list[tuple[str, list[Path]]]:
    """``(library name, files)`` for every ``.kicad_sym`` file and ``.kicad_symdir`` folder."""
    out: list[tuple[str, list[Path]]] = []
    for entry in sorted(folder.iterdir()):
        if entry.is_dir() and entry.suffix == ".kicad_symdir":
            out.append((entry.stem, sorted(p for p in entry.glob("*.kicad_sym") if p.is_file())))
        elif entry.is_file() and entry.suffix == ".kicad_sym":
            out.append((entry.stem, [entry]))
    return out


@pytest.mark.parametrize("source", SOURCES, ids=source_id)
def test_official_symbols_read(source: CensusSource | None) -> None:
    folder = _source(source, "symbols")
    assert source is not None
    start = time.perf_counter()
    counts: Counter[str] = Counter()
    issues_by_code: Counter[str] = Counter()
    for name, files in _symbol_files(folder):
        counts["libraries"] += 1
        counts["files"] += len(files)
        symbols = []
        for path in files:
            loaded = load_source(path)
            issues: list[Issue] = []
            read = symbols_from(loaded, library=name, issues=issues)
            nodes = loaded.node.nodes("symbol")
            assert len(read) == len(nodes), path.name
            for symbol, node in zip(read, nodes, strict=True):
                pins = sum(len(sub.nodes("pin")) for sub in node.nodes("symbol"))
                assert len(symbol.pins) == pins, f"{path.name}: {symbol.name}"
            symbols += read
            issues_by_code.update(i.code for i in issues)
        ids = [s.id for s in symbols]
        assert len(ids) == len(set(ids)), f"duplicate ids in {name}"
        flat = resolve_extends(symbols)
        counts["symbols"] += len(symbols)
        counts["derived"] += sum(1 for s in symbols if s.extends)
        counts["pins"] += sum(len(s.pins) for s in symbols)
        counts["flattened_pins"] += sum(len(s.pins) for s in flat)
        counts["power_global"] += sum(1 for s in symbols if s.power == "global")
        counts["power_local"] += sum(1 for s in symbols if s.power == "local")
        counts["body_style_0_units"] += sum(1 for s in symbols for u in s.units if u.body_style == 0)
        counts["alternates"] += sum(len(p.alternates) for s in symbols for p in s.pins)
    assert counts["symbols"] > 0
    report(
        source,
        "symbols",
        {
            **counts,
            "issues": dict(issues_by_code),
            "read_errors": 0,
            "seconds": round(time.perf_counter() - start, 1),
        },
    )
