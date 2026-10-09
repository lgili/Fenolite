# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0011's blink and c0013's authored built project, checked by ``fenolite check`` (capability
verification-loop: scenario "Built blink before routing" and requirement "Built examples have no assignment
differences", v0.1 acceptance item 1 in part). The boards are unrouted, so their unconnected items are
error findings; what is claimed is that they are located and that the pad nets agree."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _checkrun import check, stage
from _probes import major
from _projects import authored_project, tree_snapshot

pytestmark = pytest.mark.needs_kicad
DESIGN = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"
REF_PIN = re.compile(r"^[A-Za-z]+[0-9]+-[0-9A-Za-z]+$")
DEFAULT = [
    "model.validate",
    "erc.kicad",
    "copper.clearance",
    "length.rules",
    "placement.rules",
    "zone.fill",
    "drc.kicad",
    "parity",
    "netlist.assignment_compare",
    "roundtrip",
]
UNWANTED = ("unmatched-record", "net-label-ambiguous")


def _targets() -> list[int]:
    """The targets the running major loads: 9 on 9.0.9; 9 and 10 on 10.0.6."""
    return [target for target in (9, 10) if target <= major()]


def _blink(tmp_path: Path, target: int) -> Path:
    out = tmp_path / f"blink-{target}"
    build = [sys.executable, "-m", "fenolite", "build", str(DESIGN), "--out", str(out),
             "--kicad-version", str(target), "--confirm", "--json"]  # fmt: skip
    built = subprocess.run(build, cwd=tmp_path, capture_output=True, text=True, timeout=600, check=False)
    assert built.returncode == 0, built.stderr
    return out


def _assert_assignment_clean(env: dict[str, Any], *, pairs: int) -> None:
    compare = stage(env, "netlist.assignment_compare")
    assert compare["status"] == "ok", env["issues"]
    found = compare["summary"]["pairs"]
    assert len(found) == pairs and all(p["differences"] == 0 and p["common"] > 0 for p in found)
    assert [(p["a"], p["b"]) for p in found][-1] == ("board", "export")
    uncovered = [i["message"] for i in env["issues"] if i["code"] == "netlist.uncovered"]
    assert not [m for m in uncovered if any(reason in m for reason in UNWANTED)], uncovered
    assert not [i for i in env["issues"] if i["code"] == "netlist.assignment-differs"]


def _assert_unconnected_located(env: dict[str, Any]) -> None:
    unconnected = [i for i in env["issues"] if i["code"] == "kicad.drc.unconnected-items"]
    assert unconnected, "an unrouted board has unconnected items"
    for issue in unconnected:
        assert all(REF_PIN.match(part) for part in issue["where"].split(", ")), issue["where"]


def test_built_blink_before_routing(tmp_path: Path) -> None:
    for target in _targets():
        out = _blink(tmp_path, target)
        before = tree_snapshot(out)
        _, env, _, err = check(out)
        assert env, err
        assert [s["name"] for s in env["result"]["stages"]] == DEFAULT
        assert env["result"]["project"]["built"] is True
        erc = stage(env, "erc.kicad")  # KiCad's ERC of the schematic the build wrote (change c0062)
        assert erc["status"] == "ok" and erc["summary"]["violations"] == 0, env["issues"]
        assert erc["summary"]["sheets"] == 1 and erc["evidence"]["oracle"].startswith("kicad-cli ")
        drc = stage(env, "drc.kicad")["summary"]
        assert drc["canary"] == "fired" and drc["violations_judged"] is True
        assert drc["parity_judged"] is True and drc["parity"] == 0  # the board agrees with its schematic
        assert stage(env, "roundtrip")["status"] == "ok"
        _assert_unconnected_located(env)
        assert tree_snapshot(out) == before


def test_assignment_blink(tmp_path: Path) -> None:
    for target in _targets():
        _, env, _, err = check(_blink(tmp_path, target))
        assert env, err
        _assert_assignment_clean(env, pairs=3)  # with (model, schematic) since c0063


def test_assignment_authored_built_project(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=major(), built=True)
    _, env, _, err = check(root)
    assert env, err
    _assert_assignment_clean(env, pairs=2)
    _assert_unconnected_located(env)
