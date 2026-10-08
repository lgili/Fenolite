# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite testpoints`` (capability cli-contract, "Testpoints command" and "Manifest option of producing
commands"; change c0118). Hermetic: no tool runs. The built board is the blink with an authored test pad
and two authored fiducial marks (``_asmcli.FEATURES``); every position and size is made up."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import _schema
import pytest
from _asmcli import FEATURES, FIXTURE, LAST_LINE, built, isolate
from _asmfeatures import CALLS
from _boards import board, footprint
from _checkcli import run, without_elapsed

from fenolite.cli.cmd_testpoints import COMMAND

MM = 1_000_000
HEADER = "kind,ref,pad,net,x,y,side,access,width,height,drill"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def features(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return built(monkeypatch, tmp_path, (LAST_LINE, FEATURES))


def test_a_board_without_marks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A board without marks"."""
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(FIXTURE))
    assert code == 0 and list(tmp_path.iterdir()) == []
    result = env["result"]
    assert result["test_points"] == [] and result["fiducials"] == [] and result["holes"] == []
    assert result["coverage"]["covered"] == 0
    assert [(i["code"], i["severity"]) for i in env["issues"]] == [("testpoint.none", "info")]
    hint = env["issues"][0]["hint"]
    assert "design.test_point()" in hint and 'Footprint.pad(fab_property="test_point")' in hint
    assert (result["side"], result["template"], result["units"], result["origin"], result["y_axis"]) == (
        "both", "default", "mm", "page", "up",
    )  # fmt: skip
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-K-PAD-FABPROP", "H-K-PCB-READ", "H-K-TESTPOINT-D356"],
    }
    assert env["input"]["path"] == "two_layer.kicad_pcb" and env["receipt"] is None


def test_the_report_of_a_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = features(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder))
    assert code == 0 and env["issues"] == []
    result = env["result"]
    (point,) = result["test_points"]
    assert (point["ref"], point["pad"], point["net"]) == ("TP1", "1", "LED_A")
    assert (point["side"], point["access"], point["shape"], point["drill"]) == ("top", "top", "circle", None)
    assert point["size"] == [1_500_000, 1_500_000]
    assert all(isinstance(value, int) for value in point["position"])
    assert [(f["ref"], f["side"], f["scope"]) for f in result["fiducials"]] == [
        ("FID1", "top", "global"),
        ("FID2", "bottom", "global"),
    ]
    first, second = (f["position"] for f in result["fiducials"])
    assert (second[0] - first[0], second[1] - first[1]) == (44 * MM, 24 * MM)
    assert result["fiducials"][0]["size"] == [MM, MM]
    assert result["counts"] == {
        "test_points": 1, "fiducials_top": 1, "fiducials_bottom": 1, "holes": 0, "tooling_holes": 0,
    }  # fmt: skip
    coverage = result["coverage"]
    assert coverage["covered"] == 1 and "LED_A" not in coverage["uncovered"]
    assert coverage["eligible"] == 1 + len(coverage["uncovered"])


