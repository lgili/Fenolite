# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated footprints against kicad-cli (change c0260): the footprint of every authored package record,
written as ``Local.pretty`` for each supported target, loads in ``fp export svg`` (one SVG per footprint)
and reads back with equal pads after ``fp upgrade --force``. KiCad orders the pad layers its own way, and
the corner ratio read back is the ``roundrect_rratio`` child the pad keeps."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

import _fpwrite
import pytest
from _probes import major, runner

from fenolite.backends.kicad import slots as slotlib
from fenolite.catalog.footprints import generate, positions_of
from fenolite.catalog.footprints.record import Package
from fenolite.model.base import Opaque
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "catalog" / "footprints"))
from _package_records import every_record  # noqa: E402

pytestmark = pytest.mark.needs_kicad


def _generated() -> list[FootprintDef]:
    found: list[FootprintDef] = []
    package: Package
    for package in every_record():
        for count in positions_of(package)[:2] or (None,):
            footprint = generate(package, positions=count).footprint
            assert footprint is not None, package.file
            found.append(footprint)
    return found


def _ratio(pad: Pad) -> int | None:
    """``Pad.corner_ratio``, or the ``roundrect_rratio`` child a read-back pad keeps (ppm)."""
    if pad.corner_ratio is not None:
        return pad.corner_ratio
    bag = pad.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if isinstance(slot, Opaque) and slot.fragment.startswith("(roundrect_rratio "):
            text = slot.fragment.removeprefix("(roundrect_rratio ").removesuffix(")")
            return int(Fraction(text) * 1_000_000)
    return None


def _pads(defn: FootprintDef) -> list[tuple[object, ...]]:
    return [
        (p.number, p.shape, p.kind, p.position, p.size, p.drill, sorted(p.layers), _ratio(p))
        for p in defn.pads
    ]


@pytest.mark.parametrize("target", [9, 10])
def test_generated_footprints_load(target: int) -> None:
    if target > major():
        pytest.skip(f"a target-{target} library needs KiCad {target}")
    defs = _generated()
    result = _fpwrite.check(runner(), defs, target)
    assert result.loaded and result.svgs == len(defs), result
    assert not result.issues
    assert set(result.upgraded) == {d.name for d in defs}
    for defn in defs:
        again = result.upgraded[defn.name]
        assert _pads(again) == _pads(defn), defn.name
        assert len(again.graphics) == len(defn.graphics), defn.name
