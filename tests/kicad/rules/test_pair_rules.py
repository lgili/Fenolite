# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pair and length rule kinds and the pair selector in KiCad (capability kicad-oracle, "Differential
pair rules are enforced by kicad-cli"; hypotheses H-K-DRU-PAIR and H-K-DRU-PAIRSEL; change c0104).

Every bench carries the canary scoped to its own net; a report without it fails with "rules file not
loaded". ``tests/kicad/test_probe_results.py`` pins every outcome per version, and
``rulemap.KIND_SUPPORT`` and ``SELECTOR_SUPPORT`` follow the recorded outcomes
(``tests/unit/backends/kicad/test_rulemap_pairs.py``)."""

from __future__ import annotations

import _pairbench as pb
import _rulebench as rb
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("kind", pb.PAIR_KINDS)
def test_pair_kind(kind: str) -> None:
    """Scenario "Pair kinds on both majors": the probed rows have the DRC type of the kind, the control
    rows have none."""
    result = pb.kinds()
    rb.require_canary(result.report, result.bench)
    probed, controls = pb.KIND_ROWS[kind]
    for row in probed:
        assert pb.reported(result, row, kind), f"{kind}: row {row} is not reported"
    for row in controls:
        assert not pb.reported(result, row, kind), f"{kind}: the control row {row} is reported"
    assert run(f"dru-kind-{kind}") == "present"


@pytest.mark.parametrize("case", sorted(pb.CASES))
def test_pair_case(case: str) -> None:
    """``opt`` is accepted and never checked, a layer clause selects its layer, a gap rule needs nets that
    pair by name, parallel tracks count as coupled at any distance, and a skew within pairs does not
    compare two pairs."""
    result = pb.kinds()
    rb.require_canary(result.report, result.bench)
    _, _, expected = pb.CASES[case]
    assert run(f"dru-pair-{case}") == ("present" if expected else "absent")


@pytest.mark.parametrize("kind", ["diff_pair_gap", "length"])
def test_later_rule_governs(kind: str) -> None:
    for direction in ("forward", "reverse"):
        result = pb.order(direction)
        rb.require_canary(result.report, result.bench)
    name = "gap" if kind == "diff_pair_gap" else "length"
    assert run(f"dru-pair-order-{name}") == "present"


@pytest.mark.parametrize("case", sorted(pb.SELECTED))
def test_select_by_base(case: str) -> None:
    """The base with its ``_`` and without it select the pair; a base in lower case selects nothing."""
    result = pb.kinds()
    rb.require_canary(result.report, result.bench)
    row, expected = pb.SELECTED[case]
    assert pb.reported(result, row, "diff_pair_gap") is expected
    assert run(f"dru-pair-sel-{case}") == ("present" if expected else "absent")


def test_select_every_pair() -> None:
    result = pb.scope()
    rb.require_canary(result.report, result.bench)
    assert pb.reported(result, "SP", "diff_pair_gap") and not pb.reported(result, "SQ", "diff_pair_gap")
    assert run("dru-pair-sel-star") == "present"


def test_select_both_sides_of_a_clearance() -> None:
    """A clearance rule with the pair on both sides, after a board-wide clearance rule, sets the clearance
    inside that pair; the pair without such a rule is reported."""
    result = pb.scope()
    rb.require_canary(result.report, result.bench)
    assert not result.between("YA", pb.CLEARANCE) and result.between("YB", pb.CLEARANCE)
    assert run("dru-pair-sel-both-sides") == "present"
