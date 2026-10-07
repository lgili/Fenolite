# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place`` (capability cli-contract, "Place command"; change c0022). Hermetic: no tool runs."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink_variant
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.cli.cmd_place import COMMAND, Move, parse_move
from fenolite.cli.errors import CliError
from fenolite.geometry import BBox
from fenolite.model.board import FootprintInstance
from fenolite.placement import KEEPOUT_EVIDENCE

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000
ORIGIN = 100 * MM
"""Where a build puts the outline's top-left corner (``dsl.convert.BOARD_ORIGIN``)."""
STAGED = (("r1.place(mm(32), mm(9))\n", ""), ('d1.place(mm(38), mm(20), side="bottom")\n', ""))


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *edits: tuple[str, str], name: str = "p") -> Path:
    """A confirmed build of the blink, or of a variant with ``edits`` applied to its script."""
    text_edits = list(edits)
    script = blink_variant(tmp_path / f"{name}-src")
    text = script.read_text(encoding="utf-8")
    for old, new in text_edits:
        assert old in text, old
        text = text.replace(old, new)
    script.write_text(text, encoding="utf-8")
    out = tmp_path / name
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, (env.get("issues"), err)
    return out


def footprints(folder: Path) -> dict[str, FootprintInstance]:
    design = read_board(folder / "blink.kicad_pcb")
    assert design.board is not None
    return {footprint_ref(design, fp): fp for fp in design.board.footprints}


def region(folder: Path) -> BBox:
    return BBox.of_points(board_outline(read_board(folder / "blink.kicad_pcb")).rings[0])


def codes(env: dict[str, Any]) -> list[str]:
    return [issue["code"] for issue in env["issues"]]


# --- the grid ---------------------------------------------------------------------------------------


def test_grid_places_staged_parts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path, *STAGED)
    before = footprints(folder)
    box = region(folder)
    assert not box.contains_point(before["R1"].position) and not box.contains_point(before["D1"].position)
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(folder), "--confirm")
    assert code == 0, (env["issues"], err)
    after = footprints(folder)
    assert box.contains_point(after["R1"].position) and box.contains_point(after["D1"].position)
    assert (after["U1"].position, after["U1"].rotation) == (before["U1"].position, before["U1"].rotation)
    result = env["result"]
    assert (result["board"], result["strategy"], result["unplaced"]) == ("blink.kicad_pcb", "grid", [])
    assert [row["ref"] for row in result["moved"]] == ["D1", "R1"]
    d1 = result["moved"][0]
    assert d1["path"] == "D1" and d1["from"] == {
        "x": before["D1"].position.x, "y": before["D1"].position.y, "rotation": 0, "side": "top",
    }  # fmt: skip
    assert d1["to"] == {
        "x": after["D1"].position.x, "y": after["D1"].position.y, "rotation": 0, "side": "top",
    }  # fmt: skip
    assert result["legality"] == {} and not [c for c in codes(env) if c.startswith("place.")]
    assert env["evidence"]["level"] == "KICAD-VERIFIED"
    assert env["evidence"]["hypotheses"] == ["H-K-PLACE-MOVE", "H-K-PLACE-TOUCH"]
    assert [w["path"] for w in env["receipt"]["written"]] == [str(Path("p") / "blink.kicad_pcb")]
    assert env["input"]["path"] == "blink.kicad_pcb" and env["input"]["kind"] == "kicad_pcb"
    # the grid starts 1 mm inside the outline and keeps the parts apart
    assert (after["D1"].position.x - before["D1"].position.x) % 500_000 == 0


def test_grid_dry_run_writes_nothing_and_shows_the_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = built(monkeypatch, tmp_path, *STAGED)
    snapshot = tree_snapshot(folder)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--dry-run")
    assert code == 0 and tree_snapshot(folder) == snapshot
    (plan,) = env["result"]["plan"]
    assert plan["path"] == str(Path("p") / "blink.kicad_pcb") and plan["kind"] == "kicad_pcb"
    assert plan["overwrite"] is True
    code, _, err, _ = run(monkeypatch, tmp_path, "place", str(folder))
    assert code == 4 and err["code"] == "FEN-4001" and tree_snapshot(folder) == snapshot