def test_one_side(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = features(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--side", "bottom")
    assert code == 0
    result = env["result"]
    assert result["side"] == "bottom" and result["test_points"] == []
    assert [f["ref"] for f in result["fiducials"]] == ["FID2"] and result["coverage"]["covered"] == 0
    # the board holds a marked pad, so the report of the other side is not an unmarked board
    assert [i["code"] for i in env["issues"]] == []


def test_a_coverage_target_missed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A coverage target missed": an error finding plans no file."""
    folder = features(monkeypatch, tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "testpoints", str(folder), "--min-coverage", "100", "--out", "tp.csv",
        "--dry-run",
    )  # fmt: skip
    assert code == 5
    assert [i["code"] for i in env["issues"]] == ["testpoint.coverage-low"]
    assert env["result"]["coverage"]["covered"] == 1 and "plan" not in env["result"]
    assert list(tmp_path.glob("*.csv")) == []
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--min-coverage", "0")
    assert code == 0 and env["issues"] == []


def test_targets_of_pitch_and_fiducials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = features(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--min-fiducials", "2")
    assert code == 5
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("fiducial.too-few", "top")]
    code, env, _, _ = run(
        monkeypatch, tmp_path, "testpoints", str(folder), "--min-fiducials", "1", "--min-pitch", "2.54mm"
    )
    assert code == 0 and env["issues"] == []


def test_the_csv_of_a_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The CSV of a build", with the parts this base can place."""
    folder = features(monkeypatch, tmp_path)
    args = ("testpoints", str(folder), "--out", "tp.csv")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and [p["path"] for p in env["result"]["plan"]] == ["tp.csv"]
    assert not (tmp_path / "tp.csv").exists()
    code, _, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 4 and err["code"] == "FEN-4001"
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0 and [w["path"] for w in env["receipt"]["written"]] == ["tp.csv"]
    lines = (tmp_path / "tp.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == HEADER
    rows = [line.split(",") for line in lines[1:]]
    assert [(row[0], row[1]) for row in rows] == [
        ("test_point", "TP1"), ("fiducial", "FID1"), ("fiducial", "FID2"),
    ]  # fmt: skip
    point = dict(zip(HEADER.split(","), rows[0], strict=True))
    assert (point["pad"], point["net"], point["side"], point["access"]) == ("1", "LED_A", "top", "top")
    assert (point["width"], point["height"], point["drill"]) == ("1.5000", "1.5000", "")
    position = env["result"]["test_points"][0]["position"]
    assert (point["x"], point["y"]) == (f"{position[0] / MM:.4f}", f"{-position[1] / MM:.4f}")
    assert rows[2][6] == "bottom" and rows[1][2:4] == ["", ""] and rows[1][7] == ""


def test_the_csv_of_a_build_with_the_script_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "The CSV of a build" and "A coverage target missed" on the build of "Features in a build":
    the parts of ``design.fiducial()``, ``design.test_point()`` and ``design.tooling_hole()``."""
    folder = built(monkeypatch, tmp_path, (LAST_LINE, LAST_LINE + CALLS))
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--out", "tp.csv", "--confirm")
    assert code == 0 and env["issues"] == []
    assert env["result"]["counts"] == {
        "test_points": 1, "fiducials_top": 1, "fiducials_bottom": 1, "holes": 1, "tooling_holes": 1,
    }  # fmt: skip
    lines = (tmp_path / "tp.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == HEADER
    rows = [dict(zip(HEADER.split(","), line.split(","), strict=True)) for line in lines[1:]]
    assert [(row["kind"], row["ref"]) for row in rows] == [
        ("test_point", "TP1"), ("fiducial", "FID1"), ("fiducial", "FID2"), ("tooling_hole", "TH1"),
    ]  # fmt: skip
    assert (rows[0]["net"], rows[0]["access"]) == ("LED_A", "top") and rows[3]["drill"] == "3.0000"
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--min-coverage", "100")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["testpoint.coverage-low"]
    assert env["result"]["coverage"]["covered"] == 1


def test_the_csv_uses_the_placement_frame(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = features(monkeypatch, tmp_path)
    template = tmp_path / "frame.toml"
    template.write_text(
        '[placement]\norigin = "outline"\ny_axis = "up"\nunits = "mil"\ndecimals = 1\n'
        'sides = { top = "T", bottom = "B" }\n',
        encoding="utf-8",
    )
    code, env, _, _ = run(
        monkeypatch, tmp_path, "testpoints", str(folder), "--template", str(template), "--out", "tp.csv",
        "--confirm",
    )  # fmt: skip
    assert code == 0, env["issues"]
    assert (env["result"]["template"], env["result"]["units"], env["result"]["origin"]) == (
        "frame.toml", "mil", "outline",
    )  # fmt: skip
    rows = [line.split(",") for line in (tmp_path / "tp.csv").read_text(encoding="utf-8").splitlines()[1:]]
    by_ref = {row[1]: row for row in rows}
    # 3 mm, 30 mm and the 1.5 mm pad, from the left edge of the outline, in mils with one decimal
    assert by_ref["FID1"][4] == "118.1" and by_ref["FID1"][6] == "T" and by_ref["FID2"][6] == "B"
    assert by_ref["TP1"][4] == "1181.1" and by_ref["TP1"][8] == "59.1"


def test_no_outline_plans_no_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    template = tmp_path / "frame.toml"
    template.write_text('[placement]\norigin = "outline"\n', encoding="utf-8")
    bare = tmp_path / "bare.kicad_pcb"
    bare.write_text(board(footprint(1, ref="R1")), encoding="utf-8", newline="\n")
    args = ("testpoints", str(bare), "--template", str(template))
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--out", "tp.csv", "--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    assert [(i["code"], i["severity"]) for i in env["issues"]] == [
        ("testpoint.none", "info"),
        ("pnp.no-outline", "error"),
    ]
    assert "plan" not in env["result"] and env["receipt"] is None and not (tmp_path / "tp.csv").exists()
    code, env, _, _ = run(monkeypatch, tmp_path, *args)  # the rows are in the board frame: no outline needed
    assert code == 0 and [i["code"] for i in env["issues"]] == ["testpoint.none"]


@pytest.mark.parametrize(
    "flags",
    [
        ("--min-coverage", "101"),
        ("--min-coverage", "-1"),
        ("--min-coverage", "half"),
        ("--min-pitch", "2"),
        ("--min-pitch", "0mm"),
        ("--min-pitch", "-1mm"),
        ("--min-fiducials", "0"),
        ("--min-fiducials", "1.5"),
        ("--side", "left"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flags: tuple[str, ...]) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "testpoints", str(FIXTURE), *flags)
    assert code == 2 and err["code"] == "FEN-2001"


def test_input_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "testpoints", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and err["code"].startswith("FEN-3")
    bad = tmp_path / "bad.kicad_pcb"
    bad.write_text("(kicad_pcb", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "testpoints", str(bad))
    assert code == 3
    altium = tmp_path / "board.PcbDoc"
    altium.write_bytes(b"not a board")
    code, _, err, _ = run(monkeypatch, tmp_path, "testpoints", str(altium))
    assert code in (2, 3)


def test_paging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``paged = "test_points"``: ``--limit`` cuts the list and names the next page."""
    more = FEATURES + (
        'tp2 = Part("TP2", "Local:TestPad", footprint="Local:TestPad")\n'
        'tp3 = Part("TP3", "Local:TestPad", footprint="Local:TestPad")\n'
        "design.add(tp2, tp3)\nconnect(led_drv, tp2[1])\nconnect(vin, tp3[1])\n"
        "tp2.place(mm(30), mm(16))\ntp3.place(mm(30), mm(20))\n"
    )
    folder = built(monkeypatch, tmp_path, (LAST_LINE, more))
    code, env, _, _ = run(monkeypatch, tmp_path, "testpoints", str(folder), "--limit", "2")
    assert code == 0
    assert [row["ref"] for row in env["result"]["test_points"]] == ["TP1", "TP2"]
    page = env["result"]["page"]
    assert page["total"] == 3 and page["path"] == "test_points" and page["next"]
    code, env, _, _ = run(
        monkeypatch, tmp_path, "testpoints", str(folder), "--limit", "2", "--cursor", page["next"]
    )
    assert code == 0 and [row["ref"] for row in env["result"]["test_points"]] == ["TP3"]
    assert env["result"]["counts"]["test_points"] == 3 and env["result"]["coverage"]["covered"] == 3


def test_two_runs_are_identical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outputs = [run(monkeypatch, tmp_path, "testpoints", str(FIXTURE))[3] for _ in range(2)]
    assert without_elapsed(outputs[0]) == without_elapsed(outputs[1])
    assert str(tmp_path) not in outputs[0] and str(FIXTURE.parent) not in outputs[0]


def test_command_declaration() -> None:
    assert COMMAND.mutates and COMMAND.example_tools == () and COMMAND.paged == "test_points"
    assert COMMAND.example_args[1:] == () and COMMAND.mutation_example_args is not None
    assert COMMAND.mutation_example_args[1:] == ("--out", "testpoints.csv")


def _listed(folder: Path) -> dict[str, dict[str, object]]:
    manifest = json.loads((folder / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    return {e["path"]: e for e in manifest["artifacts"]}


def test_manifest_the_table_joins_the_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "The CSV joins the manifest" and "The test-point table joins the manifest"."""
    folder = features(monkeypatch, tmp_path)
    board = hashlib.sha256(next(folder.glob("*.kicad_pcb")).read_bytes()).hexdigest()
    code, env, _, _ = run(
        monkeypatch, tmp_path, "pnp", str(folder), "--out", "out/pnp.csv", "--manifest", "--confirm"
    )
    assert code == 0, env
    code, env, _, _ = run(
        monkeypatch, tmp_path, "testpoints", str(folder), "--out", "out/tp.csv", "--manifest", "--confirm"
    )
    assert code == 0, env
    assert [w["path"] for w in env["receipt"]["written"]] == ["out/tp.csv", "out/fenolite-artifacts.json"]
    listed = _listed(tmp_path / "out")
    assert list(listed) == ["pnp.csv", "tp.csv"]
    item = listed["tp.csv"]
    data = (tmp_path / "out" / "tp.csv").read_bytes()
    assert (item["kind"], item["layer"], item["state"], item["stale"]) == (
        "testpoints", None, "generated", False,
    )  # fmt: skip
    assert item["sha256"] == hashlib.sha256(data).hexdigest() and item["bytes"] == len(data)
    assert item["from"] == {"board": board} and str(item["tool"]).startswith("fenolite ")
    assert item["evidence"] == env["evidence"]["level"] == "INFERRED"
    assert str(tmp_path) not in (tmp_path / "out" / "fenolite-artifacts.json").read_text(encoding="utf-8")


def test_manifest_needs_a_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "testpoints", str(FIXTURE), "--manifest")
    assert code == 2 and err["code"] == "FEN-2001" and "--out" in err["hint"]
    assert list(tmp_path.iterdir()) == []
