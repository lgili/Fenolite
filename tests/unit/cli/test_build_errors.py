# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Errors of the ``build`` command (capability design-dsl; change c0011)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
LIBS = ROOT / "tests" / "data" / "libs"


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], dict[str, object]]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def script(tmp_path: Path, body: str) -> Path:
    folder = tmp_path / "s"
    folder.mkdir(exist_ok=True)
    for kind, lib in (("fp", "Mini_v9.pretty"), ("sym", "Mini_v9.kicad_sym")):
        row = f'(lib (name "Mini") (type "KiCad") (uri "{(LIBS / lib).as_posix()}") (options "") (descr ""))'
        (folder / f"{kind}-lib-table").write_text(f"({kind}_lib_table\n\t(version 7)\n\t{row}\n)\n")
    path = folder / "design.py"
    path.write_text("from fenolite.dsl import *\n" + body, encoding="utf-8")
    return path


def test_script_error_keeps_the_malformed_input_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = script(tmp_path, "\n" * 10 + "raise ValueError('x')\n")
    code, _, err = run(monkeypatch, str(path), "--out", str(tmp_path / "o"), "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and str(err["where"]).endswith(":line:12")


def test_printing_scripts_keep_one_json_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = script(tmp_path, 'print("hello")\ndesign = Design("p")\ndesign.board(mm(10), mm(10))\n')
    code, env, _ = run(monkeypatch, str(path), "--out", str(tmp_path / "o"), "--dry-run")
    assert code == 0 and "hello" in env["result"]["script_output"]  # type: ignore[index]


def test_missing_design(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, str(script(tmp_path, "x = 1\n")), "--out", str(tmp_path / "o"))
    assert code == 3 and err["code"] == "FEN-3004" and "design" in str(err["message"])


def test_unresolved_libraries_list_every_lib_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = (
        'design = Design("p")\ndesign.board(mm(20), mm(20))\n'
        'design.add(Part("R1", "Nope:A", footprint="Mini:Mini_R_0603"), '
        'Part("D1", "Nope:B", footprint="Mini:Mini_R_0603"))\n'
    )
    code, env, err = run(monkeypatch, str(script(tmp_path, body)), "--out", str(tmp_path / "o"), "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"
    assert len(env["issues"]) == 2 and all(str(i["code"]).startswith("kicad.lib.") for i in env["issues"])  # type: ignore[union-attr]


def test_duplicate_refs_in_two_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = (
        'design = Design("p")\ndesign.board(mm(30), mm(30))\na, b = Module("a"), Module("b")\n'
        'a.add(Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603"))\n'
        'b.add(Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603"))\ndesign.add(a, b)\n'
    )
    code, env, _ = run(monkeypatch, str(script(tmp_path, body)), "--out", str(tmp_path / "o"), "--dry-run")
    assert code == 5 and "model.duplicate-ref" in [i["code"] for i in env["issues"]]  # type: ignore[union-attr]


def test_dsl_error_from_to_model_has_no_locator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = 'design = Design("p")\ndesign.board(mm(30), mm(30))\n'
    code, _, err = run(monkeypatch, str(script(tmp_path, body)), "--out", str(tmp_path / "o"), "--dry-run")
    assert code == 0, err
