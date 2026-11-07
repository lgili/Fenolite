# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable drawn-context observations are exact reports, never accepted corpus baselines (c0276)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import tomllib
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence"


CI_SOURCE = "985f59a1d01a612b2eac0219243199896c24075a"
CI_RECORD_SHA = "a0034d17c072b36cb5a62c410416ce200457f5e10ab27b5ac8742babd52a157c"
CI_PROOF_SHA = "83d1ba990b1b4b7cedbfadcde391f995b89512ca95cf43c01282fd1d224ed68a"
MANIFEST_SHA = "bdc796c64b61f1e0a0240f2c133e879cc367a1ed256ea006cf883320b2cb4dcc"
STAGES = {"extract", "lower", "resolve", "native-original", "native-lowered"}
COUNT_KINDS = {
    "sheets",
    "symbols",
    "wires",
    "labels",
    "powers",
    "buses",
    "bus_entries",
    "sheet_refs",
    "opaque",
    "junctions",
}
PARTITIONS = ("partition", "lowered_partition", "lowered_native_partition")
DRAWN_CENSUS_SHA = "603aa013d44fbe2b46a5aab175a6024d5afa80829f280b8fadb45b07e912dffd"
SOURCE_BINDINGS = {
    "tests/corpus/manifest.toml": MANIFEST_SHA,
    "tests/kicad/schematic/test_drawn_corpus.py": DRAWN_CENSUS_SHA,
    "tests/_drawn_corpus.py": "185ac55b9ce3698bee45313ffe11916e735127966aa7c619cb9088ffc964bb60",
    "tests/_drawn_context.py": "e29f9c4df61c1e063e87e2e4056e035423339819efb19d1151f5a5284096178d",
}


def _digest(value: object) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2) + "\n").encode()).hexdigest()


def _change_directory(root: Path | None = None) -> Path:
    """Locate one active OR archived change; a preferred/first match is unsafe."""
    root = ROOT if root is None else root
    changes = root / "openspec/changes"
    candidates = [
        changes / "c0276-drawn-schematic",
        *sorted((changes / "archive").glob("*-c0276-drawn-schematic")),
    ]
    found = [path for path in candidates if path.is_dir()]
    assert len(found) == 1, "expected exactly one c0276 change directory"
    return found[0]


def _ci_evidence(root: Path | None = None) -> tuple[dict, dict]:
    root = ROOT if root is None else root
    folder = _change_directory(root)
    return (
        json.loads((root / "docs/evidence/drawn-ci-census-985f59a1.json").read_text()),
        json.loads((folder / "census-7.2-proof.json").read_text()),
    )