def test_grid_only_places_the_named_parts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path, *STAGED)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--only", "R1", "--confirm")
    assert code == 0, env["issues"]
    assert [row["ref"] for row in env["result"]["moved"]] == ["R1"]
    assert env["result"]["unplaced"] == ["D1"]
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--only", "R1,R99", "--dry-run")
    assert code == 5 and codes(env) == ["place.unknown-ref"] and env["issues"][0]["where"] == "R99"
    assert env["result"]["moved"] == []  # R1 is on the board now


def test_grid_two_runs_write_equal_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = built(monkeypatch, tmp_path, *STAGED, name="a")
    second = built(monkeypatch, tmp_path, *STAGED, name="b")
    assert (first / "blink.kicad_pcb").read_bytes() == (second / "blink.kicad_pcb").read_bytes()
    for folder in (first, second):
        code, _, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--confirm")
        assert code == 0
    assert (first / "blink.kicad_pcb").read_bytes() == (second / "blink.kicad_pcb").read_bytes()


def test_nothing_to_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    snapshot = tree_snapshot(folder)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--confirm")
    assert code == 0 and env["result"]["moved"] == [] and env["result"]["unplaced"] == []
    assert env["receipt"] is None and "plan" not in env["result"]
    assert tree_snapshot(folder) == snapshot


def test_grid_no_room(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path, *STAGED)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--margin", "14.5mm", "--dry-run")
    assert code == 0
    assert codes(env) == ["place.no-room", "place.no-room"]
    assert [(i["where"], i["severity"]) for i in env["issues"]] == [("D1", "warning"), ("R1", "warning")]
    assert env["result"]["moved"] == [] and env["result"]["unplaced"] == ["D1", "R1"]
    assert "plan" not in env["result"]


# --- manual moves -----------------------------------------------------------------------------------


def test_illegal_move_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(
        monkeypatch, tmp_path, ('d1.place(mm(38), mm(20), side="bottom")', "d1.place(mm(38), mm(20))")
    )
    snapshot = tree_snapshot(folder)
    move = "R1=38mm,20mm"  # the position of D1
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", move, "--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    assert codes(env) == ["place.courtyard-overlap"] and env["issues"][0]["where"] == "D1,R1"
    assert env["result"]["legality"] == {"place.courtyard-overlap": 1}
    assert env["receipt"] is None and tree_snapshot(folder) == snapshot
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", move, "--force", "--confirm")
    assert code == 5 and codes(env) == ["place.courtyard-overlap"]
    assert footprints(folder)["R1"].position.x == ORIGIN + 38 * MM
    assert [w["path"] for w in env["receipt"]["written"]] == [str(Path("p") / "blink.kicad_pcb")]


def test_move_outside_the_outline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=49.5mm,9mm", "--dry-run")
    assert code == 5 and codes(env) == ["place.outside-outline"] and env["issues"][0]["where"] == "R1"
    assert "plan" not in env["result"]


def test_unknown_reference(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R99=1mm,1mm", "--dry-run")
    assert code == 5 and codes(env) == ["place.unknown-ref"]
    assert env["issues"][0]["where"] == "R99" and "R99" in env["issues"][0]["message"]


def test_move_is_in_the_frame_of_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    out = "moved.kicad_pcb"
    snapshot = tree_snapshot(folder)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", str(folder), "--move", "R1=30mm,6.5mm", "-o", out, "--confirm"
    )
    assert code == 0, env["issues"]
    assert tree_snapshot(folder) == snapshot  # the board itself is untouched with --out
    design = read_board(tmp_path / out)
    assert design.board is not None
    r1 = next(fp for fp in design.board.footprints if footprint_ref(design, fp) == "R1")
    assert (r1.position.x, r1.position.y) == (ORIGIN + 30 * MM, ORIGIN + 6_500_000)
    assert env["result"]["strategy"] == "manual"
    assert env["result"]["moved"][0]["to"] == {
        "x": ORIGIN + 30 * MM, "y": ORIGIN + 6_500_000, "rotation": 0, "side": "top",
    }  # fmt: skip


