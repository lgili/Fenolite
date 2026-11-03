# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed existing cache receipt wire shape; MOCKED subprocesses are NOT native evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

import _schema
import pytest
from test_derived_cache import board, item, tool

from fenolite.backends.kicad import pro
from fenolite.cli import _derived_cache as cache
from fenolite.importer.provenance import Provenance, import_record, record
from fenolite.importer.source import InputFile


def authored_mocked_record(*, failure: bool = False) -> dict:
    a, b = item(), item("")
    for source, number in ((a, "0.125"), (b, "0.25")):
        source.project["board"]["design_settings"]["rules"]["AUTHORED_UNJUDGED"] = {
            "nested": [pro.JsonNumber(number), True, None, "authored"]
        }
    a = replace(a, files={**a.files, "own.kicad_pro": pro.write_project_text(a.project).encode()})
    b = replace(b, files={**b.files, "own.kicad_pro": pro.write_project_text(b.project).encode()})
    outputs = [{}] if failure else [{"own.kicad_pcb": board()}, {"own.kicad_pcb": board()}]
    summary, differences = cache.prove(a, b, tool(outputs))
    assert bool(differences) is failure
    document = json.loads(
        record(
            Provenance(licence="CC0-1.0", date="2026-11-03", fenolite="mocked-protocol-shape-only"),
            design="authored-wire-control",
            inputs=[
                InputFile(name, hashlib.sha256(data).hexdigest(), name.rsplit(".", 1)[1], None)
                for name, data in a.files.items()
            ],
            upgrades=[],
            findings={},
            equivalence=None,
            tools={"subprocess": "MOCKED_NOT_NATIVE_EVIDENCE"},
        )
    )
    document["fidelity"] = {
        "proof": {
            "levels": {"7": "differs" if failure else "equal"},
            "against": {name: hashlib.sha256(data).hexdigest() for name, data in a.files.items()},
            "derived_cache": summary,
        }
    }
    return json.loads(json.dumps(document))


@pytest.mark.parametrize("failure", (False, True))
def test_existing_producer_receipt_has_closed_optional_branches_and_source_bound_mirrors(
    failure: bool,
) -> None:
    original = authored_mocked_record(failure=failure)
    mirror = {**original, "schema": "fenolite.import-provenance.v1"}
    schema = _schema.load("formats/fenolite.import-provenance.v1.json")
    assert _schema.validate(mirror, schema) == []
    first, second = import_record(original), import_record(mirror)
    assert first is not None and second is not None
    assert first["fidelity"] == second["fidelity"]
    proof = mirror["fidelity"]["proof"]
    assert proof["against"] == proof["derived_cache"]["sides"]["a"]["input_files"]
    assert {row["file"]: row["sha256"] for row in mirror["inputs"]} == proof["against"]
    delta = proof["derived_cache"]["unjudged_project_rule_deltas"][0]
    assert delta["a"] != delta["b"]  # Native unjudged input differs; receipt makes no equality claim.
    assert proof["derived_cache"]["whole_project_json_equality_claimed"] is False


@pytest.mark.parametrize("fault", ("root", "side", "crossing", "type", "false-safety", "false-raw-equality"))
def test_unknown_known_structure_and_false_claims_are_rejected(fault: str) -> None:
    data = authored_mocked_record()
    data["schema"] = "fenolite.import-provenance.v1"
    summary = data["fidelity"]["proof"]["derived_cache"]
    if fault == "root":
        summary["unexpected"] = True
    elif fault == "side":
        summary["sides"]["extra"] = copy.deepcopy(summary["sides"]["a"])
    elif fault == "crossing":
        summary["sides"]["a"]["raw_non_simple_rings"]["extra"] = 0
    elif fault == "type":
        summary["sides"]["a"]["raw_caches"] = "one"
    elif fault == "false-safety":
        summary["drc_safety_gate_claimed"] = True
    else:
        summary["raw_cache_equality_claimed"] = True
    assert _schema.validate(data, _schema.load("formats/fenolite.import-provenance.v1.json"))


@pytest.mark.parametrize(
    "leaf", (float("nan"), float("inf"), -float("inf"), 0.125, object(), {"raw": "object"}, {1, 2})
)
def test_uninterpreted_leaf_is_finite_canonical_wire_json_only(leaf) -> None:
    data = authored_mocked_record()
    data["schema"] = "fenolite.import-provenance.v1"
    delta = data["fidelity"]["proof"]["derived_cache"]["unjudged_project_rule_deltas"][0]
    delta["a"] = ["nested", [leaf]]
    assert _schema.validate(data, _schema.load("formats/fenolite.import-provenance.v1.json"))


def test_recursive_uninterpreted_marker_is_referenced_only_by_two_narrow_delta_leaves() -> None:
    schema = _schema.load("formats/fenolite.import-provenance.v1.json")
    references = []

    def visit(value, path=()):
        if isinstance(value, dict):
            if value.get("$ref") == "#/$defs/CanonicalNativeJson":
                references.append(path)
            for key, child in value.items():
                visit(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))

    visit(schema)
    assert set(references) == {
        ("$defs", "CanonicalNativeJson", "anyOf", "4", "items"),
        ("$defs", "DerivedCacheRuleDelta", "properties", "a"),
        ("$defs", "DerivedCacheRuleDelta", "properties", "b"),
    }
