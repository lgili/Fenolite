# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exclusion profiles (capability design-equivalence, "Exclusion lists")."""

from __future__ import annotations

import dataclasses

import _cases
import pytest

from fenolite.checks.equivalence import (
    Difference,
    Excluded,
    LevelResult,
    Profile,
    Rule,
    compare_designs,
    difference_issues,
    load_profiles,
    select_profile,
)
from fenolite.checks.equivalence.exclusions import apply_rules
from fenolite.core.errors import FormatError

RULE = """
[[profile.rule]]
id = "names"
level = 3
kind = "footprint-name"
where = "R*"
attribution = "importer"
reason = "the converter renames footprints"
hypothesis = "H-G-EQ-FPNAME"
"""
HEAD = """schema = 1
[[profile]]
name = "p"
tool = "some-tool"
tool_version = "10.0"
frame = "relative"
tolerance_nm = 10
tolerance_udeg = 0
"""
PAD_SIZE_AT_1 = HEAD + RULE.replace('kind = "footprint-name"', 'kind = "pad-size"').replace(
    "level = 3", "level = 1"
)
NON_NEGATIVE = "profile 'p': tolerance_nm is a non-negative integer"


def _rule(**changes: object) -> Rule:
    base = Rule(
        "names", 3, "footprint-name", "R*", "importer", "the converter renames footprints", "H-G-EQ-FPNAME"
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


def test_file_loads() -> None:
    second = (
        '[[profile.rule]]\nid = "v"\nlevel = 1\nkind = "value"\nwhere = "*"\nattribution = "undecided"\n'
        'reason = "r"\nhypothesis = "H-G-EQ-VALUE"\nfield = "value"\ncorpus = ["row-1", "row-2"]\n'
    )
    (profile,) = load_profiles(HEAD + RULE + second, file="x.toml")
    assert profile == Profile(
        "p", "some-tool", "10.0", "relative", 10, 0,
        (_rule(), Rule("v", 1, "value", "*", "undecided", "r", "H-G-EQ-VALUE", "value", ("row-1", "row-2"))),
    )  # fmt: skip
    assert load_profiles("schema = 1\n") == ()
    assert load_profiles(HEAD)[0].rules == ()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            HEAD + RULE.replace("level = 3", "level = 1"),
            "x.toml: rule 'names' of profile 'p': 'footprint-name' is",
        ),
        (PAD_SIZE_AT_1, "rule 'names'.*'pad-size' is not a kind of level 1"),
        (HEAD + RULE + RULE, "rule 'names'.*the id is used twice"),
        (HEAD + RULE + 'colour = "red"\n', "rule 'names'.*unknown key colour"),
        (HEAD + RULE.replace('hypothesis = "H-G-EQ-FPNAME"\n', ""), "rule 'names'.*missing hypothesis"),
        (
            HEAD + RULE.replace('"importer"', '"me"'),
            "rule 'names'.*attribution is one of importer, undecided",
        ),
        (HEAD + RULE + 'field = "size"\n', "rule 'names'.*'footprint-name' has no field 'size'"),
        (HEAD + RULE + 'corpus = "row"\n', "rule 'names'.*corpus is a list"),
        (HEAD + RULE.replace("level = 3", "level = 3.0"), "rule 'names'.*level is a non-negative integer"),
        (HEAD + RULE.replace('where = "R*"', 'where = ""'), "rule 'names'.*where is a non-empty string"),
        (
            HEAD.replace('frame = "relative"', 'frame = "turned"'),
            "profile 'p': frame is one of absolute, relative",
        ),
        (HEAD.replace("tolerance_nm = 10", "tolerance_nm = -1"), NON_NEGATIVE),
        (HEAD.replace("tolerance_nm = 10", "tolerance_nm = 1.5"), NON_NEGATIVE),
        (HEAD.replace('tool = "some-tool"\n', ""), "profile 'p': missing tool"),
        (HEAD + "extra = 1\n", "profile 'p': unknown key extra"),
        (HEAD.replace("schema = 1", "schema = 2"), "x.toml: schema must be 1"),
        (HEAD.replace("schema = 1\n", ""), "schema must be 1"),
        (HEAD + "[other]\n", "unknown key other"),
        ("schema = 1\nprofile = 3\n", "profile is an array of tables"),
        ("schema = 1\nprofile = [3]\n", "profile is an array of tables"),
        ("schema = ", "x.toml: not a TOML document"),
    ],
)
def test_malformed_file(text: str, message: str) -> None:
    with pytest.raises(FormatError, match=message) as caught:
        load_profiles(text, file="x.toml")
    assert caught.value.file == "x.toml"


