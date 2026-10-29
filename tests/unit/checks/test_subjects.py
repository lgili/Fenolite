# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Finding identities, aligned with their issues (c0256)."""

import pytest

from fenolite.checks.stages import StageResult
from fenolite.checks.subjects import SUBJECT_KINDS, Subject
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence


def test_misaligned_subjects_refused_and_empty_accepted():
    issues = (Issue("length.out-of-range", "error", "long"),) * 2
    subject = Subject("net", "net_test", "SIGNAL")
    with pytest.raises(ValueError, match="aligned"):
        StageResult("length.rules", "errors", Evidence(), issues, subjects=((subject,),))
    assert StageResult("length.rules", "errors", Evidence(), issues).subjects == ()
    assert StageResult("length.rules", "errors", Evidence(), issues, subjects=((subject,), ())).subjects


def test_misaligned_closed_kinds_and_identity_required():
    assert SUBJECT_KINDS == (
        "component",
        "pin",
        "pad",
        "net",
        "netclass",
        "interface",
        "track",
        "arc",
        "via",
        "zone",
        "rule_area",
        "rule",
    )
    with pytest.raises(ValueError, match="kind"):
        Subject("footprint", "fp_test", "R1")
    with pytest.raises(ValueError, match="id"):
        Subject("net", "", "SIGNAL")
    assert Subject("net", "net_test", "SIGNAL").to_json() == {
        "kind": "net",
        "id": "net_test",
        "name": "SIGNAL",
    }


def test_subjects_length_and_envelope_indices():
    from dataclasses import replace

    from fenolite.checks.stages import CheckReport
    from fenolite.checks.subjects import for_issues
    from fenolite.cli.cmd_check import subject_rows
    from fenolite.model.circuit import Net
    from fenolite.model.design import Design

    design = Design.new("subjects", seed=0)
    design = replace(
        design,
        circuit=replace(design.circuit, nets=(Net(id="net_p", name="SK_P"), Net(id="net_n", name="SK_N"))),
    )
    item = Issue("length.skew-out-of-range", "error", "net SK_N against SK_P at 12 mm", where="SK_N")
    subjects = for_issues(design, (item,))
    assert {s.name for s in subjects[0]} == {"SK_P", "SK_N"}
    stage = StageResult("length.rules", "errors", Evidence(), (item,), subjects=subjects)
    first = Issue("check.cache-unreadable", "warning", "cache")
    report = CheckReport((stage,), (first, item), Evidence())
    assert subject_rows(report) == [{"issue": 1, "items": [s.to_json() for s in subjects[0]]}]
