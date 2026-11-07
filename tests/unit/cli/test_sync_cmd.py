# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite sync --to-source`` (capability cli-contract, "Sync command"; design-dsl, "Placements file in a
build"; changes c0069 and c0250). Each test works on a copy of the blink built into ``tmp_path``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from _layout_edit import D1_SHIFT, EDIT_UUIDS, edit_blink, move_footprint, move_symbol
from _project import COPPER_WARN, Project, codes, footprint

from fenolite.backends.kicad.sch import read_schematic
from fenolite.cli.cmd_build import MINIMAL
from fenolite.cli.cmd_sync import COMMAND, EXAMPLE_SYNC_OUT
from fenolite.dsl import BOARD_ORIGIN
from fenolite.lens.edits import read_edits
from fenolite.lens.schplacements import read_placements as read_symbol_placements

MM = 1_000_000
SYNC = ("--to-source",)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def source(p: Project) -> Path:
    return p.script.parent / "edits.toml"


def legacy(p: Project) -> Path:
    return p.script.parent / "placements.toml"


def symbols(p: Project) -> Path:
    return p.script.parent / "schematic-placements.toml"


def schematic(p: Project) -> Path:
    return p.out / "blink.kicad_sch"


def synced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    """A blink built, edited by ``edit_blink`` and synced."""
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    code, _, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    return p


def test_placements_written_beside_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    placed, _ = footprint(p.read(), "D1")
    p.edit_board(edit_blink)
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    assert [w["path"] for w in env["receipt"]["written"]] == [str(source(p)), str(symbols(p))]  # type: ignore[index]
    parts = read_edits(source(p).read_text(encoding="utf-8"), origin=BOARD_ORIGIN).parts
    assert list(parts) == ["D1"]
    assert parts["D1"].values["position"][0] == placed.position.x + D1_SHIFT  # type: ignore[attr-defined, index]
    assert parts["D1"].over == {"position": (placed.position.x, placed.position.y)}  # type: ignore[attr-defined]
    result = env["result"]
    assert result["placements"] == 1 and result["symbols"] == 3  # type: ignore[index]
    assert result["edits"] == ["D1#position"]  # type: ignore[index]
    assert result["files"] == ["edits.toml", "schematic-placements.toml"]  # type: ignore[index]
    assert result["board"] == "blink.kicad_pcb"  # type: ignore[index]
    assert env["evidence"]["level"] == "INFERRED" and env["issues"] == []  # type: ignore[index]


def test_mutation_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, err = p.run("sync", *SYNC)
    assert code == 4 and json.loads(err)["code"] == "FEN-4001" and not source(p).exists()
    assert [w["path"] for w in env["result"]["plan"]] == [str(source(p)), str(symbols(p))]  # type: ignore[index]
    code, env, _ = p.run("sync", *SYNC, "--dry-run")
    assert code == 0 and not source(p).exists()
    first = p.run("sync", *SYNC, "--dry-run")[1]["result"]["plan"]  # type: ignore[index]
    assert first == env["result"]["plan"]  # type: ignore[index]
    code, _, _ = p.run("sync", *SYNC, "--confirm")
    assert code == 0 and source(p).is_file() and symbols(p).is_file()
    # nothing changed: nothing is planned, and no confirmation is asked
    code, env, _ = p.run("sync", *SYNC)
    assert code == 0 and env["result"]["files"] == [] and "plan" not in env["result"]  # type: ignore[index,operator]
    # a changed board is written again, with a backup of the committed file
    p.edit_board(lambda t: move_footprint(t, "R1", MM, 0))
    code, env, _ = p.run("sync", *SYNC, "--confirm")
    assert code == 0 and source(p).with_name("edits.toml.bak").is_file()


def test_stale_file_found_by_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = synced(tmp_path, monkeypatch)
    before = source(p).read_bytes()
    p.edit_board(lambda t: move_footprint(t, "R1", MM, 0))
    code, env, _ = p.run("sync", *SYNC, "--check")
    assert code == 5 and source(p).read_bytes() == before
    (found,) = [i for i in env["issues"] if i["code"] == "sync.would-change"]  # type: ignore[union-attr,index]
    assert found["where"] == "edits.toml" and 'part."R1"' in found["message"]
    assert found["severity"] == "error" and "plan" not in env["result"]  # type: ignore[operator]


def test_current_file_passes_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = synced(tmp_path, monkeypatch)
    code, env, _ = p.run("sync", *SYNC, "--check")
    assert code == 0 and "sync.would-change" not in codes(env)


