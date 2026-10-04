# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The synthetic rules node and its text (capability kicad-version-gating)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.kicad import tree_equal
from fenolite.backends.kicad.versions import FileKind, kind_of, rules_text, wrap_rules
from fenolite.core.errors import FormatError

CANARY = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "data"
    / "kicad"
    / "tokens"
    / "canary"
    / "canary.kicad_dru"
)


def test_several_top_level_lists() -> None:
    node = wrap_rules("(version 1)\n(rule a (constraint clearance (min 3mm)))\n")
    assert node.name == "kicad_dru" and [c.name for c in node.nodes()] == ["version", "rule"]
    assert kind_of(node) == FileKind.RULES


def test_comment_line_refused() -> None:
    text = "(version 1)\n  # keep HV apart\n(rule a (constraint clearance (min 3mm)))\n"
    with pytest.raises(FormatError, match="line 2") as info:
        wrap_rules(text, file="b.kicad_dru")
    assert info.value.file == "b.kicad_dru" and "rules reader" in info.value.message


def test_single_quoted_name_refused() -> None:
    with pytest.raises(FormatError, match="rules reader"):
        wrap_rules("(version 1)\n(rule 'big one' (constraint clearance (min 1mm)))\n")


def test_double_quoted_condition_accepted() -> None:
    node = wrap_rules(
        "(version 1)\n(rule a (constraint clearance (min 1mm)) (condition \"A.NetName == 'X'\"))\n"
    )
    assert node.nodes("rule")[0].find("condition") is not None


def test_offsets_refer_to_the_rules_text() -> None:
    text = "(version 1)\n(rule a (constraint clearance (min 3mm)))\n"
    node = wrap_rules(text)
    assert node.nodes("rule")[0].offset == text.index("(rule")
    with pytest.raises(FormatError) as info:
        wrap_rules("(version 1)\n(rule a\n")
    assert info.value.offset is not None and info.value.offset <= len("(version 1)\n(rule a\n")


def test_printing_without_the_wrapper() -> None:
    node = wrap_rules("(version 1) (rule a (constraint clearance (min 3mm)))")
    text = rules_text(node)
    assert "kicad_dru" not in text and text.endswith("\n")
    assert text.startswith("(version 1)\n(rule a\n")
    assert tree_equal(wrap_rules(text), node)


def test_canary_round_trip() -> None:
    node = wrap_rules(CANARY.read_text(encoding="utf-8"), file=str(CANARY))
    again = wrap_rules(rules_text(node))
    assert tree_equal(again, node) and "kicad_dru" not in rules_text(node)
