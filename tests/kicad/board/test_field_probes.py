# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field probes on boards written as text (capability kicad-oracle, "Footprint fields pass the field
oracle"; hypotheses H-K-FIELD-FRAME, H-K-FIELD-JUSTIFY, H-K-FIELD-DRC and H-K-FIELD-OUTSIDE; change c0030).

These run before the model knows footprint fields. An outcome that contradicts the frame of
``design-model`` "Footprint fields" stops the change until its design is amended.
"""

from __future__ import annotations

import _fieldprobe
import pytest
from _probes import PROBES, major, run

pytestmark = pytest.mark.needs_kicad


def test_field_probes_are_registered() -> None:
    assert set(_fieldprobe.field_probes()) <= set(PROBES)
    assert set(_fieldprobe.EXPECTED) | {"field-edge-zero"} == set(_fieldprobe.field_probes())


@pytest.mark.parametrize("probe", sorted(_fieldprobe.EXPECTED))
def test_field_probe(probe: str) -> None:
    assert run(probe) == _fieldprobe.EXPECTED[probe], _fieldprobe.observed()


def test_anchor_formula() -> None:
    """The expected anchors of the 30° canaries are the design's worked examples."""
    by_key = {c.key: c for c in _fieldprobe.canaries()}
    bottom = by_key["frame-bottom-30"]
    found = _fieldprobe.anchor(bottom, bottom.fields[0])
    assert (found.x, found.y) == (1_669_873, 40_500_000)


def test_edge_zero_is_recorded_not_judged() -> None:
    """9.0.9 is silent at ``min_silk_clearance`` 0 and 10.0.6 is not; the outcome is pinned by the probe
    results file and never fails this test."""
    outcome = run("field-edge-zero")
    assert outcome in ("present", "absent"), outcome
    if outcome != _fieldprobe.EDGE_ZERO.get(major()):
        pytest.xfail(f"field-edge-zero is {outcome} on major {major()}; see the probe results file")
