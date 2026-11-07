# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hatched polygon's record and the records of Altium's repour (change c0463, tasks 3.1 and 4.1).

The boards are authored for these tests (``tests/_altium_pour.py``) and the kit sample ``pour-hatched``; no
document that Altium saved is read. ``tools/kit_pour_c0463.py record`` is run on a folder that stands in for
a run: Fenolite's own poured board in the place of each saved one."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import runpy
from pathlib import Path
from types import ModuleType

import pytest
from _altium_pour import MIL, Board, clearance, rect, via, zone

from fenolite.backends.altium import docboard, pourrecord
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import Prefix, TrackRecord
from fenolite.core.coords import Point
from fenolite.model.base import ExtBag

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "examples" / "kit" / "pour-hatched" / "design.py"


def _hatched(style: str = "45Degree") -> Board:
    pairs = (("hatch_style", style), ("grid_size", str(50 * MIL)), ("track_width", str(10 * MIL)))
    hatch = dataclasses.replace(zone("hatch", "VCC", rect(22, 2, 38, 28)), name="hatch")
    return Board(
        zones=(
            dataclasses.replace(zone("solid", "GND", rect(2, 2, 18, 28)), name="solid"),
            dataclasses.replace(hatch, ext={"altium": ExtBag(None, pairs)}),
        ),
        vias=(
            via("v1", "VCC", 10, 15),
            via("v2", "GND", 30, 15),
            via("v3", "GND", 5, 5),
            via("v4", "VCC", 35, 5),
        ),
        rules=(clearance(0.2),),
    )


def test_writer_writes_a_hatch_from_the_zone() -> None:
    """A zone with ``hatch_style``, ``grid_size`` and ``track_width`` is written with ``HATCHSTYLE``,
    ``GRIDSIZE`` and ``TRACKWIDTH``; a zone without them, or with ``Solid``, keeps the solid pour's keys."""
    data = _hatched().write(pour="outline").data
    found = {p.name: p.record for p in read_pcbdoc(data, file="x.PcbDoc").polygons}
    hatch, solid = found["hatch"], found["solid"]
    assert (hatch.get("HATCHSTYLE"), hatch.get("GRIDSIZE"), hatch.get("TRACKWIDTH")) == (
        "45Degree",
        "50mil",
        "10mil",
    )
    assert (solid.get("HATCHSTYLE"), solid.get("GRIDSIZE"), solid.get("TRACKWIDTH")) == (
        "Solid",
        "20mil",
        "8mil",
    )


def test_writer_refuses_a_hatch_it_cannot_write() -> None:
    vertices = [(0, 0), (1000, 0), (1000, 1000)]
    for hatch in (("Diagonal", 10, 10), ("90Degree", 0, 10), ("90Degree", 10, -1)):
        with pytest.raises(ValueError, match="hatch"):
            docboard.polygon_fields("TOP", vertices, name="p", pour_index=0, hatch=hatch)


def test_kit_sample_builds_its_hatches() -> None:
    """The sample ``pour-hatched`` builds both documents with the hatch of each probe, and Fenolite's pour
    pours the solid sentinel P0 as a region and each hatched polygon as tracks only (task 3.2)."""
    from fenolite.cli._kit import build_sample

    built = build_sample(SAMPLE)
    hatches = runpy.run_path(str(SAMPLE))["HATCH"]
    assert isinstance(hatches, dict)
    for variant in ("computed", "reference"):
        document = read_pcbdoc(built.files[f"{variant}/pour-hatched.PcbDoc"], file="pour-hatched.PcbDoc")
        styles = {p.name: p.record.get("HATCHSTYLE") for p in document.polygons}
        assert {name: style for name, style in styles.items() if style != "Solid"} == hatches
        assert len(styles) == 10
    record = pourrecord.document_record(built.files["computed/pour-hatched.PcbDoc"], "computed.PcbDoc")
    poured = {p["name"]: (p["regions"], p["tracks"]) for p in record["polygons"]}  # type: ignore[union-attr]
    assert poured["P0"] == (1, 0)
    assert all(poured[name][0] == 0 and poured[name][1] > 0 for name in hatches)


