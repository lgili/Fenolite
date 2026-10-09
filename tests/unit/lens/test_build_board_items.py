# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas and drawings of a script in a build (capability design-dsl, "Board items in a build";
layout-lens, "Board items declared in the script"; copper-check, "Keep-out findings" through the build's
copper guard; change c0103). No tool runs."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from _altium_drc import plant
from _buildhelp import blink, build
from _routed import NAME, Routed, codes

from fenolite.backends.kicad import boarditems
from fenolite.backends.kicad.boarditems import is_item_uuid, item_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, mm, select
from fenolite.model.board import Board

ANT = "[(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))]"
AREA = f'design.rule_area("ANT", {ANT}, forbid=("tracks", "vias"))\n'
LABEL = 'design.text("rev", "REV A", (mm(2), mm(2)))\n'
DIMENSION = 'design.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))\n'
ITEMS = AREA + LABEL + DIMENSION
CORNER = "[(mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5)), (mm(1), mm(5))]"
HV = f'design.rule_area("HV", {CORNER})\n'
SELECT = "from fenolite.dsl import select\n"
COUNTS = {"rule_areas": 1, "texts": 1, "graphics": 0, "dimensions": 1}
ZERO = {"regenerated": 0, "stale": 0}
DRAWN = "30000000-0000-4000-8000-00000000000{}"
"""Version-4 uuids of items drawn in KiCad."""


def variant() -> Design:
    """The blink with a keep-out, a label and a dimension."""
    design = blink()
    corners = [(mm(40), mm(0)), (mm(50), mm(0)), (mm(50), mm(4)), (mm(40), mm(4))]
    design.rule_area("ANT", corners, forbid=("tracks", "vias"))
    design.text("rev", "REV A", (mm(2), mm(2)))
    design.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))
    return design


def board_of(text: str) -> Board:
    board = read_board(text).board
    assert board is not None
    return board


def item_codes(env: dict[str, Any]) -> list[str]:
    return [code for code in codes(env) if code.startswith("kicad.board-item.")]


@pytest.mark.parametrize("target", [9, 10])
def test_blink_with_a_keep_out_a_label_and_a_dimension(target: int) -> None:
    """Scenario "Blink with a keep-out, a label and a dimension": written for both targets, and read
    back with the uuids that ``item_uuid`` gives their ids."""
    output = build(variant(), target)
    assert not [i for i in output.issues if i.severity == "error"], [i.code for i in output.issues]
    assert output.summary["board_items"] == COUNTS
    board = board_of(output.files["blink.kicad_pcb"].decode("utf-8"))
    (area,) = board.keepouts
    assert (area.name, area.no_tracks, area.no_vias, area.no_pads) == ("ANT", True, True, False)
    assert area.layers == ("F.Cu", "B.Cu") and len(area.outline) == 4
    assert area.native_ids["kicad"] == item_uuid(derived_id("kpo", "dsl", "area:ANT"))
    (text,) = board.texts
    assert (text.text, text.layer, text.thickness) == ("REV A", "F.SilkS", 150_000)
    assert (text.position.x, text.position.y) == (102_000_000, 102_000_000)
    assert text.native_ids["kicad"] == item_uuid(derived_id("txt", "dsl", "text:rev"))
    (dimension,) = board.dimensions
    assert (dimension.kind, dimension.layer, dimension.offset) == ("aligned", "Dwgs.User", -3_000_000)
    assert dimension.end.x - dimension.start.x == 40_000_000 and dimension.direction is None
    assert dimension.native_ids["kicad"] == item_uuid(derived_id("dim", "dsl", "dimension:width"))
    for hypothesis in boarditems.EVIDENCE.hypotheses:
        assert hypothesis in output.evidence.hypotheses
    assert output.layout is not None and output.layout.board is not None
    assert [k.name for k in output.layout.board.keepouts] == ["ANT"]


def test_a_design_without_the_calls_reports_zeros() -> None:
    output = build(blink(), 10)
    assert output.summary["board_items"] == {"rule_areas": 0, "texts": 0, "graphics": 0, "dimensions": 0}
    assert output.summary["preserved"]["board_items"] == ZERO  # type: ignore[index]
    assert "H-K-DIM" not in output.evidence.hypotheses
    text = output.files["blink.kicad_pcb"].decode("utf-8")
    assert "dimension" not in text and "(name" not in text


