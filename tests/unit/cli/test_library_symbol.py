# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library symbol`` and the action words of ``fenolite library`` (change c0261, capability
cli-contract, "Library action words" and "Library symbol command"). The board form keeps its own tests in
``test_library_cmd.py``, which this change does not edit."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.catalog.pins import read_pins
from fenolite.cli.cmd_library import ACTIONS, AVAILABLE

ROOT = Path(__file__).resolve().parents[3]
PINS = ROOT / "tests" / "data" / "pins"
EXAMPLES = ROOT / "examples" / "symbols" / "pins"


def _tables(tmp_path: Path) -> Path:
    folder = tmp_path / "pins"
    folder.mkdir()
    for path in (PINS / "example_buck.toml", EXAMPLES / "EXM120.toml"):
        shutil.copyfile(path, folder / path.name)
    return folder


def _files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_plan_and_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tables(tmp_path)
    before = _files(tmp_path)
    args = ("library", "symbol", "pins/example_buck.toml", "--out", "lib/Example.kicad_sym")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, env
    assert _files(tmp_path) == before
    result = env["result"]
    assert (result["library"], result["out"], result["format"]) == (
        "Example",
        "lib/Example.kicad_sym",
        "kicad_sym",
    )
    assert [row["name"] for row in result["symbols"]] == ["EXB6202", "EXB6202DR"]
    assert result["symbols"][1]["extends"] == "EXB6202"
    unit = result["symbols"][0]["units"][0]
    assert unit["pins"] == {"left": ["FB", "EN"], "right": ["SW", "BST"], "top": ["VIN"], "bottom": ["GND"]}
    (planned,) = result["plan"]
    assert planned["path"] == "lib/Example.kicad_sym"
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", result["plan_id"])
    assert code == 0, env
    data = (tmp_path / "lib" / "Example.kicad_sym").read_bytes()
    (receipt,) = env["receipt"]["written"]
    assert receipt["path"] == "lib/Example.kicad_sym"
    assert receipt["sha256"] == hashlib.sha256(data).hexdigest() == planned["sha256"]
    base, derived, _ = generate_symbol(read_pins(PINS / "example_buck.toml"), library="Example")
    assert data.decode("utf-8") == write_symbol_library([base, *derived], target=10)
    back = {s.name for s in read_symbol_library(tmp_path / "lib" / "Example.kicad_sym")}
    assert back == {"EXB6202", "EXB6202DR"}


def test_several_tables_and_units(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tables(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "symbol", "pins/example_buck.toml", "pins/EXM120.toml",
        "--out", "Parts.kicad_sym", "--library", "Mine", "--dry-run",
    )  # fmt: skip
    assert code == 0, env
    rows = {row["name"]: row for row in env["result"]["symbols"]}
    assert set(rows) == {"EXB6202", "EXB6202DR", "EXM120", "EXM120-T"}
    assert [u["name"] for u in rows["EXM120"]["units"]] == ["", "", "POWER"]
    assert rows["EXM120"]["issues"] == ["symbol.units-split"]
    assert [i["code"] for i in env["issues"]] == ["symbol.units-split"]
    assert env["result"]["library"] == "Mine"


def test_schlib(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tables(tmp_path)
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        "library",
        "symbol",
        "pins/EXM120.toml",
        "--out",
        "lib/Example.SchLib",
        "--confirm",
    )
    assert code == 0, env
    assert env["result"]["format"] == "altium_schlib"
    from fenolite.backends.altium.read.schlib import read_schlib

    library = read_schlib((tmp_path / "lib" / "Example.SchLib").read_bytes(), file="Example.SchLib")
    assert {c.name for c in library.components} >= {"EXM120", "EXM120-T"}


@pytest.mark.parametrize("out", ["lib/Example.lib", "Example", "/tmp/Example.kicad_sym"])
def test_wrong_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, out: str) -> None:
    _tables(tmp_path)
    before = _files(tmp_path)
    code, _, error, _ = run(
        monkeypatch, tmp_path, "library", "symbol", "pins/example_buck.toml", "--out", out
    )
    assert code == 2 and error["code"] == "FEN-2001"
    assert _files(tmp_path) == before


def test_malformed_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _tables(tmp_path)
    (folder / "bad.toml").write_text('schema = "fenolite.pins.v0"\n', encoding="utf-8")
    code, _, error, _ = run(
        monkeypatch, tmp_path, "library", "symbol", "pins/bad.toml", "--out", "x.kicad_sym"
    )
    assert code == 3 and error["code"] == "FEN-3004"


@pytest.mark.parametrize("action", sorted(set(ACTIONS) - AVAILABLE))
def test_reserved_action(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, action: str) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "library", action)
    assert code == 2 and error["code"] == "FEN-2001" and "not available" in error["message"]
    assert _files(tmp_path) == []


def test_existing_form_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The board form keeps its result and plan; two boards or ``--library`` are refused."""
    from test_derive import board_text  # pyright: ignore[reportMissingImports]
    from test_library_cmd import _board  # pyright: ignore[reportMissingImports]

    _board(tmp_path, board_text())
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "lib.pretty", "--dry-run"
    )
    assert code == 0 and [w["path"] for w in env["result"]["plan"]] == [
        "lib.pretty/LED_THT_3mm.kicad_mod",
        "lib.pretty/R_0603.kicad_mod",
    ]
    assert env["result"]["board"] == "board.kicad_pcb"
    for extra in (("other.kicad_pcb",), ("--library", "X")):
        code, _, error, _ = run(
            monkeypatch, tmp_path, "library", "board.kicad_pcb", *extra, "--out", "lib.pretty"
        )
        assert code == 2 and error["code"] == "FEN-2001"
