# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed footprints match their library definitions (capability kicad-oracle; hypotheses
H-G-BOTTOM-STORE, H-G-FLIP, H-G-PAD-ANGLE-ABS and H-K-LIB-DRC; change c0017 Decision 18).

The bench places ``Mini_R_0603``, ``Mini_LED_THT_3mm`` and ``Mini_QFP-32_7x7mm_P0.8mm`` at 0°, 30°, 90°
and 180° on both sides (24 placements) with a project ``fp-lib-table`` and an empty
``KICAD_CONFIG_HOME``. Three independent outputs check it: ``pcb export pos`` (side and rotation),
``pcb export ipcd356`` (pads relative to the first record, ±2 export units per axis) and the
library-parity check of ``pcb drc`` with three negative controls and the missing-table control. On
10.0.6 a silent missing-table control makes the run ``inconclusive`` and fails it; on 9.0.9 every DRC
outcome is only recorded (``tests/kicad/test_probe_results.py`` pins them).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import _bench
import pytest
from _boards import census
from _frame import pad_report, pos_problems, read_pos
from _probes import major, run, runner

from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
LIB_DRC = "H-K-LIB-DRC"


def written(tmp_path: Path) -> tuple[Design, Path, dict[str, Path]]:
    design = _bench.bench(major())
    board, files = _bench.write(design, major(), tmp_path)
    return design, board, files


def parity(probe: str, expected: str) -> None:
    """Assert a library-parity outcome on 10.0.6; on 9.0.9 it is only recorded (``H-K-LIB-DRC``)."""
    outcome = run(f"pcb-libdrc-{probe}")
    if major() < 10:
        return
    if outcome == "inconclusive":
        pytest.fail(f"{LIB_DRC}: the missing-table control did not fire, so {probe!r} is inconclusive")
    assert outcome == expected, f"{probe}: {outcome}"


def test_flip_angle(tmp_path: Path) -> None:
    """``H-G-FLIP``: pos side and rotation equal the model for all 24 placements; on 10.0.6 the
    wrong-flip-angle control gives exactly one ``lib_footprint_mismatch``."""
    design, board, files = written(tmp_path)
    rows = read_pos(runner().export_pos_csv(board, files=files))
    assert len(rows) == 24 and pos_problems(design, rows) == []
    assert Counter(row.side for row in rows) == {"top": 12, "bottom": 12}
    parity("bench", "absent")
    parity("flip-angle", "present")


def test_bottom_store(tmp_path: Path) -> None:
    """``H-G-BOTTOM-STORE``: every IPC-D-356 pad, relative to the first record, within ±2 export units
    of ``at + R(θ)·stored``; on 10.0.6 no mismatch for the bench and one for the unmirrored control."""
    design, board, files = written(tmp_path)
    report = pad_report(design, read_ipcd356(runner().export_ipcd356(board, files=files)))
    assert report.problems == [] and report.matched == sum(len(fp.pads) for fp in design.board.footprints)  # type: ignore[union-attr]
    parity("bench", "absent")
    parity("unmirrored", "present")


def test_pad_angles(tmp_path: Path) -> None:
    """``H-G-PAD-ANGLE-ABS``: no mismatch with absolute pad angles and one for the relative-angle
    control; the IPC-D-356 ``R`` fields are recorded, not asserted."""
    design, board, files = written(tmp_path)
    report = pad_report(design, read_ipcd356(runner().export_ipcd356(board, files=files)))
    census("flip", f"r_fields:{major()}", sorted(f"{stored}->{r}" for (stored, r) in report.r_fields))
    parity("bench", "absent")
    parity("relative-angles", "present")


def test_lib_drc() -> None:
    """``H-K-LIB-DRC``: a mismatch for an altered placement, none for an exact one, and
    ``lib_footprint_issues`` without the table; inconclusive (failing) on 10.0.6 when that control is
    silent, recorded only on 9.0.9."""
    outcomes = {name: run(f"pcb-libdrc-{name}") for name in ("missing-table", "exact", *_bench.CONTROLS)}
    census("flip", f"libdrc:{major()}", outcomes)
    if major() < 10:
        return
    if outcomes["missing-table"] != "present":
        pytest.fail(f"{LIB_DRC}: the missing-table control reported no lib_footprint_issues (inconclusive)")
    assert outcomes["exact"] == "absent"
    assert all(outcomes[name] == "present" for name in _bench.CONTROLS), outcomes


def test_exact_control_has_no_mismatch() -> None:
    parity("exact", "absent")
