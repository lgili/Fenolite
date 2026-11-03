# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source-bound native level6 floor/class proof and stale plans (c0352)."""

from __future__ import annotations

import json
from pathlib import Path

from _importcode import STAMP, copy_project, imported

from fenolite.api import run


def test_verify_source_records_native_scope_and_binds_original_project_bytes(tmp_path: Path) -> None:
    source = copy_project(tmp_path)
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    script = tmp_path / "out" / "design.py"
    args = ("verify-source", str(script), "--against", str(source), "--levels", "6", "--record")
    planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    level = next(level for level in planned.result["levels"] if level["level"] == 6)
    scope = level["summary"]["native_project_rules"]
    assert level["status"] == "equal" and scope["judged_count"] > 5
    assert {"min_clearance", "min_track_width"} <= set(scope["judged_keys"])
    assert source.name in planned.result["against"]["files"]
    original_provenance = (script.parent / "PROVENANCE.json").read_bytes()
    data = json.loads(source.read_text())
    data["board"]["design_settings"]["rules"]["min_clearance"] = 0.001
    source.write_text(json.dumps(data))
    stale = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert stale.exit_code == 4 and stale.error["code"] == "FEN-4002"
    assert (script.parent / "PROVENANCE.json").read_bytes() == original_provenance
    tampered = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert tampered.exit_code == 5, tampered.error
    assert any(d["level"] == 6 and d["field"] == "min_clearance" for d in tampered.result["differences"])
    assert "plan_id" not in tampered.result


def test_real_import_record_fidelity_is_closed_and_v0_v1_meaning_matches(tmp_path: Path) -> None:
    import copy
    import hashlib

    import _schema

    from fenolite.importer.provenance import import_record

    source = copy_project(tmp_path)
    assert imported(tmp_path, source, "--confirm").exit_code == 0
    script = tmp_path / "out" / "design.py"
    args = ("verify-source", str(script), "--against", str(source), "--levels", "6", "--record")
    planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert confirmed.exit_code == 0, confirmed.error
    document = json.loads((script.parent / "PROVENANCE.json").read_text())
    schema = _schema.load("formats/fenolite.import-provenance.v1.json")
    mirror = {**document, "schema": "fenolite.import-provenance.v1"}
    assert _schema.validate(mirror, schema) == []
    original_record, mirrored_record = import_record(document), import_record(mirror)
    assert original_record is not None and mirrored_record is not None
    assert original_record["fidelity"] == mirrored_record["fidelity"]
    proof = document["fidelity"]["proof"]
    assert (
        proof["native_project_rules"]["a_read_files"][source.name]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert proof["native_project_rules"]["a_read_files"][source.name] == proof["against"][source.name]
    for fault in ("unknown-fidelity-member", "wrong-proof-type", "unknown-native-member", "wrong-hash-type"):
        invalid = copy.deepcopy(mirror)
        if fault == "unknown-fidelity-member":
            invalid["fidelity"]["unexpected"] = True
        elif fault == "wrong-proof-type":
            invalid["fidelity"]["proof"] = "not a proof"
        elif fault == "unknown-native-member":
            invalid["fidelity"]["proof"]["native_project_rules"]["extra"] = 1
        else:
            invalid["fidelity"]["proof"]["native_project_rules"]["a_read_files"][source.name] = 123
        assert _schema.validate(invalid, schema), fault


def test_cli_equivalent_keeps_native_and_existing_curve_differences(tmp_path: Path) -> None:
    from fenolite.backends.kicad import pro

    source = copy_project(tmp_path, "a")
    other = copy_project(tmp_path, "b")
    data = pro.read_project_text(other.read_text())
    data["board"]["design_settings"]["rules"].update(
        max_error=pro.millimetres(10_000), min_clearance=pro.millimetres(1_000)
    )
    other.write_text(pro.write_project_text(data))
    result = run("equivalent", str(source), str(other), "--level", "6", cwd=tmp_path, timestamp=STAMP)
    assert result.exit_code == 5, result.error
    assert {"min_clearance", "max_curve_error"} <= {d["field"] for d in result.result["differences"]}
