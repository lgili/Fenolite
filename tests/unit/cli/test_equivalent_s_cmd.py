# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The S CLI result keeps equivalent's wire shape and validates its active schema (c0278)."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import _schema
import pytest
from _checkcli import run
from _equivalent_s import project, remove_one_junction, root

from fenolite.api import equivalent


def test_cli_is_the_same_api_result_and_the_schema_stays_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = project(tmp_path / "original", "hier")
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "equivalent", str(root(original)), str(root(original)), "--level", "S"
    )
    assert code == 0, error
    result = envelope["result"]
    assert result == equivalent(root(original), root(original), level="S").to_json()
    schema = _schema.load("fenolite.equivalent.v0.json")
    assert _schema.validate(result, schema) == []
    for key, value in (("level", "other"), ("extra", 1)):
        assert _schema.validate({**result, key: value}, schema)
    for location, key, value in (("levels", "level", "other"), ("levels", "extra", 1)):
        changed = copy.deepcopy(result)
        changed[location][0][key] = value
        assert _schema.validate(changed, schema)


def test_planted_junction_error_rows_validate_without_accepting_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = project(tmp_path / "original", crossing=True)
    changed = tmp_path / "changed"
    shutil.copytree(original, changed)
    remove_one_junction(changed, critical=True)
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "equivalent", str(original), str(changed), "--level", "S"
    )
    assert code == 5 and not envelope["result"]["equivalent"]
    assert _schema.validate(envelope["result"], _schema.load("fenolite.equivalent.v0.json")) == []
    assert {issue["code"] for issue in envelope["issues"] if issue["severity"] == "error"} == {
        "equiv.drawn-net",
        "equiv.item-missing",
    }
    bad = copy.deepcopy(envelope["result"])
    bad["differences"][0]["kind"] = "unknown-kind"
    assert _schema.validate(bad, _schema.load("fenolite.equivalent.v0.json"))
