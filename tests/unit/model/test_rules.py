# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import _schema
import pytest

from fenolite.core.errors import FormatError
from fenolite.core.ids import new_id
from fenolite.model import Design, Rule, RuleSubject, Selector, canonical
from fenolite.model.rules import HeightLimit, PadSelection, ProximityRule, RuleSet

PWR_TRACK = RuleSubject(item_kind="track", net="PWR_3V3", netclass="power", ref=None, layer="F.Cu")
SIG_VIA = RuleSubject(item_kind="via", net="SDA", netclass="default", ref=None, layer="B.Cu")
U1_PAD = RuleSubject(item_kind="pad", net="GND", netclass="default", ref="U1", layer="F.Cu")


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (Selector("all"), (True, True, True)),
        (Selector("net", "PWR_*"), (True, False, False)),
        (Selector("netclass", "default"), (False, True, True)),
        (Selector("ref", "U*"), (False, False, True)),
        (Selector("layer", "B.Cu"), (False, True, False)),
        (Selector("item_kind", "via"), (False, True, False)),
        (
            Selector("and", items=(Selector("layer", "F.Cu"), Selector("item_kind", "pad"))),
            (False, False, True),
        ),
        (Selector("or", items=(Selector("net", "SDA"), Selector("net", "GND"))), (False, True, True)),
        (Selector("not", items=(Selector("item_kind", "track"),)), (False, True, True)),
    ],
)
def test_selector_truth_table(selector: Selector, expected: tuple[bool, bool, bool]) -> None:
    assert tuple(selector.matches(s) for s in (PWR_TRACK, SIG_VIA, U1_PAD)) == expected


@pytest.mark.parametrize(
    "build",
    [
        lambda: Selector("and", items=(Selector("all"),)),
        lambda: Selector("not"),
        lambda: Selector("net"),
        lambda: Selector("all", items=(Selector("all"), Selector("all"))),
    ],
)
def test_invalid_selectors(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


def test_rule_fields() -> None:
    rule = Rule(
        id=new_id("rul", random.Random(1)),
        name="hv",
        kind="clearance",
        selector_a=Selector("netclass", "mains"),
        selector_b=Selector("netclass", "isolated_lv"),
        min=2_500_000,
        priority=1,
    )
    assert rule.severity == "error" and rule.min == 2_500_000


# ------------------------------------------------------------------ proximity rules (change c0113)

RST = "rst_00000000-0000-4000-8000-000000000001"


def _dec7() -> ProximityRule:
    return ProximityRule("dec7", (PadSelection("C5", "1"),), (PadSelection("U1", "7"),), 2_000_000)


def test_proximity_rules_round_trip(tmp_path: Path) -> None:
    design = Design.new("prox", seed=7)
    assert design.rules is not None
    design = dataclasses.replace(design, rules=dataclasses.replace(design.rules, proximity=(_dec7(),)))
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.rules is not None
    assert loaded.rules.proximity == (_dec7(),)
    data = json.loads((tmp_path / "rules.json").read_text(encoding="utf-8"))
    assert data["proximity"] == [
        {
            "name": "dec7",
            "parts": [{"path": "C5", "number": "1"}],
            "anchor": [{"path": "U1", "number": "7"}],
            "within": 2000000,
        }
    ]
    assert _schema.validate(data, _schema.load("fenolite.model.v0/rules.json")) == []


def test_proximity_selection_with_index_round_trips() -> None:
    rule = ProximityRule("k", (PadSelection("ch1/U1", "A1", 0),), (PadSelection("U2"),), 1, "warning")
    assert canonical.loads(canonical.dumps(rule), ProximityRule) == rule


def test_rules_file_of_an_older_build_loads_and_keeps_its_bytes() -> None:
    older = '{\n  "id": "' + RST + '"\n}\n'
    loaded = canonical.loads(older, RuleSet)
    assert loaded.proximity == ()
    assert _schema.validate(json.loads(older), _schema.load("fenolite.model.v0/rules.json")) == []
    assert canonical.dumps(loaded) == older


def test_rule_set_without_proximity_is_written_without_the_key() -> None:
    assert "proximity" not in canonical.dumps(RuleSet(id=RST))


@pytest.mark.parametrize(
    "build",
    [
        lambda: ProximityRule("r", (), (PadSelection("U1"),), 1),
        lambda: ProximityRule("r", (PadSelection("C1"),), (), 1),
        lambda: ProximityRule("r", (PadSelection("C1"),), (PadSelection("U1"),), 0),
        lambda: ProximityRule("r", (PadSelection("C1"),), (PadSelection("U1"),), -5),
        lambda: ProximityRule("", (PadSelection("C1"),), (PadSelection("U1"),), 1),
        lambda: PadSelection("U1", index=0),
        lambda: PadSelection("U1", "1", -1),
        lambda: PadSelection(""),
        lambda: RuleSet(id=RST, proximity=(_dec7(), _dec7())),
    ],
)
def test_refused_proximity_values(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


def test_refused_proximity_value_in_a_file_is_a_format_error() -> None:
    text = (
        '{"id": "'
        + RST
        + '", "proximity": [{"name": "r", "parts": [], "anchor": [{"path": "U1"}], "within": 1}]}'
    )
    with pytest.raises(FormatError):
        canonical.loads(text, RuleSet)


def test_proximity_compatibility_is_documented() -> None:
    text = (Path(__file__).resolve().parents[3] / "docs" / "design-model.md").read_text(encoding="utf-8")
    section = text.split("## Proximity rules", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(section.split())
    assert "`PadSelection(" in flat and "`ProximityRule(" in flat and "`proximity`" in flat
    assert "0.2.x and 0.3.0 cannot read a `rules.json` that carries `proximity`" in flat


# ------------------------------------------------------------------ height limits (change c0140)


def test_height_limits_round_trip(tmp_path: Path) -> None:
    design = Design.new("heights", seed=7)
    assert design.rules is not None
    limits = (HeightLimit("FAN", 12_000_000), HeightLimit("LID", 5_000_000, "warning"))
    design = dataclasses.replace(design, rules=dataclasses.replace(design.rules, heights=limits))
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.rules is not None
    assert loaded.rules.heights == limits
    data = json.loads((tmp_path / "rules.json").read_text(encoding="utf-8"))
    assert data["heights"] == [
        {"area": "FAN", "max": 12000000},
        {"area": "LID", "max": 5000000, "severity": "warning"},
    ]
    assert _schema.validate(data, _schema.load("fenolite.model.v0/rules.json")) == []


def test_rules_file_of_an_older_build_has_no_height_limit() -> None:
    older = '{\n  "id": "' + RST + '"\n}\n'
    loaded = canonical.loads(older, RuleSet)
    assert loaded.heights == ()
    assert canonical.dumps(loaded) == older
    assert "heights" not in canonical.dumps(RuleSet(id=RST))


@pytest.mark.parametrize(
    "build",
    [
        lambda: HeightLimit("LID", 0),
        lambda: HeightLimit("LID", -1),
        lambda: HeightLimit("", 1_000_000),
        lambda: HeightLimit("LID", 1_000_000, "ignore"),  # type: ignore[arg-type]
        lambda: RuleSet(id=RST, heights=(HeightLimit("LID", 1), HeightLimit("LID", 2))),
    ],
)
def test_refused_height_values(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


def test_height_compatibility_is_documented() -> None:
    text = (Path(__file__).resolve().parents[3] / "docs" / "design-model.md").read_text(encoding="utf-8")
    section = text.split("## Height limits", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(section.split())
    assert "`HeightLimit(" in flat and "`heights`" in flat
    assert "0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`" in flat
