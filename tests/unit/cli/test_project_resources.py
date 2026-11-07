# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0354: exact authored worksheets retain independent native project scopes."""

from __future__ import annotations

import hashlib
import json

import pytest
from _project_resources import WORKSHEET, source_with_resource
from _project_template import STAMP, built, imported, snapshot

from fenolite.api import run
from fenolite.cli import plans
from fenolite.core.state import state_dir


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("scope", ["pcbnew", "schematic", "both"])
def test_exact_resource_and_native_scopes_survive_import_and_build(tmp_path, target, scope) -> None:
    source = source_with_resource(tmp_path, target, scope)
    original = snapshot(source.parent)
    code = imported(tmp_path, source, target=target)
    assert (code / "native/frames/authored.kicad_wks").read_bytes() == WORKSHEET
    assert "design.sheet(" not in (code / "design.py").read_text()
    provenance = json.loads((code / "PROVENANCE.json").read_text())
    assert any(
        row["file"] == "frames/authored.kicad_wks" and row["sha256"] == hashlib.sha256(WORKSHEET).hexdigest()
        for row in provenance["inputs"]
    )
    output = built(tmp_path, code, target=target)
    assert (output.parent / "frames/authored.kicad_wks").read_bytes() == WORKSHEET
    expected = json.loads(source.read_text())
    actual = json.loads(output.read_text())
    for kind in ("pcbnew", "schematic"):
        assert actual[kind]["page_layout_descr_file"] == expected[kind]["page_layout_descr_file"]
    assert snapshot(source.parent) == original
    proof = run(
        "verify-source",
        str(code / "design.py"),
        "--against",
        str(source),
        "--levels",
        "1,2,3,4,5,6,7,8,S",
        "--kicad-version",
        str(target),
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert proof.exit_code == 0, (proof.error, proof.result)
    assert proof.result["differences"] == [] and proof.result["accepted"] == []


def test_changed_resource_invalidates_import_and_build_plans(tmp_path) -> None:
    source = source_with_resource(tmp_path, 10, "pcbnew")
    code = imported(tmp_path, source)
    output = tmp_path / "new-build"
    args = ("build", str(code / "design.py"), "--out", str(output))
    planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    stored = plans.load(state_dir(), planned.result["plan_id"])
    resource = code / "native/frames/authored.kicad_wks"
    assert stored is not None
    assert (
        resource.relative_to(tmp_path).as_posix(),
        hashlib.sha256(WORKSHEET).hexdigest(),
    ) in stored.depends
    resource.write_bytes(WORKSHEET + b" ")
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert confirmed.exit_code == 4 and confirmed.error["code"] == "FEN-4002"
    assert not output.exists()
    import_args = ("import", str(source), "--to", "python", "--out", "changed-import")
    planned = run(*import_args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    (source.parent / "frames/authored.kicad_wks").write_bytes(WORKSHEET + b" ")
    confirmed = run(
        *import_args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, timestamp=STAMP
    )
    assert confirmed.exit_code == 4 and confirmed.error["code"] == "FEN-4002"
    assert not (tmp_path / "changed-import").exists()


def test_distinct_pcb_and_schematic_resources_remain_distinct(tmp_path) -> None:
    source = source_with_resource(tmp_path, 10, "pcbnew")
    other = WORKSHEET.replace(b"AUTHORED FRAME", b"AUTHORED SCHEMATIC")
    (source.parent / "frames/schematic.kicad_wks").write_bytes(other)
    data = json.loads(source.read_text())
    data["schematic"]["page_layout_descr_file"] = "frames/schematic.kicad_wks"
    source.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    original = snapshot(source.parent)
    code = imported(tmp_path, source)
    assert (code / "native/frames/schematic.kicad_wks").read_bytes() == other
    output = built(tmp_path, code)
    made = json.loads(output.read_text())
    assert made["pcbnew"]["page_layout_descr_file"] == "${KIPRJMOD}/frames/authored.kicad_wks"
    assert made["schematic"]["page_layout_descr_file"] == "frames/schematic.kicad_wks"
    assert (output.parent / "frames/authored.kicad_wks").read_bytes() == WORKSHEET
    assert (output.parent / "frames/schematic.kicad_wks").read_bytes() == other
    assert snapshot(source.parent) == original
