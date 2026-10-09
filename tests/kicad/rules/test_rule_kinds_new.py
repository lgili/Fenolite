# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The six rule kinds of change c0071 in KiCad (capability kicad-oracle, "New rule kinds are enforced by
kicad-cli"; hypotheses H-K-DRU-KIND-2 and H-K-DRU-COURTYARD). One bench holds a probed and a control item
for five kinds; creepage runs on the slot bench of the board analyses. Every bench carries the canary
scoped to its own net, and a run without the canary violation fails."""

from __future__ import annotations

import _creepbench
import _kindcases as kc
import _rulebench as rb
import pytest
from _probes import major, run

from fenolite.backends.kicad.lowering import lower_rules
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleSet, Selector

pytestmark = pytest.mark.needs_kicad
CREEPAGE_MAJORS = frozenset({10})
"""The majors on which ``kicad-cli`` reports a creepage violation on the slot bench (9.0.9 reports none)."""


@pytest.mark.parametrize("kind", kc.NEW_KINDS)
def test_new_kind(kind: str) -> None:
    if kind == "creepage":
        for report, bench in kc.creepage_runs():
            assert report is not None and _creepbench.canary_fired(report, bench), "rules file not loaded"
        expected = "present" if major() in CREEPAGE_MAJORS else "absent"
        assert run("dru-kind-creepage") == expected
        return
    result = kc.board_kinds()
    rb.require_canary(result.report, result.bench)
    assert kc.flagged(result, kind, "probe"), f"{kind}: the probed item has no violation of the kind"
    assert not kc.flagged(result, kind, "control"), f"{kind}: the control item has a violation of the kind"
    assert run(f"dru-kind-{kind}") == "present"


def test_no_tracks_rule() -> None:
    """A ``no_tracks`` rule written by ``lower_rules`` gives one ``items_not_allowed`` for the track of its
    net on its layer, and none for that net's track on another layer or another net's track on its layer
    (capability kicad-oracle, "Plane routing passes the oracle"; ``H-K-DRU-NOTRACKS``, change c0107)."""
    result = kc.no_tracks()
    report = rb.require_canary(result.report, result.bench)
    assert "(constraint disallow track)" in kc.no_tracks_rules()
    probe, other_layer, other_net = (result.bench.uuids(label) for label in kc.NO_TRACKS_LABELS)
    found = [v for v in report.violations if v.type in kc.NO_TRACKS_TYPES]
    assert len(found) == 1 and {i.uuid for i in found[0].items} & set(probe), found
    assert other_layer and other_net
    for label in kc.NO_TRACKS_LABELS[1:]:
        assert not result.of(label, kc.NO_TRACKS_TYPES), (
            f"the control track {label} is reported as not allowed"
        )
    assert run("dru-kind-no_tracks") == "present"


def test_courtyard_selection() -> None:
    by_reference, by_member = kc.courtyard("reference"), kc.courtyard("member")
    for result in (by_reference, by_member):
        rb.require_canary(result.report, result.bench)
    types = kc.VIOLATION_TYPES["courtyard_clearance"]
    assert by_reference.between("cy", types), "A.Reference does not select the footprint"
    assert not by_member.between("cy", types), "A.memberOfFootprint selects the footprint after all"
    assert run("dru-courtyard-reference") == "present" and run("dru-courtyard-member") == "absent"


def test_bench_rules_are_what_the_writer_gives() -> None:
    """The rule texts of the benches equal the lowering of the model rules they stand for."""
    made = {
        "hole_to_hole": Selector("net", "HH_A"),
        "hole_clearance": Selector("net", "HC_V"),
        "annular_width": Selector("net", "AW"),
        "courtyard_clearance": Selector("ref", "CY1"),
        "silk_clearance": Selector("all"),
    }
    rules = tuple(
        Rule(id=derived_id("rul", "oracle", kind), name=kind, kind=kind, selector_a=made[kind], min=minimum)  # type: ignore[arg-type]
        for kind, _, minimum in kc.BOARD_RULES
    )
    lowered = lower_rules(RuleSet(id=derived_id("rst", "oracle", "kinds"), rules=rules), target=10).text
    # the writer orders equal priorities by name; the bench lists the kinds in its own order
    assert sorted(rb.with_scoped_canary(lowered).split("(rule ")) == sorted(kc.board_rules().split("(rule "))
    creepage = Rule(
        id=derived_id("rul", "oracle", "creepage"),
        name="creepage",
        kind="creepage",
        selector_a=Selector("net", "A"),
        selector_b=Selector("net", "B"),
        min=11_050_000,
    )
    text = lower_rules(RuleSet(id=derived_id("rst", "oracle", "creep"), rules=(creepage,)), target=10).text
    condition = "A.NetName == 'A' && B.NetName == 'B'"
    assert text == "(version 1)\n" + kc.rule_text("fenolite_0_creepage", "creepage", 11_050_000, condition)


def test_scoped_canary_is_the_canary_with_a_condition() -> None:
    plain, scoped = rb.canary_rule(), rb.scoped_canary_rule()
    assert scoped.replace("\t(condition \"A.NetName == 'CANARY_A'\")\n", "") == plain
    assert rb.with_scoped_canary("(version 1)\n(rule x)\n").index("(rule canary") < len("(version 1)\n") + 1
