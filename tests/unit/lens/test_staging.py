# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strategy groups staged as one box (change c0255; capability placement-in-code, "Strategy groups without a
pose"): the build reports each part of a group as staged and continues its staging row after the groups."""

from __future__ import annotations

from _buildhelp import blink, build, codes

from fenolite.backends.kicad.embed import footprint_extent
from fenolite.core.coords import Point
from fenolite.dsl import Design, Part, placements
from fenolite.lens.preserve import CodePlacement, is_staged, staging_after

MM = 1_000_000


def unplaced(*refs: str) -> Design:
    """The blink with the parts ``refs`` left unplaced (as ``test_build_place``)."""
    script = blink()
    d = Design("blink")
    d.board("50mm", "30mm")
    for path, part in script.parts.items():
        fresh = Part(part.ref, part.lib_id, footprint=part.footprint, value=part.value)
        if path not in refs:
            assert part.request is not None
            r = part.request
            fresh.place(f"{r.x}nm", f"{r.y}nm", rot=r.rotation // 1_000_000, side=r.side, locked=r.locked)
        d.add(fresh)
    return d


def test_group_staged_parts_and_the_row_after_them() -> None:
    design = unplaced("D1", "R1")
    requested = dict(placements(design))
    # D1 stands for a part of a staged group: placed at the staging offset, the row continuing at 170 mm
    group = CodePlacement(Point(160 * MM, 102 * MM), 0, "top", False, "", True, 170 * MM)
    requested["D1"] = group
    out = build(design, placements_override=requested)
    assert codes(out).count("layout.unplaced") == 2 and out.files
    assert sorted(out.summary["staged"]) == ["D1", "R1"]  # type: ignore[arg-type]
    fps = {fp.lib_ref.split(":")[1]: fp for fp in out.design.board.footprints}  # type: ignore[union-attr]
    assert fps["Mini_LED_THT_3mm"].position == Point(160 * MM, 102 * MM)
    from _buildhelp import LIBS

    from fenolite.backends.kicad.mod import read_footprint

    res = footprint_extent(read_footprint(LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod"))
    assert fps["Mini_R_0603"].position.x + res.x0 == 170 * MM


def test_helpers() -> None:
    plain = CodePlacement(Point(0, 0), 0, "top", False)
    staged = CodePlacement(Point(0, 0), 0, "top", False, staged=True, after=5)
    assert not is_staged(plain) and is_staged(staged)
    assert staging_after({"a": plain}) is None and staging_after({"a": plain, "b": staged}) == 5
