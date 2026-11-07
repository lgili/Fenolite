# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's reading of the mapped rule scopes of the public Altium rows against Altium's PCB filter (change
c0462, task 5.1; S-2214). ``tests/data/altium/kit/scope-oracle-c0462.json`` holds, per scope, the objects of
each kind on the copper layers that the filter of Altium Designer 24.5.2.23 selected; for each of them
Fenolite's selector selects as many tracks, arcs, vias, pads and polygons (``tools/altium_scope_oracle.py``,
``fenolite_counts``), but for the differences of ``KNOWN``, each pinned with its reason."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _corpus import CorpusItem, heavy_enabled, manifest_items, require

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "tests" / "data" / "altium" / "kit" / "scope-oracle-c0462.json"
TOOL = ROOT / "tools" / "altium_scope_oracle.py"
KINDS = ("track", "arc", "via", "pad", "polygon")
ROWS = sorted(
    (item for item in manifest_items("altium") if item.id.startswith("altium-third-party-pcbdoc-")),
    key=lambda item: item.id,
)

KNOWN: dict[tuple[str, str], dict[str, tuple[int, int]]] = {
    ("altium-third-party-pcbdoc-02", "(CompPinCount < 5)"): {"track": (252, 191), "arc": (16, 0)},
    ("altium-third-party-pcbdoc-02", "InNetClass('PWR')"): {"polygon": (11, 12)},
    ("altium-third-party-pcbdoc-04", "(CompPinCount < 5)"): {"arc": (2, 0)},
    ("altium-third-party-pcbdoc-04", "not InNet('GND')"): {"arc": (2, 0)},
    ("altium-third-party-pcbdoc-07", "Not IsDifferentialPair"): {
        "track": (475, 0),
        "arc": (20, 0),
        "via": (60, 0),
        "pad": (116, 0),
        "polygon": (9, 0),
    },
    ("altium-third-party-pcbdoc-08", "(CompPinCount < 5)"): {"arc": (535, 529), "via": (1749, 1770)},
    ("altium-third-party-pcbdoc-08", "(OnTopLayer or OnBottomLayer) and InNet('GND')"): {
        "track": (1077, 1065),
        "arc": (26, 0),
    },
}
"""``(row, scope)`` → kind → ``(Altium's count, Fenolite's)``. Row ``-02``, ``CompPinCount < 5``: the filter
counts the 61 split lines and 16 arcs of the board's plane layers as copper tracks and arcs, which Fenolite
reads as the outlines of the plane's regions, not as tracks. Row ``-02``, ``InNetClass('PWR')``: the filter
selects 11 of the 12 polygons of the class's nets, and each of them alone with its net (extra scopes x4 to
x9 and ``GND``); not explained. Row ``-04``: the filter counts two keep-out arcs of footprints on the top
layer as arcs; Fenolite reads them as keep-out areas, not copper. Row ``-07``, extra scope x3: ``Not
IsDifferentialPair`` selects every object, since ``IsDifferentialPair`` returns the pairs alone; Fenolite
refuses it outside a rule on pairs (``object-kind``), so the comparison counts none. Row ``-08``: the filter
selects the copper tracks and arcs of footprints (12 tracks and 26 arcs of ``GND`` on the outer layers, 6
arcs of components with fewer than 5 pins), which the comparison does not count, since the import holds them
in the footprints; and of the 37 vias of components, which the import makes free vias, ``CompPinCount < 5``
selects only the 16 whose component has fewer than 5 pins."""

NOT_RUN = {
    ("altium-third-party-pcbdoc-08", "(InDifferentialPairClass('All Differential Pairs'))"): (
        "maps since the reading of InDifferentialPairClass changed; extra scope x2 ran it without brackets"
    ),
}
"""Scopes the reader maps today that the plan as run did not hold, with the run that stands for each."""


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("altium_scope_oracle_corpus", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _oracle() -> dict[str, Any]:
    return json.loads(ORACLE.read_text("utf-8"))


def test_the_oracle_records_the_run() -> None:
    """The run of 2026-11-06 on 24.5.2.23: 7 of the 8 rows measured, every scope of them counted; row
    ``-01`` not measured (the PCB Filter panel did not open on it)."""
    oracle = _oracle()
    assert (oracle["source"], oracle["altium"]) == ("S-2214", "24.5.2.23")
    rows = {row["row"]: row for row in oracle["rows"]}
    assert sorted(rows) == [item.id for item in ROWS]
    manifest = tomllib.loads((ROOT / "tests" / "corpus" / "manifest.toml").read_text("utf-8"))
    digests = {row["id"]: row["sha256"] for row in manifest["file"]}
    assert {item.id: rows[item.id]["sha256"] for item in ROWS} == {item.id: digests[item.id] for item in ROWS}
    assert [ident for ident, row in rows.items() if not row["measured"]] == ["altium-third-party-pcbdoc-01"]
    measured = [
        scope for row in rows.values() if row["measured"] for scope in (*row["scopes"], *row["extras"])
    ]
    assert len(measured) == 69 + 8 and {scope["state"] for scope in measured} == {"done"}


def _compare(item: CorpusItem, scopes: list[dict[str, Any]]) -> dict[str, dict[str, tuple[int, int]]]:
    tool = _tool()
    path = require(item)
    texts = [scope["scope"] for scope in scopes]
    mine = tool.fenolite_counts(path.read_bytes(), path.name, texts)
    found: dict[str, dict[str, tuple[int, int]]] = {}
    for scope, counts in zip(scopes, mine, strict=True):
        kinds = (*KINDS, "component") if "component" in counts else KINDS
        pairs = {kind: (scope["copper"].get(kind, 0), counts.get(kind, 0)) for kind in kinds}
        differ = {kind: pair for kind, pair in pairs.items() if pair[0] != pair[1]}
        if differ:
            found[scope["scope"]] = differ
    return found


@pytest.mark.needs_corpus
@pytest.mark.parametrize("item", ROWS, ids=[item.id for item in ROWS])
def test_fenolite_selects_what_the_filter_selects(item: CorpusItem) -> None:
    if item.heavy and not heavy_enabled():
        pytest.skip(f"{item.id} is a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    (row,) = [row for row in _oracle()["rows"] if row["row"] == item.id]
    path = require(item)
    today = _tool().mapped_scopes(path.read_bytes(), path.name)
    if not row["measured"]:
        assert today == row["scope_texts"]
        pytest.skip(f"{item.id}: not measured (S-2214)")
    run = {scope["scope"] for scope in (*row["scopes"], *row["extras"])}
    assert {scope for scope in today if scope not in run} == {
        scope for (ident, scope) in NOT_RUN if ident == item.id
    }
    expected = {scope: kinds for (ident, scope), kinds in KNOWN.items() if ident == item.id}
    assert _compare(item, [*row["scopes"], *row["extras"]]) == expected
