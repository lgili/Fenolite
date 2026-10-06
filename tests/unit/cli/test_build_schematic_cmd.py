# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build`` with a schematic (capability design-dsl, "Schematic in a build", "Schematic
placements file", "Build command" and "Edited outputs are not overwritten"; change c0061)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _buildhelp import blink_variant
from _layout_edit import edit_blink

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"
SCHEMATIC = ("blink.kicad_sch", "sym-lib-table", "lib/Mini.kicad_sym", "lib/fenolite.kicad_sym")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def written(env: dict[str, object], out: Path) -> list[str]:
    return sorted(Path(w["path"]).relative_to(out).as_posix() for w in env["receipt"]["written"])  # type: ignore[index]


def codes(env: dict[str, object]) -> list[str]:
    return [i["code"] for i in env.get("issues", [])]  # type: ignore[union-attr]


def snapshot(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in folder.rglob("*")
        if p.is_file() and p.suffix != ".bak"
    }


def test_the_blink_gets_a_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")
    assert code == 0 and set(SCHEMATIC) <= set(written(env, out))
    assert len(written(env, out)) == 18
    assert env["result"]["schematic"] == {  # type: ignore[index]
        "file": "blink.kicad_sch",
        "paper": "A4",
        "sheets": 1,
        "files": [],
        "symbols": 5,
        "labels": 8,
        "no_connects": 29,
        "wires": 1,
        "satellites": 1,
        "power_flags": 2,
        "libraries": ["lib/Mini.kicad_sym", "lib/fenolite.kicad_sym"],
        "unconnected_pads": 29,
    }
    _, dry, _ = run(monkeypatch, str(BLINK), "--out", str(tmp_path / "C"), "--dry-run")
    kinds = {Path(w["path"]).name: w["kind"] for w in dry["result"]["plan"]}  # type: ignore[index]
    assert (kinds["blink.kicad_sch"], kinds["Mini.kicad_sym"], kinds["sym-lib-table"]) == (
        "kicad_sch",
        "kicad_sym",
        "sym-lib-table",
    )
    assert "H-K-SCH-MINIMAL" in env["evidence"]["hypotheses"]  # type: ignore[index]
    record = json.loads((out / ".fenolite" / "build.json").read_text(encoding="utf-8"))["files"]
    assert set(SCHEMATIC) <= set(record) and len(record) == 11


def test_skipping_the_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--schematic", "skip", "--confirm")
    assert code == 0 and not set(SCHEMATIC) & set(written(env, out))
    assert not [p for p in written(env, out) if p.endswith((".kicad_sch", ".kicad_sym"))]
    assert env["result"]["schematic"] is None  # type: ignore[index]
    assert "unconnected-(" not in (out / "blink.kicad_pcb").read_text(encoding="utf-8")


def test_a_rebuild_is_identical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    assert run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")[0] == 0
    before = snapshot(out)
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")
    assert code == 0 and snapshot(out) == before
    assert "build.schematic-replaced" not in codes(env)
    assert env["result"]["preserved"]["kept"] == ["D1", "R1", "U1"]  # type: ignore[index]


def test_an_edited_schematic_is_replaced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    assert run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")[0] == 0
    sheet = out / "blink.kicad_sch"
    first = sheet.read_bytes()
    edited = first.rstrip()[:-1] + b'\t(text "note" (at 20 20 0) (effects (font (size 1.27 1.27))))\n)\n'
    sheet.write_bytes(edited)
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--dry-run")
    assert code == 0 and codes(env).count("build.schematic-replaced") == 1 and sheet.read_bytes() == edited
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")
    assert code == 0
    (found,) = [i for i in env["issues"] if i["code"] == "build.schematic-replaced"]  # type: ignore[union-attr]
    assert found["severity"] == "warning" and "blink.kicad_sch" in found["where"]
    assert sheet.read_bytes() == first and (out / "blink.kicad_sch.bak").read_bytes() == edited


def test_an_edited_symbol_library_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    assert run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")[0] == 0
    library = out / "lib" / "Mini.kicad_sym"
    library.write_bytes(library.read_bytes().replace(b"Mini_R", b"Mini_X", 1))
    before = snapshot(out)
    code, env, err = run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")
    assert code == 7 and json.loads(err)["code"] == "FEN-7001" and snapshot(out) == before
    assert [i["where"] for i in env["issues"] if i["code"] == "build.layout-exists"] == [str(library)]  # type: ignore[union-attr]
    table = out / "sym-lib-table"
    library.write_bytes(before["lib/Mini.kicad_sym"])
    table.write_bytes(table.read_bytes() + b"\n")
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--dry-run")
    assert code == 7 and "build.layout-exists" in codes(env)
    code, _, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--discard-layout", "--confirm")
    assert code == 0 and (out / "sym-lib-table.bak").is_file()