def test_rotation_through_the_project_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    args = ("--move", "R1=32mm,9mm,90", "--move", "D1=38mm,20mm,30,top")
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), *args, "--confirm")
    assert code == 0, env["issues"]
    after = footprints(folder)
    assert (after["R1"].rotation, after["R1"].side) == (90_000_000, "top")
    assert (after["D1"].rotation, after["D1"].side) == (30_000_000, "top")
    assert [row["ref"] for row in env["result"]["moved"]] == ["D1", "R1"]
    assert env["result"]["moved"][0]["from"]["side"] == "bottom"
    # without the vendored library the rotation is refused, and a translation still works
    (folder / "fp-lib-table").unlink()
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=32mm,9mm,0", "--dry-run")
    assert code == 5 and codes(env) == ["place.no-definition"] and env["issues"][0]["where"] == "R1"
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=30mm,9mm", "--dry-run")
    assert code == 0 and [row["ref"] for row in env["result"]["moved"]] == ["R1"]


def test_locked_parts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    move = "U1=16mm,15mm"
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", move, "--dry-run")
    assert code == 5 and codes(env) == ["place.locked"] and env["issues"][0]["where"] == "U1"
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", move, "--force", "--confirm")
    assert code == 0, env["issues"]
    assert codes(env) == ["place.script-locked"] and env["issues"][0]["severity"] == "warning"
    assert footprints(folder)["U1"].position.x == ORIGIN + 16 * MM
    # an unlocked part gets no such warning
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=30mm,9mm", "--dry-run")
    assert code == 0 and codes(env) == []


