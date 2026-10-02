# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0011's blink, built by ``fenolite build`` and checked by ``fenolite check`` (capability
verification-loop, scenario "Built blink is clean")."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from _checkrun import check, stage
from _probes import major
from _projects import tree_snapshot

pytestmark = pytest.mark.needs_kicad
DESIGN = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def test_built_blink_is_clean(tmp_path: Path) -> None:
    out = tmp_path / "blink"
    build = [sys.executable, "-m", "fenolite", "build", str(DESIGN), "--out", str(out),
             "--kicad-version", str(major()), "--confirm", "--json"]  # fmt: skip
    built = subprocess.run(build, cwd=tmp_path, capture_output=True, text=True, timeout=600, check=False)
    assert built.returncode == 0, built.stderr
    before = tree_snapshot(out)
    code, env, _, err = check(out)
    assert code == 0, (env.get("issues"), err)
    assert [s["name"] for s in env["result"]["stages"]] == [
        "model.validate",
        "erc.lite",
        "drc.kicad",
        "roundtrip",
    ]
    assert env["result"]["project"]["built"] is True
    assert stage(env, "erc.lite")["status"] == "ok"
    drc = stage(env, "drc.kicad")["summary"]
    assert drc["canary"] == "fired" and drc["violations_judged"] is False
    assert stage(env, "roundtrip")["status"] == "ok"
    assert tree_snapshot(out) == before