def test_altium_target_refuses_the_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = (str(BLINK), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run")
    code, _, err = run(monkeypatch, *args, "--schematic", "skip")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001"
    assert run(monkeypatch, *args)[0] == 0


def test_a_placements_file_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src")
    (tmp_path / "src" / "schematic-placements.toml").write_text(
        '["R1"]\nx = 25.4\ny = 50.8\nrotation = 90\n\n["R9"]\nx = 50.8\ny = 50.8\n', encoding="utf-8"
    )
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0 and "build.symbol-placement-unknown" in codes(env)
    assert "(at 25.4 50.8 90)" in (out / "blink.kicad_sch").read_text(encoding="utf-8")
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--schematic", "skip", "--dry-run")
    assert code == 0 and "build.symbol-placement-unknown" not in codes(env)


def test_a_placement_off_the_grid_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src")
    (tmp_path / "src" / "schematic-placements.toml").write_text('["R1"]\nx = 25.5\ny = 50.8\n', "utf-8")
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5 and not out.exists()
    (found,) = [i for i in env["issues"] if i["code"] == "build.symbol-placement-invalid"]  # type: ignore[union-attr]
    assert found["severity"] == "error" and found["where"] == "R1" and "x" in found["message"]


def test_a_short_between_symbols_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src")
    (tmp_path / "src" / "schematic-placements.toml").write_text(
        '["R1"]\nx = 25.4\ny = 25.4\n\n["D1"]\nx = 25.4\ny = 33.02\nrotation = 270\n', encoding="utf-8"
    )
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5 and "build.symbol-short" in codes(env) and not out.exists()


def test_a_broken_placements_file_is_malformed_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src")
    (tmp_path / "src" / "schematic-placements.toml").write_text("[R1\n", encoding="utf-8")
    code, _, err = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004"


def test_rebuild_over_an_edited_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    assert run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")[0] == 0
    board = out / "blink.kicad_pcb"
    board.write_text(edit_blink(board.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")
    assert code == 0 and env["result"]["preserved"]["board"] is True  # type: ignore[index]
    assert env["result"]["preserved"]["kept"] == ["D1", "R1", "U1"]  # type: ignore[index]
    assert "layout.net-removed" not in codes(env) and "build.schematic-replaced" not in codes(env)


def test_help_names_the_option(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        cli_main.main(["build", "--help"])
    except SystemExit:
        pass
    text = " ".join(capsys.readouterr().out.split())
    assert "--schematic {write,skip}" in text and "sym-lib-table" in text


def test_altium_takes_copper_from_a_board_built_beside_a_schematic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """altium-build, "Copper from a routed KiCad board": a single-pad ``unconnected-(…)`` net is no net."""
    out = tmp_path / "B"
    assert run(monkeypatch, str(BLINK), "--out", str(out), "--confirm")[0] == 0
    board = out / "blink.kicad_pcb"
    assert board.read_text(encoding="utf-8").count('(net "unconnected-(') == 29
    args = (str(BLINK), "--out", str(tmp_path / "A"), "--target", "altium", "--dry-run")
    code, env, _ = run(monkeypatch, *args, "--copper-from", str(board))
    assert code == 0 and "altium.copper-board-mismatch" not in codes(env)
    wrong = tmp_path / "wrong.kicad_pcb"
    text = board.read_text(encoding="utf-8").replace('(net "unconnected-(U1-PA1-Pad2)")', '(net "GND")')
    wrong.write_text(text, encoding="utf-8", newline="\n")
    code, env, _ = run(monkeypatch, *args, "--copper-from", str(wrong))
    found = [i for i in env["issues"] if i["code"] == "altium.copper-board-mismatch"]  # type: ignore[union-attr]
    assert code == 5 and [i["where"] for i in found] == ["U1.2"]


# -- the layout option (c0070)


def test_help_names_the_layout_option(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        cli_main.main(["build", "--help"])
    except SystemExit:
        pass
    text = " ".join(capsys.readouterr().out.split())
    assert "--schematic-layout {readable,grid}" in text and "one sheet per module" in text


def test_altium_target_refuses_the_layout_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = (str(BLINK), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run")
    code, _, err = run(monkeypatch, *args, "--schematic-layout", "grid")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001"


def test_grid_layout_of_the_blink_has_a_label_on_every_pin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--schematic-layout", "grid", "--confirm")
    assert code == 0
    summary = env["result"]["schematic"]  # type: ignore[index]
    assert (summary["labels"], summary["wires"], summary["satellites"], summary["sheets"]) == (9, 0, 0, 1)
    assert "(wire" not in (out / "blink.kicad_sch").read_text(encoding="utf-8")
