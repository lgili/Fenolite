# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Critical routes on the reference boards judged by the running ``kicad-cli`` (change c0244; capability
net-roles, "Open reference variants"; hypothesis ``H-K-CRIT-DRC``): each ``open`` variant is built for the
tool's major, its inferred groups are confirmed, and ``fenolite route --router octilinear --roles critical
--gate drc`` routes it. The gate drops nothing and finds nothing new, the reply is ``KICAD-VERIFIED``, and
KiCad's DRC of the written board has no violation type with more entries than the board before.

``kicad-cli`` 9 refills no zone (c0222's ``test_reference_drc.py``), so on 9 the board carries the fill of
the unit tests (``fill_as_outline``) before it is routed, as a user's board carries KiCad's own fill; 10
refills the zones in the gate."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import runner
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "roles"))
from _roleboards import EXAMPLES, Built, fill_as_outline  # noqa: E402

pytestmark = pytest.mark.needs_kicad
BOARDS = ("buck_shunt", "half_bridge", "bms")


def _fenolite(*args: str) -> tuple[int, dict[str, Any], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), stderr.getvalue()


def _build(board: str, out: Path) -> Built:
    major = kicad_cli_major()
    assert major is not None
    script = EXAMPLES / board / "open.py"
    code, env, err = _fenolite(
        "build", str(script), "--out", str(out), "--kicad-version", str(major), "--confirm"
    )
    assert code == 0, (env, err)
    built = Built(out, out / f"{board}_open.kicad_pcb")
    if major < 10:
        built.board.write_text(fill_as_outline(built.board.read_text(encoding="utf-8")), encoding="utf-8")
    code, _, err = _fenolite("roles", str(built.board), "--accept-all", "--confirm")
    assert code == 0, err
    return built


def _drc(board: Path) -> Counter[str]:
    report = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    return Counter(item.type for item in report.report.violations if not item.excluded)


@pytest.mark.parametrize("board", BOARDS)
def test_critical_routes_pass_drc(tmp_path: Path, board: str) -> None:
    """``H-K-CRIT-DRC``: the gate drops nothing and no violation type grows."""
    cli = kicad_cli()
    assert cli is not None
    built = _build(board, tmp_path / "out")
    before = _drc(built.board)
    route = ("route", str(built.board), "--router", "octilinear", "--roles", "critical", "--gate", "drc")
    code, env, err = _fenolite(*route, "--kicad-cli", cli, "--dry-run")
    assert code == 0, err
    gate = env["result"]["gate"]
    assert gate["dropped"] == [] and gate["findings"] == [], gate
    assert env["evidence"]["level"] == "KICAD-VERIFIED", env["evidence"]
    assert not [e for e in env["result"]["roles"] if e["reason"] == "drc"]
    code, _, err = _fenolite(*route, "--kicad-cli", cli, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, err
    after = _drc(built.board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)
