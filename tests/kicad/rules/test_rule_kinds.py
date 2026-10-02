# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Each lowered kind in KiCad (capability rules-model, "Each kind is enforced"; hypothesis H-K-DRU-KIND;
change c0018). One bench holds a probed and a control item per kind, each 4 mm from other copper; the
rules are lowered with ``lower_rules`` on nets of the probed items."""

from __future__ import annotations

import _rulebench as rb
import _rulecases as rc
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad
VIOLATION_TYPES = {
    "clearance": "clearance",
    "edge_clearance": "copper_edge_clearance",
    "track_width": "track_width",
    "via_diameter": "via_diameter",
    "hole_size": "drill_out_of_range",
    "via_drill": "drill_out_of_range",
}
"""The violation type observed per kind on 9.0.9 and 10.0.6 (``docs/formats/kicad/rules.md``)."""


@pytest.mark.parametrize("kind", rc.KINDS)
def test_kind(kind: str) -> None:
    result = rc.kinds()
    rb.require_canary(result.report, result.bench)
    probe = "clearance_probe_a" if kind == "clearance" else f"{kind}_probe"
    control = "clearance_control_a" if kind == "clearance" else f"{kind}_control"
    assert result.types_of(probe) == (VIOLATION_TYPES[kind],)
    assert result.types_of(control) == ()
    assert run(f"dru-kind-{kind}") == "present"
