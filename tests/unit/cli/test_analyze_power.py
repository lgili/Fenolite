# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze --kinds power`` and ``--kinds insulation`` (capability board-analyses, "Power and
insulation kinds"; change c0115). Hermetic: the command runs no tool and writes no file. Every current,
thickness and resistivity here is illustrative."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _analysis import creep_bench
from _checkcli import run
from _power import written_strip
from _routed import NAME, Routed

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import write_board
from fenolite.cli.cmd_analyze import ALL_KINDS, KINDS, OPT_IN_KINDS
from fenolite.core.evidence import Level, strength

ROOT = Path(__file__).resolve().parents[3]
STRIP = ROOT / "tests" / "data" / "analysis" / "strip_10.kicad_pcb"
FIXTURE = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
HEAD = 'schema = "fenolite.requirements.v0"\n'
C0047_INPUTS = {
    "kinds",
    "temp_rise_mk",
    "copper_thickness",
    "via_plating",
    "board_thickness",
    "pairs",
    "within",
    "arc_tol",
    "requirements",
    "boundary",
}
"""The keys of ``result.inputs`` before change c0115."""


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", *args)
    return code, env, err


def test_the_data_file_is_the_authored_strip() -> None:
    assert STRIP.read_text(encoding="utf-8") == write_board(written_strip(), target=10).text
    assert "authored for Fenolite, illustrative values" in STRIP.read_text(encoding="utf-8")
    assert KINDS == ("current", "clearance", "creepage") and OPT_IN_KINDS == ("power", "insulation", "length")
    assert ALL_KINDS == (*KINDS, *OPT_IN_KINDS)


def test_strip_path_from_the_command_line(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A path from the command line"."""
    monkeypatch.setattr(subprocess, "run", None)
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(STRIP), "--kinds", "power", "--path", "J1-1", "U1-1",
        "--copper-thickness", "50um", "--resistivity", "20", "--json",
    )  # fmt: skip
    assert code == 0
    (row,) = env["result"]["power"]
    assert row["resistance_uohm"] == {"low": 1440, "high": 1440} and row["drop_mv"] is None
    assert row["net"] == "VBUS" and row["start"] == ["J1-1"] and row["end"] == ["U1-1"]
    (fill,) = row["elements"]
    assert fill["kind"] == "fill" and fill["section"]["low"] == 5_000_000 and fill["series"] is True
    inputs = env["result"]["inputs"]
    assert inputs["paths"] == [[["J1-1"], ["U1-1"]]] and inputs["resistivity_pohm_m"] == 20_000
    assert inputs["groove_nm"] is None and inputs["kinds"] == ["power"]
    assert env["result"]["summary"]["power"]["paths"] == 1 and "distances" not in env["result"]
    # no rise was given, so no capacity: the reply says so and is unverified
    assert [(found["code"], found["where"]) for found in env["issues"]] == [
        ("analysis.input-missing", "temperature rise")
    ]
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_strip_path_judged_from_a_requirements_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    text = (
        HEAD
        + '[[path]]\nfrom = ["J1-1"]\nto = ["U1-1"]\nmilliamps = 10000\ntemp_rise_mk = 20000\ndrop_mv = 10\n'
    )
    (tmp_path / "req.toml").write_text(text, encoding="utf-8", newline="\n")
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(STRIP), "--kinds", "power", "--requirements", "req.toml",
        "--copper-thickness", "50um", "--resistivity", "20", "--json",
    )  # fmt: skip
    assert code == 5
    assert [found["code"] for found in env["issues"]] == ["analysis.drop-above"]
    (row,) = env["result"]["power"]
    assert row["drop_mv"] == {"low": 14, "high": 15} and row["milliamps"] == 10_000
    assert env["evidence"]["level"] == "INFERRED"
    assert {"H-G-AN-POUR", "H-G-AN-SECTION", "H-G-AN-NETWORK"} <= set(env["evidence"]["hypotheses"])


