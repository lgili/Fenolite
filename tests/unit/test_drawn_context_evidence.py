# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable drawn-context observations are exact reports, never accepted corpus baselines (c0276)."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence"


def test_observations_preserve_history_and_bind_every_declared_input() -> None:
    assert hashlib.sha256((EVIDENCE / "drawn-schematic.json").read_bytes()).hexdigest() == (
        "101950108297d7094bfc2aa5a74581586b53cae224576307f68b5531e54938af"
    )
    manifest = ROOT / "tests/corpus/manifest.toml"
    declared = {row["id"]: row for row in tomllib.loads(manifest.read_text(encoding="utf-8"))["file"]}
    expected = {
        ident
        for ident, row in declared.items()
        if "sch" in row["uses"] and "origin:kicad-demos" in row["uses"]
    }
    record = json.loads((EVIDENCE / "drawn-context.json").read_text(encoding="utf-8"))
    assert record["schema"] == "fenolite.drawn-corpus-measurement.v0"
    old, current = record["observations"]
    assert old["code_commit"] == "695dee0f1bdf2cff066edad0220c63cf064ae0a2"
    assert current["code_commit"] == "ce3b999244af8e6a246f9457289ef6b5023bba05"
    assert old["guard_context_classification_code_commit"] == current["code_commit"]
    for observation in (old, current):
        rows = observation["rows"]
        assert len(rows) == len(expected) == len({r["id"] for r in rows}) == 130
        assert {r["id"] for r in rows} == expected
        assert observation["statuses"] == Counter(r["status"] for r in rows)
        assert not observation["required_ci_passed"] and not observation["evidence_promoted"]
        for row in rows:
            assert row["code_commit"] == observation["code_commit"]
            assert row["native_version"] == "9.0.2"
            assert row["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
            assert row["input_sha256"] == row["expected_sha256"] == declared[row["id"]]["sha256"]
    audit = current["cache_input_sha256_audit"]
    assert Counter(i["use"] for i in audit) == {"sch": 132, "project": 54}
    assert all(i["matches"] and i["input_sha256"] == declared[i["id"]]["sha256"] for i in audit)
    assert current["exit_code"] == old["exit_code"] == 1
    assert current["retained_cad_files"] == 0


def test_context_maps_retain_all_instances_refusals_and_names_without_cad_payload() -> None:
    raw = (EVIDENCE / "drawn-context.json").read_text(encoding="utf-8")
    current = json.loads(raw)["observations"][1]
    cases = [case for row in current["rows"] for case in row.get("contexts", [])]
    assert len(cases) == current["compatible_rows"] == 92
    assert len({case["context"]["owner_id"] for case in cases}) == 36
    refusals = Counter(
        (c["refusal"]["stage"], c["refusal"]["type"]) for c in cases if c["status"] == "refused"
    )
    assert refusals == {("read", "UnsupportedFormatError"): 5, ("source-symbols", "FormatError"): 36}
    assert current["source_naming_difference_rows"] == 21
    for row in current["rows"]:
        for case in row.get("contexts", []):
            context = case["context"]
            assert context["owner_id"] == context["native_export_root_id"]
            assert (
                context["target_instances"]
                == sum(i["input_id"] == row["id"] for i in context["instances"])
                > 0
            )
            paths = [i["instance_path_sha256"] for i in context["instances"]]
            assert len(paths) == len(set(paths)) and all(re.fullmatch(r"[0-9a-f]{64}", p) for p in paths)
            if context["scope"] == "registered-project":
                project = context["project_input"]
                assert project["input_sha256"] == project["expected_sha256"]
            if case["status"] == "equal":
                assert all(
                    case[k]["equal"] for k in ("partition", "lowered_partition", "lowered_native_partition")
                )
    assert "(kicad_sch" not in raw and "(symbol" not in raw and "/workspace/" not in raw
    tasks = (ROOT / "openspec/changes/c0276-drawn-schematic/tasks.md").read_text(encoding="utf-8")
    assert "- [ ] 7.2 " in tasks
