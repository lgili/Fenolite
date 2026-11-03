# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The cross-job gate rejects missing, stale and incomplete evidence (c0347)."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("verify_drawn_floor", ROOT / "tools/verify_drawn_floor.py")
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def authored_reports(tmp_path):
    manifest = tmp_path / "manifest.toml"
    original_sha, upgraded_sha = "1" * 64, "2" * 64
    manifest.write_text(f'''[[file]]
id = "authored-floor"
sha256 = "{original_sha}"
uses = ["sch-old", "origin:kicad-demos"]
''')
    signature = {
        "pins": 2,
        "groups": 1,
        "pins_sha256": "3" * 64,
        "partition_sha256": "4" * 64,
        "named_sha256": "5" * 64,
    }
    context = {
        "owner_id": "authored-floor",
        "owner_sha256": original_sha,
        "errors": [],
        "target_instances": 1,
        "instances": [{"input_id": "authored-floor", "input_sha256": original_sha}],
    }
    inputs = [{"id": "authored-floor", "relative": "authored.kicad_sch", "sha256": original_sha}]
    old = {
        "schema": "fenolite.drawn-floor.v0",
        "id": "authored-floor",
        "code_commit": "authored-code",
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "major": 9,
        "native_version": "9.0.9",
        "originals_unchanged": True,
        "original": {
            "status": "refused",
            "expectation": "original-reader-floor",
            "refusal": {"code": "FEN-3003"},
            "input_sha256": original_sha,
        },
        "inputs": inputs,
        "context": context,
        "status": "original/refused",
        "upgrade_capability": False,
        "original_native": signature,
    }
    new = copy.deepcopy(old)
    comparison = {
        "equal": True,
        "naming_equal": True,
        "name_differences": 0,
        "native_only_pins": 0,
        "drawn_unlisted_pins": 0,
    }
    new.update(
        major=10,
        native_version="10.0.6",
        status="upgraded/equal",
        upgrade_capability=True,
        upgraded_native=dict(signature),
        upgrades=[
            {
                "relative": "authored.kicad_sch",
                "tool": "kicad-cli",
                "tool_version": "10.0.6",
                "from_version": 20230121,
                "to_version": 20260306,
                "sha256_before": original_sha,
                "sha256_after": upgraded_sha,
            }
        ],
        upgraded_census={
            "status": "equal",
            "inputs": [{"id": "authored-floor", "sha256": upgraded_sha}],
            **{name: dict(comparison) for name in bridge.COMPARISONS},
        },
    )
    return manifest, [old, new]


def test_complete_authored_same_commit_bridge_passes(tmp_path) -> None:
    manifest, records = authored_reports(tmp_path)
    (tmp_path / "drawn-floor.json").write_text(json.dumps(records))
    assert bridge.verify(tmp_path, manifest, "authored-code") == 1


@pytest.mark.parametrize(
    "defect",
    [
        "missing-row",
        "missing-major",
        "commit",
        "manifest",
        "original",
        "input",
        "context",
        "native-pin",
        "partition",
        "name",
        "missing-signature",
        "incomplete-census",
        "missing-comparison",
        "naming",
        "missing-upgrade",
        "upgrade-digest",
        "upgrade-tool",
        "upgraded-output",
        "duplicate-owner",
    ],
)
def test_planted_cross_job_failures_refuse(defect: str, tmp_path) -> None:
    manifest, records = authored_reports(tmp_path)
    old, new = records
    if defect == "missing-row":
        records.clear()
    elif defect == "missing-major":
        records.pop()
    elif defect == "commit":
        new["code_commit"] = "other-code"
    elif defect == "manifest":
        old["manifest_sha256"] = "wrong"
    elif defect == "original":
        old["originals_unchanged"] = False
    elif defect == "input":
        new["inputs"][0]["sha256"] = "0" * 64
    elif defect == "context":
        old["context"]["instances"][0]["input_sha256"] = "0" * 64
    elif defect in {"native-pin", "partition", "name"}:
        field = {"native-pin": "pins_sha256", "partition": "partition_sha256", "name": "named_sha256"}[defect]
        old["original_native"][field] = "0" * 64
    elif defect == "missing-signature":
        del old["original_native"]["pins_sha256"]
    elif defect == "incomplete-census":
        new["upgraded_census"]["status"] = "refused"
    elif defect == "missing-comparison":
        del new["upgraded_census"]["lowered_native_partition"]
    elif defect == "naming":
        new["upgraded_census"]["lowered_native_partition"]["name_differences"] = 1
    elif defect == "missing-upgrade":
        new["upgrades"].clear()
    elif defect == "upgrade-digest":
        new["upgrades"][0]["sha256_before"] = "0" * 64
    elif defect == "upgrade-tool":
        new["upgrades"][0]["tool_version"] = "other"
    elif defect == "upgraded-output":
        new["upgraded_census"]["inputs"][0]["sha256"] = "0" * 64
    elif defect == "duplicate-owner":
        records.append(copy.deepcopy(old))
    (tmp_path / "drawn-floor.json").write_text(json.dumps(records))
    with pytest.raises(ValueError):
        bridge.verify(tmp_path, manifest, "authored-code")


def test_ci_keeps_both_failed_artifacts_and_requires_the_complete_bridge() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "needs: [kicad-9, kicad-10]" in workflow
    assert "--uses rt0 --uses sch --uses libs" in workflow
    for major in (9, 10):
        assert f"name: drawn-floor-kicad-{major}" in workflow
    assert workflow.count("path: /tmp/**/drawn-floor.json") == 2
    command = 'tools/verify_drawn_floor.py --reports /tmp/drawn-floor-evidence --commit "$GITHUB_SHA"'
    assert command in workflow
    assert 'test "$NATIVE_NINE_RESULT" = success' in workflow
    assert 'test "$NATIVE_TEN_RESULT" = success' in workflow
