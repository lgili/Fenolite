# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Subject identities stay aligned with visible concise and paginated check findings."""

from pathlib import Path

from fenolite import api
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.stages import CheckReport, StageResult
from fenolite.checks.subjects import Subject
from fenolite.cli import cmd_check
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.ids import derived_id


def test_subjects_after_concise_and_pagination(monkeypatch):
    board = Path(__file__).resolve().parents[3] / "tests/data/kicad/board/two_layer.kicad_pcb"
    issues = (
        Issue("length.out-of-range", "warning", "A", where="A"),
        Issue("length.input-missing", "warning", "B", where="B"),
        Issue("length.out-of-range", "warning", "C", where="C"),
    )
    subjects = tuple((Subject("net", derived_id("net", "testing", n), n),) for n in ("A", "B", "C"))
    stage = StageResult("length.rules", "ok", Evidence(), issues, subjects=subjects)
    report = CheckReport((stage,), issues, Evidence())
    checked = cmd_check.Checked(project_set(board), False, report, None)
    monkeypatch.setattr(cmd_check, "run_stages", lambda *a, **kw: checked)
    one = api.run("check", str(board), "--limit", "1")
    assert one.exit_code == 0
    assert one.result["subjects"] == [{"issue": 0, "items": [subjects[0][0].to_json()]}]
    two = api.run("check", str(board), "--limit", "1", "--cursor", one.result["page"]["next"])
    assert two.exit_code == 0
    assert two.result["subjects"] == [{"issue": 0, "items": [subjects[1][0].to_json()]}]
    concise = api.run("check", str(board), "--format", "concise", "--limit", "1")
    assert concise.exit_code == 0
    assert len(concise.envelope["issues"]) == 1
    assert [item["name"] for item in concise.result["subjects"][0]["items"]] == ["A", "C"]
    assert concise.result["subjects"][0]["issue"] == 0