def test_copper_left(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    board = folder / "blink.kicad_pcb"
    r1 = footprints(folder)["R1"]
    pad = r1.pads[0]
    x, y = (r1.position.x + pad.position.x) / MM, (r1.position.y + pad.position.y) / MM
    segment = (
        f"\t(segment\n\t\t(start {x:g} {y:g})\n\t\t(end {x:g} {y - 3:g})\n\t\t(width 0.25)\n"
        '\t\t(layer "F.Cu")\n\t\t(net 0)\n\t\t(uuid "5e5e5e5e-0000-4000-8000-000000000001")\n\t)\n'
    )
    text = board.read_text(encoding="utf-8")
    board.write_text(text[: text.rindex(")")] + segment + ")\n", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=30mm,9mm", "--dry-run")
    assert code == 0, env["issues"]
    assert codes(env) == ["place.copper-left"] and env["issues"][0]["where"] == "R1"
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "D1=38mm,21mm", "--dry-run")
    assert code == 0 and codes(env) == []


# --- arguments --------------------------------------------------------------------------------------


def test_parse_move() -> None:
    assert parse_move("R1=12mm,8mm") == Move("R1", 12 * MM, 8 * MM)
    assert parse_move(" U2 = 0.5in , -1mm , 90 , bottom ") == Move(
        "U2", 12_700_000, -MM, 90_000_000, "bottom"
    )
    assert parse_move("R1=1mm,1mm,-90").rotation == 270_000_000
    for bad in (
        "R1",
        "R1=1mm",
        "=1mm,1mm",
        "R1=1,1",
        "R1=1mm,1mm,x",
        "R1=1mm,1mm,0,left",
        "R1=1mm,1mm,0,top,x",
    ):
        with pytest.raises(CliError) as caught:
            parse_move(bad)
        assert caught.value.code == "FEN-2001", bad


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = str(FIXTURE)
    for args in (
        ("--strategy", "grid", "--move", "R1=1mm,1mm"),
        ("--move", "R1=1mm,1mm", "--only", "R1"),
        ("--strategy", "manual", "--only", "R1"),
        ("--move", "R1=1,1"),
        ("--pitch", "0mm"),
        ("--gap", "1"),
        ("--strategy", "anneal"),
    ):
        code, _, err, _ = run(monkeypatch, tmp_path, "place", board, *args, "--dry-run")
        assert (code, err["code"]) == (2, "FEN-2001"), args
    code, _, err, _ = run(monkeypatch, tmp_path, "place", str(tmp_path / "missing.kicad_pcb"), "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"


def test_native_board_and_the_example(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert COMMAND.mutates and COMMAND.name == "place"
    assert (
        COMMAND.example_args[-1] == "--dry-run" and COMMAND.mutation_example_args == COMMAND.example_args[:-1]
    )
    code, env, err, _ = run(monkeypatch, tmp_path, "place", *COMMAND.example_args)
    assert code == 0, (env["issues"], err)
    assert [p["path"] for p in env["result"]["plan"]] == ["fenolite-placed.kicad_pcb"]
    (row,) = env["result"]["moved"]
    assert (row["ref"], row["path"]) == ("R1", "R1")
    assert row["from"] == {"x": 20 * MM, "y": 15 * MM, "rotation": 90_000_000, "side": "top"}
    assert row["to"] == {"x": 12 * MM, "y": 8 * MM, "rotation": 90_000_000, "side": "top"}
    assert not (tmp_path / "fenolite-placed.kicad_pcb").exists()
    # a native board has no staged part, so the grid has nothing to do
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(FIXTURE), "--dry-run")
    assert code == 0 and env["result"]["moved"] == [] and env["result"]["strategy"] == "grid"


# --- keep-outs, rules and measures (change c0113) -------------------------------------------------------

NEAR = '\ndesign.near("led", d1, r1.pad(2), within=mm(5))\n'
NO_RULES = {"near": {"judged": 0, "failed": 0, "skipped": 0}}


def with_keepout(folder: Path, box: tuple[int, int, int, int], *layers: str) -> None:
    """Draw a rule area that forbids footprints on the built board, ``box`` in millimetres from the
    outline's top-left corner, as a user would in KiCad."""
    import dataclasses

    from fenolite.backends.kicad.pcb import write_board
    from fenolite.core.coords import Point
    from fenolite.model.board import Keepout

    path = folder / "blink.kicad_pcb"
    design = read_board(path)
    assert design.board is not None
    x0, y0, x1, y1 = (ORIGIN + value * MM for value in box)
    ring = (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))
    area = Keepout(
        id="kpo_00000000-0000-4000-8000-000000000001", outline=ring, layers=layers, no_footprints=True
    )
    board = dataclasses.replace(design.board, keepouts=(area,))
    path.write_text(write_board(dataclasses.replace(design, board=board), target=10).text, encoding="utf-8")


def test_nothing_to_place_reports_rules_and_measures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Nothing to place": no move, no change of the measures, no write."""
    folder = built(monkeypatch, tmp_path)
    snapshot = tree_snapshot(folder)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--confirm")
    assert code == 0 and tree_snapshot(folder) == snapshot
    result = env["result"]
    assert result["moved"] == [] and result["rules"] == NO_RULES
    measures = result["measures"]
    assert measures["change"] == {"hpwl": 0, "ratsnest": 0}
    assert measures["nets"] > 0 and measures["hpwl"] >= measures["ratsnest"] > 0
    assert set(measures) == {"nets", "hpwl", "ratsnest", "longest", "left_out", "congestion", "change"}
    # the class Default of the built project: a 0.2 mm track and a 0.2 mm clearance
    assert measures["congestion"]["pitch"] == 400_000 and measures["congestion"]["tracks_per_layer"] == 5
    assert env["evidence"]["level"] == "KICAD-VERIFIED"


def test_keepout_avoided_by_the_grid_and_refused_for_a_move(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Keep-out avoided by the grid and refused for a move"."""
    plain = built(monkeypatch, tmp_path, STAGED[0], name="plain")
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(plain), "--confirm")
    assert code == 0
    free = footprints(plain)["R1"].position
    corner = BBox(ORIGIN, ORIGIN, ORIGIN + 8 * MM, ORIGIN + 8 * MM)
    assert corner.contains_point(free)  # without the area, the grid puts R1 into the corner

    folder = built(monkeypatch, tmp_path, STAGED[0])
    with_keepout(folder, (0, 0, 8, 8), "F.Cu")
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(folder), "--confirm")
    assert code == 0, (env["issues"], err)
    placed = footprints(folder)["R1"].position
    assert region(folder).contains_point(placed) and not corner.contains_point(placed)
    assert [row["ref"] for row in env["result"]["moved"]] == ["R1"]
    assert not [c for c in codes(env) if c.startswith("place.keepout")]
    # the board holds a rule area that forbids footprints: the keep-out evidence joins the envelope
    assert "H-K-PLACE-KEEPOUT" in env["evidence"]["hypotheses"]
    assert env["evidence"]["level"] == KEEPOUT_EVIDENCE.level.value

    snapshot = tree_snapshot(folder)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=4mm,4mm", "--confirm")
    assert code == 5 and tree_snapshot(folder) == snapshot
    found = [i for i in env["issues"] if i["code"] == "place.keepout"]
    assert [(i["severity"], i["where"]) for i in found] == [("error", "R1")]
    assert env["result"]["legality"] == {"place.keepout": 1}
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", str(folder), "--move", "R1=4mm,4mm", "--force", "--confirm"
    )
    assert code == 5 and "place.keepout" in codes(env)
    assert corner.contains_point(footprints(folder)["R1"].position)  # written all the same