def test_graphics_are_written_and_read_back() -> None:
    design = blink()
    design.line("l", (mm(1), mm(29)), (mm(9), mm(29)), layer="F.Fab", width=mm(0.1))
    design.rect("r", (mm(1), mm(25)), (mm(3), mm(27)), layer="F.Mask", width=mm(0), fill=True)
    design.circle("c", (mm(6), mm(26)), (mm(7), mm(26)), layer="F.SilkS", width=mm(0.12))
    design.arc("a", (mm(10), mm(26)), (mm(11), mm(27)), (mm(12), mm(26)), layer="Dwgs.User", width=mm(0.1))
    design.polygon(
        "p", [(mm(14), mm(25)), (mm(16), mm(25)), (mm(15), mm(27))], layer="B.SilkS", width=mm(0.1)
    )
    design.text("t", "BACK", (mm(20), mm(28)), layer="B.SilkS", justify="right top", rot=90)
    output = build(design, 10)
    assert not [i for i in output.issues if i.severity == "error"]
    assert output.summary["board_items"] == {"rule_areas": 0, "texts": 1, "graphics": 5, "dimensions": 0}
    board = board_of(output.files["blink.kicad_pcb"].decode("utf-8"))
    scripted = {g.native_ids["kicad"]: g for g in board.graphics if is_item_uuid(g.native_ids["kicad"])}
    wanted = {key: item_uuid(derived_id("gfx", "dsl", f"graphic:{key}")) for key in "lrcap"}
    assert set(scripted) == set(wanted.values())
    assert {key: scripted[wanted[key]].kind for key in wanted} == {
        "l": "line", "r": "rect", "c": "circle", "a": "arc", "p": "polygon"
    }  # fmt: skip
    assert (scripted[wanted["r"]].filled, scripted[wanted["r"]].width) == (True, 0)
    assert scripted[wanted["l"]].width == 100_000 and scripted[wanted["l"]].layer == "F.Fab"
    (text,) = board.texts
    assert (text.h_justify, text.v_justify, text.rotation) == ("right", "top", 90_000_000)


def test_unknown_area_stops_the_build_of_a_model() -> None:
    design = blink()
    design.rules.rule("far", "clearance", where=select.area("NOPE"), min=mm(1))
    output = build(design, 10)
    (found,) = [i for i in output.issues if i.code == "build.area-unknown"]
    assert found.severity == "error" and "'far'" in found.message and "'NOPE'" in found.message
    assert found.hint == "declare the area with design.rule_area() or remove the selector"
    assert output.files == {}


def test_unknown_area_stops_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Unknown area stops the build": exit 5, one issue, nothing written."""
    project = Routed(tmp_path, monkeypatch, confirm=False)
    rule = 'design.rules.rule("far", "clearance", where=select.area("NOPE"), min=mm(1))\n'
    plant(project, SELECT, rule)
    code, env, _ = project.build("--confirm")
    assert code == 5
    (found,) = [i for i in env["issues"] if i["code"] == "build.area-unknown"]
    assert "far" in found["message"] and "NOPE" in found["message"]
    assert not project.out.exists() or list(project.out.iterdir()) == []


def test_a_declared_area_is_a_valid_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    rule = 'design.rules.rule("hv", "clearance", where=select.area("H*"), min=mm(2))\n'
    plant(project, SELECT, HV, rule)
    code, env, err = project.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    rules = (project.out / f"{NAME}.kicad_dru").read_text(encoding="utf-8")
    assert "(condition \"A.intersectsArea('H*')\")" in rules
    assert [k.name for k in board_of(project.board.read_text(encoding="utf-8")).keepouts] == ["HV"]


