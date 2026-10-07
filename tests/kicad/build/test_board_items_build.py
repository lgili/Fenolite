# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A built project with a keep-out, a label and a dimension in KiCad (capability design-dsl, "Board items
in a build", scenario "Blink with a keep-out, a label and a dimension"; verification-loop, "Keep-out issue
code", scenario "Check fails on copper in a keep-out"; change c0103)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import _buildcases as bc
import _checkrun
import _rulebench as rb
import pytest
from _build_judge import baseline_outcome
from _buildhelp import blink, build
from _probes import major

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.boarditems import item_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, mm

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
ROOT = Path(__file__).resolve().parents[3]
ROUTED = ROOT / "examples" / "blink_routed"
ANCHOR = "# Stitching vias every 5 mm"
OVER_TRACK = "[(mm(15), mm(6)), (mm(25), mm(6)), (mm(25), mm(8)), (mm(15), mm(8))]"
KEEPOUT = f'design.rule_area("ANT", {OVER_TRACK}, layers=("F.Cu",), forbid=("tracks",))\n'
"""A keep-out over the script track of ``LED_DRV`` that runs along y = 7 mm."""


def variant() -> Design:
    design = blink()
    corners = [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))]
    design.rule_area("ANT", corners, forbid=("tracks", "vias"))
    design.text("rev", "REV A", (mm(2), mm(2)))
    design.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))
    return design


@pytest.mark.parametrize("target", TARGETS)
def test_board_items_blink_builds_clean(target: int) -> None:
    """The variant loads, its DRC holds no error, and the rules file is loaded (the canary fires)."""
    output = build(variant(), target)
    assert not [i for i in output.issues if i.severity == "error"]
    files = bc._files(output)  # noqa: SLF001
    assert bc.loads(files, "blink.kicad_pcb")
    plain = bc.drc(files, "blink.kicad_pcb")
    assert baseline_outcome(plain.report, excepted=bc.BASELINE_EXCEPTIONS) == "absent"
    assert plain.report is not None
    natives = {
        item_uuid(derived_id(prefix, "dsl", key))
        for prefix, key in (("kpo", "area:ANT"), ("txt", "text:rev"), ("dim", "dimension:width"))
    }
    named = {(v.type, v.severity) for v in plain.report.violations if natives & {i.uuid for i in v.items}}
    # the centred label 2 mm from the corner reaches the board edge: KiCad warns, and reports no error
    assert named <= {("silk_edge_clearance", "warning")}, named
    canary = dict(files)
    canary["blink.kicad_dru"] = rb.with_canary(output.files["blink.kicad_dru"].decode("utf-8"))
    loaded = bc.drc(canary, "blink.kicad_pcb")
    assert loaded.report is not None and any(v.type == "clearance" for v in loaded.report.violations)
    board = read_board(output.files["blink.kicad_pcb"].decode("utf-8")).board
    assert board is not None
    assert {k.native_ids["kicad"] for k in board.keepouts} | {t.native_ids["kicad"] for t in board.texts} | {
        d.native_ids["kicad"] for d in board.dimensions
    } == natives


def _cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}


def test_board_items_check_fails_on_copper_in_a_keep_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Check fails on copper in a keep-out": the build writes with ``--copper-check warn``, and
    ``check`` reports the track in both stages: ``copper.keepout`` and KiCad's ``items_not_allowed``."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    root = tmp_path / "repo"
    shutil.copytree(ROUTED, root / "examples" / "blink_routed")
    shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
    script = root / "examples" / "blink_routed" / "design.py"
    text = script.read_text(encoding="utf-8")
    assert ANCHOR in text
    script.write_text(text.replace(ANCHOR, KEEPOUT + ANCHOR), encoding="utf-8")
    out = tmp_path / "B"
    target = str(major())
    code, env = _cli(monkeypatch, "--kicad-version", target, "build", str(script), "--out", str(out),
                     "--copper-check", "warn", "--confirm")  # fmt: skip
    assert code == 0, env.get("issues")
    code, env, _stdout, stderr = _checkrun.check(out)
    assert code == 5, stderr
    (found,) = [i for i in env["issues"] if i["code"] == "copper.keepout"]
    assert found["severity"] == "error" and "ANT" in found["message"] and "LED_DRV" in found["message"]
    drc = [i for i in env["issues"] if i["code"].endswith("drc.items-not-allowed")]
    assert [i["severity"] for i in drc] == ["error"]
    assert found["where"] == f"{drc[0]['where']}, ANT"  # the same track, by its locator
    board = read_board((out / "blink_routed.kicad_pcb").read_text(encoding="utf-8"), file="b.kicad_pcb").board
    assert board is not None
    (track,) = [t for t in board.tracks if t.provenance and t.provenance.locator == drc[0]["where"]]
    assert track.layer == "F.Cu" and track.start.y == track.end.y == 107_000_000
