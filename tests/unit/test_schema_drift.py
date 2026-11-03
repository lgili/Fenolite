# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Committed JSON Schemas equal what tools/gen_schemas.py generates, and the validator works."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import _schema
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_schemas", ROOT / "tools" / "gen_schemas.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


GEN = _generator()


@pytest.mark.parametrize("target", GEN.TARGETS, ids=lambda t: t.schema_id)
def test_schema_file_matches_generator(target: object) -> None:
    path = ROOT / target.out  # type: ignore[attr-defined]
    assert path.exists(), f"{target.out} missing: run tools/gen_schemas.py"  # type: ignore[attr-defined]
    assert path.read_text(encoding="utf-8") == GEN.render(target), (
        f"{target.out} is stale: run tools/gen_schemas.py"  # type: ignore[attr-defined]
    )


def test_check_mode_passes() -> None:
    assert GEN.main(["--check"]) == 0


def test_validator_rejects_bad_envelopes() -> None:
    schema = _schema.load("fenolite.envelope.v0.json")
    good = {
        "ok": True, "command": "x", "schema": "fenolite.x.v0", "input": None, "result": {},
        "issues": [], "evidence": {"level": "UNVERIFIED", "oracle": None, "hypotheses": []},
        "receipt": None, "elapsed_ms": 0,
    }  # fmt: skip
    assert _schema.validate(good, schema) == []
    assert _schema.validate({**good, "extra": 1}, schema)
    assert _schema.validate({**good, "schema": "x.v0"}, schema)
    assert _schema.validate({**good, "elapsed_ms": -1}, schema)
    bad_issue = {
        "code": "Bad",
        "severity": "error",
        "message": "m",
        "where": "",
        "hint": "",
        "retryable": False,
    }
    assert _schema.validate({**good, "issues": [bad_issue]}, schema)
    assert _schema.validate(
        {**good, "evidence": {"level": "MAYBE", "oracle": None, "hypotheses": []}}, schema
    )
    missing = dict(good)
    del missing["receipt"]
    assert _schema.validate(missing, schema)


def test_error_schema() -> None:
    schema = _schema.load("fenolite.error.v0.json")
    ok = {"code": "FEN-2001", "message": "m", "hint": "h", "retryable": False, "where": ""}
    assert _schema.validate(ok, schema) == []
    assert _schema.validate({**ok, "code": "FEN-8001"}, schema)


def test_library_schema_is_a_target() -> None:
    from fenolite.model.schema import LIBRARY_SCHEMA, SCHEMA_DIR

    name, schema_id, ref = LIBRARY_SCHEMA
    target = next(t for t in GEN.TARGETS if t.schema_id == schema_id)
    assert (target.out, target.ref) == (f"{SCHEMA_DIR}/{name}", ref) and name == "library.json"


def test_library_drift_names_the_file(tmp_path: Path) -> None:
    target = next(t for t in GEN.TARGETS if t.schema_id == "fenolite.library.v0")
    stale = tmp_path / "library.json"
    stale.write_text(GEN.render(target).replace('"pins"', '"pinz"'), encoding="utf-8")
    assert stale.read_text(encoding="utf-8") != GEN.render(target)
    assert target.out.endswith("library.json")


def test_validator_distinguishes_boolean_and_numeric_literals() -> None:
    assert _schema.validate(True, {"enum": [-1, 1]})
    assert _schema.validate(1, {"enum": [True]})
    assert _schema.validate(1, {"const": True})
    assert _schema.validate(True, {"const": True}) == []
    assert _schema.validate(1.0, {"enum": [1]}) == []


def test_result_judge_rejects_removed_rows_and_changed_nested_types():
    from fenolite.cli.results.compatibility import schema_changes

    before = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {"type": "object", "properties": {"quantity": {"type": "integer"}}},
            }
        },
    }
    assert [
        (c.kind, c.path) for c in schema_changes(before, {"type": "object", "properties": {}}, name="bom")
    ] == [("removed", "bom.rows")]
    after = json.loads(json.dumps(before))
    after["properties"]["rows"]["items"]["properties"]["quantity"]["type"] = "string"
    assert [(c.kind, c.path) for c in schema_changes(before, after, name="bom")] == [
        ("type-changed", "bom.rows[].quantity")
    ]


def test_result_judge_allows_additions_and_definition_renames_but_checks_maps():
    from fenolite.cli.results.compatibility import schema_changes

    before = {
        "type": "object",
        "properties": {"named": {"$ref": "#/$defs/Old"}},
        "$defs": {"Old": {"type": "object", "additionalProperties": {"type": "integer"}}},
    }
    after = {
        "type": "object",
        "properties": {"named": {"$ref": "#/$defs/New"}, "added": {"type": "string"}},
        "$defs": {"New": {"type": "object", "additionalProperties": {"type": "integer"}}},
    }
    assert schema_changes(before, after, name="example") == ()
    after["$defs"]["New"]["additionalProperties"]["type"] = "string"
    assert [(c.kind, c.path) for c in schema_changes(before, after, name="example")] == [
        ("type-changed", "example.named.{key}")
    ]


def test_input_judge_rejects_new_required_fields():
    from fenolite.cli.results.compatibility import schema_changes

    before = {"type": "object", "properties": {"existing": {"type": "string"}}}
    after = {**before, "required": ["existing"]}
    assert [(c.kind, c.path) for c in schema_changes(before, after, name="input", input_mode=True)] == [
        ("required-added", "input.existing")
    ]


def test_declared_literals_and_map_value_types_cannot_silently_change():
    from fenolite.cli.results.compatibility import schema_changes

    assert schema_changes({"enum": ["top", "bottom"]}, {"enum": ["top"]}, name="side")
    assert schema_changes({"enum": ["top", "bottom"]}, {"enum": ["bottom", "top"]}, name="side") == ()
    assert schema_changes(
        {"type": "object", "additionalProperties": {"type": "integer"}},
        {"type": "object", "additionalProperties": True},
        name="counts",
    )


def test_release_schema_comparison_is_read_only_and_names_removed_keys(monkeypatch):
    from types import SimpleNamespace

    import fenolite

    tool = _generator()
    target = tool.Target("fenolite.result.bom.v1", "unused", "schemas/fenolite.bom.v1.json", True)
    monkeypatch.setattr(tool, "TARGETS", [target])
    monkeypatch.setattr(fenolite, "__version__", "1.2.0")
    before = {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "string"}}}}
    monkeypatch.setattr(tool, "render", lambda _: json.dumps({"type": "object", "properties": {}}))
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[1] == "tag":
            return SimpleNamespace(stdout="v1.0.0\nv1.1.0\nv1.2.0rc1\nv2.0.0\n")
        if args[1] == "ls-tree":
            return SimpleNamespace(stdout=target.out + "\n")
        assert args == ["git", "show", "v1.1.0:" + target.out]
        return SimpleNamespace(stdout=json.dumps(before))

    monkeypatch.setattr(tool.subprocess, "run", run)
    assert tool.compatibility_problems() == ["removed: fenolite.result.bom.v1.rows"]
    assert [args[1] for args in calls] == ["tag", "ls-tree", "show"]
