# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A zone on the box of a board with arcs and cut-outs, refilled by KiCad 10 (capability kicad-oracle,
"Outline shapes and holes pass the oracle"; hypothesis H-K-ZONE-BOX; change c0102). KiCad 9.0 has no
``--refill-zones``, so this fact is measured on 10.0 only."""

from __future__ import annotations

import _outlinebench as ob
import pytest
from _probes import run

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_zone_box_fill() -> None:
    assert run("zone-box-fill") == "absent", "the fill of a zone on the box leaves the board"
    # the same board built from a script, its zone declared without an outline
    assert ob.zone_box_fill("script") == "absent", "the board built from the script differs"