def _validate_ci_census(record: dict, proof: dict) -> None:
    """Structural gates precede immutable source seals, so incomplete data never closes the task."""
    assert record.get("measured_source") == proof.get("measurement_source") == CI_SOURCE, "measurement source"
    assert record["manifest_sha256"] == proof["manifest_sha256"] == MANIFEST_SHA, "manifest binding"
    assert record["CI_run"] == 41708879698 and record["CI_conclusion"] == "failure", "CI scope"
    assert record["required_current_integration_passed"] is False, "CI scope"
    for key, proof_key, expected in (
        (
            "prior_retained_audit_sha256",
            "prior_audit_sha256",
            "d834982a6d19269d33ac48eaaf99b1f801e639e6b958ca88b20a7a86bae1e17b",
        ),
        (
            "retention_manifest_sha256",
            "retention_manifest_sha256",
            "9b830ffc2cbe90beb41a6834d17dc5cd88b3ed3f4a091108a73560d2eb747c94",
        ),
    ):
        assert record[key] == proof[proof_key] == expected, "retained source link"
    assert {v["path"]: v["sha256"] for v in record["source_bindings"]} == SOURCE_BINDINGS, "source bindings"
    assert record["source_bindings"] == proof["source_bindings"], "source bindings"
    declared = {r["id"]: r for r in tomllib.loads((ROOT / "tests/corpus/manifest.toml").read_text())["file"]}
    expected_ids = {key for key, r in declared.items() if {"sch", "origin:kicad-demos"} <= set(r["uses"])}
    assert len(expected_ids) == 130 and set(record["majors"]) == {"9", "10"}, "major coverage"
    catalog = record["metadata_catalog"]
    for name in ("owners", "input_sets"):
        assert all(_digest(value) == key for key, value in catalog[name].items()), "catalog binding"
    configurations = (
        (
            "9",
            "9.0.9",
            87,
            5,
            38,
            262,
            132,
            57,
            18515,
            126171394740,
            "c3b2c3efd6be9ec7a1144c2c1c7f8fd8e0f5cfb4a25f9e5adbd430fb8279786b",
        ),
        (
            "10",
            "10.0.6",
            113,
            1,
            16,
            131,
            1,
            82,
            18586,
            126171394674,
            "13c210de5ded6c12fabde9d67e01102790f34f222b457e47176a53135bcc1e5d",
        ),
    )
    for (
        major,
        version,
        equal,
        floor,
        tags,
        raw_count,
        aliases,
        warnings,
        name_sum,
        job_id,
        archive_sha,
    ) in configurations:
        section = record["majors"][major]
        assert section["native_version"] == version and section["job"]["id"] == job_id, "native version/job"
        assert section["job"]["status"] == "completed", "native version/job"
        assert section["job"]["conclusion"] == ("success" if major == "9" else "failure"), "CI scope"
        assert section["artifact"]["sha256"] == archive_sha, "artifact source link"
        rows, summary = section["records"], section["summary"]
        assert len(rows) == len({r["id"] for r in rows}) == 130, "row coverage"
        assert {r["id"] for r in rows} == expected_ids, "row coverage"
        statuses = {"equal": equal, "refused": floor, "native-version-incompatible": tags}
        assert Counter(r["status"] for r in rows) == summary["statuses"] == statuses, "outcome census"
        contexts = [c for r in rows for c in r["contexts"]]
        assert len(contexts) == summary["contexts"] == equal and summary["rows"] == 130, "context coverage"
        raw = [item for r in rows for item in r["retained_raw_reports"]]
        assert len(raw) == len({item["member"] for item in raw}) == raw_count, "alias coverage"
        assert summary["raw_members"] == section["artifact"]["raw_reports"] == raw_count, "alias coverage"
        assert summary["byte_identical_alias_copies"] == aliases == raw_count - len(rows), "alias coverage"
        for row in rows:
            assert row["kind"] == "schematic", "row kind"
            assert row["expected_sha256"] == declared[row["id"]]["sha256"], "row input hash"
            assert (
                isinstance(row["seconds"], (int, float))
                and math.isfinite(row["seconds"])
                and row["seconds"] >= 0
            ), "row timing"
            copies = row["retained_raw_reports"]
            assert copies and len({item["sha256"] for item in copies}) == 1, "alias identity"
            assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in copies), "alias identity"
            if row["status"] == "native-version-incompatible":
                assert row["seconds"] == 0 and not row["contexts"], "tag nonexecution"
                assert row["input_sha256"] in (None, row["expected_sha256"]), "row input hash"
                continue
            assert row["input_sha256"] == row["expected_sha256"], "row input hash"
            if row["status"] == "refused":
                assert row["expectation"] == "original-reader-floor" and not row["contexts"], "floor refusal"
                assert row["refusal"] == {
                    "code": "FEN-3003",
                    "stage": "read",
                    "type": "UnsupportedFormatError",
                }, "floor refusal"
                assert row["declared_format"] < 20231120, "floor refusal"
                continue
            assert row["contexts"], "context coverage"
            for ctx in row["contexts"]:
                assert COUNT_KINDS <= ctx["counts_by_entity_kind"].keys(), "entity-kind counts"
                assert all(type(v) is int and v >= 0 for v in ctx["counts_by_entity_kind"].values()), (
                    "entity-kind counts"
                )
                assert set(ctx["stage_seconds"]) == STAGES, "stage timing"
                assert all(
                    isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
                    for v in ctx["stage_seconds"].values()
                ), "stage timing"
                owner = catalog["owners"][ctx["owner_record_sha256"]]
                inputs = catalog["input_sets"][ctx["input_set_sha256"]]
                assert owner["owner_id"] == ctx["owner_id"] == owner["native_export_root_id"], "owner binding"
                assert (
                    owner["target_instances"]
                    == sum(i["input_id"] == row["id"] for i in owner["instances"])
                    > 0
                ), "owner binding"
                assert all(
                    i["input_sha256"] == declared[i["input_id"]]["sha256"] for i in owner["instances"]
                ), "instance input hash"
                assert {row["id"], owner["owner_id"]} <= {i["id"] for i in inputs}, "context input coverage"
                assert all(
                    i["sha256"] == i["expected_sha256"] == declared[i["id"]]["sha256"] for i in inputs
                ), "context input hash"
                if owner["scope"] == "registered-project":
                    project = owner["project_input"]
                    assert (
                        project["input_sha256"]
                        == project["expected_sha256"]
                        == declared[project["id"]]["sha256"]
                    ), "project input hash"
                assert set(ctx["comparisons"]) == set(PARTITIONS), "complete partition"
                for comparison in ctx["comparisons"].values():
                    assert comparison["equal"] is True, "complete partition"
                    assert (
                        comparison["native_only_pins"]
                        == comparison["drawn_unlisted_pins"]
                        == comparison["only_drawn_groups"]
                        == comparison["only_native_groups"]
                        == 0
                    ), "complete partition"
                    assert (
                        comparison["drawn_pins"] == comparison["native_pins"]
                        and comparison["drawn_groups"] == comparison["native_groups"]
                    ), "complete partition"
                    assert comparison["naming_equal"] == (comparison["name_differences"] == 0), "naming flags"
        for key in PARTITIONS:
            comparisons = [c["comparisons"][key] for c in contexts]
            different = {
                r["id"] for r in rows for c in r["contexts"] if not c["comparisons"][key]["naming_equal"]
            }
            expected_warnings = 0 if key == "lowered_native_partition" else warnings
            expected_sum = 0 if key == "lowered_native_partition" else name_sum
            assert len(different) == expected_warnings, "naming census"
            actual = {
                "compared_contexts": equal,
                "contexts_equal": equal - expected_warnings,
                "contexts_different": expected_warnings,
                "rows_with_differences": sorted(different),
                "name_difference_count_sum_across_contexts": sum(p["name_differences"] for p in comparisons),
            }
            assert actual["name_difference_count_sum_across_contexts"] == expected_sum, "naming census"
            assert summary["naming"][key] == actual, "naming census"
            assert summary["comparison_connectivity_equal"][key] == equal, "complete partition"
        assert proof["summaries"][major] == summary, "portable summary binding"
    assert (
        proof["documentary_verification"]["exit"] == 0
        and proof["documentary_verification"]["all_rows_expanded_against_retained_original_JSON"] is True
    ), "verification receipt"
    limits = proof["scope_limits"]
    assert limits["overall_CI_conclusion"] == "failure", "CI scope"
    for key in (
        "new_native_or_corpus_execution",
        "later_runtime_equivalence_claimed",
        "hypotheses_promoted",
        "universal_names_claimed",
        "7.1_complete",
        "9.2_complete",
        "c0347_gate_changed",
    ):
        assert limits[key] is False, "measurement scope"
    assert proof["record_sha256"] == _digest(record), "portable record binding"
    assert _digest(record) == CI_RECORD_SHA, "sealed observation bytes"
    assert _digest(proof) == CI_PROOF_SHA, "sealed receipt bytes"


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
    tasks = (_change_directory() / "tasks.md").read_text(encoding="utf-8")
    if "- [x] 7.2 " in tasks:
        _validate_ci_census(*_ci_evidence())
    else:
        assert "- [ ] 7.2 " in tasks