def test_version_prefix() -> None:
    profiles = tuple(
        Profile(name, "t", version, "relative", 0, 0)
        for name, version in (("kicad-import", "10"), ("kicad-import", "10.0"), ("other", "10.0.6"))
    )
    assert select_profile(profiles, "kicad-import", "10.0.6") is profiles[1]
    assert select_profile(profiles, "kicad-import", "10.0") is profiles[1]
    assert select_profile(profiles, "kicad-import", "10.1.0") is profiles[0]
    assert select_profile(profiles, "kicad-import", "10.01") is profiles[0]
    assert select_profile(profiles, "kicad-import", "11.0.0") is None
    assert select_profile(profiles, "kicad-import", "100.0") is None
    assert select_profile(profiles, "missing", "10.0.6") is None
    assert select_profile(profiles, "other", "10.0.6") is profiles[2]


def test_rule_excludes_and_reports() -> None:
    parts = [("R1", "1k"), ("R2", "1k")]
    pads = {"R1": [_cases.pad("1")], "R2": [_cases.pad("1")]}
    a = _cases.design(parts, pads, name="a")
    b = _cases.placed(
        _cases.with_component(_cases.design(parts, pads, name="b"), "R2", value="2k2"), "R1", lib_ref="L:X"
    )
    assert [(d.level, d.kind, d.where) for d in compare_designs(a, b, level=4).differences] == [
        (1, "value", "R2"), (3, "footprint-name", "R1"),
    ]  # fmt: skip
    report = compare_designs(a, b, level=4, rules=(_rule(),))
    assert report.levels[2].differences == ()
    assert report.levels[2].excluded == (
        Excluded(Difference(3, "footprint-name", "R1", "lib_ref", "FP_R1", "X"), "names", _rule().reason),
    )
    assert [(d.kind, d.where) for d in report.levels[0].differences] == [("value", "R2")]
    assert not report.equivalent
    issues = difference_issues(report)
    assert [(i.code, i.severity, i.where) for i in issues] == [
        ("equiv.value", "error", "R2"), ("equiv.excluded", "info", ""),
    ]  # fmt: skip
    assert issues[1].message == "rule names excludes 1 difference(s): the converter renames footprints"
    both = compare_designs(a, b, level=4, rules=(_rule(), _rule(id="v", level=1, kind="value", where="R2")))
    assert both.equivalent and len(both.excluded) == 2 and both.differences == ()


def test_rule_matching() -> None:
    found = Difference(3, "pad-size", "U1-12", "size", "1x2", "1x3")
    assert _rule(kind="pad-size", where="U1-*").matches(found)
    assert _rule(kind="pad-size", where="U1-*", field="size").matches(found)
    assert not _rule(kind="pad-size", where="u1-*").matches(found)  # the glob keeps the letter case
    assert not _rule(kind="pad-size", where="U2-*").matches(found)
    assert not _rule(kind="pad-drill", where="*").matches(found)
    assert not _rule(kind="pad-size", where="*", level=4).matches(found)
    assert not _rule(kind="pad-size", where="*", field="drill").matches(found)


def test_first_rule_wins_and_a_rule_stops_no_comparison() -> None:
    one = Difference(3, "pad-size", "U1-1", "size", "1x2", "1x3")
    two = Difference(3, "pad-drill", "U1-1", "drill", "", "5")
    result = LevelResult(3, 1, (two, one))
    first, second = (
        _rule(id="first", kind="pad-size", where="U1-*"),
        _rule(id="second", kind="pad-size", where="*"),
    )
    applied = apply_rules(result, (first, second))
    assert applied.differences == (two,) and [e.rule_id for e in applied.excluded] == ["first"]
    assert apply_rules(result, (second, first)).excluded[0].rule_id == "second"
    assert apply_rules(result, ()) == result
