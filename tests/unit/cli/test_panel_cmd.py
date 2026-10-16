# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite panel`` (capability cli-contract, "Panel command"; change c0173)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from _panels import PANELS, committed_board, run, script_for


def _plan(envelope: dict[str, object], out: Path) -> list[str]:
    result = envelope["result"]
    assert isinstance(result, dict)
    return sorted(Path(p["path"]).relative_to(out).as_posix() for p in result.get("plan", []))


@pytest.fixture(autouse=True)
def _cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_dry_run_of_a_panel(tmp_path: Path) -> None:
    out = tmp_path / "P"
    code, env, err = run("panel", str(PANELS / "tabs.py"), "--out", str(out), "--target", "10", "--dry-run")
    assert code == 0, err
    plan = _plan(env, out)
    assert {"tabs.kicad_pcb", "tabs.kicad_pro", "tabs.panel.json", "fp-lib-table"} <= set(plan)
    assert "lib/Fenolite_Panel.pretty/MouseBites_5x0.6mm_P1mm.kicad_mod" in plan
    assert "lib/Fenolite_Assembly.pretty/ToolingHole_3mm.kicad_mod" in plan
    result = env["result"]
    assert isinstance(result, dict)
    panel = result["panel"]
    assert panel["copies"] == 8 and (panel["rows"], panel["cols"]) == (2, 4) and panel["form"] == "kicad"
    assert panel["size"] == {"w": 180_000_000, "h": 76_000_000}
    assert not out.exists()
    evidence = env["evidence"]
    assert isinstance(evidence, dict) and evidence["level"] == "KICAD-VERIFIED"


def test_confirm_writes_the_plan(tmp_path: Path) -> None:
    out = tmp_path / "P"
    code, env, err = run("panel", str(PANELS / "mixed.py"), "--out", str(out), "--target", "10", "--confirm")
    assert code == 0, err
    assert (out / "mixed.kicad_pcb").is_file() and (out / "mixed.panel.json").is_file()
    receipt = env["receipt"]
    assert isinstance(receipt, dict)
    written = {Path(w["path"]).relative_to(out).as_posix() for w in receipt["written"]}
    assert {"mixed.kicad_pcb", "mixed.panel.json", ".fenolite/mixed.panel-written.json"} <= written
    again = run("panel", str(PANELS / "mixed.py"), "--out", str(out), "--target", "10", "--confirm")
    assert again[0] == 0, again[2]


def test_error_findings_plan_no_write(tmp_path: Path) -> None:
    out = tmp_path / "P"
    code, env, _ = run("panel", str(PANELS / "vscore.py"), "--out", str(out), "--target", "10", "--dry-run")
    assert code == 5
    issues = env["issues"]
    assert isinstance(issues, list)
    assert [i["code"] for i in issues if i["severity"] == "error"] == ["panel.vscore-copper"] * 2
    assert _plan(env, out) == []


def test_embedded_form_while_the_gate_is_off(tmp_path: Path) -> None:
    out = tmp_path / "P"
    args = (
        "panel",
        str(PANELS / "tabs.py"),
        "--out",
        str(out),
        "--target",
        "altium",
        "--altium-panel",
        "embedded",
    )
    code, _, err = run(*args, "--dry-run")
    assert code == 7 and "FEN-7001" in err and "--altium-panel flat" in err
    assert not out.exists()


def test_usage_errors(tmp_path: Path) -> None:
    out = str(tmp_path / "P")
    code, _, err = run(
        "panel",
        str(PANELS / "tabs.py"),
        "--out",
        out,
        "--target",
        "10",
        "--altium-panel",
        "flat",
        "--dry-run",
    )
    assert code == 2 and "FEN-2001" in err
    code, _, err = run("panel", str(PANELS / "tabs.py"), "--out", out, "--target", "9", "--dry-run")
    assert code == 2 and "KiCad 10" in err
    code, _, err = run("panel", str(tmp_path / "none.py"), "--out", out, "--target", "10", "--dry-run")
    assert code == 3 and "FEN-3001" in err


def test_a_script_that_binds_no_panel(tmp_path: Path) -> None:
    script = tmp_path / "empty.py"
    script.write_text("x = 1\n", encoding="utf-8")
    code, _, err = run("panel", str(script), "--out", str(tmp_path / "P"), "--target", "10", "--dry-run")
    assert code == 3 and "FEN-3004" in err and "panel" in err


def test_mirror_is_refused_by_a_kicad_target(tmp_path: Path) -> None:
    script = tmp_path / "m.py"
    script.write_text(
        "from fenolite.dsl import Panel\npanel = Panel('m', board='board_t10.kicad_pcb')\npanel.grid(1, 2, mirror=True)\n",
        encoding="utf-8",
    )
    os.link(committed_board(10), tmp_path / "board_t10.kicad_pcb")
    code, _, err = run("panel", str(script), "--out", str(tmp_path / "P"), "--target", "10", "--dry-run")
    assert code == 7 and "FEN-7001" in err


def test_an_edited_output_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "P"
    script = script_for("mixed", tmp_path / "s", committed_board(9))
    assert run("panel", str(script), "--out", str(out), "--target", "9", "--confirm")[0] == 0
    board = out / "mixed.kicad_pcb"
    board.write_text(board.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    code, env, _ = run("panel", str(script), "--out", str(out), "--target", "9", "--dry-run")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["panel.output-changed"]  # type: ignore[index, union-attr]
    code, _, err = run(
        "panel", str(script), "--out", str(out), "--target", "9", "--dry-run", "--discard-layout"
    )
    assert code == 0, err