def test_rings_hash_does_not_depend_on_the_first_vertex_or_the_winding() -> None:
    ring = [Point(0, 0), Point(10, 0), Point(10, 5), Point(0, 5)]
    turned = [*ring[2:], *ring[:2]]
    assert pourrecord._canonical(ring) == pourrecord._canonical(turned) == pourrecord._canonical(ring[::-1])
    assert pourrecord._area(ring) == pourrecord._area(ring[::-1]) == 50


def test_direction_is_exact_and_the_same_both_ways() -> None:
    prefix = Prefix(1, 0, 0, None, 0, None, False)

    def track(x1: int, y1: int, x2: int, y2: int) -> TrackRecord:
        return TrackRecord(b"", prefix, x1, y1, x2, y2, 100, None, b"")

    assert (
        pourrecord._direction(track(0, 0, 500, 500)) == pourrecord._direction(track(500, 500, 0, 0)) == "1:1"
    )
    assert pourrecord._direction(track(0, 0, 0, -30)) == "0:1"
    assert pourrecord._direction(track(0, 0, -40, 20)) == "2:-1"
    assert pourrecord._direction(track(7, 7, 7, 7)) == "0:0"


def test_a_row_record_holds_no_geometry() -> None:
    """Without ``detail`` a polygon's entry holds counts, an area and hashes, never a coordinate list; with
    it, the poured tracks and arcs are listed."""
    data = _hatched().write().data
    plain = pourrecord.document_record(data, "a.PcbDoc")
    detail = pourrecord.document_record(data, "a.PcbDoc", detail=True)
    for entry in plain["polygons"]:  # type: ignore[union-attr]
        assert not any(isinstance(value, list) for value in entry.values())
    assert all("track_list" in entry and "arc_list" in entry for entry in detail["polygons"])  # type: ignore[union-attr]
    solid = next(e for e in plain["polygons"] if e["name"] == "solid")  # type: ignore[union-attr]
    assert solid["regions"] >= 1 and solid["vertices"] > 4  # the void of the VCC via
    assert 0 < solid["area_nm2"] < 16 * 26 * 10**12


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kit_pour_c0463", ROOT / "tools" / "kit_pour_c0463.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_reads_a_run_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``record`` writes ``pour-hatched.json`` (with the poured tracks) and ``repour.json`` (aggregates) from
    the boards of a run folder, here Fenolite's own poured boards in their place."""
    tool = _tool()
    monkeypatch.setattr(tool, "ROWS", ("row-a",))
    saved = tmp_path / "run"
    reference = saved / "pour-hatched" / "reference" / "pour-hatched.PcbDoc"
    reference.parent.mkdir(parents=True)
    poured = _hatched().write().data
    reference.write_bytes(_hatched().write(pour="outline").data)
    (saved / "pour-hatched" / "repoured.PcbDoc").write_bytes(poured)
    row = saved / "repour" / "row-a"
    row.mkdir(parents=True)
    (row / "board.PcbDoc").write_bytes(_hatched().write(pour="outline").data)
    (row / "repoured.PcbDoc").write_bytes(poured)
    (saved / "messages.json").write_text(json.dumps({"row-a": {"dialogs": [], "messages": {"Warning": 2}}}))
    out = tmp_path / "records"
    tool.record(saved, "AD 26.5", "2026-11-07", out)
    hatched = json.loads((out / "pour-hatched.json").read_text(encoding="utf-8"))
    rows = json.loads((out / "repour.json").read_text(encoding="utf-8"))
    assert hatched["schema"] == rows["schema"] == pourrecord.SCHEMA
    assert (hatched["step"], rows["step"], rows["tool"], rows["date"]) == (
        "K6.12",
        "repour",
        "AD 26.5",
        "2026-11-07",
    )
    assert "track_list" in hatched["documents"]["pour-hatched"]["polygons"][0]
    entry = rows["documents"]["row-a"]
    assert entry["messages"] == {"dialogs": [], "messages": {"Warning": 2}}
    assert entry["source_sha256"] != entry["sha256"] and "track_list" not in entry["polygons"][0]