def test_only_complete_source985_census_receipt_can_support_closure() -> None:
    _validate_ci_census(*_ci_evidence())


def test_historical_failed_observations_cannot_substitute_for_ci_measurement() -> None:
    historical = json.loads((EVIDENCE / "drawn-context.json").read_text())["observations"]
    _, proof = _ci_evidence()
    for observation in historical:
        with pytest.raises(AssertionError, match="measurement source"):
            _validate_ci_census(observation, proof)
    record, _ = _ci_evidence()
    with pytest.raises(AssertionError, match="measurement source"):
        _validate_ci_census(record, {})


def _rebind_metadata(record: dict, ctx: dict, kind: str, mutate) -> None:
    """Rehash a tampered catalog entry so semantic controls, not a stale digest, reject it."""
    field = "owner_record_sha256" if kind == "owners" else "input_set_sha256"
    entry = deepcopy(record["metadata_catalog"][kind][ctx[field]])
    mutate(entry)
    key = _digest(entry)
    record["metadata_catalog"][kind][key] = entry
    ctx[field] = key


@pytest.mark.parametrize(
    "case,reason",
    (
        ("source", "measurement source"),
        ("missing-major", "major coverage"),
        ("missing-row", "row coverage"),
        ("duplicate-row", "row coverage"),
        ("floor-as-equal", "outcome census"),
        ("tag-executed", "tag nonexecution"),
        ("missing-stage", "stage timing"),
        ("nonfinite-stage", "stage timing"),
        ("missing-kind", "entity-kind counts"),
        ("negative-count", "entity-kind counts"),
        ("row-hash", "row input hash"),
        ("context-hash", "context input hash"),
        ("project-hash", "project input hash"),
        ("lost-pin", "complete partition"),
        ("different-group", "complete partition"),
        ("erased-warning", "naming census"),
        ("collapsed-alias", "alias coverage"),
        ("different-alias", "alias identity"),
        ("artifact-link", "artifact source link"),
        ("source-binding", "source bindings"),
        ("receipt-link", "retained source link"),
        ("record-link", "portable record binding"),
        ("receipt-bytes", "sealed receipt bytes"),
        ("global-green", "CI scope"),
    ),
)
def test_incomplete_or_changed_ci_data_cannot_close_measurement(case: str, reason: str) -> None:
    record, proof = _ci_evidence()
    section = record["majors"]["9"]
    row = next(r for r in section["records"] if r["status"] == "equal")
    ctx = row["contexts"][0]
    if case == "source":
        record["measured_source"] = "0" * 40
    elif case == "missing-major":
        del record["majors"]["10"]
    elif case == "missing-row":
        section["records"].pop()
    elif case == "duplicate-row":
        section["records"][-1] = deepcopy(section["records"][0])
    elif case == "floor-as-equal":
        next(r for r in section["records"] if r["status"] == "refused")["status"] = "equal"
    elif case == "tag-executed":
        next(r for r in section["records"] if r["status"] == "native-version-incompatible")["seconds"] = 1
    elif case == "missing-stage":
        del ctx["stage_seconds"]["resolve"]
    elif case == "nonfinite-stage":
        ctx["stage_seconds"]["resolve"] = float("nan")
    elif case == "missing-kind":
        del ctx["counts_by_entity_kind"]["wires"]
    elif case == "negative-count":
        ctx["counts_by_entity_kind"]["wires"] = -1
    elif case == "row-hash":
        row["input_sha256"] = "0" * 64
    elif case == "context-hash":
        _rebind_metadata(record, ctx, "input_sets", lambda value: value[0].update(sha256="0" * 64))
    elif case == "project-hash":
        _rebind_metadata(
            record, ctx, "owners", lambda value: value["project_input"].update(input_sha256="0" * 64)
        )
    elif case == "lost-pin":
        ctx["comparisons"]["partition"]["native_pins"] -= 1
    elif case == "different-group":
        ctx["comparisons"]["partition"]["only_native_groups"] = 1
    elif case == "erased-warning":
        ctx = next(
            c
            for r in section["records"]
            for c in r["contexts"]
            if c["comparisons"]["partition"]["name_differences"]
        )
        for key in ("partition", "lowered_partition"):
            ctx["comparisons"][key].update(naming_equal=True, name_differences=0)
    elif case == "collapsed-alias":
        next(r for r in section["records"] if len(r["retained_raw_reports"]) > 1)[
            "retained_raw_reports"
        ].pop()
    elif case == "different-alias":
        next(r for r in section["records"] if len(r["retained_raw_reports"]) > 1)["retained_raw_reports"][0][
            "sha256"
        ] = "0" * 64
    elif case == "artifact-link":
        section["artifact"]["sha256"] = "0" * 64
    elif case == "source-binding":
        record["source_bindings"][0]["sha256"] = "0" * 64
    elif case == "receipt-link":
        proof["retention_manifest_sha256"] = "0" * 64
    elif case == "record-link":
        proof["record_sha256"] = "0" * 64
    elif case == "receipt-bytes":
        proof["documentary_verification"]["script_sha256"] = "0" * 64
    elif case == "global-green":
        record["CI_conclusion"] = "success"
    else:
        raise AssertionError(case)
    with pytest.raises(AssertionError, match=reason):
        _validate_ci_census(record, proof)


