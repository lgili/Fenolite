# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The lint of grammar families (change c0263, "Fields and code attributes", "Prefix-free fields",
scenarios "A field without a placeholder" and "An ambiguous field")."""

from __future__ import annotations

import pytest
from _grammars import FILM_R, MLCC, THIN_R, authored, edited

from fenolite.pick.grammar.codes import ISSUE_CODES
from fenolite.pick.grammar.lint import lint_family, prefix_pairs
from fenolite.pick.grammar.schema import parse_family


def codes(found: list) -> list[str]:  # type: ignore[type-arg]
    return [item.code for item in found]


def test_the_authored_grammars_are_clean() -> None:
    for family in authored():
        assert lint_family(family) == [], family.id


def test_a_field_without_a_placeholder() -> None:
    """Scenario "A field without a placeholder" (the command's exit code is in test_family_cmd.py)."""
    family = edited(
        MLCC, "[fields.packing]", '[fields.grade]\ncodes.A = { packing = "tray" }\n\n[fields.packing]'
    )
    found = lint_family(family)
    assert codes(found) == ["family.pattern-field"] and "grade" in found[0].message


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("{packing}", "{packing}{grade}", "{grade} names no field"),
        ("{packing}", "{packing}{size}", "appears 2 times"),
    ],
)
def test_pattern_problems(old: str, new: str, fragment: str) -> None:
    found = [item for item in lint_family(edited(MLCC, old, new)) if item.code == "family.pattern-field"]
    assert found and any(fragment in item.message for item in found), [item.message for item in found]


def test_two_value_fields() -> None:
    text = MLCC.read_text(encoding="utf-8").replace("{packing}", "{packing}{extra}", 1)
    text = text.replace("[[valid]]", '[fields.extra]\nscheme = "rkm"\nunit = "pF"\n\n[[valid]]', 1)
    found = lint_family(parse_family(text, file="x.toml"))
    assert [item.message for item in found if item.code == "family.pattern-field"] == [
        "Example:EX_MLCC: 2 value fields (value, extra); exactly one field has a scheme"
    ]


def test_an_ambiguous_field() -> None:
    """Scenario "An ambiguous field"."""
    family = edited(MLCC, 'codes."05" = { case = "0805"', 'codes."0" = { case = "0805"')
    found = [item for item in lint_family(family) if item.code == "family.ambiguous-code"]
    assert len(found) == 1 and "size" in found[0].message and "code 0 " in found[0].message
    assert "03" in found[0].message


def test_an_rkm_domain_that_is_not_prefix_free() -> None:
    family = edited(FILM_R, 'value = { min = "1.5k", max = "680k" }', 'value = { min = "1k", max = "680k" }')
    found = [item for item in lint_family(family) if item.code == "family.ambiguous-code"]
    assert found and "1K is a proper prefix of 1K5" in found[0].message


def test_prefix_pairs() -> None:
    assert prefix_pairs(["03", "0", "05", "1", "10K", "100K"]) == [
        ("0", "03"),
        ("0", "05"),
        ("1", "100K"),
        ("1", "10K"),
    ]


def test_matrix_codes_values_prefer_and_sources() -> None:
    assert codes(lint_family(edited(MLCC, 'tolerance = ["K", "J"]', 'tolerance = ["K", "Q"]'))) == [
        "family.matrix-unknown-code"
    ]
    assert codes(lint_family(edited(MLCC, 'size = "03"\nvoltage = "B"', 'size = "07"\nvoltage = "B"'))) == [
        "family.matrix-unknown-code"
    ]
    found = lint_family(edited(THIN_R, 'max = "976k"', 'max = "10M"'))
    assert codes(found) == ["family.value-unencodable"] and "10MΩ" in found[0].message
    assert codes(lint_family(edited(MLCC, 'prefer = "T"\n', ""))) == ["family.prefer-missing"]
    assert codes(lint_family(edited(MLCC, 'prefer = "T"', 'prefer = "Q"'))) == ["family.prefer-missing"]
    found = lint_family(
        edited(THIN_R, 'power = ["EXT series datasheet rev A, table 1 (illustrative)"]\n', "")
    )
    assert codes(found) == ["family.source-missing"] and "power" in found[0].message
    assert codes(lint_family(edited(MLCC, 'sources = ["EX series', 'sources = [] # ["EX series'))) == [
        "family.source-missing", "family.source-missing", "family.source-missing"
    ]  # fmt: skip


def test_an_empty_row_is_a_warning() -> None:
    found = lint_family(
        edited(MLCC, 'value = { min = "10pF", max = "1nF" }', 'value = { min = "11pF", max = "11.5pF" }')
    )
    assert codes(found) == ["family.matrix-empty-row"] and found[0].severity == "warning"


def test_every_lint_code_is_registered() -> None:
    assert {code for code in ISSUE_CODES if code.startswith("family.")} == set(ISSUE_CODES)
