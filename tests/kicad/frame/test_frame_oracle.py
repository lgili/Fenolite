# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-frame queries against the running ``kicad-cli`` (capability kicad-oracle, "Board-frame queries agree
with kicad-cli"; ``H-G-FRAME-SHAPE``, ``H-G-FRAME-CRTYD`` and the reused rows ``H-G-ROT-DIR``,
``H-G-BOTTOM-PLACE``, ``H-G-PAD-ANGLE-ABS``; change c0028)."""

from __future__ import annotations

from pathlib import Path

import _framebench
import pytest
from _probes import major, run, runner

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.ipcd356 import read_ipcd356

pytestmark = pytest.mark.needs_kicad
QUARTER = 90_000_000


def test_pad_positions(tmp_path: Path) -> None:
    """Every pad record of ``pcb export ipcd356`` matches one ``board_pads`` record by reference and pin;
    position differences agree within the export's rounding, and ``R`` is ``(−rotation) mod 360°``."""
    target = major()
    design = _framebench.bench(target)
    board, files = _framebench.write(design, target, tmp_path)
    export = read_ipcd356(runner().export_ipcd356(board, files=files))
    pads = {(pad.ref, pad.number): pad for pad in board_pads(design)}
    records = [r for r in export.records if r.ref != "VIA"]
    assert len(records) == len(pads) == len({(r.ref, r.pin) for r in records})
    first = records[0]
    origin = pads[(first.ref, first.pin)]
    unit = export.unit_nm
    quarter_refs = 0
    for record in records:
        pad = pads[(record.ref, record.pin)]
        # the export frame is Y up, in units of 2540 nm; only differences are compared
        dx = (record.x - first.x) * unit - (pad.position.x - origin.position.x)
        dy = -(record.y - first.y) * unit - (pad.position.y - origin.position.y)
        # each record is rounded to a unit, so two records differ by at most one unit beyond the model;
        # a second unit is allowed where the footprint is not at a multiple of 90°
        on_axis = pad.rotation % QUARTER == 0
        limit = (1 if on_axis else 2) * unit
        assert abs(dx) <= limit and abs(dy) <= limit, (record.ref, record.pin, dx, dy)
        assert record.rotation == (-pad.rotation // 1_000_000) % 360, (record.ref, record.pin)
        quarter_refs += on_axis
    assert quarter_refs > len(records) // 2
    bottom_270 = [p for p in pads.values() if p.side == "bottom" and p.rotation % 360_000_000 == 3 * QUARTER]
    assert bottom_270, "the bench holds bottom footprints at 270°"


def test_shape_canary() -> None:
    """Scenario "Clearance canary": every near probe gives exactly one clearance violation, no far one any."""
    assert run("pcb-frame-shape-near") == "present"
    assert run("pcb-frame-shape-far") == "absent"


def test_courtyard_canary() -> None:
    """Scenario "Courtyard canary": every overlapping pair gives one violation, no gapped pair any."""
    assert run("pcb-frame-crtyd-overlap") == "present"
    assert run("pcb-frame-crtyd-gap") == "absent"
