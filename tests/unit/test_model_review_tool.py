# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A generated inventory never stands in for actual maintainer approval (c0218)."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def tool():
    path = Path(__file__).resolve().parents[2] / "tools/model_review.py"
    spec = importlib.util.spec_from_file_location("authored_model_review_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def inventory():
    return {
        "decision": "pending",
        "decision_date": None,
        "reviewer": None,
        "classes": [
            {
                "class": "Authored",
                "decision": "pending",
                "fields": [
                    {"name": "status", "decision": "pending", "default": {"value": {"decision": "pending"}}}
                ],
            }
        ],
        "extension_keys": [{"key": "authored", "decision": "pending"}],
    }


def test_actual_inventory_defaults_are_pending_without_a_historical_date():
    data = tool().inventory()
    assert data["decision_date"] is None and data["reviewer"] is None
    assert all(entry["decision"] == "pending" for entry in data["extension_keys"])
    for entry in data["classes"]:
        assert entry["decision"] == "pending"
        assert all(field["decision"] == "pending" for field in entry["fields"])


def test_explicit_synthetic_review_keeps_type_default_payloads_immutable():
    before = inventory()
    original = copy.deepcopy(before)
    after = tool().record_keep_all(before, reviewer="Authored Reviewer", decision_date="2001-02-03")
    assert before == original and after is not before
    assert after["classes"][0]["decision"] == "keep"
    assert after["classes"][0]["fields"][0]["decision"] == "keep"
    assert after["classes"][0]["fields"][0]["default"] == before["classes"][0]["fields"][0]["default"]
    assert after["reviewer"] == "Authored Reviewer" and after["decision_date"] == "2001-02-03"


@pytest.mark.parametrize(
    "args", [("--keep-all",), ("--reviewer", "Authored"), ("--keep-all", "--reviewer", "Authored")]
)
def test_cli_never_assumes_approval_or_date(tmp_path: Path, args):
    module = tool()
    with pytest.raises(SystemExit) as caught:
        module.main(["--out", str(tmp_path / "review.json"), *args])
    assert caught.value.code == 2 and not (tmp_path / "review.json").exists()


def test_pending_review_check_is_repeatable(tmp_path: Path, monkeypatch, capsys):
    module = tool()
    monkeypatch.setattr(module, "inventory", inventory)
    path = tmp_path / "review.json"
    assert module.main(["--out", str(path)]) == 0
    assert module.main(["--out", str(path), "--check"]) == 0
    assert "all decisions PENDING" in capsys.readouterr().out


def test_actual_approved_model0_shapes_are_preserved_by_migration_candidate():
    root = Path(__file__).resolve().parents[2]
    review = root / "openspec/changes/archive/2026-11-04-c0218-model-schema-1-0"
    approved = json.loads((review / "model0-approved.json").read_text())
    actual = tool().inventory()
    shapes = {
        c["class"]: {
            "class": c["class"],
            "fields": [{k: f[k] for k in ("name", "type", "default")} for f in c["fields"]],
        }
        for c in actual["classes"]
    }
    assert approved["reviewer"] == "Luiz Carlos Gili"
    assert approved["decision_date"] == "2026-11-03"
    assert len(approved["classes"]) == approved["class_count"] == 174
    assert sum(len(c["fields"]) for c in approved["classes"]) == approved["field_count"] == 1247
    # an approved field keeps its name, type, default and order; a later change may only add fields with a
    # default (the design model's additive rule: a document written before it loads unchanged), e.g. c0411
    # FootprintInstance.keepouts and c0419 SymbolDef.fields
    for c in approved["classes"]:
        assert c["decision"] == "keep"
        found = shapes.pop(c["class"])["fields"]
        names = [f["name"] for f in found]
        kept = [f for f in found if f["name"] in {g["name"] for g in c["fields"]}]
        assert kept == c["fields"], c["class"]
        added = [f for f in found if f not in kept]
        assert all(f["default"]["kind"] != "required" for f in added), (c["class"], names)
    added_classes = set(shapes) - {"fenolite.model.migrate.Step"}
    assert "fenolite.model.migrate.Step" in shapes
    for name in added_classes:  # a class added by a later change is reached only through a defaulted field
        assert name.startswith("fenolite.model."), name
    assert len(shapes["fenolite.model.migrate.Step"]["fields"]) == 4
    assert len(approved["extension_keys"]) == approved["extension_key_count"] == 40
    assert {(e["backend"], e["key"]) for e in approved["extension_keys"]} == {
        (e["backend"], e["key"]) for e in actual["extension_keys"]
    }
    assert all(e["decision"] == "keep" for e in approved["extension_keys"])


def test_stored_inventory_is_current():
    """Change c0404: a model field, type, default or extension key that changes without the inventory
    fails here, not only when someone runs the tool by hand."""
    assert tool().main(["--check"]) == 0


def test_check_fails_on_shape_and_passes_on_moved_readers(tmp_path: Path, monkeypatch, capsys):
    module = tool()

    def current():
        data = inventory()
        data["readers"] = {"status": ["src/authored.py"]}
        data["generic_readers"] = []
        data["extension_keys"][0]["readers"] = ["src/authored.py"]
        return data

    monkeypatch.setattr(module, "inventory", current)
    path = tmp_path / "review.json"
    assert module.main(["--out", str(path)]) == 0
    moved = json.loads(path.read_text())
    moved["readers"]["status"].append("src/other.py")
    moved["extension_keys"][0]["readers"] = []
    path.write_text(json.dumps(moved))
    assert module.main(["--out", str(path), "--check"]) == 0
    assert "reader locations moved" in capsys.readouterr().out
    changed = json.loads(path.read_text())
    changed["classes"][0]["fields"][0]["name"] = "renamed"
    path.write_text(json.dumps(changed))
    assert module.main(["--out", str(path), "--check"]) == 1
    assert "inventory is stale" in capsys.readouterr().err
    assert module.main(["--out", str(tmp_path / "absent.json"), "--check"]) == 1