@pytest.mark.parametrize("archived", (False, True))
def test_receipt_lookup_works_active_or_archived(tmp_path: Path, archived: bool) -> None:
    relative = "archive/2026-11-03-c0276-drawn-schematic" if archived else "c0276-drawn-schematic"
    folder = tmp_path / "openspec/changes" / relative
    folder.mkdir(parents=True)
    original = _change_directory()
    for name in ("tasks.md", "census-7.2-proof.json"):
        (folder / name).write_bytes((original / name).read_bytes())
    evidence = tmp_path / "docs/evidence"
    evidence.mkdir(parents=True)
    (evidence / "drawn-ci-census-985f59a1.json").write_bytes(
        (EVIDENCE / "drawn-ci-census-985f59a1.json").read_bytes()
    )
    assert _change_directory(tmp_path) == folder
    _validate_ci_census(*_ci_evidence(tmp_path))


@pytest.mark.parametrize(
    "locations",
    (
        (),
        ("c0276-drawn-schematic", "archive/2026-11-03-c0276-drawn-schematic"),
        ("archive/2026-11-03-c0276-drawn-schematic", "archive/2026-11-04-c0276-drawn-schematic"),
    ),
)
def test_receipt_lookup_refuses_missing_or_ambiguous_spec(tmp_path: Path, locations: tuple[str, ...]) -> None:
    for relative in locations:
        (tmp_path / "openspec/changes" / relative).mkdir(parents=True)
    with pytest.raises(AssertionError, match="exactly one c0276 change directory"):
        _change_directory(tmp_path)


