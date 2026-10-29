# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project review never turns missing/limited/historical evidence into a pass (c0239)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.core.errors import FormatError
from fenolite.view.project_review import merge, read_report, status

DIGEST = "a" * 64
SCENE = {"meta": {"name": "sample.kicad_pcb", "sha256": DIGEST, "evidence": "INFERRED"}}


def reply(*stages: dict[str, Any], issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "command": "check",
        "issues": issues or [],
        "input": {"path": "sample.kicad_pcb", "sha256": DIGEST},
        "result": {"stages": list(stages)},
    }


def stage(name: str = "drc.kicad", **kwargs: Any) -> dict[str, Any]:
    return {"name": name, "status": "ok", "evidence": {"level": "INFERRED"}, **kwargs}


def cards(check: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return {card["id"]: card for card in status(SCENE, check, **kwargs)["cards"]}


def test_absent_reports_are_not_passes() -> None:
    found = cards()
    assert found.pop("read")["state"] == "passed"
    assert all(item["state"] == "not-run" for item in found.values())


@pytest.mark.parametrize(
    ("extra", "issues", "expected"),
    [
        ({}, [], "passed"),
        ({"status": "skipped", "reason": "no-schematic"}, [], "limited"),
        ({"status": "future-status"}, [], "limited"),
        ({"status": ["ok"]}, [], "limited"),
        ({"status": "errors"}, [], "failed"),
        ({"summary": {"limits": {"clearance": 20}}}, [], "limited"),
        ({"evidence": {}}, [], "limited"),
        ({}, [{"code": "kicad.drc.clearance", "severity": "warning"}], "limited"),
        ({}, [{"code": "kicad.drc.clearance", "severity": "error"}], "failed"),
    ],
)
def test_stage_states(extra: dict[str, Any], issues: list[dict[str, Any]], expected: str) -> None:
    found = cards(reply(stage(**extra), issues=issues))["drc"]
    assert found["state"] == expected
    assert found["stages"][0]["evidence"] == ("UNKNOWN" if extra.get("evidence") == {} else "INFERRED")


def test_partial_category_and_per_stage_evidence() -> None:
    found = cards(reply(stage("parity")))["connectivity"]
    assert found["state"] == "limited" and found["missing"] == ["netlist.assignment_compare"]
    found = cards(reply(stage("parity"), stage("netlist.assignment_compare")))["connectivity"]
    assert found["state"] == "passed"


def test_error_without_a_stage_record_remains_a_failure() -> None:
    found = cards(reply(issues=[{"code": "kicad.drc.short", "severity": "error"}]))["drc"]
    assert found["state"] == "failed" and found["stages"][0]["evidence"] == "UNKNOWN"
    found = cards(reply(issues=[{"code": "kicad.drc.clearance", "severity": "warning"}]))["drc"]
    assert found["state"] == "limited"


@pytest.mark.parametrize(
    "source",
    [{}, {"sha256": "b" * 64, "path": "sample.kicad_pcb"}, {"sha256": DIGEST, "path": "another.kicad_pcb"}],
)
def test_unbound_report_never_passes(source: dict[str, Any]) -> None:
    check = reply(stage()) | {"input": source}
    assert cards(check)["drc"]["state"] == "limited"
    check["issues"] = [{"code": "kicad.drc.short", "severity": "error"}]
    assert cards(check)["drc"]["state"] == "failed"
    assert not status(SCENE, check)["binding"]["matched"]


def test_scope_is_recomputed_after_live_save() -> None:
    check = reply(stage())
    assert cards(check)["drc"]["state"] == "passed"
    changed = {"meta": SCENE["meta"] | {"sha256": "b" * 64}}
    assert next(c for c in status(changed, check)["cards"] if c["id"] == "drc")["state"] == "limited"


def test_convert_and_export_keep_their_limits() -> None:
    converted = {
        "command": "convert",
        "ok": True,
        "input": reply()["input"],
        "issues": [],
        "evidence": {"level": "INFERRED"},
        "receipt": {"files": [{"path": "out"}]},
        "result": {"equivalence": {"unexplained": 0}, "report": {"lossy": False}, "experimental": False},
    }
    assert cards(reports=[read_report(converted)])["convert"]["state"] == "passed"
    dry = converted | {"receipt": None}
    assert cards(reports=[dry])["convert"]["state"] == "limited"
    for changes in ({"equivalence": None}, {"experimental": True}, {"report": {"lossy": True}}):
        item = converted | {"result": converted["result"] | changes}
        assert cards(reports=[item])["convert"]["state"] == "limited"
    exported = converted | {"command": "export", "result": {"artifacts": [{"path": "top.gbr"}]}}
    assert cards(reports=[read_report(exported)])["export"]["state"] == "limited"
    assert "readback" in " ".join(cards(reports=[exported])["export"]["reasons"])
    assert cards(reports=[converted | {"ok": False}])["convert"]["state"] == "failed"


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"command": "check", "result": {}, "issues": [], "ok": True},
        {"command": "export", "result": {}, "issues": []},
        {"command": "convert", "result": {}, "issues": ["bad"], "ok": True},
        {"command": ["convert"], "result": {}, "issues": [], "ok": True},
    ],
)
def test_bad_report_is_refused(data: Any) -> None:
    with pytest.raises(FormatError, match="complete convert or export"):
        read_report(data)


def test_merge_replaces_stages_by_name_and_keeps_each_input() -> None:
    """Scenario "Stages merged by name" (change c0302)."""
    new_digest = "b" * 64
    old = reply(
        stage("model.validate"),
        stage("copper.clearance", status="errors"),
        issues=[
            {"code": "copper.short", "severity": "error", "message": "old short"},
            {"code": "model.dangling", "severity": "info", "message": "kept"},
        ],
    )
    new = reply(stage("copper.clearance"), issues=[{"code": "copper.clearance-unset", "severity": "info"}])
    new["input"] = {"path": "sample.kicad_pcb", "sha256": new_digest}
    merged = merge(old, new)
    names = [s["name"] for s in merged["result"]["stages"]]
    assert names == ["model.validate", "copper.clearance"]
    by_name = {s["name"]: s for s in merged["result"]["stages"]}
    assert by_name["copper.clearance"]["status"] == "ok"
    assert by_name["copper.clearance"]["input"]["sha256"] == new_digest
    assert by_name["model.validate"]["input"]["sha256"] == DIGEST
    assert [i["message"] for i in merged["issues"] if i["code"].startswith("model.")] == ["kept"]
    assert not [i for i in merged["issues"] if i["code"] == "copper.short"]
    scene = {"meta": SCENE["meta"] | {"sha256": new_digest}}
    found = {card["id"]: card for card in status(scene, merged)["cards"]}
    assert found["clearance"]["state"] == "passed"
    assert found["model"]["state"] == "limited"
    assert any("does not match" in r for r in found["model"]["stages"][0]["reasons"])
    first = merge(None, new)
    assert first["result"]["stages"][0]["input"]["sha256"] == new_digest
