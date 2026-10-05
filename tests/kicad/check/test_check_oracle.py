# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` with the running ``kicad-cli`` (capability verification-loop: "Check is read-only",
"DRC stage and the rules canary", "Evidence per check stage" and "Check output is deterministic"). Every
project is assembled in ``tmp_path``, so the ``kicad-9`` job needs no corpus."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _checkrun import check, stage, without_elapsed
from _probes import major, version
from _projects import STEM, authored_project, native_project, tree_snapshot

from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad.canary import CANARY_TWO_RUN
from fenolite.checks import STAGE_ORDER
from fenolite.core.evidence import Evidence

pytestmark = pytest.mark.needs_kicad
RULES = Path(__file__).resolve().parents[2] / "data" / "kicad" / "rules"


def _projects(tmp_path: Path) -> dict[str, Path]:
    return {
        "built": authored_project(tmp_path / "a", major=major(), built=True),
        "native": native_project(tmp_path / "b"),
        "broken": authored_project(tmp_path / "c", major=major(), built=True, rules="broken"),
    }


def test_read_only(tmp_path: Path) -> None:
    for name, root in _projects(tmp_path).items():
        before = tree_snapshot(root)
        _, env, _, err = check(root)
        assert env, (name, err)
        assert tree_snapshot(root) == before, name
        assert not (root / ".fenolite").exists() or name != "native"
        writes = stage(env, "drc.kicad")["summary"]["tool_writes"]
        if major() >= 10:  # 9.0.9 writes no .kicad_prl in a pcb drc run (H-K-PRO-PRL)
            assert f"{STEM}.kicad_prl" in writes, (name, writes)


def test_canary(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=major(), built=True)
    _, env, _, err = check(root)
    assert env, err
    drc = stage(env, "drc.kicad")
    assert drc["summary"]["canary"] == "fired"
    # in a two-run major the counted report comes from the plain run, so nothing is stripped from it
    assert (drc["summary"]["canary_removed"] == 0) == (major() in CANARY_TWO_RUN)
    assert drc["summary"]["violations_judged"] is True
    # no count and no issue includes a canary item
    findings = [i for i in env["issues"] if i["code"].startswith("kicad.drc.")]
    assert len(findings) == drc["summary"]["violations"] + drc["summary"]["unconnected"]
    assert not [i for i in findings if "FENOLITE_CANARY" in i["message"]]
    combined = Evidence.combine(drcmod.EVIDENCE, oraclemod.EVIDENCE)
    assert drc["evidence"]["level"] == combined.level.value
    assert drc["evidence"]["oracle"] == f"kicad-cli {version()}"
    assert [s["name"] for s in env["result"]["stages"]] == [
        "model.validate",
        "erc.kicad",
        "copper.clearance",
        "zone.fill",
        "drc.kicad",
        "parity",
        "netlist.assignment_compare",
        "roundtrip",
    ]


def test_rules_not_loaded_built(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=major(), built=True, rules="broken")
    code, env, _, _ = check(root)
    errors = [i["code"] for i in env["issues"] if i["severity"] == "error"]
    assert code == 5 and "kicad.drc.rules-not-loaded" in errors
    assert all(code.startswith("kicad.drc.") for code in errors)  # every other error is a DRC finding


def test_rules_not_loaded_native(tmp_path: Path) -> None:
    root = native_project(tmp_path, rules="broken")
    code, env, _, _ = check(root)
    found = [i for i in env["issues"] if i["code"] == "kicad.drc.rules-not-loaded"]
    assert [i["severity"] for i in found] == ["info"]
    assert (code == 5) == any(i["severity"] == "error" for i in env["issues"])
    assert stage(env, "drc.kicad")["evidence"]["level"] == "UNVERIFIED"


def test_rules_without_a_project_file(tmp_path: Path) -> None:
    root = native_project(tmp_path, rules=None)
    (root / f"{STEM}.kicad_pro").unlink()
    shutil.copyfile(RULES / "units.kicad_dru", root / f"{STEM}.kicad_dru")
    _, env, _, _ = check(root)
    assert "kicad.drc.rules-not-loaded" in [i["code"] for i in env["issues"]]
    assert stage(env, "drc.kicad")["summary"]["canary"] == "not-applicable"


def test_deterministic(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=major(), built=True)
    every = ("--stages", ",".join(STAGE_ORDER))
    first, second = check(root, *every)[2], check(root, *every)[2]
    assert [s["name"] for s in json.loads(first)["result"]["stages"]] == list(STAGE_ORDER)
    assert without_elapsed(first) == without_elapsed(second)
    for forbidden in ("<tmp>", str(Path.home()), str(tmp_path), str(root)):
        assert forbidden not in first, forbidden
