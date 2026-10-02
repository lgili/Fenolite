# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board-setup minimums bench without KiCad (capability kicad-oracle, "Board-setup minimums are
proved by kicad-cli", scenario "Canary missing"; change c0026)."""

from __future__ import annotations

import json
from typing import cast

import _minimum_bench as mb
import pytest

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.pro import MINIMUM_POINTER
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.errors import Issue
from fenolite.model.design import Design

DESIGN = mb.bench_design(target=10)


def report(*violations: tuple[str, tuple[str, ...]]) -> DrcReport:
    """An authored report text with one violation per ``(type, uuids)``, read with read_drc_report."""
    items = [
        {
            "type": kind,
            "description": "authored",
            "severity": "error",
            "items": [{"uuid": u, "description": "item", "pos": {"x": 1, "y": 2}} for u in uuids],
        }
        for kind, uuids in violations
    ]
    text = json.dumps(
        {
            "source": "bench.kicad_pcb",
            "date": "2026-10-02",
            "kicad_version": "10.0.6",
            "violations": items,
            "unconnected_items": [],
            "schematic_parity": [],
            "coordinate_units": "mm",
        }
    )
    return read_drc_report(text)


CANARY = ("clearance", mb.pair_uuids(DESIGN, mb.CANARY))
HV = ("clearance", mb.pair_uuids(DESIGN, mb.HV))
EVERY_ITEM = tuple((mb.VIOLATION_TYPES[k], mb.item_uuids(DESIGN, k)) for k in mb.KINDS)


def test_items() -> None:
    assert [len(mb.item_uuids(DESIGN, k)) for k in mb.KINDS] == [2, 1, 1, 1, 1]
    uuids = [u for k in mb.KINDS for u in mb.item_uuids(DESIGN, k)]
    assert len(set(uuids)) == len(uuids)


@pytest.mark.parametrize("kind", mb.KINDS)
def test_each_kind_present_and_absent(kind: str) -> None:
    own = (mb.VIOLATION_TYPES[kind], mb.item_uuids(DESIGN, kind))
    assert mb.judge_item(report(CANARY, own), kind=kind, design=DESIGN) == "present"
    assert mb.judge_item(report(CANARY), kind=kind, design=DESIGN) == "absent"
    other = ("track_dangling", mb.item_uuids(DESIGN, kind)[:1])
    assert mb.judge_item(report(CANARY, other), kind=kind, design=DESIGN) == "absent"


def test_clearance_needs_the_pair() -> None:
    half = ("clearance", mb.item_uuids(DESIGN, "clearance")[:1])
    assert mb.judge_item(report(CANARY, half), kind="clearance", design=DESIGN) == "absent"


def test_hv_row() -> None:
    assert mb.judge_class(report(CANARY, HV), design=DESIGN) == "present"
    assert mb.judge_class(report(CANARY), design=DESIGN) == "absent"


def test_canary_missing() -> None:
    every = report(*EVERY_ITEM, HV)
    for kind in mb.KINDS:
        assert mb.judge_item(every, kind=kind, design=DESIGN) == "inconclusive"
    assert mb.judge_class(every, design=DESIGN) == "inconclusive"
    assert mb.judge_item(None, kind="clearance", design=DESIGN) == "inconclusive"
    with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
        mb.assert_loaded("inconclusive", "rules-lowered")
    mb.assert_loaded("present", "rules-lowered")


@pytest.mark.parametrize("target", [9, 10])
def test_bench_written(target: int) -> None:
    issues: list[Issue] = []
    files = write_triad(DESIGN, name="bench", target=target, issues=issues)
    rules = cast(JsonObject, _json.get(_json.loads(files["bench.kicad_pro"]), MINIMUM_POINTER))
    assert {k: cast(JsonNumber, rules[k]).text for k in mb.KEYS_LOWERED} == dict(mb.KEYS_LOWERED)
    floor = [i for i in issues if i.code == "kicad.project.below-floor"]
    assert len(floor) == 1 and "'Default'" in floor[0].message
    assert "A.NetName == 'CANARY_A'" in files["bench.kicad_dru"]


@pytest.mark.parametrize("run", mb.RUNS)
def test_run_files(run: str) -> None:
    files = mb.run_files(run, 10)
    rules = cast(JsonObject, _json.get(_json.loads(files["bench.kicad_pro"]), MINIMUM_POINTER))
    keys = {k: cast(JsonNumber, rules[k]).text for k in mb.KEYS_LOWERED}
    if run == "keys-lowered" or run == "rules-lowered":
        assert keys == dict(mb.KEYS_LOWERED)
    else:
        assert keys == mb.template_keys(10) and keys["min_clearance"] == mb.RAISED_CLEARANCE
    assert ("fenolite_0_fab_clearance" in files["bench.kicad_dru"]) == run.startswith("rules")


def test_design_type() -> None:
    assert isinstance(DESIGN, Design) and DESIGN.rules is not None and len(DESIGN.rules.rules) == 6
