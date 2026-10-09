# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An outline change on the running ``kicad-cli`` (capability kicad-oracle, "Outline and layer changes pass
the oracle"; layout-lens, "Outline changes across rebuilds"; change c0102): a routed board rebuilt on a
narrower outline is one that KiCad accepts. KiCad 10 only, where the whole loop runs."""

from __future__ import annotations

import pytest
from _probes import run

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_rebuild_outline_keeps_what_fits() -> None:
    assert run("rebuild-outline") == "absent", "a board adapted to a new outline fails in KiCad"
