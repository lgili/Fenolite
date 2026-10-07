# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plane fan-out of ``fenolite route`` under ``kicad-cli`` (capability kicad-oracle, "Plane routing passes
the oracle", fan-out; hypothesis H-K-FANOUT; change c0107). The cases are in ``board/_planecases.py``.

The board is judged by the ``kicad-cli`` of its own major: the target-10 board on 10.0, and the target-9
board, filled by ``fenolite fill`` with a ``kicad-cli`` 10, on 9.0. 9.0 cannot refill zones (S-0037): where
it runs with no ``kicad-cli`` 10 beside it (the pinned image, the ``kicad-9`` job) it judges the two filled
target-9 boards of ``tests/data/kicad/routing/``, which the run on 10.0 writes with
``FENOLITE_PROBES_WRITE=1`` and compares with its own fill otherwise."""

from __future__ import annotations

import os

import _planebench as pb
import _planecases as pc
import pytest
from _probes import WRITE_VARIABLE, major, run

pytestmark = pytest.mark.needs_kicad


def test_fanout_passes_check_and_drc() -> None:
    target = 10 if major() >= 10 else 9
    found = pc.fanout_run(target)
    if not found.filled:
        pytest.skip("the target-9 board is filled by kicad-cli 10: none is here, and no filled fixture")
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


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("label", pc.FANOUT_LABELS)
def test_fixture_is_the_filled_board(label: str) -> None:
    """The committed fixture is the target-9 board that this run filled; ``FENOLITE_PROBES_WRITE=1`` writes
    it. The run that fills is the run that judges the fan-out of that board on 10.0."""
    found = pc.fanout_run(9)
    filled = dict(found.boards)[label]
    assert pc.fanout_outcome(9) == "equal", "the target-9 fan-out does not pass on this kicad-cli"
    path = pc.fanout_fixture(label)
    if os.environ.get(WRITE_VARIABLE) == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(filled, encoding="utf-8", newline="\n")
    assert path.is_file(), f"run with {WRITE_VARIABLE}=1 to write {path.name}"
    assert path.read_text(encoding="utf-8") == filled