def test_an_area_rule_for_target_9_waits_for_its_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``SELECTOR_SUPPORT["area"]`` holds the majors of the probe ``dru-cond-area`` only: a target outside
    it refuses the rule, and never writes it unproved."""
    from fenolite.backends.kicad import rulemap

    if 9 in rulemap.SELECTOR_SUPPORT["area"]:
        pytest.skip("dru-cond-area is recorded for 9.0: the rule is written for target 9")
    project = Routed(tmp_path, monkeypatch, target=9, confirm=False)
    plant(project, SELECT, HV, 'design.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))\n')
    code, env, err = project.build("--confirm")
    assert code != 0 and "area" in (err + str(env.get("issues")))
    assert not project.board.is_file()


def _drawn_area(name: str = "HV") -> str:
    return (
        f'\t(zone (layers "F.Cu" "B.Cu") (uuid "{DRAWN.format(1)}") (name "{name}") (hatch edge 0.5)\n'
        "\t\t(keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour allowed)"
        " (footprints allowed))\n"
        "\t\t(polygon (pts (xy 101 101) (xy 105 101) (xy 105 105) (xy 101 105)))\n\t)\n"
    )


def _drawn_text() -> str:
    return (
        f'\t(gr_text "HAND" (at 103 128 0) (layer "F.SilkS") (uuid "{DRAWN.format(2)}")\n'
        "\t\t(effects (font (size 1 1) (thickness 0.15)))\n\t)\n"
    )


def _append(*items: str) -> Any:
    def change(text: str) -> str:
        body = text.rstrip()
        assert body.endswith(")")
        return body[:-1] + "".join(items) + ")\n"

    return change


def test_an_area_drawn_in_kicad_is_a_valid_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "An area drawn in KiCad is a valid target"."""
    project = Routed(tmp_path, monkeypatch)
    assert uuid.UUID(DRAWN.format(1)).version == 4
    project.edit_board(_append(_drawn_area()))
    plant(project, SELECT, 'design.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))\n')
    code, env, err = project.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    (area,) = board_of(project.board.read_text(encoding="utf-8")).keepouts
    assert (area.name, area.native_ids["kicad"]) == ("HV", DRAWN.format(1))
    rules = (project.out / f"{NAME}.kicad_dru").read_text(encoding="utf-8")
    assert "(condition \"A.intersectsArea('HV')\")" in rules
    assert env["result"]["board_items"] == {"rule_areas": 0, "texts": 0, "graphics": 0, "dimensions": 0}
    assert item_codes(env) == []


@pytest.mark.parametrize("target", [9, 10])
def test_reproducible_builds_with_board_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    """Scenario "Reproducible builds with board items": two processes with different seeds and hash
    seeds write every file with the same bytes."""
    project = Routed(tmp_path, monkeypatch, target=target, confirm=False)
    plant(project, ITEMS)
    outputs = []
    for seed in ("1", "2"):
        out = tmp_path / f"out-{seed}"
        command = [
            sys.executable, "-m", "fenolite", "--kicad-version", str(target), "--seed", seed, "build",
            str(project.script), "--out", str(out), "--confirm", "--json",
        ]  # fmt: skip
        env = {**os.environ, "PYTHONHASHSEED": seed, "KICAD_CONFIG_HOME": str(tmp_path / "config")}
        run = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
        assert run.returncode == 0, run.stderr
        outputs.append(
            {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
        )
    assert outputs[0] == outputs[1]
    board = board_of(outputs[0][f"{NAME}.kicad_pcb"].decode("utf-8"))
    assert (len(board.keepouts), len(board.texts), len(board.dimensions)) == (1, 1, 1)


# --- rebuilds (layout-lens, "Board items declared in the script") ---------------------------------------


def test_rebuild_writes_the_same_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, ITEMS)
    code, env, err = project.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    assert env["result"]["board_items"] == COUNTS and env["result"]["preserved"]["board_items"] == ZERO
    first = project.files()
    code, env, _ = project.build("--confirm")
    assert code == 0 and project.files() == first
    assert env["result"]["preserved"]["board_items"] == ZERO and item_codes(env) == []


def test_rebuild_edited_label_is_written_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Edited label is written again"."""
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, ITEMS)
    assert project.build("--confirm")[0] == 0
    built = project.files()
    old = '(gr_text "REV A"\n\t\t(at 102 102 0)'
    project.edit_board(lambda text: text.replace(old, '(gr_text "REV A"\n\t\t(at 103 102 0)'))
    assert project.files() != built
    code, env, _ = project.build("--confirm")
    assert code == 0 and project.files()[f"{NAME}.kicad_pcb"] == built[f"{NAME}.kicad_pcb"]
    (note,) = [i for i in env["issues"] if i["code"] == "kicad.board-item.regenerated"]
    native = item_uuid(derived_id("txt", "dsl", "text:rev"))
    assert note["severity"] == "info" and "text" in note["message"] and "position" in note["message"]
    assert note["where"] == native
    assert env["result"]["preserved"]["board_items"] == {"regenerated": 1, "stale": 0}


