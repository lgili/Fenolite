# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The flattened Altium panel through KiCad's importer (capability board-panels, "Panel evidence";
hypothesis ``H-A-PANEL-FLAT``; change c0173). The documents are those of ``_panelbench``."""

from __future__ import annotations

import _panelbench as pb
import pytest
from _probes import run

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_flat_panel_imports_at_the_kicad_panel_places() -> None:
    outcome = run("altium-panel-flat")
    details = {}
    if outcome != "equal":
        for name in ("tabs", "mixed"):
            found = pb.flat_import(name)
            if found is not None:
                details[name] = {k: (len(found[0][k]), len(found[1][k])) for k in found[0]}
    assert outcome == "equal", details
