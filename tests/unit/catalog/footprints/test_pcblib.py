# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated footprints in an Altium PCB library (change c0260, maintainer's answer to open question 3,
scenario "PcbLib read back with equal pads")."""

from __future__ import annotations

from decimal import Decimal

from _package_records import every_record

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium import pcblib
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.catalog.footprints import generate, positions_of
from fenolite.core.units import u_to_nm
from fenolite.model.library import FootprintDef

ALLOWED_DROPS = ("pad EP without F.Paste", "rect on F.Paste")
"""What the Altium writer leaves out of a generated footprint: the paste windows of an exposed pad and its
missing paste opening (Altium keeps paste as a pad expansion)."""


def _extras(defn: FootprintDef) -> dict[str, pcblib.PadExtras]:
    return {
        pad.id: pcblib.PadExtras(None if pad.corner_ratio is None else Decimal(pad.corner_ratio) / 1_000_000)
        for pad in defn.pads
    }


def _generated() -> list[FootprintDef]:
    found: list[FootprintDef] = []
    for package in every_record():
        for count in positions_of(package)[:2] or (None,):
            footprint = generate(package, positions=count).footprint
            assert footprint is not None, package.file
            found.append(footprint)
    return found


def test_every_family_passes_the_writer_check() -> None:
    for defn in _generated():
        check = pcblib.check_footprint(defn, _extras(defn))
        assert check.refusal is None, (defn.name, check.refusal)
        assert all(drop in ALLOWED_DROPS for drop in check.dropped), (defn.name, check.dropped)
        assert check.pads == defn.pads


def test_pcblib_read_back_with_equal_pads() -> None:
    defs = _generated()
    data = pcblib.write_pcblib([pcblib.LibFootprint(d, _extras(d)) for d in defs], filename="Local.PcbLib")
    library = read_pcblib(data, file="Local.PcbLib")
    assert not [i for i in library.issues if i.severity == "error"]
    assert sorted(library.names) == sorted(d.name for d in defs)
    for defn in defs:
        read = library.footprint(defn.name)
        assert read is not None, defn.name
        assert [p.name for p in read.pads] == [p.number for p in defn.pads], defn.name
        for written, pad in zip(defn.pads, read.pads, strict=True):
            assert abs(u_to_nm(pad.x) - written.position.x) <= 2, (defn.name, pad.name)
            assert abs(u_to_nm(pad.y) + written.position.y) <= 2, (defn.name, pad.name)  # the library is Y up
            assert abs(u_to_nm(pad.size_top[0]) - written.size.w) <= 2, (defn.name, pad.name)
            assert abs(u_to_nm(pad.size_top[1]) - written.size.h) <= 2, (defn.name, pad.name)
            assert pad.shape_top == rec.PAD_SHAPES[written.shape], (defn.name, pad.name)
            if written.shape == "roundrect":
                assert pad.alternate_shapes is not None and pad.alternate_shapes[0] == rec.ROUNDED_ALTERNATE
            assert abs(u_to_nm(pad.hole) - (written.drill or 0)) <= 2, (defn.name, pad.name)
            assert pad.plated == (written.kind == "thru_hole"), (defn.name, pad.name)
