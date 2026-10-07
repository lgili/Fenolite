# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net lengths as KiCad counts them (capability kicad-oracle, "Net length parity canaries"; hypotheses
H-K-NETLEN-TOTAL, H-K-NETLEN-STACKUP, H-K-NETLEN-RULES, and H-K-NETLEN-VIA10 on 10.0.x or H-K-NETLEN-VIA9
on 9.0.x; change c0106).

Each case of ``tests/_lengthbench.py`` is judged from the JSON report of ``pcb drc`` only, with ``T`` taken
from ``length_facts`` for the running major. A run whose scoped canary does not fire fails. The printed
``actual`` values are shown with ``-rA`` and kept in ``docs/evidence/length.md``.

The rules cases compare KiCad's violations with the nets ``H-K-NETLEN-RULES`` predicts. The stage
``length.rules`` joins them once change c0104 gives the model the length and skew rule kinds; until then
the ``length-rules-*`` probes are not registered.
"""

from __future__ import annotations

import _lengthbench as lb
import _lengthcases as lc
import pytest
from _probes import major, run, runner

pytestmark = pytest.mark.needs_kicad
TOTAL_CASES = tuple(case for case in lb.CASES if case not in (*lb.VIA_CASES, "rules"))
VIA_CASES = ("four", "four-explicit", "six", "eight")
DEFAULT_CASES = ("two", "four", "six", "eight")


def _show(found: lc.Bracket) -> None:
    low = found.reported(found.below)
    for net in sorted(found.totals):
        print(f"{found.case} {major()} {net}: total {found.totals[net]} nm, actual {low.get(net, '-')} mm")


def _require(found: lc.Bracket) -> None:
    if not found.canary:
        pytest.fail("rules file not loaded: the canary violation is absent from a DRC report", pytrace=False)


@pytest.mark.parametrize("case", TOTAL_CASES)
def test_total(case: str) -> None:
    found = lc.bracket(runner(), case)
    _require(found)
    _show(found)
    assert set(found.reported(found.below)) == set(found.totals), "a net is not reported 1 µm below its total"
    assert not found.reported(found.above), "a net is reported 1 µm above its total"
    assert run(lc.probe_id(case)) == "equal"


@pytest.mark.parametrize("case", VIA_CASES)
def test_via(case: str) -> None:
    found = lc.bracket(runner(), case)
    _require(found)
    _show(found)
    assert set(found.reported(found.below)) == set(found.totals), "a net is not reported 1 µm below its total"
    assert not found.reported(found.above), "a net is reported 1 µm above its total"
    assert run(lc.probe_id(case)) == "equal"


def test_via_the_two_majors_count_a_via_apart() -> None:
    """Scenario "The two majors count a via apart": a through via between ``F.Cu`` and ``In1.Cu`` on the
    explicit stack-up."""
    found = lc.bracket(runner(), "four-explicit")
    _require(found)
    assert found.totals["V_F_IN1"] == (20_153_750 if major() >= 10 else 20_000_000)
    assert found.outcome == "equal"


@pytest.mark.parametrize("case", DEFAULT_CASES)
def test_default_stackup(case: str) -> None:
    """``H-K-NETLEN-STACKUP``: a file without a stack-up is counted on 35 µm copper and equal dielectrics."""
    found = lc.bracket(runner(), case)
    _require(found)
    assert found.facts.stackup == "default"
    assert any(length.vias for length in found.facts.nets.values())
    assert found.outcome == "equal"


def test_via_unprojected_node() -> None:
    """A stack-up node without its silkscreen and paste rows, which the reader projects no stack-up from
    (design, Risks). The probe records whether KiCad counts the node's thicknesses for its vias: ``equal``
    on 10.0.6, where the default stack-up would be wrong. So the facts claim no depth for such a board."""
    node = lc.bracket(runner(), "four-unprojected", "four-explicit")
    _require(node)
    _show(node)
    own = lc.facts_of("four-unprojected", major())
    assert own.stackup == "none" and not own.depths
    assert run(lc.probe_id("four-unprojected")) in ("equal", "different")
    if major() >= 10:
        assert run(lc.probe_id("four-unprojected")) == "equal"


@pytest.mark.parametrize("case", sorted(lb.RULES_TEXTS))
def test_rules(case: str) -> None:
    """``H-K-NETLEN-RULES``: the nets KiCad reports for a length or a skew rule."""
    canary, pairs, texts = lc.rules_run(runner(), case)
    if not canary:
        pytest.fail(
            "rules file not loaded: the canary violation is absent from the DRC report", pytrace=False
        )
    for text in texts:
        print(f"{case} {major()}: {text}")
    assert pairs == lb.RULES_EXPECTED[case]
