# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual same-tool cache regeneration proof on original CC0 geometry (c0340)."""

from __future__ import annotations

import json
from pathlib import Path

import _kicad
import _schema
import pytest
from _drawn_curve import curve_project
from _fidelity import roundtrip, snapshot

from fenolite import api
from fenolite.backends.kicad.cli import KicadCli
from fenolite.importer.provenance import import_record

pytestmark = pytest.mark.needs_kicad


def test_source_cache_and_fresh_build_compare_by_complete_native_geometry(tmp_path: Path) -> None:
    version = _kicad.supported_version()
    if not version.startswith("10."):
        pytest.skip("native derived-cache regeneration requires KiCad10; native9 defaults tested separately")
    source = curve_project(tmp_path / "original", 10, 10_000)
    path = source / "font_probe.kicad_pcb"
    native = KicadCli(Path(_kicad.cli()))
    saved = native.refill(path, files={p.name: p for p in source.iterdir() if p.is_file()})
    assert saved.run.ok and saved.board is not None
    path.write_bytes(saved.board)
    before = snapshot(source)
    output = tmp_path / "roundtrip"
    result = roundtrip(source, output)
    assert result.exit_code == 0, (result.error, result.result.get("differences"))
    assert result.result["accepted"] == result.result["differences"] == []
    assert all(row["status"] == "equal" for row in result.result["levels"])
    level7 = next(level for level in result.result["levels"] if level["level"] == 7)
    proof = level7["summary"]["derived_cache"]
    assert level7["status"] == proof["status"] == "equal"
    assert proof["version"] == version
    assert proof["complete_regenerated_geometry_equal"] is True
    assert proof["raw_cache_equality_claimed"] is False
    assert [proof["sides"][side]["raw_caches"] for side in ("a", "b")] == [2, 0]
    assert [proof["sides"][side]["regenerated_caches"] for side in ("a", "b")] == [2, 2]
    assert proof["sides"]["a"]["exact_geometry_sha256"] == proof["sides"]["b"]["exact_geometry_sha256"]
    assert snapshot(source) == before
    (tmp_path / "derived-cache-receipt.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    script = output / "code/design.py"
    args = ("verify-source", str(script), "--against", str(source), "--record")
    planned = api.run(*args, "--dry-run", cwd=tmp_path, seed=0)
    assert planned.exit_code == 0, planned.error
    confirmed = api.run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, seed=0)
    assert confirmed.exit_code == 0, confirmed.error
    recorded = json.loads((script.parent / "PROVENANCE.json").read_text())["fidelity"]["proof"][
        "derived_cache"
    ]
    assert recorded["status"] == "equal"
    document = json.loads((script.parent / "PROVENANCE.json").read_text())
    mirror = {**document, "schema": "fenolite.import-provenance.v1"}
    assert _schema.validate(mirror, _schema.load("formats/fenolite.import-provenance.v1.json")) == []
    original_member, mirrored_member = import_record(document), import_record(mirror)
    assert original_member is not None and mirrored_member is not None
    assert original_member["fidelity"] == mirrored_member["fidelity"]
    against = document["fidelity"]["proof"]["against"]
    assert all(against[name] == digest for name, digest in recorded["sides"]["a"]["input_files"].items())
    assert [recorded["sides"][side]["raw_caches"] for side in ("a", "b")] == [2, 0]
    assert snapshot(source) == before
    missing = api.run(
        "verify-source",
        str(script),
        "--against",
        str(source),
        "--kicad-cli",
        "/fenolite-authored-missing-tool",
        cwd=tmp_path,
        seed=0,
    )
    assert missing.exit_code == 6 and missing.error and missing.error["code"] == "FEN-6001"
    rule_path = source / "font_probe.kicad_dru"
    valid_rules = rule_path.read_bytes()
    rule_path.write_bytes(b"(version 1) (rule")
    malformed = api.run("verify-source", str(script), "--against", str(source), cwd=tmp_path, seed=0)
    assert malformed.exit_code in (3, 5), (malformed.error, malformed.result.get("differences"))
    if malformed.exit_code == 5:
        assert any(d["field"] == "native_regeneration" for d in malformed.result["differences"])
    rule_path.write_bytes(valid_rules)
    assert snapshot(source) == before
    # A real script setting mutation fails existing level6 before common-tool qualification.
    script = output / "code/design.py"
    text = script.read_text()
    assert text.count('max_curve_error=mm("0.01")') == 1
    script.write_text(text.replace('max_curve_error=mm("0.01")', 'max_curve_error=mm("0.02")'))
    changed = api.run("verify-source", str(script), "--against", str(source), cwd=tmp_path, seed=0)
    assert changed.exit_code == 5 and changed.result["accepted"] == []
    assert any(d["level"] == 6 and d["field"] == "max_curve_error" for d in changed.result["differences"])
    assert (
        "derived_cache"
        not in next(level for level in changed.result["levels"] if level["level"] == 7)["summary"]
    )
    assert snapshot(source) == before
