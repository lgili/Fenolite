# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The placement guard of ``fenolite build`` (capability design-dsl, "Placement legality in a build"; change
c0022). Hermetic: the guard reads the planned bytes back and runs no tool."""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import BLINK, blink, blink_variant, build
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.cli.cmd_build import placement_guard
from fenolite.geometry import BBox
from fenolite.lens import build as lens_build
from fenolite.placement import ISSUE_CODES

MM = 1_000_000
R1_PLACE = "r1.place(mm(32), mm(9))"
D1_PLACE = 'd1.place(mm(38), mm(20), side="bottom")'
NO_RULES: dict[str, Any] = {"rules": {"near": {"judged": 0, "failed": 0, "skipped": 0}}}
"""``result.placement.rules`` of a design without placement rules (change c0113)."""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def variant(tmp_path: Path, *edits: tuple[str, str]) -> Path:
    script = blink_variant(tmp_path / "src")
    text = script.read_text(encoding="utf-8")
    for old, new in edits:
        assert old in text, old
        text = text.replace(old, new)
    script.write_text(text, encoding="utf-8")
    return script


def place_issues(env: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(i["code"], i["severity"], i["where"]) for i in env["issues"] if i["code"].startswith("place.")]


def courtyard_boxes() -> dict[str, BBox]:
    """The courtyard box of each part of the built blink, relative to its position."""
    output = build(blink(), 10)
    design = read_board(output.files["blink.kicad_pcb"].decode("utf-8"), file="blink.kicad_pcb")
    assert design.board is not None
    by_id = {fp.id: fp for fp in design.board.footprints}
    boxes: dict[str, BBox] = {}
    for extent in KicadBackend().placed_extents(design):
        fp = by_id[extent.footprint_id]
        box = BBox.of_points([p for ring in (*extent.front, *extent.back) for p in ring])
        at = fp.position
        boxes[footprint_ref(design, fp)] = BBox(box.x0 - at.x, box.y0 - at.y, box.x1 - at.x, box.y1 - at.y)
    return boxes


def test_overlap_reported_and_build_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``R1`` beside ``D1`` on the top, their courtyards overlapping by 0.1 mm; no copper touches."""
    boxes = courtyard_boxes()
    # a flip mirrors about the local X axis, so D1's box keeps its X range on the top
    d1_right = 38 * MM + boxes["D1"].x1
    r1_x = d1_right - 100_000 - boxes["R1"].x0
    script = variant(
        tmp_path,
        (D1_PLACE, "d1.place(mm(38), mm(20))"),
        (R1_PLACE, f'r1.place(mm("{r1_x / MM:.6f}"), mm(20))'),
    )
    out = tmp_path / "out"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, (env["issues"], err)
    assert place_issues(env) == [("place.courtyard-overlap", "warning", "D1,R1")]
    assert env["result"]["placement"] == {"ran": True, "counts": {"place.courtyard-overlap": 1}, **NO_RULES}
    assert (out / "blink.kicad_pcb").is_file()
    assert env["result"]["copper_check"]["shorts"] == 0


def test_part_over_the_edge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path, (R1_PLACE, "r1.place(mm(49.5), mm(9))"))
    out = tmp_path / "out"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--dry-run")
    assert code == 0, (env["issues"], err)
    assert place_issues(env) == [("place.outside-outline", "warning", "R1")]
    assert env["result"]["placement"]["counts"] == {"place.outside-outline": 1}
    assert not out.exists()


def test_staged_parts_are_not_judged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path, (R1_PLACE + "\n", ""))
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", "out", "--dry-run")
    assert code == 0, (env["issues"], err)
    assert [(i["code"], i["where"]) for i in env["issues"] if i["code"] == "layout.unplaced"] == [
        ("layout.unplaced", "R1")
    ]
    assert place_issues(env) == [] and env["result"]["staged"] == ["R1"]
    assert env["result"]["placement"] == {"ran": True, "counts": {}, **NO_RULES}


@pytest.mark.parametrize("target", [9, 10])
def test_clean_blink_stays_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: int) -> None:
    out = tmp_path / "out"
    code, env, err, _ = run(
        monkeypatch,
        tmp_path,
        "build",
        str(BLINK),
        "--out",
        str(out),
        "--kicad-version",
        str(target),
        "--confirm",
    )
    assert code == 0, (env["issues"], err)
    assert place_issues(env) == [] and env["result"]["placement"] == {"ran": True, "counts": {}, **NO_RULES}
    # the guard changes no byte: the files are those of ``build_design``
    expected = build(blink(), target).files
    written = {rel: (out / rel).read_bytes() for rel in expected}
    assert written == dict(expected)
    assert {rel for rel in tree_snapshot(out) if (out / rel).is_file()} == set(expected)


def test_refused_build_does_not_run_the_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path, ("connect(led_a, r1[2], d1[2])", "connect(led_a, r1[2], d1[2], r1[9])"))
    code, env, _, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", "out", "--dry-run")
    assert code == 5
    assert env["result"]["placement"] == {"ran": False, "counts": {}, **NO_RULES} and place_issues(env) == []


