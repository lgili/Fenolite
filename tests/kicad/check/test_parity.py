# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic parity in the DRC run, on the running major (capability kicad-oracle, "Parity in the DRC run";
verification-loop, "Parity findings"; ``H-K-PARITY-RUN``; change c0062)."""

from __future__ import annotations

from pathlib import Path

import _erccases as cases
import pytest
from _checkrun import check, stage
from _probes import major, run
from _projects import built_blink_project

from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set

PARITY_CODES = ("net-conflict", "missing-footprint", "extra-footprint", "footprint-symbol-mismatch")

pytestmark = pytest.mark.needs_kicad


def test_flag_fills_the_parity_list() -> None:
    assert run("drc-parity-flag") == "present"
    report = cases.conflict_run(True).report
    assert report is not None
    assert "net_conflict" in cases.parity_types(report)
    assert {v.severity for v in report.schematic_parity} <= {"error", "warning"}


def test_no_flag_no_parity() -> None:
    assert run("drc-parity-noflag") == "absent"
    report = cases.conflict_run(False).report
    assert report is not None and report.schematic_parity == ()


def test_canary_does_not_change_parity() -> None:
    assert run("drc-parity-canary") == "equal"


def test_unloadable_schematic() -> None:
    """Both majors write no report at all when the flag is passed and the schematic does not load."""
    assert run("drc-parity-unloadable") == "absent"
    failed = cases.unloadable_parity()
    assert failed.report is None and failed.run.returncode not in (0, None)
    assert failed.run.stderr.strip()


# -- the product path: ``KicadOracle.drc`` and ``fenolite check`` (verification-loop, "Parity findings")


def test_built_project_in_agreement(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink", target=major())
    _, env, _, err = check(root, "--stages", "drc.kicad")
    assert env, err
    summary = stage(env, "drc.kicad")["summary"]
    assert summary["parity_judged"] is True and summary["parity"] == 0
    assert not [i for i in env["issues"] if i["code"].removeprefix("kicad.drc.") in PARITY_CODES]
    assert not [i for i in env["issues"] if i["code"] == "kicad.drc.parity-unchecked"]


def test_built_pad_on_another_net(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink", target=major())
    (root / cases.BOARD).write_bytes(cases.conflict_files()[cases.BOARD])
    _, env, _, err = check(root, "--stages", "drc.kicad")
    assert env, err
    summary = stage(env, "drc.kicad")["summary"]
    assert summary["parity_judged"] is True and summary["parity"] >= 1
    conflicts = [i for i in env["issues"] if i["code"] == "kicad.drc.net-conflict"]
    assert conflicts and "R1-2" in [i["where"] for i in conflicts]
    assert summary["types"]["kicad.drc.net-conflict"] == "net_conflict"
    assert {i["severity"] for i in conflicts} <= {"warning", "error"}


def test_oracle_passes_the_flag_and_strips_the_canary(tmp_path: Path) -> None:
    """The product run on the board that disagrees: the parity entries of the counted report are those of
    a plain flagged run, the canary fired, and no parity entry names a canary track."""
    root = cases.write(cases.conflict_files(), tmp_path / "blink")
    outcome = KicadOracle(cases.runner()).drc(project_set(root))
    plain = cases.conflict_run(True).report
    assert outcome.report is not None and plain is not None
    assert outcome.parity_judged is True and outcome.canary == "fired"
    assert cases.parity_entries(outcome.report) == cases.parity_entries(plain) != []


def test_oracle_unloadable_schematic_keeps_the_copper_verdict(tmp_path: Path) -> None:
    root = cases.write(cases.unloadable(cases.blink_files(major())), tmp_path / "blink")
    outcome = KicadOracle(cases.runner()).drc(project_set(root))
    assert outcome.report is not None and outcome.parity_judged is False
    assert outcome.canary == "fired" and outcome.message
    assert outcome.report.schematic_parity == ()
