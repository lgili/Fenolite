# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The derived rules of impedance targets judged by ``pcb drc`` on both majors (capability kicad-oracle,
"Impedance targets pass the oracle", scenario "Rules and the built design on both majors"; hypothesis
H-K-DRU-IMPEDANCE; change c0105).

The probe ``dru-impedance-width`` joins ``_probes.PROBES`` in the commit that records it on both majors.
"""

from __future__ import annotations

import _zbench as zb
import pytest

pytestmark = pytest.mark.needs_kicad


def test_width_rules_per_layer() -> None:
    """A track 1 µm above ``max`` and one 50 µm below ``min`` are reported on their layers; a track of the
    class on a layer without a rule is not."""
    function, _majors = zb.width_probes()["dru-impedance-width"]
    found = function()
    print("dru-impedance-width:", found, zb.dump(zb.width_run()))
    assert found != "inconclusive", "rules file not loaded: the canary violation is absent from a DRC report"
    assert found == "present"


@pytest.mark.parametrize("narrow", [False, True])
def test_built(narrow: bool) -> None:
    """The design with both targets, built for the running major: it loads with no
    ``missing_tuning_profile``, the canary fires, the tracks at the targets' geometry get no finding, and a
    track 50 µm narrower gets one ``track_width`` finding."""
    result = zb.built_run(narrow)
    print("built", "narrow" if narrow else "exact", zb.dump(result))
    assert result.report is not None and result.canary, "rules file not loaded: the canary did not fire"
    assert not result.any_of(zb.MISSING_TYPES)
    assert not any(result.of(label, zb.GAP_TYPES) for label in ("usb_a", "usb_b"))
    widths = [label for label in ("se_f", "se_b", "usb_a", "usb_b") if result.of(label, zb.WIDTH_TYPES)]
    assert widths == (["se_b"] if narrow else [])
