# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census: resolution through the template tables (kicad-library-resolution, "Resolution evidence").

Counts go only to the file named by ``FENOLITE_CENSUS_OUT``.
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import pytest
from _libcensus import CensusSource, census_sources, report, resolver_for, source_id

from fenolite.backends.kicad._libread import load_source
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.mod import footprint_from
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends

pytestmark = [pytest.mark.needs_libs, pytest.mark.slow]
SOURCES: list[CensusSource | None] = [*census_sources()] or [None]
FOOTPRINT_FAILURES = {"kicad.lib.missing-entry", "kicad.lib.unknown-nickname", "kicad.lib.invalid-id"}


def _need(source: CensusSource | None) -> CensusSource:
    if source is None:
        pytest.skip("no official library source with a known major")
    return source


@pytest.mark.parametrize("source", SOURCES, ids=source_id)
def test_reference_items_resolve(source: CensusSource | None, tmp_path: Path) -> None:
    src = _need(source)
    resolver = resolver_for(src, tmp_path)
    resistor = resolver.symbol("Device:R")
    assert resistor.reference == "R" and len(resistor.pins) == 2
    footprint = resolver.footprint("Resistor_SMD:R_0603_1608Metric")
    assert len(footprint.pads) == 2 and footprint.library == "Resistor_SMD"
    origins = Counter(origin for _, origin, _ in resolver.rows("symbol"))
    report(
        src,
        "reference",
        {
            "symbol_rows": len(resolver.rows("symbol")),
            "footprint_rows": len(resolver.rows("footprint")),
            "origins": dict(origins),
            "table_issues": dict(Counter(i.code for i in resolver.issues)),
        },
    )


@pytest.mark.parametrize("source", SOURCES, ids=source_id)
def test_footprint_properties_resolve(source: CensusSource | None, tmp_path: Path) -> None:
    src = _need(source)
    resolver = resolver_for(src, tmp_path)
    start = time.perf_counter()
    counts: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    for row, _, table in resolver.rows("symbol"):
        if row.type != "KiCad":
            continue
        path = Path(resolver.expand(row.uri, row_table=table))
        if not path.exists():
            counts["dangling_rows"] += 1
            continue
        for symbol in resolve_extends(read_symbol_library(path, library=row.nickname)):
            counts["symbols"] += 1
            if not symbol.footprint:
                counts["empty"] += 1
                continue
            try:
                resolver.locate(symbol.footprint, "footprint")
            except LibraryError as exc:
                failures[exc.issue.code] += 1
            else:
                counts["resolved"] += 1
    assert set(failures) <= FOOTPRINT_FAILURES, failures
    assert counts["resolved"] > 0
    report(
        src,
        "footprint_properties",
        {**counts, "failures": dict(failures), "seconds": round(time.perf_counter() - start, 1)},
    )


@pytest.mark.parametrize("source", SOURCES, ids=source_id)
def test_missing_models_are_warnings(source: CensusSource | None, tmp_path: Path) -> None:
    src = _need(source)
    resolver = resolver_for(src, tmp_path)
    start = time.perf_counter()
    counts: Counter[str] = Counter()
    for row, _, table in resolver.rows("footprint"):
        if row.type != "KiCad":
            continue
        folder = Path(resolver.expand(row.uri, row_table=table))
        for path in sorted(folder.glob("*.kicad_mod")):
            fp = footprint_from(load_source(path), library=row.nickname)
            counts["models"] += len(fp.models)
            warnings = resolver.missing_models(fp)
            assert all(w.code == "kicad.lib.missing-3d-model" and w.severity == "warning" for w in warnings)
            counts["missing"] += len(warnings)
            counts["unresolved_variable"] += sum(1 for w in warnings if "has no value" in w.message)
    assert counts["models"] > 0
    report(src, "models", {**counts, "seconds": round(time.perf_counter() - start, 1)})
