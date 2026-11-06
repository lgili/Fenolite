# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Repour oracle (change c0463, task 4.2; design D5; ``docs/formats/altium/pcb-pour.md``, "Records of
Altium's repour").

Altium Designer 24.5 repoured the eight public rows of the pour census (S-2224), and
``tests/data/altium/kit/repour.json`` holds, per polygon, the counts, area and ring hash of that pour. The
record holds no geometry of a row, so the comparisons that need the saved boards run only when
``FENOLITE_ALTIUM_REPOUR_DIR`` names the folder of the run (``tools/kit_pour_c0463.py``; the boards stay on
the maintainer's machine):

- without it, each source of the corpus cache is checked against the record, and the polygons whose saved
  pour is not Altium's repour (stale) are named;
- with it, each saved board is checked against the record, and Fenolite's pour of it is compared by M1 to
  M4 with the regions Altium poured.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.pourrecord import SCHEMA, document_record

pytestmark = pytest.mark.needs_corpus

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "tests" / "data" / "altium" / "kit" / "repour.json"
FOLDER = "FENOLITE_ALTIUM_REPOUR_DIR"
"""The environment variable that names the run's folder (``repour/<corpus id>/repoured.PcbDoc``)."""
DOCUMENTS = [
    *manifest_items("altium-pcbdoc"),
    *(row for row in manifest_items("rta") if row.id == "altium-third-party-pcbdoc-08"),
]
"""The seven rows of use ``altium-pcbdoc`` and the heavy eighth, as in the pour census."""

STALE: dict[str, tuple[int, ...]] = {
    "altium-third-party-pcbdoc-01": (0, 2),
    "altium-third-party-pcbdoc-02": (0, 1, 3, 5, 7, 9),
    "altium-third-party-pcbdoc-03": (),
    "altium-third-party-pcbdoc-04": (0, 2, 3, 4, 5, 6, 7, 8),
    "altium-third-party-pcbdoc-05": (),
    "altium-third-party-pcbdoc-06": (0, 1, 2, 5, 7, 8),
    "altium-third-party-pcbdoc-07": (),
    "altium-third-party-pcbdoc-08": (0, 16, 23, 26, 31),
}
"""Row → the positions in ``Polygons6`` of the polygons whose saved rings are not those of Altium 24.5's
repour (S-2224)."""

ORACLE: dict[str, tuple[dict[str, int], dict[str, tuple[str, ...]]]] = {
    "altium-third-party-pcbdoc-01": (
        {},
        {
            "P31 B.Cu": ("M1", "M2", "M3", "M4"), "P30 F.Cu": ("M2",), "P32 F.Cu": ("M1", "M2", "M3", "M4"),
            "P33 F.Cu": ("M1", "M2", "M3"), "P35 F.Cu": ("M1", "M2", "M3", "M4"),
        },
    ),
    "altium-third-party-pcbdoc-02": ({"depends-on-refused": 6, "rule-unmapped": 6}, {}),
    "altium-third-party-pcbdoc-03": ({}, {"P0 B.Cu": ("M2", "M3", "M4")}),
    "altium-third-party-pcbdoc-04": (
        {},
        {
            "P14 F.Cu": ("M1", "M2"), "P11 F.Cu": ("M2",), "P7 F.Cu": ("M1", "M2"), "P8 F.Cu": ("M1", "M2"),
            "P10 F.Cu": ("M2",), "P9 F.Cu": ("M1", "M2"), "P12 In1.Cu": ("M2",), "P13 In2.Cu": ("M2",),
            "P5 B.Cu": ("M2",),
        },
    ),
    "altium-third-party-pcbdoc-05": ({}, {"P1 B.Cu": ("M2",), "P0 F.Cu": ("M2",)}),
    "altium-third-party-pcbdoc-06": ({"depends-on-refused": 6, "rule-unmapped": 4}, {}),
    "altium-third-party-pcbdoc-07": (
        {},
        {
            "P27 In2.Cu": ("M2",), "P19 In2.Cu": ("M2",), "P25 In2.Cu": ("M2",), "P24 In1.Cu": ("M2",),
            "P18 In1.Cu": ("M2",), "P29 F.Cu": ("M2",), "P21 F.Cu": ("M2",), "P28 B.Cu": ("M2", "M3"),
            "P17 B.Cu": ("M2",),
        },
    ),
    "altium-third-party-pcbdoc-08": ({"depends-on-refused": 18, "rule-unmapped": 15}, {}),
}  # fmt: skip
"""Row → the refused polygons per reason, and the failed criteria of each compared polygon (``P<POURINDEX>
<layer>``) against Altium's repour (S-2224), measured on ``claude/c0463-pour`` without the rule scopes of
c0462: the same refusals and failures as the census against the saved pours, since rows 03 and 05 saved
Altium's repour. Task 4.3 repins them with the census on ``cac/lote-29``. The spec's target is no refusal
and no failure.

Rows ``-04`` and ``-07`` are repinned on ``cac/lote-29`` (c0462 reads their Clearance scopes) with the edge
and relief conductor of S-2227: every polygon pours; on ``-04`` 4 of 9 fail M1 (the top layer), on
``-07`` none does, and M2 remains. Parting a pinch that the neck removal closes again takes M3 and M4
off ``P0 F.Cu`` of ``-05``.

On ``cac/lote-29`` 60687e26d (c0462 tasks 4.3 to 4.5) every row is repinned: the 5 polygons of ``-01`` pour
and fail, 4 by M1 (ratios 1.27 to 4.01); ``-06`` and ``-08`` are refused ``rule-unmapped`` where they were
refused for a connect or rule scope. Rows 01 to 08 hold the same refusals and failures as the census."""


def _record() -> dict[str, object]:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _polygons(entry: object) -> list[dict[str, object]]:
    assert isinstance(entry, dict)
    polygons = entry["polygons"]
    assert isinstance(polygons, list)
    return polygons


def _saved(item: CorpusItem) -> Path:
    folder = os.environ.get(FOLDER)
    if not folder:
        pytest.skip(f"{FOLDER} names no folder of the Repour run")
    if item.heavy:
        require(item)  # the heavy row skips as in the census
    path = Path(folder) / "repour" / item.id / "repoured.PcbDoc"
    if not path.is_file():
        pytest.fail(f"{path} is missing from the run's folder")
    return path


def test_record_is_the_runs() -> None:
    """The record names its schema, the run and every row, and holds no list in a row's polygon."""
    record = _record()
    assert (record["schema"], record["step"], record["tool"], record["date"]) == (
        SCHEMA,
        "repour",
        "AD 24.5",
        "2026-11-06",
    )
    documents = record["documents"]
    assert isinstance(documents, dict) and sorted(documents) == sorted(STALE)
    for key, entry in documents.items():
        assert entry["messages"] == {"dialogs": [], "messages": {}}, key
        for polygon in _polygons(entry):
            assert not any(isinstance(value, list) for value in polygon.values()), key


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_stale_saved_pours_are_named(item: CorpusItem) -> None:
    """Scenario of D5: the source is the one Altium repoured, holds the same polygons, and its saved pour is
    Altium's repour except on the polygons of ``STALE``, which are listed (``-rA``). Altium may save the
    polygons of an internal plane in another order (row ``-01``: its split planes of ``PLANE2`` come first),
    so those are compared as a set; they pour no region."""
    path = require(item)
    data = path.read_bytes()
    entry = _record()["documents"][item.id]  # type: ignore[index]
    assert entry["source_sha256"] == hashlib.sha256(data).hexdigest()
    saved = document_record(data, path.name)["polygons"]
    repoured = _polygons(entry)
    assert isinstance(saved, list) and len(saved) == len(repoured)

    def plane(polygon: dict[str, object]) -> bool:
        return str(polygon["layer"]).upper().startswith("PLANE")

    def plain(polygons: list[dict[str, object]]) -> list[tuple[object, ...]]:
        return sorted(
            (p["layer"], p["name"], p["pour_index"], p["regions"], p["rings_sha256"]) for p in polygons
        )

    assert plain([p for p in saved if plane(p)]) == plain([p for p in repoured if plane(p)])
    stale: list[int] = []
    for before, after in zip(
        [p for p in saved if not plane(p)], [p for p in repoured if not plane(p)], strict=True
    ):
        assert (before["name"], before["layer"], before["pour_index"]) == (
            after["name"],
            after["layer"],
            after["pour_index"],
        )
        if before["rings_sha256"] != after["rings_sha256"]:
            stale.append(int(before["index"]))
            change = abs(int(after["area_nm2"]) - int(before["area_nm2"]))
            print(f"{item.id} polygon {before['index']} {before['layer']}: stale, area change {change} nm2")
    assert tuple(stale) == STALE[item.id]


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_saved_board_is_the_recorded_one(item: CorpusItem) -> None:
    """The board of the run's folder is the one the record was made from, polygon by polygon."""
    path = _saved(item)
    data = path.read_bytes()
    entry = _record()["documents"][item.id]  # type: ignore[index]
    assert entry["sha256"] == hashlib.sha256(data).hexdigest()
    assert document_record(data, "repoured.PcbDoc")["polygons"] == _polygons(entry)


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_repour_oracle(item: CorpusItem) -> None:
    """Fenolite pours each polygon of the board Altium repoured, and each poured polygon is compared by M1 to
    M4 with the regions Altium poured; a failure is listed with its places (``-rA``)."""
    if importlib.util.find_spec("pyclipper") is None:
        pytest.skip("the pour needs the geo extra")
    from fenolite.backends.altium.pour import pour_reading, read_pour
    from fenolite.backends.altium.pourcompare import compare_computed

    path = _saved(item)
    reading = read_pour(path.read_bytes(), file=path.name)
    result = pour_reading(reading)
    refused: dict[str, int] = {}
    for polygon in result.polygons:
        if not polygon.poured:
            key = "exact" if polygon.exact else polygon.reason
            refused[key] = refused.get(key, 0) + 1
    found = compare_computed(reading, result)
    failed = {f"P{v.pour_index} {v.layer}": v.failed for v in found.polygons if not v.passed}
    for verdict in found.polygons:
        print(f"{item.id} P{verdict.pour_index} {verdict.layer}: M1 {verdict.ratio:.3f}")
        for failure in verdict.failures:
            print(f"    {failure.criterion} {failure.message}")
    assert (refused, failed) == ORACLE[item.id]
