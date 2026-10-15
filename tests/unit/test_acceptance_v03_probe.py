# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A prepared or failed acceptance never becomes an equal oracle probe."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper():
    spec = importlib.util.spec_from_file_location(
        "acceptance_probe_unit", ROOT / "tests" / "kicad" / "acceptance" / "_v03acceptance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "passed,complete,mode,expected",
    [
        (True, True, "full", "equal"),
        (False, True, "full", "different"),
        (True, False, "full", "different"),
        (True, True, "prepare", "different"),
    ],
)
def test_probe_requires_completed_external_acceptance(monkeypatch, passed, complete, mode, expected):
    module = helper()
    monkeypatch.setattr(
        module, "result", lambda: {"passed": passed, "acceptance_complete": complete, "mode": mode}
    )
    assert module.outcome() == expected


def test_measured_expected_outcome_is_ten_only() -> None:
    ten = json.loads((ROOT / "docs/evidence/kicad/probes/10.0.6.json").read_text(encoding="utf-8"))
    assert ten["probes"]["acceptance-v03"] == "equal"
    for path in (ROOT / "docs/evidence/kicad/probes").glob("9*.json"):
        assert "acceptance-v03" not in json.loads(path.read_text(encoding="utf-8"))["probes"]
