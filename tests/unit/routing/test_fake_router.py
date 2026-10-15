# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sleeping/failing fake processes record their launch without loading the model."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from _fakerouter import create_fake_router


@pytest.mark.parametrize("mode", ["fail", "sleep"])
def test_fake_router_records_failure_without_importing_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    checkout = create_fake_router(tmp_path)
    blocked = tmp_path / "unavailable-model" / "fenolite"
    blocked.mkdir(parents=True)
    (blocked / "__init__.py").write_text(
        "# SPDX-License-Identifier: Apache-2.0\n"
        "# Copyright (c) 2026 Fenolite contributors\n"
        "raise RuntimeError('the model must not load for this mode')\n",
        encoding="utf-8",
    )
    source = tmp_path / "input.kicad_pcb"
    source.write_text("authored test input, not a parsed board", encoding="utf-8")
    output = tmp_path / "output.kicad_pcb"
    runs = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(blocked.parent))
    monkeypatch.setenv("FAKE_ROUTER_MODE", mode)
    monkeypatch.setenv("FAKE_ROUTER_SLEEP", "0.01")
    monkeypatch.setenv("FAKE_ROUTER_FAIL_NET", "A1")
    monkeypatch.setenv("FAKE_ROUTER_RUNS", str(runs))
    done = subprocess.run(
        [sys.executable, str(checkout / "py_router" / "route.py"), str(source), str(output), "--nets", "A1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert done.returncode == 2
    assert "boom from fake router" in done.stderr
    assert not output.exists()
    (launch,) = [json.loads(line) for line in runs.read_text(encoding="utf-8").splitlines()]
    assert launch["nets"] == ["A1"] and launch["board"] == source.read_text(encoding="utf-8")
