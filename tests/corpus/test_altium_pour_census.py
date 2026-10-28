# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The poured copper of the public PCB documents (change c0215; ``docs/formats/altium/pcb-pour.md``, "Saved
poured regions" and "Pour inputs"). The documents are the eight rows of the corpus manifest, read from the
corpus cache with Fenolite's own readers (S-0835); the eighth is heavy (``FENOLITE_HEAVY=1``). A count here
says what Altium saved; it raises no row above ``CORPUS-VERIFIED`` and says nothing of what Altium does."""

from __future__ import annotations

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord, RegionVertex

pytestmark = pytest.mark.needs_corpus

DOCUMENTS = [
    *manifest_items("altium-pcbdoc"),
    *(row for row in manifest_items("rta") if row.id == "altium-third-party-pcbdoc-08"),
]
"""The seven rows of use ``altium-pcbdoc`` and the heavy eighth."""
CENSUS: dict[str, tuple[int, int, int, int, int]] = {
    "altium-third-party-pcbdoc-01": (5, 40, 136, 5, 0),
    "altium-third-party-pcbdoc-02": (13, 12, 58, 6, 7),
    "altium-third-party-pcbdoc-03": (1, 6, 271, 0, 1),
    "altium-third-party-pcbdoc-04": (9, 11, 27, 9, 0),
    "altium-third-party-pcbdoc-05": (2, 5, 45, 0, 2),
    "altium-third-party-pcbdoc-06": (10, 11, 30, 10, 0),
    "altium-third-party-pcbdoc-07": (9, 16, 40, 9, 0),
    "altium-third-party-pcbdoc-08": (33, 128, 2075, 25, 8),
}
"""Row → its polygons of type ``Polygon``, its poured regions, their holes, and the polygons that hold
``POUROVER=TRUE`` with ``POUROVERSTYLE=1`` and ``POUROVER=FALSE`` with ``POUROVERSTYLE=2`` (census of
2026-10-26)."""
REGION_KEYS = (
    "V7_LAYER", "NAME", "KIND", "SUBPOLYINDEX", "UNIONINDEX", "ARCRESOLUTION", "ISSHAPEBASED", "CAVITYHEIGHT"
)  # fmt: skip
SQUARE_UNITS = {"250000000000.000000": 2500 * 10**8, "232500465000.930304": None, "15500031000.062008": None}
"""The saved ``AREATHRESHOLD`` values: 2500 mil² in square file units, and two that are 1.5 mm² and 0.1 mm²
there (checked against the nanometre value below)."""


def _document(item: CorpusItem) -> PcbDocument:
    path = require(item)
    return read_pcbdoc(path.read_bytes(), file=path.name)


def _poured(document: PcbDocument) -> list[tuple[int, RegionRecord]]:
    return [
        (at, region)
        for at, region in enumerate(document.regions)
        if isinstance(region, RegionRecord) and region.prefix.polygon is not None
    ]


def _area2(ring: tuple[RegionVertex, ...]) -> float:
    return sum(a.x * b.y - b.x * a.y for a, b in zip(ring, (*ring[1:], ring[0]), strict=True))


def _near(first: tuple[RegionVertex, ...], second: tuple[RegionVertex, ...]) -> bool:
    """The two rings have the same vertices within one file unit."""
    return len(first) == len(second) and all(
        abs(a.x - b.x) <= 1 and abs(a.y - b.y) <= 1 for a, b in zip(first, second, strict=True)
    )


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_regions(item: CorpusItem) -> None:
    """Rows of "Saved poured regions": the keys of a poured region, its prefix (no net, its polygon's
    position), its twin in ``ShapeBasedRegions6``, the winding of its rings and the counts of the census."""
    document = _document(item)
    polygons = [p for p in document.polygons if p.polygon_type == "Polygon"]
    poured = _poured(document)
    over = [(p.record.get("POUROVER"), p.record.get("POUROVERSTYLE")) for p in polygons]
    found = (
        len(polygons),
        len(poured),
        sum(region.hole_count for _, region in poured),
        over.count(("TRUE", "1")),
        over.count(("FALSE", "2")),
    )
    assert found == CENSUS[item.id]
    assert len(over) == found[3] + found[4]  # no other pairing, and no style 0
    for at, region in poured:
        keys = tuple(key for key, _ in region.properties.fields)
        assert keys == REGION_KEYS, (item.id, at)
        fields = dict(region.properties.fields)
        polygon = document.polygons[region.prefix.polygon or 0]
        assert polygon.polygon_type == "Polygon"
        assert (fields["KIND"], fields["UNIONINDEX"], fields["ISSHAPEBASED"]) == ("0", "0", "FALSE")
        assert fields["ARCRESOLUTION"] == polygon.record.get("ARCRESOLUTION")
        assert region.prefix.net is None and region.prefix.component is None
        assert (region.prefix.flags1, region.prefix.flags2) == (0x0C, 0)
        twin = document.shape_regions[at]
        assert isinstance(twin, RegionRecord)
        assert twin.prefix == region.prefix and twin.properties.fields == region.properties.fields
        assert _near(twin.outline, region.outline), (item.id, at)  # whole units against doubles
        assert len(twin.holes) == len(region.holes)
        assert all(_near(a, b) for a, b in zip(twin.holes, region.holes, strict=True)), (item.id, at)
        assert (region.outline[0].x, region.outline[0].y) != (region.outline[-1].x, region.outline[-1].y)
        assert _area2(region.outline) < 0  # clockwise in the file's frame
        assert all(_area2(hole) > 0 for hole in region.holes)


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_regions_thresholds(item: CorpusItem) -> None:
    """Row I12: ``AREATHRESHOLD`` is in square file units (2.54 nm squared); the three saved values are
    2500 mil², 1.5 mm² and 0.1 mm² there."""
    millimetres = {"232500465000.930304": 1.5, "15500031000.062008": 0.1}
    for polygon in (p for p in _document(item).polygons if p.polygon_type == "Polygon"):
        value = polygon.record.get("AREATHRESHOLD") or ""
        assert value in SQUARE_UNITS, (item.id, value)
        square_nm = float(value) * 2.54**2
        if value in millimetres:
            assert abs(square_nm - millimetres[value] * 10**12) < 1.0e3
        else:
            assert float(value) == SQUARE_UNITS[value]


TIME_LIMIT_S = 60.0
"""Task 3.6 of change c0215: above this for one document the plan comes back to the maintainer."""


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_pour_time(item: CorpusItem) -> None:
    """Reading a public document and pouring every polygon of it stays within ``TIME_LIMIT_S``
    (``docs/evidence/altium-pour.md``, "Time")."""
    import importlib.util
    import time

    if importlib.util.find_spec("pyclipper") is None:
        pytest.skip("the pour needs the geo extra")
    from fenolite.backends.altium.pour import pour_reading, read_pour

    path = require(item)
    start = time.perf_counter()
    result = pour_reading(read_pour(path.read_bytes(), file=path.name))
    elapsed = time.perf_counter() - start
    assert result.polygons
    assert elapsed < TIME_LIMIT_S, (item.id, elapsed)


POUR_CENSUS: dict[str, tuple[int, dict[str, int], dict[str, tuple[str, ...]]]] = {
    "altium-third-party-pcbdoc-01": (5, {"depends-on-refused": 3, "polygon-cutout": 2}, {}),
    "altium-third-party-pcbdoc-02": (
        12, {"depends-on-refused": 3, "outline": 1, "outline-arc": 2, "polygon-cutout": 6}, {},
    ),
    "altium-third-party-pcbdoc-03": (1, {}, {"B.Cu GND_L02_P000": ("M2", "M3", "M4")}),
    "altium-third-party-pcbdoc-04": (9, {"depends-on-refused": 5, "rule-scope": 4}, {}),
    "altium-third-party-pcbdoc-05": (
        2, {}, {"B.Cu GND_BOTTOM": ("M2",), "F.Cu GND_TOP": ("M2", "M3", "M4")},
    ),
    "altium-third-party-pcbdoc-06": (
        10, {"connect-scope": 1, "depends-on-refused": 6, "polygon-cutout": 3}, {},
    ),
    "altium-third-party-pcbdoc-07": (
        9, {"depends-on-refused": 1, "outline": 1, "outline-arc": 4, "rule-scope": 3}, {},
    ),
    "altium-third-party-pcbdoc-08": (
        33,
        {"connect-scope": 2, "depends-on-refused": 13, "outline-arc": 6, "polygon-cutout": 2,
         "rule-scope": 10},
        {},
    ),
}  # fmt: skip
"""Row → its polygons, the refused ones per reason, and the failed criteria of each compared polygon (by
layer and name) against the regions the document holds (``docs/evidence/altium-pour.md``, census of
2026-10-26). M1 passes on every compared polygon."""


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_pour_census(item: CorpusItem) -> None:
    """Scenario "Census counts are pinned": every polygon is poured or refused with a reason of
    ``pour.REASONS``, and each poured one is compared by M1 to M4 with the regions the document holds. A
    failed comparison is listed (``-rA``) with its polygon and its places; it fails nothing, since a saved
    pour may be stale, or poured by another version or with AdvancedPour."""
    import importlib.util

    if importlib.util.find_spec("pyclipper") is None:
        pytest.skip("the pour needs the geo extra")
    from fenolite.backends.altium.pour import REASONS, pour_reading, read_pour
    from fenolite.backends.altium.pourcompare import compare_computed

    path = require(item)
    reading = read_pour(path.read_bytes(), file=path.name)
    result = pour_reading(reading)
    refused: dict[str, int] = {}
    for polygon in result.polygons:
        if not polygon.poured:
            assert polygon.reason in REASONS, (item.id, polygon.reason)
            refused[polygon.reason] = refused.get(polygon.reason, 0) + 1
    found = compare_computed(reading, result)
    failed = {f"{v.layer} {v.name}": v.failed for v in found.polygons if not v.passed}
    for verdict in found.polygons:
        print(f"{item.id} {verdict.layer} {verdict.name}: pieces {verdict.pieces}, M1 {verdict.ratio:.3f}")
        for failure in verdict.failures:
            print(f"    {failure.criterion} {failure.message} {failure.at or ''}")
    assert (len(result.polygons), refused, failed) == POUR_CENSUS[item.id]
    assert all(verdict.ratio <= 1 for verdict in found.polygons)
