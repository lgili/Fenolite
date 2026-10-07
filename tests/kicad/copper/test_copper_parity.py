# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``check_copper`` against ``kicad-cli pcb drc`` on authored benches (``H-K-COPPER-SHAPES``,
``H-K-COPPER-RESOLVE``, ``H-K-COPPER-ZONES``; capability kicad-oracle, "Copper verdict parity canaries";
change c0029), and on fills whose zone has a clearance of its own (``H-K-COPPER-ZONECLR``; "Zone clearance
parity canaries"; change c0068).

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


@pytest.mark.parametrize("case", cp.ZONE_CASES)
def test_zone_clearance_parity(case: str) -> None:
    """Scenario "Zone clearance parity on both majors" (and "Rule below the zone clearance")."""
    spec = cp.ZONE_CASES[case]
    found = cp.compared(spec.bench, (cp.zone_group(case),))
    assert len(found) == 3 * len(spec.kinds) and _differences(found) == []
    assert [kicad for _, kicad, _ in found] == ["clearance", "clean", "clean"] * len(spec.kinds)
    assert run(f"copper-zoneclr-{case}") == "equal"


def test_fill_fill_recorded() -> None:
    """Scenario "Two fills are recorded, not compared"."""
    assert run("copper-fill-fill") in ("present", "absent")


# --- net-tie rows (capability kicad-oracle, "Net-tie parity canaries"; change c0114) ---------------


def test_net_tie_parity_of_grouped_pads() -> None:
    """Scenario "Parity of grouped pads": KiCad and ``check_copper`` give the same verdict for the pads of
    one group, and for the same pads without a group."""
    import _tiebench as tb

    target = tb.running_target()
    found = {
        label: (tb.kicad_pad_verdict(label), tb.fenolite_verdict(target, label)) for label in tb.COMPARED
    }
    assert all(kicad == ours for kicad, ours in found.values()), found
    assert found["touching"] == ("clean", "clean") and found["touching-plain"] == ("short", "short")
    assert found["close-plain"] == ("clearance", "clearance")
    assert run("copper-nettie-group") == "equal"


def test_net_tie_parity_of_ungrouped_pads_is_recorded() -> None:
    """The documented difference: between two pads of a net-tie footprint that share no group
    ``check_copper`` reports one finding and KiCad none. Recorded, never a failure."""
    import _tiebench as tb

    target = tb.running_target()
    for label, found in tb.RECORDED.items():
        assert tb.pad_findings(target, label) == [found], label
    assert run("copper-nettie-ungrouped") in ("equal", "different")