def test_rebuild_removed_rule_area_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Removed rule area is removed"."""
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, AREA, HV)
    assert project.build("--confirm")[0] == 0
    assert [k.name for k in board_of(project.board.read_text(encoding="utf-8")).keepouts] == ["ANT", "HV"]
    project.edit_script(HV, "")
    code, env, _ = project.build("--confirm")
    assert code == 0
    assert [k.name for k in board_of(project.board.read_text(encoding="utf-8")).keepouts] == ["ANT"]
    (stale,) = [i for i in env["issues"] if i["code"] == "kicad.board-item.stale"]
    assert stale["severity"] == "warning" and "HV" in stale["message"] and "rule area" in stale["message"]
    assert env["result"]["preserved"]["board_items"] == {"regenerated": 0, "stale": 1}


def test_rebuild_keeps_drawings_made_in_kicad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Drawings made in KiCad are kept": no code, and the second build writes the bytes of the
    first."""
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, ITEMS)
    assert project.build("--confirm")[0] == 0
    project.edit_board(_append(_drawn_text(), _drawn_area("HAND")))
    code, env, _ = project.build("--confirm")
    assert code == 0 and item_codes(env) == []
    first = project.files()
    board = board_of(first[f"{NAME}.kicad_pcb"].decode("utf-8"))
    assert [t.text for t in board.texts] == ["HAND", "REV A"]
    assert [k.name for k in board.keepouts] == ["HAND", "ANT"]
    assert board.texts[0].native_ids["kicad"] == DRAWN.format(2)
    code, env, _ = project.build("--confirm")
    assert code == 0 and item_codes(env) == [] and project.files() == first
    assert env["result"]["preserved"]["board_items"] == ZERO


# --- the copper guard -----------------------------------------------------------------------------

OVER_TRACK = "[(mm(15), mm(6)), (mm(25), mm(6)), (mm(25), mm(8)), (mm(15), mm(8))]"
"""A box over the script track of ``LED_DRV`` that runs along y = 7 mm."""


def test_guard_stops_copper_in_a_keep_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, f'design.rule_area("KO", {OVER_TRACK}, layers=("F.Cu",), forbid=("tracks",))\n')
    code, env, _ = project.build("--confirm")
    assert code == 5 and not project.board.is_file()
    (found,) = [i for i in env["issues"] if i["code"] == "copper.keepout"]
    assert found["severity"] == "error" and "KO" in found["message"] and "LED_DRV" in found["message"]
    assert "tracks" in found["message"] and "F.Cu" in found["message"]


def test_guard_in_warn_mode_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, f'design.rule_area("KO", {OVER_TRACK}, layers=("F.Cu",), forbid=("tracks",))\n')
    code, env, err = project.build("--copper-check", "warn", "--confirm")
    assert code == 0, err
    (found,) = [i for i in env["issues"] if i["code"] == "copper.keepout"]
    assert found["severity"] == "warning" and project.board.is_file()


def test_guard_applies_an_area_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A track 1.7 mm from the track inside an area is clean, and a clearance error once a 2 mm rule is
    scoped to that area."""
    area = f'design.rule_area("HV", {OVER_TRACK})\n'
    near = 'design.track("near", r1.pad(2), (mm(36), mm(5)), (mm(20), mm(5)), width=mm(0.3))\n'
    project = Routed(tmp_path, monkeypatch, confirm=False)
    plant(project, area, near)
    code, env, err = project.build("--dry-run")
    assert code == 0, (env.get("issues"), err)
    plant(project, SELECT, 'design.rules.rule("hv", "clearance", where=select.area("HV"), min=mm(2))\n')
    code, env, _ = project.build("--dry-run")
    assert code == 5
    found = [i for i in env["issues"] if i["code"] == "copper.clearance"]
    assert found and all("2 mm (rule:" in i["message"] and "hv)" in i["message"] for i in found)
