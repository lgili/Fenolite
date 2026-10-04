# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes first (c0022 Decision 1; hypotheses H-K-PLACE-MOVE and H-K-PLACE-TOUCH), run before the placement
code relies on them: a footprint moved by ``move_footprint`` is read by ``kicad-cli`` at the requested
placement with its pad nets, and KiCad decides whether courtyards that only touch overlap. Fallbacks: a
move probe that records ``different`` makes ``move_footprint`` refuse rotation and side changes (design
Decision 4); ``placement.legality.TOUCHING_OVERLAPS`` follows the touch outcome (Decision 6)."""

from __future__ import annotations

import _placecases as pc
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", sorted(pc.MOVES))
def test_move(case: str) -> None:
    assert pc.move_problems(case, pc.major()) == []
    assert run(f"place-move-{case}") == "equal"


def test_touch() -> None:
    hits = pc.touch_hits()
    assert hits is not None
    assert {label: count for label, count in hits.items() if label.startswith("control")} == {
        "control top": 1,
        "control bottom": 1,
    }
    outcome = run("place-touch")
    assert outcome in ("absent", "present"), hits
    touching = {label: count for label, count in hits.items() if not label.startswith("control")}
    assert set(touching) == {"edge top", "corner top", "edge bottom", "corner bottom"}
    assert all(count == (1 if outcome == "present" else 0) for count in touching.values()), hits
