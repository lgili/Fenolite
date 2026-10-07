# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plane fan-out of ``fenolite route`` under ``kicad-cli`` (capability kicad-oracle, "Plane routing passes
the oracle", fan-out; hypothesis H-K-FANOUT; change c0107). The cases are in ``board/_planecases.py``.

The board is judged by the ``kicad-cli`` of its own major: the target-10 board on 10.0, and the target-9
board, filled by ``fenolite fill`` with a local ``kicad-cli`` 10, on 9.0."""

from __future__ import annotations

import _planebench as pb
import _planecases as pc
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_fanout_passes_check_and_drc() -> None:
    target = 10 if major() >= 10 else 9
    found = pc.fanout_run(target)
    if not found.filled:
        pytest.skip("the target-9 board is filled by kicad-cli 10, and none is on this machine")
    made = found.result["plane_fanout"]
    assert isinstance(made, dict)
    assert made["nets"] == ["GND", "VCC"] and made["vias"] == made["tracks"] == len(pb.PLANE_PADS)
    assert made["failed"] == [] and found.result["plane_layers"] == list(pb.PLANE_LAYERS)
    assert found.findings == (), "the copper check has a finding on the fan-out"
    assert found.before is not None and found.after is not None, "kicad-cli wrote no DRC report"
    assert found.open_plane_items(found.before), "the control: without fan-out the SMD plane pads are open"
    assert found.open_plane_items() == [], "a pad of a plane net is still unconnected after the fill"
    assert found.new_errors == set(), sorted(found.new_errors)
    assert run(f"route-fanout-t{target}") == "equal"
