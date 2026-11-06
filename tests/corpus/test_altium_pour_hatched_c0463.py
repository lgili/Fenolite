# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hatched pour against Altium's (change c0463, task 3.2; design D3; ``docs/formats/altium/pcb-pour.md``,
"Hatched pour"; ``H-A-POUR-HATCH``).

The kit sample ``pour-hatched`` is Fenolite's own; Altium Designer 24.5 repoured it in K6.12 (S-2223) and
``tests/data/altium/kit/pour-hatched.json`` lists, per hatched polygon, the tracks and arcs it poured, in
the file's units. The sample is built here, with its hatches poured by Fenolite into ``computed/``, and the
copper of each hatched polygon, as the written document holds it, is compared by M1 to M4 with the copper
of Altium's tracks and arcs.
"""

from __future__ import annotations

import importlib.util
import json
import runpy
from fractions import Fraction
from pathlib import Path

import pytest

from fenolite.core.coords import Point

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "examples" / "kit" / "pour-hatched" / "design.py"
RECORD = ROOT / "tests" / "data" / "altium" / "kit" / "pour-hatched.json"
HATCHED = ("P1", "P2", "P3", "P4", "P5", "P6", "P7")


def _altium(entry: dict[str, list[list[int]]]) -> list[tuple[tuple[Point, ...], int]]:
    """The centre lines and widths of the tracks and arcs Altium poured for one polygon, in the frame of
    the import: Y negated, no offset."""
    from fenolite.backends.altium.adapter.units import circle_points, pcb_length, pcb_point
    from fenolite.geometry.shapes import Circle

    found: list[tuple[tuple[Point, ...], int]] = []
    for x1, y1, x2, y2, width in entry["track_list"]:
        found.append(((pcb_point(x1, y1), pcb_point(x2, y2)), pcb_length(width)))
    for cx, cy, radius, start, end, width in entry["arc_list"]:
        assert (start, end) == (0.0, 360.0)  # S-2223: every arc of a hatch is a full circle
        centre, _ = circle_points(cx, cy, radius)
        ring = Circle.from_radius(centre, pcb_length(radius)).polygonize(50)
        found.append(((*ring, ring[0]), pcb_length(width)))
    return found


@pytest.fixture(scope="module")
def built() -> dict[str, bytes]:
    from fenolite.cli._kit import build_sample

    return dict(build_sample(SAMPLE).files)


def test_the_record_is_the_samples(built: dict[str, bytes]) -> None:
    """The record was made from this sample: its hatches are the sample's, and its reference document is
    the one the run took (``sample_sha256``)."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    hatches = runpy.run_path(str(SAMPLE))["HATCH"]
    polygons = record["documents"]["pour-hatched"]["polygons"]
    assert {p["name"]: p["hatch_style"] for p in polygons if p["hatch_style"] != "Solid"} == hatches
    assert all(p["tracks"] > 0 and p["regions"] == 0 for p in polygons if p["name"] in HATCHED)


def test_hatches_are_written_as_tracks(built: dict[str, bytes]) -> None:
    """Each hatched polygon of ``computed/`` is poured as tracks of its polygon (no net, sub-polygon 1, as
    S-2223 holds them) and no region; the solid sentinel keeps its region."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.altium.read.pcbprims import TrackRecord

    document = read_pcbdoc(built["computed/pour-hatched.PcbDoc"], file="pour-hatched.PcbDoc")
    names = {index: p.name for index, p in enumerate(document.polygons)}
    tracks: dict[str, int] = {}
    for track in document.tracks:
        if isinstance(track, TrackRecord) and track.prefix.polygon is not None:
            assert (track.prefix.net, track.sub_polygon) == (None, 1)
            tracks[names[track.prefix.polygon]] = tracks.get(names[track.prefix.polygon], 0) + 1
    assert sorted(tracks) == list(HATCHED)
    regions = {names[index] for index in names if document.regions_of(index)}
    assert "P0" in regions and not regions & set(HATCHED)


@pytest.mark.parametrize("name", HATCHED)
def test_hatch_matches_altium(built: dict[str, bytes], name: str) -> None:
    """Scenario "The hatched sample": the copper of the polygon as Fenolite wrote it passes M1 to M4 against
    the copper of the tracks and arcs Altium poured (S-2223); failures are listed with their places
    (``-rA``)."""
    from fenolite.backends.altium.pour import PolygonPour, PourResult, polygons_of, read_pour
    from fenolite.backends.altium.pourcompare import compare_computed
    from fenolite.geometry.boolean.clipper import ClipperBackend

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    entry = next(p for p in record["documents"]["pour-hatched"]["polygons"] if p["name"] == name)
    reading = read_pour(built["computed/pour-hatched.PcbDoc"], file="pour-hatched.PcbDoc")
    polygon = next(p for p in polygons_of(reading) if p.name == name)
    assert polygon.index == entry["index"] and polygon.hatch is not None
    backend = ClipperBackend()
    strokes = [
        piece for core, width in _altium(entry) for piece in backend.stroke([core], width // 2, tol=10)
    ]
    altium = PolygonPour(
        polygon.index, polygon.layer, polygon.net, backend.union(strokes), polygon.arc_resolution
    )
    found = compare_computed(reading, PourResult((altium,)), backend=backend)
    (verdict,) = found.polygons
    for failure in verdict.failures:
        print(f"{name} {failure.criterion} {failure.message} at {failure.at}")
    area = sum((Fraction(abs(d.size)) for d in verdict.differences), start=Fraction(0))
    print(f"{name}: M1 {verdict.ratio:.3f}, pieces {verdict.pieces}, differences {area / 10**12} mm2")
    assert verdict.passed, [f.criterion for f in verdict.failures]
