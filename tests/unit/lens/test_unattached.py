# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Creation warnings use user locations and do not fail successful builds."""

import statistics
import time
from pathlib import Path
from unittest.mock import patch

from fenolite.api import run
from fenolite.cli._script import run_design_script


def test_lost_and_quiet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Part, Net, mm\n"
        'design = Design("unattached")\n'
        "design.board(mm(20), mm(10))\n"
        'r = Part("R5", "Fenolite:Resistor")\n'
        'spare = Net("SPARE")\n'
    )
    reply = run("build", str(script), "--out", str(tmp_path / "out"), "--dry-run")
    assert reply.exit_code == 0, reply.error
    lost = [i for i in reply.envelope["issues"] if i["code"] == "build.unattached"]
    assert [i["where"] for i in lost] == ["design.py:line:4", "design.py:line:5"]
    assert "R5" in lost[0]["message"] and "SPARE" in lost[1]["message"]
    minimal = Path("src/fenolite/dsl/_minimal.py").resolve()
    reply = run("build", str(minimal), "--out", str(tmp_path / "quiet"), "--dry-run")
    assert reply.exit_code == 0, reply.error
    assert not [i for i in reply.envelope["issues"] if i["code"] == "build.unattached"]


def test_cost_largest_example():
    root = Path(__file__).resolve().parents[3]
    script = max((root / "examples").rglob("*.py"), key=lambda p: len(p.read_bytes()))
    enabled, disabled = [], []
    for _ in range(3):
        start = time.perf_counter()
        tracked = run_design_script(script)
        enabled.append(time.perf_counter() - start)
        with (
            patch("fenolite.dsl.part.record", lambda *a: None),
            patch("fenolite.dsl.interfaces.record", lambda *a: None),
        ):
            start = time.perf_counter()
            untracked = run_design_script(script)
            disabled.append(time.perf_counter() - start)
        assert len(tracked.design.parts) == len(untracked.design.parts)
    print(
        f"{script.relative_to(root)}: {len(tracked.design.parts)} parts; "
        f"median enabled={statistics.median(enabled):.6f}s, disabled={statistics.median(disabled):.6f}s"
    )
