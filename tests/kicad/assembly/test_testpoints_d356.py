# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test-point report against ``pcb export ipcd356`` (capability kicad-oracle, "Test-point report agrees
with IPC-D-356"; hypothesis ``H-K-TESTPOINT-D356``; change c0118).

The bench holds a top SMD, a bottom SMD and a through-hole test pad, and a top SMD pad without a mask
layer, each marked ``test_point`` on its own net (``_featurebench.TEST_PADS``). They are written through
the model API: ``design.test_point()`` waits for changes c0102 and c0103."""

from __future__ import annotations

import _featurebench as fb
import _probes
import pytest

from fenolite.backends.kicad import frame
from fenolite.backends.kicad.pcb import read_board
from fenolite.exports import testpoints

pytestmark = pytest.mark.needs_kicad


def _recorded() -> None:
    if _probes.major() not in fb.MAJORS:
        pytest.skip(f"the probes of change c0118 are recorded for the majors {fb.MAJORS} only")


def test_four_kinds_of_test_pad() -> None:
    """Scenario "Four kinds of test pad"."""
    _recorded()
    assert _probes.run("asm-testpoint-d356") == "equal"


@pytest.mark.parametrize("target", [9, 10])
def test_rows_and_records(target: int) -> None:
    """The four rows have the access ``top``, ``bottom``, ``both`` and ``none``; their records hold
    ``A01 S2``, ``A02 S1``, ``A00 S0`` and ``A01 S3``; and each row agrees with its record."""
    _recorded()
    if target not in fb.targets(_probes.runner()):
        pytest.skip(f"KiCad {_probes.major()} does not load target {target}")
    design = read_board(fb.feature_text(target))
    rows = testpoints.report(design, frame.board_pads(design)).test_points
    by_position = {row.position: row.access for row in rows}
    assert tuple(by_position[at] for _, at, _, _ in fb.TEST_PADS) == fb.ACCESS
    assert fb.mask_codes(_probes.runner(), target) == fb.CODES
    assert fb.report_problems(_probes.runner(), target) == []