def test_keepout_on_the_back_does_not_judge_a_part_on_the_top(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = built(monkeypatch, tmp_path)
    with_keepout(folder, (0, 0, 8, 8), "B.Cu")
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=4mm,4mm", "--dry-run")
    assert code == 0 and not [c for c in codes(env) if c.startswith("place.keepout")]


def test_rules_and_measures_of_a_move(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Rules and measures of a move": a rule is reported as a warning and never refuses."""
    script = blink_variant(tmp_path / "near-src", append=NEAR)
    folder = tmp_path / "near"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(folder), "--confirm")
    assert code == 0, (env.get("issues"), err)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=36mm,18mm", "--dry-run")
    assert code == 0, env["issues"]
    assert "placement.too-far" not in codes(env)
    assert env["result"]["rules"] == {"near": {"judged": 1, "failed": 0, "skipped": 0}}
    assert env["result"]["measures"]["change"]["hpwl"] < 0
    # a judged rule is Fenolite's own definition: the envelope is never above INFERRED
    assert env["evidence"]["level"] == "INFERRED"

    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=2mm,2mm", "--dry-run")
    assert code == 0, env["issues"]
    found = [i for i in env["issues"] if i["code"] == "placement.too-far"]
    assert [(i["severity"], i["where"]) for i in found] == [("warning", "D1")]
    assert env["result"]["rules"] == {"near": {"judged": 1, "failed": 1, "skipped": 0}}
    assert len(env["result"]["plan"]) == 1  # a rule never refuses the write
    assert env["result"]["measures"]["change"]["hpwl"] != 0


def test_native_board_has_measures_and_no_rules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "place", str(FIXTURE), "--strategy", "manual", "--dry-run")
    assert code == 0, env["issues"]
    assert env["result"]["rules"] == NO_RULES and env["result"]["measures"]["nets"] > 0
    assert env["result"]["measures"]["change"] == {"hpwl": 0, "ratsnest": 0}