def test_guard_on_planned_files() -> None:
    files = dict(build(blink(), 10).files)
    assert placement_guard(files, name="blink") == ((), {"ran": True, "counts": {}, **NO_RULES})
    assert placement_guard({}, name="blink") == ((), {"ran": False, "counts": {}, **NO_RULES})
    # every part of the blink is at least 3 mm from the edge, and none is 20 mm from it
    assert placement_guard(files, name="blink", edge_clearance=3 * MM)[0] == ()
    issues, summary = placement_guard(files, name="blink", edge_clearance=20 * MM)
    assert {i.code for i in issues} == {"place.edge-clearance"} and summary["counts"] == {
        "place.edge-clearance": 3
    }
    left_out, _ = placement_guard(files, name="blink", edge_clearance=20 * MM, staged=("R1", "U1"))
    assert [i.where for i in left_out] == ["D1"]


def test_guard_caps_every_severity_at_warning() -> None:
    files = dict(build(blink(), 10).files)
    text = files["blink.kicad_pcb"].decode("utf-8")
    assert "(at 132 109)" in text  # R1, moved onto U1 at (114, 115)
    files["blink.kicad_pcb"] = text.replace("(at 132 109)", "(at 114 115)", 1).encode("utf-8")
    issues, summary = placement_guard(files, name="blink")
    assert [(i.code, i.severity, i.where) for i in issues] == [
        ("place.courtyard-overlap", "warning", "R1,U1")
    ]
    assert ISSUE_CODES["place.courtyard-overlap"] == "error" and summary["counts"] == {
        "place.courtyard-overlap": 1
    }


def test_lens_build_is_unchanged() -> None:
    """``lens`` may not import ``placement``: the codes join the envelope from ``cmd_build`` only."""
    assert not [code for code in lens_build.BUILD_ISSUE_CODES if code.startswith("place.")]
    source = Path(lens_build.__file__).read_text(encoding="utf-8")
    assert "fenolite.placement" not in source


# --- placement rules and keep-outs in the guard (change c0113) ------------------------------------------

NEAR = '\ndesign.near("led", d1, r1.pad(2), within=mm(5))\n'


def test_rules_reported_as_warnings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Rules reported as warnings": a rule that fails never refuses a build."""
    script = blink_variant(tmp_path / "src", append=NEAR)
    code, env, _, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", "out", "--dry-run")
    assert code == 0, env["issues"]
    found = [i for i in env["issues"] if i["code"].startswith("placement.")]
    assert [(i["code"], i["severity"], i["where"]) for i in found] == [("placement.too-far", "warning", "D1")]
    assert "rule led" in found[0]["message"] and "R1-2" in found[0]["message"]
    assert env["result"]["placement"] == {
        "ran": True,
        "counts": {"placement.too-far": 1},
        "rules": {"near": {"judged": 1, "failed": 1, "skipped": 0}},
    }
    assert place_issues(env) == []
    assert not (tmp_path / "out").exists()


def test_rule_met_gives_no_issue_and_is_stored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=NEAR.replace("mm(5)", "mm(13)"))
    out = tmp_path / "out"
    code, env, _, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    assert not [i for i in env["issues"] if i["code"].startswith("placement.")]
    assert env["result"]["placement"]["rules"] == {"near": {"judged": 1, "failed": 0, "skipped": 0}}
    stored = json.loads((out / ".fenolite" / "rules.json").read_text(encoding="utf-8"))
    assert stored["proximity"] == [
        {
            "name": "led",
            "parts": [{"path": "D1"}],
            "anchor": [{"path": "R1", "number": "2"}],
            "within": 13 * MM,
        }
    ]


def test_rule_on_a_staged_part_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path, (D1_PLACE, ""))
    script.write_text(script.read_text(encoding="utf-8") + NEAR, encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", "out", "--dry-run")
    assert code == 0, env["issues"]
    found = [
        (i["code"], i["severity"], i["where"]) for i in env["issues"] if i["code"].startswith("placement.")
    ]
    assert found == [("placement.rule-skipped", "info", "D1")]
    assert env["result"]["placement"]["rules"] == {"near": {"judged": 0, "failed": 0, "skipped": 1}}


def test_guard_judges_the_keepouts_of_the_planned_board() -> None:
    """A rule area that forbids footprints, drawn over ``R1`` on the planned board: one warning."""
    from fenolite.backends.kicad.pcb import write_board
    from fenolite.core.coords import Point
    from fenolite.model.board import Keepout

    files = dict(build(blink(), 10).files)
    design = read_board(files["blink.kicad_pcb"].decode("utf-8"), file="blink.kicad_pcb")
    assert design.board is not None
    r1 = next(fp for fp in design.board.footprints if footprint_ref(design, fp) == "R1")
    x, y = r1.position.x, r1.position.y
    ring = tuple(Point(x + dx * MM, y + dy * MM) for dx, dy in ((-3, -3), (3, -3), (3, 3), (-3, 3)))

    def planned(*layers: str) -> dict[str, bytes]:
        area = Keepout(
            id="kpo_00000000-0000-4000-8000-000000000001", outline=ring, layers=layers, no_footprints=True
        )
        board = dataclasses.replace(design.board, keepouts=(area,))  # type: ignore[arg-type]
        text = write_board(dataclasses.replace(design, board=board), target=10).text
        assert text.count("(footprints not_allowed)") == 1
        return {**files, "blink.kicad_pcb": text.encode("utf-8")}

    issues, summary = placement_guard(planned("F.Cu"), name="blink")
    assert [(i.code, i.severity, i.where) for i in issues] == [("place.keepout", "warning", "R1")]
    assert summary["counts"] == {"place.keepout": 1} and ISSUE_CODES["place.keepout"] == "error"
    assert placement_guard(planned("B.Cu"), name="blink")[0] == ()  # R1 is on the top
