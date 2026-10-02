# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-setup minimums proved by ``kicad-cli`` (capability kicad-oracle, "Board-setup minimums are proved
by kicad-cli"; hypotheses H-K-PRO-MIN-KEYS, H-K-PRO-MIN-RULE-2, H-K-PRO-MIN-WRITE and H-K-PRO-MIN-CLASS;
change c0026). Each test asserts the outcome that the shipped tables of ``lowering`` give."""

from __future__ import annotations

import _mincases as mc
import _minimum_bench as mb
import pytest
from _probes import major, run

from fenolite.backends.kicad.lowering import FLOOR_OVER_RULES, MINIMUM_KEYS, RULES_OVER_CLASSES

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


def _outcome(name: str, kind: str, target: int) -> str:
    outcome = run(f"pro-min-{name}-{kind}-t{target}")
    mb.assert_loaded(outcome, f"{name} (target {target})")
    return outcome


def _types(name: str, kind: str, target: int) -> list[str]:
    result = mc.run(name, target)
    return mb.found_types(result.report, result.design, kind) if result.report is not None else []


@pytest.mark.parametrize("target", TARGETS)
def test_keys(target: int) -> None:
    for kind in MINIMUM_KEYS[target]:
        assert _outcome("keys-template", kind, target) == "present", (
            kind,
            _types("keys-template", kind, target),
        )
        assert _outcome("keys-lowered", kind, target) == "absent", (
            kind,
            _types("keys-lowered", kind, target),
        )


@pytest.mark.parametrize("target", TARGETS)
def test_floor_over_rules(target: int) -> None:
    for kind, key in MINIMUM_KEYS[target].items():
        expected = "present" if major() in FLOOR_OVER_RULES[key] else "absent"
        assert _outcome("rules-template", kind, target) == expected, (
            kind,
            _types("rules-template", kind, target),
        )


@pytest.mark.parametrize("target", TARGETS)
def test_written(target: int) -> None:
    for kind in MINIMUM_KEYS[target]:
        assert _outcome("rules-lowered", kind, target) == "absent", (
            kind,
            _types("rules-lowered", kind, target),
        )


@pytest.mark.parametrize("target", TARGETS)
def test_rules_over_classes(target: int) -> None:
    control = run(f"pro-min-class-control-t{target}")
    mb.assert_loaded(control, f"keys-template (target {target})")
    assert control == "present"
    outcome = run(f"pro-min-class-t{target}")
    mb.assert_loaded(outcome, f"rules-lowered (target {target})")
    assert outcome == ("absent" if major() in RULES_OVER_CLASSES else "present")
