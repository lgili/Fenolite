# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Result schemas distinguish extensible data maps from declared object structures."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import _schema
import pytest


def generator():
    path = Path(__file__).resolve().parents[3] / "tools/gen_schemas.py"
    spec = importlib.util.spec_from_file_location("_result_schema_generator", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class AuthoredLeaf:
    value: int


@dataclass(frozen=True)
class AuthoredResult:
    item: AuthoredLeaf
    values: dict[str, AuthoredLeaf] = field(metadata={"description": "measurements indexed by user names"})
    sometimes: str = field(metadata={"optional": True})


def test_published_additions_are_open_but_internal_checks_close_structures():
    tool = generator()
    schema = tool.SchemaBuilder(all_required=True, published_open=True, optional_metadata=True).root(
        AuthoredResult, "fenolite.result.authored.v1"
    )
    data = {"item": {"value": 1}, "values": {"user-name": {"value": 2}}}
    assert _schema.validate(data, _schema.closed(schema)) == []
    assert _schema.validate({**data, "added": True}, schema) == []
    assert _schema.validate({**data, "added": True}, _schema.closed(schema))
    extra = {**data, "values": {"another-name": {"value": 3, "surprise": 4}}}
    assert _schema.validate(extra, schema) == []
    assert _schema.validate(extra, _schema.closed(schema))
    assert _schema.validate({**data, "values": {"user-name": "wrong type"}}, schema)
    assert schema["additionalProperties"] is True  # closed() never mutates the published data


def test_schema_ids_are_unique_and_all_local_references_resolve():
    tool = generator()
    identifiers = [target.schema_id for target in tool.TARGETS]
    paths = [target.out for target in tool.TARGETS]
    assert len(identifiers) == len(set(identifiers))
    assert len(paths) == len(set(paths))

    def visit(node, root):
        if isinstance(node, dict):
            if "$ref" in node:
                assert node["$ref"].startswith("#/$defs/")
                assert node["$ref"].removeprefix("#/$defs/") in root["$defs"]
            for value in node.values():
                visit(value, root)
        elif isinstance(node, list):
            for value in node:
                visit(value, root)

    for target in tool.TARGETS:
        schema = json.loads(tool.render(target))
        visit(schema, schema)


def test_fixed_tuple_arity_and_shared_class_names_remain_precise():
    tool = generator()
    leaf_a = dataclass(type("Leaf", (), {"__annotations__": {"number": int}}))
    leaf_b = dataclass(type("Leaf", (), {"__annotations__": {"text": str}}))
    row = dataclass(type("Row", (), {"__annotations__": {"a": leaf_a, "b": leaf_b, "at": tuple[int, int]}}))
    schema = tool.SchemaBuilder(all_required=True, unique_defs=True, strict_tuples=True).root(row, "authored")
    data = {"a": {"number": 1}, "b": {"text": "authored"}, "at": [1, 2]}
    assert _schema.validate(data, schema) == []
    assert _schema.validate({**data, "at": [1]}, schema)
    assert _schema.validate({**data, "b": {"number": 1}}, schema)


def test_after_activation_targets_cannot_regenerate_frozen_v0(monkeypatch):
    from fenolite.cli import api

    tool = generator()
    monkeypatch.setattr(api, "CONTRACT_VERSION", "v1")
    assert all(not target.schema_id.endswith(".v0") for target in tool._targets())
    with pytest.raises(SystemExit):
        tool.main(["--freeze-v0"])


def test_frozen_receipt_detects_removed_or_changed_bytes(monkeypatch, tmp_path):
    tool = generator()
    folder = tmp_path / "schemas"
    folder.mkdir()
    frozen = folder / "fenolite.authored.v0.json"
    frozen.write_text('{"authored":true}\n')
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    assert tool.main(["--freeze-v0"]) == 0
    assert tool.frozen_problems() == []
    frozen.write_text('{"authored":false}\n')
    assert tool.frozen_problems() == ["frozen schema changed or missing: schemas/fenolite.authored.v0.json"]
    frozen.unlink()
    assert tool.frozen_problems()


def test_prepared_schematic_equivalence_and_missing_input_counts_are_typed():
    from _result_contract import result_problems

    schematic = {
        "level": "S",
        "name": "schematic",
        "compared": 1,
        "differences": 0,
        "excluded": 0,
        "notices": 0,
        "summary": {"instances": 1, "pins": 2, "sheets": 1, "extraction_issues": 0},
    }
    assert result_problems("equivalent", {"level": "S", "levels": [schematic]}) == []
    side = {
        "backend": "kicad",
        "path": "root.kicad_sch",
        "sha256": "a" * 64,
        "components": 1,
        "footprints": 0,
        "netlist_source": "schematic",
    }
    assert (
        result_problems(
            "convert",
            {
                "equivalence": {
                    "level": "S",
                    "levels": [schematic],
                    "differences": [],
                    "notices": [],
                    "excluded": [],
                    "explained": [],
                    "unexplained": 0,
                    "translation": [0, 0],
                    "equivalent": True,
                    "frame": "board",
                    "profile": {"name": "authored", "rules": 0, "tool_version": ""},
                    "sides": {"a": side, "b": side},
                    "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0},
                }
            },
        )
        == []
    )
    assert result_problems("equivalent", {"level": "unsupported"})
    distance = {
        "boundary": "copper",
        "faces_alone": 0,
        "pairs": 0,
        "unsupported": {},
        "missing": {"outline": 1},
    }
    assert result_problems("analyze", {"summary": {"distances": distance}}) == []
    distance["missing"] = {"outline": "one"}
    assert result_problems("analyze", {"summary": {"distances": distance}})


def test_unit_helper_validates_serialized_values_and_materialized_public_files():
    from _result_contract import document_problems, result_problems

    from fenolite.cli.api import PlannedWrite

    assert result_problems("bom", {"undeclared": True})
    valid = PlannedWrite("marks.json", b'{"schema":"fenolite.review.v0","marks":[]}', "review")
    invalid = PlannedWrite(
        "marks.json",
        b'{"schema":"fenolite.review.v1","marks":[{"id":"m","doc":"board","x_nm":"wrong","y_nm":0}]}',
        "review",
    )
    assert document_problems((valid,)) == []
    assert any("x_nm" in error for error in document_problems((invalid,)))
