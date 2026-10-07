# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas in the DSL (capability design-dsl, "Rule areas in the DSL"; change c0103)."""

from __future__ import annotations

import pytest

from fenolite import dsl
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, RuleArea, mm, to_model
from fenolite.dsl import items as itemlib
from fenolite.model import canonical

ANT = [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(10)), (mm(40), mm(10))]
HV = [(mm(0), mm(0)), (mm(20), mm(0)), (mm(20), mm(30))]


def design(copper: int = 2) -> Design:
    made = Design("areas")
    made.board(mm(50), mm(30), copper=copper)
    return made


def test_antenna_keep_out_in_the_model() -> None:
    """Scenario "Antenna keep-out in the model"."""
    d = design()
    area = d.rule_area("ANT", ANT, forbid=("tracks", "vias", "pours"))
    assert isinstance(area, RuleArea) and area is d.rule_areas["ANT"]
    assert area.outline[0] == (40_000_000, 0) and area.layers == ("F.Cu", "B.Cu")
    board = to_model(d).board
    assert board is not None
    (keepout,) = board.keepouts
    assert keepout.id == derived_id("kpo", "dsl", "area:ANT") and keepout.name == "ANT"
    assert keepout.layers == ("F.Cu", "B.Cu")
    assert [(p.x, p.y) for p in keepout.outline] == [
        (140_000_000, 100_000_000), (150_000_000, 100_000_000), (150_000_000, 110_000_000),
        (140_000_000, 110_000_000),
    ]  # fmt: skip
    assert (keepout.no_tracks, keepout.no_vias, keepout.no_copper_pour) == (True, True, True)
    assert (keepout.no_pads, keepout.no_footprints) == (False, False)


def test_area_for_rules_only() -> None:
    """Scenario "Area for rules only"."""
    d = design()
    hv = d.rule_area("HV", HV, layers=("F.Cu",))
    (keepout,) = to_model(d).board.keepouts  # type: ignore[union-attr]
    assert keepout.layers == ("F.Cu",) and hv.name == "HV" and hv.forbid == ()
    settings = (keepout.no_tracks, keepout.no_vias, keepout.no_pads, keepout.no_copper_pour,
                keepout.no_footprints)  # fmt: skip
    assert settings == (False,) * 5


def test_layers_default_to_every_copper_layer() -> None:
    d = design(copper=4)
    assert d.rule_area("A", ANT).layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    assert d.rule_area("B", ANT, layers=("In2.Cu", "F.Cu"), forbid=("pads",)).layers == ("In2.Cu", "F.Cu")


def test_refused_calls() -> None:
    """Scenario "Refused calls": each names its argument and records nothing."""
    bare = Design("areas")
    with pytest.raises(DslError, match=r"board\(\)"):
        bare.rule_area("HV", HV)
    d = design()
    d.rule_area("HV", HV)
    calls = (
        (lambda: d.rule_area("H V", HV), "name"),
        (lambda: d.rule_area("A", HV[:2]), "outline"),
        (lambda: d.rule_area("B", HV, layers=("In1.Cu",)), "In1.Cu"),
        (lambda: d.rule_area("C", HV, forbid=("silkscreen",)), "silkscreen"),  # not "footprints": c0113
        (lambda: d.rule_area("hv", HV), "hv"),
        (lambda: d.rule_area("HV", HV), "HV"),
        (lambda: d.rule_area("D", HV, layers=()), "layers"),
        (lambda: d.rule_area("E", HV, layers=("F.Cu", "F.Cu")), "twice"),
        (lambda: d.rule_area("F", HV, forbid=("vias", "vias")), "twice"),
        (lambda: d.rule_area("G", HV, forbid="vias"), "forbid"),  # type: ignore[arg-type]
        (lambda: d.rule_area("H*", HV), "name"),
        (lambda: d.rule_area("I", [(mm(0), mm(0)), (mm(1), 2), (mm(1), mm(1))]), "outline"),
    )
    for call, word in calls:
        with pytest.raises(DslError, match=word):
            call()
    assert list(d.rule_areas) == ["HV"] and bare.rule_areas == {}


def test_call_order_does_not_matter() -> None:
    """Scenario "Call order does not matter"."""
    texts = []
    for order in (("ANT", "HV"), ("HV", "ANT")):
        d = design()
        for name in order:
            d.rule_area(name, ANT if name == "ANT" else HV, forbid=("tracks",) if name == "ANT" else ())
        assert list(d.rule_areas) == list(order)
        texts.append(canonical.dump_texts(to_model(d))["board.json"])
        assert [k.name for k in to_model(d).board.keepouts] == ["ANT", "HV"]  # type: ignore[union-attr]
    assert texts[0] == texts[1]


def test_tables_of_the_items_module() -> None:
    assert dict(itemlib.FORBID) == {
        "tracks": "no_tracks", "vias": "no_vias", "pads": "no_pads", "pours": "no_copper_pour",
        "footprints": "no_footprints",  # change c0113
    }  # fmt: skip
    assert dsl.RuleArea is itemlib.RuleArea and "RuleArea" in dsl.__all__
    assert not hasattr(Design, "keepout")
