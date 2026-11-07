# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source code and native project preserve exact approximation configuration (c0340)."""

from __future__ import annotations

import shutil
from pathlib import Path

import _drawn_fonts
import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot

from fenolite import api
from fenolite.backends.kicad import pro
from fenolite.backends.kicad.lowering import millimetres


@pytest.mark.parametrize("target", (9, 10))
def test_project_curve_error_survives_full_proof_and_changed_setting_is_found(
    target: int, tmp_path: Path
) -> None:
    source = _drawn_fonts.original(tmp_path / "original", target=target)
    project = source / "font_probe.kicad_pro"
    data = pro.read_project_text(project.read_text())
    data["board"]["design_settings"]["rules"]["max_error"] = millimetres(10_000)
    project.write_text(pro.write_project_text(data))
    before = snapshot(source)
    output = tmp_path / "roundtrip"
    reply = roundtrip(source, output)
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["accepted"] == reply.result["differences"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    built = pro.read_project_text((output / "built/font_probe.kicad_pro").read_text())
    assert pro.project_curve_error(built) == 10_000
    script = output / "code/design.py"
    text = script.read_text()
    assert text.count('max_curve_error=mm("0.01")') == 1
    script.write_text(text.replace('max_curve_error=mm("0.01")', 'max_curve_error=mm("0.02")'))
    changed = api.run("verify-source", str(script), "--against", str(source), cwd=tmp_path, seed=0)
    assert changed.exit_code == 5, changed.error
    assert changed.result["accepted"] == []
    assert [
        (item["kind"], item["field"], item["a"], item["b"]) for item in changed.result["differences"]
    ] == [("rule-field", "max_curve_error", "10000", "20000")]
    cloned = tmp_path / "edited-fresh-input"
    shutil.copytree(script.parent, cloned)
    fresh = api.run(
        "verify-source", str(cloned / "design.py"), "--against", str(source), cwd=tmp_path, seed=0
    )
    assert fresh.exit_code == 5, fresh.error
    assert fresh.result["differences"] == changed.result["differences"]
    assert fresh.result["accepted"] == []
    assert snapshot(source) == before


def test_record_tracks_adjacent_project_and_generated_reads(tmp_path: Path) -> None:
    source = _drawn_fonts.original(tmp_path / "original", target=9)
    output = tmp_path / "roundtrip"
    reply = roundtrip(source, output)
    assert reply.exit_code == 0
    script = output / "code/design.py"
    args = ("verify-source", str(script), "--against", str(source / "font_probe.kicad_pcb"), "--record")
    planned = api.run(*args, "--dry-run", cwd=tmp_path, seed=0)
    assert planned.exit_code == 0, planned.error
    assert "font_probe.kicad_pro" in planned.result["against"]["files"]
    assert "font_probe.kicad_pro" in planned.result["build"]["read_files"]
    target = output / "code/PROVENANCE.json"
    untouched = target.read_bytes()
    # A byte-only change to an actual project input invalidates the reviewed record plan.
    project = source / "font_probe.kicad_pro"
    project.write_bytes(project.read_bytes() + b"\n")
    stale = api.run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, seed=0)
    assert stale.exit_code == 4 and stale.error and stale.error["code"] == "FEN-4002"
    assert target.read_bytes() == untouched
