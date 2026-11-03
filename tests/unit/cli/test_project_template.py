# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plan/input binding and opt-in native-project ownership at the public CLI (c0351)."""

from __future__ import annotations

import hashlib
import json

import pytest
from _project_template import SETTINGS, STAMP, authored, built, imported, snapshot

from fenolite.api import run
from fenolite.cli import plans
from fenolite.core.state import state_dir


def test_declared_template_is_read_and_a_stale_review_changes_nothing(tmp_path) -> None:
    source = authored(tmp_path / "original")
    code = imported(tmp_path, source)
    output = tmp_path / "built"
    args = ("build", str(code / "design.py"), "--out", str(output))
    planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    staged = plans.load(state_dir(), planned.result["plan_id"])
    template = code / "native/project.kicad_pro"
    assert staged is not None
    assert (
        template.relative_to(tmp_path).as_posix(),
        hashlib.sha256(template.read_bytes()).hexdigest(),
    ) in staged.depends
    assert not output.exists()
    template = code / "native/project.kicad_pro"
    template.write_bytes(template.read_bytes() + b" ")
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path, timestamp=STAMP)
    assert confirmed.exit_code == 4 and confirmed.error["code"] == "FEN-4002"
    assert not output.exists()
    reviewed_again = run(*args, "--dry-run", cwd=tmp_path, timestamp=STAMP)
    assert reviewed_again.exit_code == 3 and reviewed_again.error["code"] == "FEN-3004"
    assert "digest" in reviewed_again.error["message"] and not output.exists()


@pytest.mark.parametrize("lossy", [False, True])
def test_altium_refuses_the_explicit_native_project_before_staging(lossy, tmp_path) -> None:
    source = authored(tmp_path / "original")
    code = imported(tmp_path, source)
    args = ("--allow-lossy",) if lossy else ()
    refused = run(
        "build",
        str(code / "design.py"),
        "--out",
        "altium",
        "--target",
        "altium",
        "--dry-run",
        *args,
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert refused.exit_code == 7 and refused.error["code"] == "FEN-7001"
    assert "native/project.kicad_pro" in refused.error["where"]
    assert not (tmp_path / "altium").exists() and "plan_id" not in (refused.result or {})


def test_opted_in_template_is_authoritative_over_unmanaged_rebuild_edits(tmp_path) -> None:
    source = authored(tmp_path / "original")
    code = imported(tmp_path, source)
    template_before = snapshot(code)
    output = built(tmp_path, code)
    data = json.loads(output.read_text())
    data["schematic"]["drawing"].update({"intersheets_ref_show": False, "intersheets_ref_prefix": "WRONG"})
    data["board"]["design_settings"]["rules"]["min_via_annular_width"] = 0.01
    data["authored_output_only"] = True
    output.write_text(json.dumps(data))
    rebuilt = built(tmp_path, code)
    data = json.loads(rebuilt.read_text())
    assert {key: data["schematic"]["drawing"][key] for key in SETTINGS} == SETTINGS
    assert data["board"]["design_settings"]["rules"]["min_via_annular_width"] == 0.19
    assert "authored_output_only" not in data
    assert snapshot(code) == template_before
