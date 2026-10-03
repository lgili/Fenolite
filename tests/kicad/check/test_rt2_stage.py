# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The RT2 stage on the running ``kicad-cli`` (capability verification-loop, "RT2 stage", scenario "Real
runs on both majors"): normalised by ``pcb upgrade`` on 10.0, compared as written on 9.0."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkrun import check, stage
from _probes import major
from _projects import authored_project, native_project, tree_snapshot

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("kind", ["native", "built"])
def test_real_runs(tmp_path: Path, kind: str) -> None:
    root = (
        native_project(tmp_path)
        if kind == "native"
        else authored_project(tmp_path, major=major(), built=True)
    )
    before = tree_snapshot(root)
    code, env, _, err = check(root, "--stages", "roundtrip.rt2")
    assert env, err
    rt2 = stage(env, "roundtrip.rt2")
    assert code == 0 and rt2["status"] == "ok", env["issues"]
    assert rt2["summary"]["holds"] is True and rt2["summary"]["differences"] == 0
    assert rt2["summary"]["normalised"] is (major() >= 10)
    assert rt2["summary"]["before"] == rt2["summary"]["after"] or rt2["summary"]["unstable"] > 0
    assert [s["name"] for s in env["result"]["stages"]] == ["roundtrip.rt2"]
    assert tree_snapshot(root) == before
