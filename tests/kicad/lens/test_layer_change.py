# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A copper count change on the running ``kicad-cli`` (capability kicad-oracle, "Outline and layer changes
pass the oracle"; hypothesis H-K-LAYER-CHANGE; change c0102): what KiCad does with added rows, with items
left on removed rows and with a stale stack-up, and that a board adapted by a rebuild is one it accepts."""

from __future__ import annotations

import _layerbench as lb
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


def test_layer_facts_added_rows() -> None:
    assert run("layers-added") == "absent", "added inner rows give a new DRC finding"


def test_layer_facts_items_left_on_removed_rows() -> None:
    assert run("layers-left-items") == "present", "KiCad accepts items on removed layers"


def test_layer_facts_stale_stackup() -> None:
    assert run("layers-stale-stackup") == "present", "a stale stack-up still gives thicknesses"
    # and a board without a stack-up gets KiCad's default thicknesses
    job = lb.job_file(lb.edited("added"))
    assert job is not None and lb.copper_layers(job) == 6 and lb.thicknesses(job) > 0


@pytest.mark.kicad_min_major(10)
def test_rebuild_layers() -> None:
    assert run("rebuild-layers") == "absent", "a board adapted to a new copper count fails in KiCad"