@pytest.mark.parametrize(
    "field",
    (
        "new_native_or_corpus_execution",
        "later_runtime_equivalence_claimed",
        "hypotheses_promoted",
        "universal_names_claimed",
        "7.1_complete",
        "9.2_complete",
        "c0347_gate_changed",
    ),
)
def test_receipt_scope_cannot_be_promoted(field: str) -> None:
    record, proof = _ci_evidence()
    proof["scope_limits"][field] = True
    with pytest.raises(AssertionError, match="measurement scope"):
        _validate_ci_census(record, proof)


def test_future_separate_closure_does_not_promote_the_historical_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "openspec/changes/archive/2026-11-03-c0276-drawn-schematic"
    folder.mkdir(parents=True)
    original = _change_directory()
    proof_bytes = (original / "census-7.2-proof.json").read_bytes()
    (folder / "census-7.2-proof.json").write_bytes(proof_bytes)
    tasks = (original / "tasks.md").read_text(encoding="utf-8")
    for task in ("7.1", "9.2"):
        tasks = tasks.replace(f"- [ ] {task} ", f"- [x] {task} ")
        assert f"- [x] {task} " in tasks
    (folder / "tasks.md").write_text(tasks, encoding="utf-8")
    evidence = tmp_path / "docs/evidence"
    evidence.mkdir(parents=True)
    for name in ("drawn-context.json", "drawn-ci-census-985f59a1.json"):
        (evidence / name).write_bytes((EVIDENCE / name).read_bytes())
    manifest = tmp_path / "tests/corpus/manifest.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes((ROOT / "tests/corpus/manifest.toml").read_bytes())
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    monkeypatch.setitem(globals(), "EVIDENCE", evidence)
    # The same historical assertions and full closure guard still run after archive,
    # even when later independent proofs have completed the other tasks.
    test_context_maps_retain_all_instances_refusals_and_names_without_cad_payload()
    _, receipt = _ci_evidence()
    assert receipt["scope_limits"]["7.1_complete"] is False
    assert receipt["scope_limits"]["9.2_complete"] is False
    assert (folder / "census-7.2-proof.json").read_bytes() == proof_bytes
