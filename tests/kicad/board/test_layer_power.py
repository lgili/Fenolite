# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A copper row of type ``power`` under ``kicad-cli`` (capability kicad-oracle, "Plane routing passes the
oracle", row type; hypothesis H-K-LAYER-POWER; change c0107). The cases are in ``_planecases.py``."""

from __future__ import annotations

import _planebench as pb
import _planecases as pc
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def targets() -> list[int]:
    """The board formats the running major loads: its own and the older one."""
    return [9, 10] if major() >= 10 else [9]


def test_power_rows_load_and_add_no_violation_type() -> None:
    for target in targets():
        found = pc.power_run(target)
        assert found.signal is not None, f"t{target}: the control board with signal rows does not load"
        assert found.power is not None, f"t{target}: the board with power rows does not load"
        assert found.new_types == set(), f"t{target}: {sorted(found.new_types)}"
        assert run(f"pcb-layer-power-t{target}") == "equal"


def test_power_rows_plot_as_inner_copper() -> None:
    """The Gerber file function of a ``power`` row is that of a signal row: ``Copper,L<n>,Inr``."""
    for target in targets():
        functions = pc.power_run(target).functions
        assert functions == ((1, "Top"), (2, "Inr"), (3, "Inr"), (4, "Bot")), (target, functions)


@pytest.mark.kicad_min_major(10)
def test_power_rows_survive_a_resave() -> None:
    """``pcb upgrade --force`` (10.0 only) keeps the type of both rows."""
    assert pc.power_run(10).resaved == pb.PLANE_LAYERS
    assert run("pcb-layer-power-resave") == "equal"
