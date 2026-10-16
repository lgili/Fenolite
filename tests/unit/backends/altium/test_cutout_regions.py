# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board cut-out regions (capability altium-pcb-writer, "Board cut-out regions"; change c0168;
``docs/formats/altium/pcb-records.md``, "Board cut-outs")."""

from __future__ import annotations

import runpy
from pathlib import Path

import _altium_slotcases as cases
import pytest

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cutouts import CUTOUT_TOL, cutout_items, item_where
from fenolite.backends.altium.pcbdoc import CUTOUT_REGIONS, PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.dsl import Design, to_model
from fenolite.model.board import Outline

ROOT = Path(__file__).resolve().parents[4]
SLOTS = ROOT / "tests" / "data" / "slots" / "design.py"
MM = 1_000_000


def _outline() -> Outline:
    design = runpy.run_path(str(SLOTS))["design"]
    assert isinstance(design, Design)
    board = to_model(design).board
    assert board is not None and board.outline is not None
    return board.outline


def _read_rings(data: bytes) -> list[tuple[dict[str, str], int, list[Point]]]:
    found: list[tuple[dict[str, str], int, list[Point]]] = []
    for region in read_pcbdoc(data).regions:
        assert isinstance(region, RegionRecord)
        points = [Point(round(v.x), round(v.y)) for v in region.outline]
        found.append((dict(region.properties.fields), region.prefix.layer, points))
    return found


def test_the_gate_is_off_until_the_kit() -> None:
    assert CUTOUT_REGIONS is False


def test_the_keys_of_a_cut_out_region() -> None:
    """``KIND=0`` with ``ISBOARDCUTOUT=TRUE`` last, on the Keep-Out layer, no keep-out flag, no net."""
    data = rec.cutout_region([(0, 0), (100, 0), (100, 100)])
    plain = rec.region_record(rec.KEEPOUT_LAYER, [(0, 0), (100, 0), (100, 100)])
    assert data != plain and b"|CAVITYHEIGHT=0mil|ISBOARDCUTOUT=TRUE\0" in data
    assert b"KIND=0" in data and b"KEEPOUTRESTRICTIONS" not in data
    assert data[1 + 4 + 1] == 0x0C and data[1 + 4 + 2] == 0  # the two flag bytes: no keep-out
    with pytest.raises(ValueError):
        rec.cutout_region([(0, 0), (1, 1)])


def test_the_items_follow_the_kicad_lowering() -> None:
    """One lowering: the rings and the order of ``cutout_items`` are those of the KiCad backend's
    ``lowered_outline``, the L merged into one, named ``slot/S2+slot/S3``."""
    pytest.importorskip("pyclipper")
    from fenolite.backends.kicad.outline import lowered_outline

    outline = _outline()
    items = cutout_items(outline)
    assert [item.where for item in items] == ["cutout/1", "slot/S1", "slot/S2+slot/S3"]
    lowered = lowered_outline(outline)
    assert [item.ring.points for item in items] == list(lowered.cutouts)
    assert item_where("slot S9") == "slot/S9" and item_where("cut-out 2") == "cutout/2"


def test_without_a_union_the_l_is_one_item_with_a_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the ``geo`` extra the overlapping slots are still one item, which cannot be written."""
    from fenolite.backends.altium import cutouts
    from fenolite.geometry.errors import BackendUnavailable

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise BackendUnavailable(Issue("geometry.backend-unavailable", "error", "no backend"))

    monkeypatch.setattr(cutouts, "merge_groups", unavailable)
    items = cutout_items(_outline())
    (merged,) = [item for item in items if item.where == "slot/S2+slot/S3"]
    assert merged.problem is not None and "fenolite[geo]" in merged.problem
    assert all(item.problem is None for item in items if item is not merged)


def test_the_merged_l_as_one_region() -> None:
    """Scenario "The merged L as one region": written and read back by Fenolite's reader, one region with
    the keys of a board cut-out, its ring within 1 µm of the written one."""
    pytest.importorskip("pyclipper")
    (item,) = [i for i in cutout_items(_outline()) if i.where == "slot/S2+slot/S3"]
    board = (
        Point(100 * MM, 100 * MM),
        Point(160 * MM, 100 * MM),
        Point(160 * MM, 140 * MM),
        Point(100 * MM, 140 * MM),
    )
    data = write_pcbdoc(PcbDocSpec(outline=board, cutouts=(item.points(),)), filename="l.PcbDoc")
    ((keys, layer, points),) = _read_rings(data)
    assert keys["KIND"] == "0" and keys["ISBOARDCUTOUT"] == "TRUE" and layer == rec.KEEPOUT_LAYER
    written = item.points()
    assert len(points) == len(written)
    for a, b in zip(points, written, strict=True):
        x = (b.x - 100 * MM + 25_400_000) * 50 / 127
        y = (140 * MM - b.y + 25_400_000) * 50 / 127
        assert abs(a.x - x) <= 1 and abs(a.y - y) <= 1  # one unit, 2.54 nm
    # every point of the ring lies within CUTOUT_TOL of the merged ring with its arcs
    assert len(written) > len(item.ring.points) and CUTOUT_TOL == 1_000


def test_the_committed_fixture_document_is_current() -> None:
    """``tests/data/slots/slots_altium.PcbDoc`` equals a fresh build of ``altium.py`` with the gate on;
    ``FENOLITE_SLOTS_WRITE=1`` writes it."""
    pytest.importorskip("pyclipper")
    fresh = cases.fixture_document(gate=True)
    if cases.write_wanted():
        cases.FIXTURE.write_bytes(fresh)
    assert cases.FIXTURE.read_bytes() == fresh
    assert len(cases.written_cutouts(fresh)) == 3 and len(cases.written_slots(fresh)) == 3


def test_the_gate_off_document_has_no_region() -> None:
    assert cases.written_cutouts(cases.fixture_document(gate=False)) == []
