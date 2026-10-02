# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project and rules files are merged (capability layout-lens; change c0019)."""

from __future__ import annotations

import pytest
from _preserve_help import fresh

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.dru import RulesLossError, read_rules
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import FutureFormatError
from fenolite.core.errors import FormatError, Issue
from fenolite.lens.preserve import merge_rules

LOWERED = (
    "(version 1)\n"
    "(rule fenolite_1_pwr (condition \"A.NetClass == 'PWR'\") (constraint clearance (min 0.2mm)))\n"
)


def test_user_rules_follow_fenolites() -> None:
    existing = (
        "(version 1)\n# by hand\n(rule user_gap (constraint clearance (min 0.3mm)))\n"
        "(rule fenolite_old (constraint clearance (min 9mm)))\n"
    )
    text = merge_rules(LOWERED, existing, target=10, file="blink.kicad_dru")
    assert text.index("fenolite_1_pwr") < text.index("# by hand") < text.index("user_gap")
    assert "fenolite_old" not in text and text.count("(version 1)") == 1
    assert [r.name for r in read_rules(text).rules][-1] == "user_gap"
    assert merge_rules(LOWERED, text, target=10) == text


def test_version_2_refused() -> None:
    with pytest.raises(FutureFormatError):
        merge_rules(LOWERED, "(version 2)\n(rule a (constraint clearance (min 1mm)))\n", target=10)


def test_broken_rules_located() -> None:
    with pytest.raises(FormatError) as caught:
        merge_rules(
            LOWERED,
            "(version 1)\n\n(rule 'big one' (constraint clearance (min 1mm)))\n",
            target=10,
            file="b.kicad_dru",
        )
    assert "b.kicad_dru" in str(caught.value)


def test_ten_only_rule_for_target_9() -> None:
    existing = "(version 1)\n(rule mask (constraint bridged_mask))\n"
    with pytest.raises(RulesLossError):
        merge_rules(LOWERED, existing, target=9)
    issues: list[Issue] = []
    text = merge_rules(LOWERED, existing, target=9, allow_lossy=True, issues=issues)
    assert "bridged_mask" not in text and "rules.dropped-for-target" in [i.code for i in issues]


def test_write_triad_keeps_a_user_class() -> None:
    output = fresh()
    data = _json.loads(output.files["blink.kicad_pro"].decode("utf-8"))
    user = dict(data["net_settings"]["classes"][0])
    user["name"] = "USER"
    data["net_settings"]["classes"].append(user)
    texts = write_triad(output.design, name="blink", target=10, existing_project=_json.dumps(data))
    names = [c["name"] for c in _json.loads(texts["blink.kicad_pro"])["net_settings"]["classes"]]
    assert "USER" in names and "PWR" in names