def test_altium_board_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A path on an imported Altium board": the routed blink built for Altium, read back."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    built = cli_main.main(
        ["build", str(routed.script), "--out", str(routed.out), "--target", "altium", "--confirm", "--json"]
    )
    assert built == 0, stdout.getvalue()[:400]
    document = routed.out / f"{NAME}.PcbDoc"
    code, env, err = analyze(
        monkeypatch, tmp_path, str(document), "--kinds", "power", "--path", "R1-2", "D1-2",
        "--copper-thickness", "35um", "--resistivity", "20", "--json",
    )  # fmt: skip
    assert code == 0, err
    (row,) = env["result"]["power"]
    assert row["net"] == "LED_A"
    kinds = [element["kind"] for element in row["elements"]]
    assert kinds.count("via-group") == 1 and set(kinds) == {"track", "via-group"}
    assert row["resistance_uohm"]["low"] > 0
    assert "analysis.path-open" not in [found["code"] for found in env["issues"]]
    imported = json.loads(json.dumps(env["evidence"]))["level"]
    _, inspected, _ = analyze(
        monkeypatch,
        tmp_path,
        str(document),
        "--kinds",
        "current",
        "--temp-rise",
        "10",
        "--copper-thickness",
        "35um",
    )
    assert strength(Level(imported)) <= strength(Level(inspected["evidence"]["level"]))


def test_default_kinds_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Default kinds unchanged". Against the reply of c0047, a reply without the new kinds
    differs in three keys of ``inputs`` and in ``over`` of each measure, and in nothing else."""
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(FIXTURE), "--temp-rise", "10", "--copper-thickness", "35um",
        "--within", "0.5mm", "--board-thickness", "1.6mm", "--json",
    )  # fmt: skip
    assert code == 0
    result = env["result"]
    assert "power" not in result and "power" not in result["summary"]
    assert set(result) == {"current", "distances", "summary", "inputs"}
    assert result["inputs"]["kinds"] == ["current", "clearance", "creepage"]
    # the stack-up change (c0101) adds two keys of its own beside the three of this one
    added = set(result["inputs"]) - C0047_INPUTS - {"board_thickness_source", "stackup"}
    assert added == {"paths", "resistivity_pohm_m", "groove_nm"}
    assert (
        result["inputs"]["paths"],
        result["inputs"]["resistivity_pohm_m"],
        result["inputs"]["groove_nm"],
    ) == ([], None, None)
    assert result["distances"], "the fixture has a pair closer than 0.5 mm"
    for row in result["distances"]:
        assert set(row) == {"net_a", "net_b", "gaps", "clearance", "creepage"}
        for measure in (*row["gaps"], row["clearance"], row["creepage"]):
            if measure is not None:
                assert set(measure) == {"low", "high", "layer", "points", "items", "bounded", "over"}
    assert "grooves" not in result["summary"]["distances"]


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Usage errors"."""
    cases = (
        (str(STRIP), "--path", "J1-1", "U1-1", "--json"),
        (str(STRIP), "--kinds", "current", "--groove-width", "1mm", "--temp-rise", "10", "--json"),
        (str(STRIP), "--resistivity", "20", "--json"),
        (str(STRIP), "--kinds", "power", "--path", "J1", "U1-1", "--json"),
        (str(STRIP), "--kinds", "power", "--resistivity", "17.2345", "--json"),
        (str(STRIP), "--kinds", "power", "--resistivity", "copper", "--json"),
        (str(STRIP), "--kinds", "power,thermal", "--json"),
    )
    for args in cases:
        code, _, err = analyze(monkeypatch, tmp_path, *args)
        assert (code, err["code"]) == (2, "FEN-2001"), args


def test_insulation_kind_and_groove_width(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "slot.kicad_pcb"
    board.write_text(write_board(creep_bench("slot").design, target=10).text, encoding="utf-8", newline="\n")
    code, env, _ = analyze(
        monkeypatch,
        tmp_path,
        str(board),
        "--kinds",
        "creepage",
        "--pair",
        "A",
        "B",
        "--groove-width",
        "3mm",
        "--json",
    )
    assert code == 0
    (row,) = env["result"]["distances"]
    assert row["creepage"]["low"] == 9_000_000 and env["result"]["inputs"]["groove_nm"] == 3_000_000
    assert env["result"]["summary"]["distances"]["grooves"] == {"3000000": {"bridged": 1, "counted": 0}}
    assert "H-G-AN-GROOVE" in env["evidence"]["hypotheses"]
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "insulation", "--pair", "A", "B", "--json"
    )
    assert code == 0
    (row,) = env["result"]["distances"]
    assert set(row) == {"net_a", "net_b", "insulation", "sheets"} and row["insulation"] is None
