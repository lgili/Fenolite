# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builds of 4, 6 and 8 copper layers through fill, DRC and export (capability kicad-oracle, "Builds of
four, six and eight copper layers pass the oracle"; hypothesis H-K-BUILD-LAYERS; change c0100).

On 10.0 the variant of ``_layercases`` is built for targets 9 and 10, filled, checked, exported and built
again. With ``FENOLITE_PROBES_WRITE=1`` that run writes the filled target-9 boards of 6 and 8 layers to
``tests/data/kicad/layers/``. On 9.0, which cannot refill zones (S-0037), those two fixtures replace the
board of a target-9 build and give the DRC report and the Gerbers.
"""

from __future__ import annotations

import os

import _layercases as lc
import pytest
from _probes import WRITE_VARIABLE, major, run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("target", lc.TARGETS)
@pytest.mark.parametrize("copper", lc.COUNTS)
def test_layers_build_fill_check_export(copper: int, target: int) -> None:
    """Scenario "Builds on KiCad 10"."""
    result = lc.layer_run(copper, target)
    print(f"n={copper} t{target}: {dict(result.functions)}")
    assert result.problems == () and result.drc_problems == () and result.gerber_problems == ()
    assert dict(result.functions) == lc.expected_functions(copper)
    assert run(f"build-layers-{copper}-t{target}") == "absent"
    assert run(f"build-layers-gerbers-{copper}-t{target}") == "equal"


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("copper", lc.FIXTURE_COUNTS)
def test_fixture_is_the_filled_board(copper: int) -> None:
    """The committed fixture is the board that this run filled; ``FENOLITE_PROBES_WRITE=1`` writes it."""
    filled = lc.layer_run(copper, 9).filled_board
    assert filled
    path = lc.fixture(copper)
    if os.environ.get(WRITE_VARIABLE) == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(filled, encoding="utf-8")
    assert path.is_file(), f"run with {WRITE_VARIABLE}=1 to write {path.name}"
    assert path.read_text(encoding="utf-8") == filled


@pytest.mark.parametrize("copper", lc.FIXTURE_COUNTS)
def test_filled_fixture_on_kicad_9(copper: int) -> None:
    """Scenario "Filled fixtures on KiCad 9": DRC and Gerbers of the boards that 10.0 filled."""
    if major() != 9:
        pytest.skip("the 9.0 half: 10.0 runs the whole loop in test_layers_build_fill_check_export")
    result = lc.fixture_run(copper)
    print(f"n={copper}: {result}")
    assert result.loaded and result.violations == 0 and result.unconnected == 0
    assert result.gerbers == tuple(sorted(lc.copper_names(copper)))
    assert run(f"build-layers-{copper}-t9") == "absent"
    assert run(f"build-layers-gerbers-{copper}-t9") == "equal"
