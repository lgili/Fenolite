# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check_copper`` against ``kicad-cli pcb drc`` on authored benches (``H-K-COPPER-SHAPES``,
``H-K-COPPER-RESOLVE``, ``H-K-COPPER-ZONES``; capability kicad-oracle, "Copper verdict parity canaries";
change c0029).

Each bench runs once per session; a report without the canary violation fails with "rules file not
loaded". ``tests/kicad/test_probe_results.py`` pins every outcome per version.
"""

from __future__ import annotations

import _copperparity as cp
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def _differences(rows: list[tuple[cp.Row, str, str]]) -> list[str]:
    return [
        f"{row.group} at {row.gap} nm: KiCad {kicad}, Fenolite {ours}"
        for row, kicad, ours in rows
        if kicad != ours
    ]


@pytest.mark.parametrize("kind", cp.KINDS)
def test_parity_per_pair_kind(kind: str) -> None:
    """Scenario "Parity on both majors": every row of the kind agrees under the three clearance sources."""
    found = [entry for source in cp.SOURCES for entry in cp.compared(source, (kind,))]
    assert len(found) == len(cp.SOURCES) * (2 if kind == "arc-track" else 3)
    assert _differences(found) == []
    assert {kicad for _, kicad, _ in found} == {"clearance", "clean"}  # the rows tell the two apart
    assert run(f"copper-parity-{kind}") == "equal"


@pytest.mark.parametrize("source", ["class", "floor"])
def test_parity_of_the_class_and_floor_sources(source: str) -> None:
    """The benches written through the triad path: the class clearance, and the board minimum above the
    classes, give ``c``."""
    found = cp.compared(source, cp.KINDS)
    assert len(found) == 20 and _differences(found) == []


@pytest.mark.parametrize("case", cp.RESOLVE)
def test_resolve(case: str) -> None:
    """Scenario "Rule below the class value" and the five other resolution rows."""
    source = "floor" if case == "floor-above-rule" else "class"
    found = cp.compared(source, (case,))
    assert found and _differences(found) == []
    assert {kicad for _, kicad, _ in found} == {"clearance", "clean"}
    assert run(f"copper-resolve-{case}") == "equal"


def test_fill_parity() -> None:
    """Zone fills are judged as stored, on a target-10 board whose zone clearance is 0 (10.0 only)."""
    if major() < 10:
        pytest.skip("fill parity is proved on kicad-cli 10 with a target-10 board")
    found = cp.compared("rule", (cp.FILL,))
    assert len(found) == 3 and _differences(found) == []
    assert run(f"copper-parity-{cp.FILL}") == "equal"


def test_parity_zone_overlap_recorded() -> None:
    if major() < 10:
        pytest.skip("the zone bench is written for target 10")
    assert run("copper-zone-overlap") in ("present", "absent")


@pytest.mark.parametrize("name", cp.BOUNDARY)
def test_parity_boundary_recorded(name: str) -> None:
    """KiCad may apply a tolerance at the boundary; Fenolite stays strict and reports both rows."""
    ((row, _, ours),) = cp.compared("rule", (f"boundary-{name}",))
    assert ours == "clearance" and row.gap < cp.CLEARANCE["rule"]
    assert run(f"copper-boundary-{name}") in ("present", "absent")