def test_check_without_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, env, _ = p.run("sync", *SYNC, "--check")
    assert code == 5 and codes(env) == ["sync.would-change"] * 2 and not source(p).exists()
    assert [i["where"] for i in env["issues"]] == ["edits.toml", "schematic-placements.toml"]  # type: ignore[union-attr,index]


def test_usage_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, _, err = p.run("sync", "--dry-run")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001" and "--to-source" in json.loads(err)["message"]
    code, _, err = p.run("sync", *SYNC, "--check", "--confirm")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001"


def test_no_board_yet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, err = p.run("sync", *SYNC, "--dry-run", out=empty)
    error = json.loads(err)
    assert code == 3 and error["code"] == "FEN-3001" and "fenolite build" in error["hint"]


def test_script_errors_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script("design.add(u1, r1, d1)", 'design.add(u1, r1, d1)\ndesign.moved_net("A", "B")')
    code, _, err = p.run("sync", *SYNC, "--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004"


def test_complement_issues_through_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    p.edit_script('Net("LED_A")', 'Net("LED_ANODE")')
    code, env, _ = p.run("sync", *SYNC, "--dry-run")
    assert code == 0 and codes(env) == ["sync.net-dropped"]
    p.edit_script('value="330"', 'value="4k7"')
    code, env, _ = p.run("sync", *SYNC, "--dry-run")
    # with a base record the changed script is a pending change, which the next build writes (c0250)
    assert codes(env) == ["sync.net-dropped"] and env["result"]["pending"] == ["R1#value"]  # type: ignore[index]
    (p.out / "fenolite-base.json").unlink()
    code, env, _ = p.run("sync", *SYNC, "--dry-run")
    assert sorted(codes(env)) == ["sync.net-dropped", "sync.value-differs"]


def test_deterministic_and_without_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("sync started a subprocess")

    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    first = p.run("sync", *SYNC, "--dry-run")[1]["result"]["plan"]  # type: ignore[index]
    again = p.run("sync", *SYNC, "--dry-run")[1]["result"]["plan"]  # type: ignore[index]
    assert first == again and first[0]["sha256"]


# -- the schematic half ("Symbol placement extraction")

GRID = 1_270_000


def r1_origin(p: Project) -> tuple[int, int]:
    sheet = read_schematic(schematic(p).read_text(encoding="utf-8"), file="blink.kicad_sch")
    (symbol,) = [s for s in sheet.symbols if s.ref == "R1"]
    return symbol.position.x, symbol.position.y


def test_moved_symbol_reaches_the_source_and_the_next_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = Project(tmp_path, monkeypatch)
    x, y = r1_origin(p)
    text = schematic(p).read_text(encoding="utf-8")
    schematic(p).write_text(move_symbol(text, "R1", 2 * GRID, 0), encoding="utf-8")
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0 and env["issues"] == [], err
    entries = read_symbol_placements(symbols(p).read_text(encoding="utf-8"))
    assert sorted(entries) == ["D1", "R1", "U1"] and (entries["R1"].x, entries["R1"].y) == (x + 2 * GRID, y)
    assert env["result"]["symbols"] == 3  # type: ignore[index]
    # the next build draws the schematic again, with the symbol where the file says
    code, env, err = p.build("--confirm")
    assert code == 0, err
    assert r1_origin(p) == (x + 2 * GRID, y)
    # and a sync of that build changes nothing
    code, env, _ = p.run("sync", *SYNC, "--check")
    assert code == 0 and env["result"]["files"] == []  # type: ignore[index]


def test_symbol_off_the_grid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    text = schematic(p).read_text(encoding="utf-8")
    schematic(p).write_text(move_symbol(text, "R1", MM, 0), encoding="utf-8")
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    (found,) = [i for i in env["issues"] if i["code"] == "sync.symbol-off-grid"]  # type: ignore[union-attr,index]
    assert found["where"] == "R1" and found["severity"] == "warning" and "1.27 mm" in found["message"]
    entries = read_symbol_placements(symbols(p).read_text(encoding="utf-8"))
    assert sorted(entries) == ["D1", "U1"] and env["result"]["symbols"] == 2  # type: ignore[index]


def test_no_schematic_no_symbol_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    skipped = tmp_path / "skipped"
    assert p.run("build", "--schematic", "skip", "--confirm", out=skipped)[0] == 0
    code, env, err = p.run("sync", *SYNC, "--dry-run", out=skipped)
    assert code == 0, err
    assert env["result"]["symbols"] is None and env["result"]["files"] == ["edits.toml"]  # type: ignore[index]


# -- the file in a build ("Placements file in a build")


def test_file_places_a_part(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_script("r1.place(mm(32), mm(9))\n", "")
    legacy(p).write_text('schema = "fenolite.placements.v0"\n[part."R1"]\nx = 20\ny = 10\n', encoding="utf-8")
    fresh = tmp_path / "fresh"
    code, env, err = p.run("build", "--confirm", out=fresh)
    assert code == 0, err
    p.out = fresh
    r1, _ = footprint(p.read(), "R1")
    assert (r1.position.x, r1.position.y) == (120 * MM, 110 * MM)  # type: ignore[attr-defined]
    assert "layout.unplaced" not in codes(env)
    preserved = env["result"]["preserved"]["source"]  # type: ignore[index]
    assert preserved == {"file": "placements.toml", "used": ["R1"], "stale": [], "unknown": []}
    record = json.loads((fresh / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert len(record["source"]["placements.toml"]) == 64


def test_file_survives_a_discarded_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    placed, _ = footprint(p.read(), "D1")
    p.edit_board(edit_blink)
    assert p.run("sync", *SYNC, "--confirm")[0] == 0
    code, env, err = p.build("--discard-layout", "--confirm")
    assert code == 0, err
    design = p.read()
    d1, _ = footprint(design, "D1")
    assert d1.position.x == placed.position.x + D1_SHIFT  # type: ignore[attr-defined]
    assert design.board is not None and not design.board.tracks and not design.board.vias
    assert not set(EDIT_UUIDS) & {t.native_ids["kicad"] for t in design.board.tracks}
    overridden = [i["where"] for i in env["issues"] if i["code"] == "layout.place-overridden"]  # type: ignore[union-attr,index]
    assert overridden == ["D1"]
    assert env["result"]["preserved"]["source"]["used"] == ["D1"]  # type: ignore[index]


def test_invalid_file_stops_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    before = p.files()
    legacy(p).write_text(
        'schema = "fenolite.placements.v0"\n[part."R1"]\nx = 1\ny = 2\nside = "left"\n', encoding="utf-8"
    )
    code, env, _ = p.build("--confirm")
    (found,) = [i for i in env["issues"] if i["code"] == "layout.source-invalid"]  # type: ignore[union-attr,index]
    assert code == 5 and "R1" in found["message"] and "side" in found["message"]
    assert p.files() == before and env["result"]["files"] == []  # type: ignore[index]


def test_broken_file_exits_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    legacy(p).write_text('[part."R1"]\nx = 1\ny = 2\n', encoding="utf-8")
    code, _, err = p.build("--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004" and "placements.toml" in err


def test_stale_and_unknown_entries_in_a_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = synced(tmp_path, monkeypatch)
    assert p.build(*COPPER_WARN, "--confirm")[0] == 0  # the build records the synced edit in its base
    p.edit_board(lambda t: move_footprint(t, "D1", MM, 0))
    text = source(p).read_text(encoding="utf-8")
    source(p).write_text(text + '\n[part."R9"]\nx = 1\ny = 2\n\n[part."R9".over]\nunplaced = true\n', "utf-8")
    code, env, err = p.build(*COPPER_WARN, "--confirm")
    assert code == 0, err
    preserved = env["result"]["preserved"]["source"]  # type: ignore[index]
    assert preserved == {"file": "edits.toml", "used": [], "stale": ["D1"], "unknown": ["R9"]}
    assert {"layout.source-stale", "layout.source-unknown"} <= set(codes(env))


def test_altium_build_places_from_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    legacy(p).write_text('schema = "fenolite.placements.v0"\n[part."R1"]\nx = 20\ny = 10\n', encoding="utf-8")
    code, env, err = p.run("build", "--target", "altium", "--dry-run", out=tmp_path / "A")
    assert code == 0, err
    overridden = [i["where"] for i in env["issues"] if i["code"] == "layout.place-overridden"]  # type: ignore[union-attr,index]
    assert overridden == ["R1"]


# -- the registered example


def test_a_hole_in_the_placements_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A hole in the placements file" (design-dsl, "Board holes in a build"; change c0102): a
    hole part is a part for the layout lens, with no rule of its own."""
    p = Project(tmp_path, monkeypatch)
    p.script.write_text(
        p.script.read_text(encoding="utf-8")
        + 'design.hole("H1", mm(4), mm(4), drill=mm(3.2))\n'
        + 'h2 = design.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))\n'
        + "connect(gnd, h2[1])\n",
        encoding="utf-8",
    )
    code, _, err = p.build("--confirm")
    assert code == 0, err
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    # the holes stand where the script places them: edits.toml holds no table for them (c0250)
    text = source(p).read_text(encoding="utf-8")
    assert '[part."H1"]' not in text and '[part."H2"]' not in text
    code, env, err = p.build("--confirm")
    assert code == 0, err
    named = [i for i in env["issues"] if "H1" in i["message"] or "H2" in i["message"]]  # type: ignore[union-attr, index]
    assert not [i for i in named if i["code"] in ("layout.place-forced", "layout.source-stale")]


def test_command_registration() -> None:
    assert (COMMAND.name, COMMAND.mutates, COMMAND.schema) == ("sync", True, "fenolite.sync.v0")
    assert COMMAND.example_args == (str(MINIMAL), "--out", EXAMPLE_SYNC_OUT, "--to-source", "--dry-run")
    assert COMMAND.mutation_example_args is None


def test_example_folder_is_a_fresh_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``tests/data/lens/sync_minimal`` equals a target-10 build of the packaged minimal script."""
    import io

    import fenolite.cli.main as cli_main

    out, stdout = tmp_path / "fresh", io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    args = ["--kicad-version", "10", "build", str(MINIMAL), "--out", str(out), "--confirm", "--json"]
    assert cli_main.main(args) == 0
    committed = Path(EXAMPLE_SYNC_OUT)
    # the cache folder .fenolite/ is regenerable and not committed; sync reads the board only
    built = {
        p.relative_to(out).as_posix(): p.read_bytes()
        for p in sorted(out.rglob("*"))
        if p.is_file() and ".fenolite" not in p.parts
    }
    held = {
        p.relative_to(committed).as_posix(): p.read_bytes()
        for p in sorted(committed.rglob("*"))
        if p.is_file() and ".fenolite" not in p.parts
    }
    assert held == built


# -- edits and conflicts (change c0250)


def test_value_edit_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from _layout_edit import edit_properties

    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: edit_properties(t, None, {"R1": {"value": "4k7"}})[0] or t)
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    parts = read_edits(source(p).read_text(encoding="utf-8"), origin=BOARD_ORIGIN).parts
    assert parts["R1"].values == {"value": "4k7"} and parts["R1"].over == {"value": "330"}
    assert "H-K-EDIT-SCH-VALUE" in env["evidence"]["hypotheses"]  # type: ignore[index]
    # the next build applies the recorded edit: no edit.unrecorded
    code, env, err = p.build("--confirm")
    assert code == 0 and "edit.unrecorded" not in codes(env), err


def test_conflict_found_by_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from _layout_edit import edit_properties

    p = synced(tmp_path, monkeypatch)
    before = source(p).read_bytes()
    p.edit_board(lambda t: edit_properties(t, None, {"R1": {"value": "4k7"}})[0] or t)
    p.edit_script('value="330"', 'value="470"')
    code, env, _ = p.run("sync", *SYNC, "--check")
    assert code == 5 and source(p).read_bytes() == before
    (conflict,) = [i for i in env["issues"] if i["code"] == "sync.conflict"]  # type: ignore[union-attr,index]
    assert conflict["where"] == "R1#value"  # type: ignore[index]
    code, env, _ = p.run("sync", *SYNC, "--confirm")
    assert code == 5 and source(p).read_bytes() == before


def test_take_is_a_build_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    code, _, err = p.run("sync", *SYNC, "--take", "cad", "--dry-run")
    error = json.loads(err)
    assert code == 2 and error["code"] == "FEN-2001" and "fenolite build --take" in error["hint"]


def test_legacy_placements_migrated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(edit_blink)
    legacy(p).write_text(
        '# Written by fenolite sync --to-source.\nschema = "fenolite.placements.v0"\n\n'
        '[part."D1"]\nx = 42\ny = 20\nrotation = 0\nside = "bottom"\nlocked = false\n',
        encoding="utf-8",
    )
    code, env, err = p.run("sync", *SYNC, "--confirm")
    assert code == 0, err
    assert "sync.placements-migrated" in codes(env) and source(p).is_file()
    assert legacy(p).is_file(), "sync never writes or removes placements.toml"
