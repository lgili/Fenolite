# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``nolead`` family with its exposed pad and paste grid (change c0260, scenario "QFN exposed pad")."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.lands import LANDS, Goals, LandTable
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def _ep_170(raw: dict[str, Any]) -> None:
    raw.update(name="QFN16_Test")
    raw["ep"] = {"length": "1.70mm", "width": "1.70mm"}
    raw["land"]["ep"] = {"length": "1.70mm", "width": "1.70mm"}


def test_qfn_exposed_pad(record: Record) -> None:
    table = replace(LANDS[1], paste_cell=3_000_000)
    result = generate(record("qfn16", _ep_170), table=table)
    fp = result.footprint
    assert fp is not None
    ep = next(p for p in fp.pads if p.number == "EP")
    assert (ep.size.w, ep.size.h) == (1_700_000, 1_700_000) and ep.layers == ("F.Cu", "F.Mask")
    windows = [g for g in fp.graphics if g.layer == "F.Paste"]
    assert len(windows) == 4 and all(g.filled and g.kind == "rect" for g in windows)
    centres = sorted(((a.x + b.x) // 2, (a.y + b.y) // 2) for a, b in (g.points for g in windows))
    assert centres == [(-425_000, -425_000), (-425_000, 425_000), (425_000, -425_000), (425_000, 425_000)]
    assert {(b.x - a.x, b.y - a.y) for a, b in (g.points for g in windows)} == {(680_000, 680_000)}


def test_record_paste_and_numbering(record: Record) -> None:
    result = generate(record("qfn16"))
    fp = result.footprint
    assert fp is not None and len(fp.pads) == 17
    windows = [g for g in fp.graphics if g.layer == "F.Paste"]
    assert len(windows) == 4  # 1.68 mm < 2 paste cells of lands/1
    pads = {p.number: p for p in fp.pads}
    assert pads["1"].position.x == -1_400_000 and pads["1"].position.y < 0
    assert pads["5"].position.y == 1_400_000  # the bottom row follows the left row
    assert pads["1"].size.w > pads["1"].size.h and pads["5"].size.h > pads["5"].size.w


def test_given_paste_grid(record: Record) -> None:
    def grid(raw: dict[str, Any]) -> None:
        raw["land"]["paste"] = {"grid": [3, 3], "window": "0.4mm", "pitch": "0.55mm"}

    fp = generate(record("qfn16", grid)).footprint
    assert fp is not None
    windows = [g for g in fp.graphics if g.layer == "F.Paste"]
    assert len(windows) == 9


def test_calculated_lands_keep_clear_of_the_exposed_pad(record: Record) -> None:
    def big_ep(raw: dict[str, Any]) -> None:
        raw.pop("land")
        raw.update(name="QFN16_Big")
        raw["ep"] = {"length": "2.20mm", "width": "2.20mm"}

    table = LandTable(version=1, goals={"nolead": Goals(150_000, -150_000, -30_000)})
    result = generate(record("qfn16", big_ep), table=table)
    fp = result.footprint
    assert fp is not None and "package.pads-clipped" in [i.code for i in result.issues]
    ep = next(p for p in fp.pads if p.number == "EP")
    for pad in fp.pads:
        if pad.number == "EP":
            continue
        dx = max(0, abs(pad.position.x) - pad.size.w // 2 - ep.size.w // 2)
        dy = max(0, abs(pad.position.y) - pad.size.h // 2 - ep.size.h // 2)
        assert max(dx, dy) >= table.pad_gap, pad.number


def test_exposed_pad_larger_than_the_body(record: Record) -> None:
    def huge(raw: dict[str, Any]) -> None:
        raw.update(name="QFN16_Huge")
        raw["ep"] = {"length": "3.2mm", "width": "3.2mm"}

    result = generate(record("qfn16", huge))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.dimensions-inconsistent"]


def test_dual_no_lead(record: Record) -> None:
    def dfn(raw: dict[str, Any]) -> None:
        raw.update(name="DFN6_Test", pins=6, arrangement="dual", pitch="0.65mm")
        raw["land"] = {
            "source": "S-0962 test",
            "pad": {"length": "0.6mm", "width": "0.3mm"},
            "row_spacing": "2.8mm",
        }

    fp = generate(record("qfn16", dfn)).footprint
    assert fp is not None and [p.number for p in fp.pads] == ["1", "2", "3", "4", "5", "6", "EP"]
    assert fp.pads[0].position.y == -650_000 and fp.pads[0].position.x == -1_400_000
