# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad conditions of the leaves ``zone``, ``hole`` and ``pad_type`` (change c0462, task 3.2; S-2213;
capability kicad-file-backend, "Zone, hole and pad-type conditions"). They are written only for a major whose
``dru-cond-<key>`` probe is recorded ``present`` (10.0.6); on another major a rule that uses one is a reported
loss."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad.rulemap import condition_text, hole_condition, parse_condition
from fenolite.model.rules import Rule, Selector


def _rule(selector: Selector) -> Rule:
    return Rule(id="rul_x", name="r", kind="clearance", selector_a=selector, min=200_000)


@pytest.fixture
def proved(monkeypatch: pytest.MonkeyPatch) -> None:
    """As if the three probes were recorded ``present`` on both majors."""
    support = dict(rulemap.SELECTOR_SUPPORT)
    support.update(dict.fromkeys(rulemap.LEAF_KEYS_C0462, frozenset({9, 10})))
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", MappingProxyType(support))


@pytest.mark.parametrize(
    ("selector", "text"),
    [
        (Selector("zone", "GND_Top"), "A.Name == 'GND_Top'"),
        (Selector("pad_type", "smd"), "A.Pad_Type == 'SMD'"),
        (Selector("pad_type", "th"), "A.Pad_Type == 'Through-hole'"),
        (Selector("pad_type", "npth"), "A.Pad_Type == 'NPTH, mechanical'"),
        (
            Selector("hole", "300000..1000000"),
            "((A.Type == 'Via' && A.Hole >= 0.3mm && A.Hole <= 1mm) || "
            "(A.Type == 'Pad' && A.Hole_Size_X >= 0.3mm && A.Hole_Size_X <= 1mm))",
        ),
        (
            Selector("hole", "..900000"),
            "((A.Type == 'Via' && A.Hole > 0mm && A.Hole <= 0.9mm) || "
            "(A.Type == 'Pad' && A.Hole_Size_X > 0mm && A.Hole_Size_X <= 0.9mm))",
        ),
        (
            Selector("hole", "1000001.."),
            "((A.Type == 'Via' && A.Hole >= 1.000001mm) || (A.Type == 'Pad' && A.Hole_Size_X >= 1.000001mm))",
        ),
    ],
)
def test_written_and_read_back(proved: None, selector: Selector, text: str) -> None:
    written, issues = condition_text(_rule(selector), target=10)
    assert (written, issues) == (text, ())
    assert parse_condition(text) == (selector, None)


def test_a_leaf_in_a_larger_condition(proved: None) -> None:
    selector = Selector("and", items=(Selector("pad_type", "th"), Selector("hole", "..800000")))
    written, issues = condition_text(_rule(selector), target=9)
    assert not issues and written is not None
    assert parse_condition(written) == (selector, None)


def test_the_shipped_table_holds_10_alone() -> None:
    """The three probes are recorded ``present`` on 10.0.6 and not yet run on 9.0.9."""
    assert {key: rulemap.SELECTOR_SUPPORT[key] for key in rulemap.LEAF_KEYS_C0462} == dict.fromkeys(
        rulemap.LEAF_KEYS_C0462, frozenset({10})
    )


def test_unproved_leaves_are_losses() -> None:
    """On a major without the probe: a rule with a new leaf is not written."""
    for selector in (Selector("zone", "Z"), Selector("hole", "1.."), Selector("pad_type", "smd")):
        written, issues = condition_text(_rule(selector), target=9)
        assert [issue.code for issue in issues] == ["rules.unsupported-selector"]
        assert "not proved" in issues[0].message


def test_a_kicad_rule_with_an_unproved_leaf_stays_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no major proved, a KiCad rule with a new leaf is not lifted; with one proved, it is."""
    outside = rulemap._outside_kind("clearance", Selector("zone", "Z"), None, ())  # pyright: ignore[reportPrivateUsage]
    assert outside is None
    support = {
        key: value for key, value in rulemap.SELECTOR_SUPPORT.items() if key not in rulemap.LEAF_KEYS_C0462
    }
    monkeypatch.setattr(rulemap, "SELECTOR_SUPPORT", MappingProxyType(support))
    outside = rulemap._outside_kind("clearance", Selector("zone", "Z"), None, ())  # pyright: ignore[reportPrivateUsage]
    assert outside is not None and "no probe" in outside


@pytest.mark.parametrize(
    "text",
    [
        "A.Hole >= 0.3mm",
        "(A.Type == 'Via' && A.Hole >= 0.3mm) || (A.Type == 'Pad' && A.Hole_Size_X >= 0.4mm)",
        "(A.Type == 'Pad' && A.Hole_Size_X >= 0.3mm) || (A.Type == 'Via' && A.Hole >= 0.3mm)",
        "(A.Type == 'Via' && A.Hole > 0mm) || (A.Type == 'Pad' && A.Hole_Size_X > 0mm)",
        "(A.Type == 'Via' && A.Hole_Size_X >= 0.3mm) || (A.Type == 'Pad' && A.Hole_Size_X >= 0.3mm)",
        "A.Pad_Type == 'Edge connector'",
        "A.Hole == 0.3mm",
    ],
)
def test_outside_the_written_forms(text: str) -> None:
    assert parse_condition(text) is None


def test_hole_condition_needs_a_bound() -> None:
    with pytest.raises(ValueError, match="hole"):
        hole_condition("A", "..")
