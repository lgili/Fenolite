# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A build with a drawn schematic (capability design-dsl, "Drawn schematic in a build" and "Drawn schematic
build result"; change c0276)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import _drawn
import pytest
from _buildhelp import LIBS

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.sexpr import Node, parse

EXAMPLE = _drawn.EXAMPLE / "design.py"


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


def copy_example(folder: Path) -> Path:
    """The drawn example under ``folder``, with library tables that name the mini library by absolute path."""
    shutil.copytree(_drawn.EXAMPLE, folder)
    row = '\t(lib (name "Mini") (type "KiCad") (uri "{}") (options "") (descr ""))\n'
    for table, head, uri in (
        ("fp-lib-table", "fp_lib_table", LIBS / "Mini_v9.pretty"),
        ("sym-lib-table", "sym_lib_table", LIBS / "Mini_v9.kicad_sym"),
    ):
        (folder / table).write_text(f"({head}\n\t(version 7)\n{row.format(uri.as_posix())})\n", "utf-8")
    return folder / "design.py"


def written(env: dict[str, object], out: Path) -> list[str]:
    return sorted(Path(w["path"]).relative_to(out).as_posix() for w in env["receipt"]["written"])  # type: ignore[index]


def test_drawn_example_built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Drawn example built" and "Result of a drawn build"."""
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(EXAMPLE), "--out", str(out), "--confirm")
    assert code == 0, err
    files = written(env, out)
    assert {"drawn.kicad_sch", "sheets/child.kicad_sch"} <= set(files)
    root = parse((out / "drawn.kicad_sch").read_text(encoding="utf-8"))
    heads = [c.name for c in root.children if isinstance(c, Node)]
    assert heads.count("junction") == 1 and heads.count("wire") == 4
    schematic = env["result"]["schematic"]  # type: ignore[index]
    assert schematic["source"] == "drawn"  # type: ignore[index]
    assert schematic["drawn"] == {
        "file": "schematic.toml",
        "wires": 4,
        "junctions": 1,
        "labels": 7,
        "buses": 0,
        "opaque": 0,
    }  # type: ignore[index]
    record = json.loads((out / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert record["schematic"] == {"source": "drawn", "file": "schematic.toml"}
    before = {p: (out / p).read_bytes() for p in files}
    code, env, _ = run(monkeypatch, str(EXAMPLE), "--out", str(out), "--confirm")
    assert code == 0 and {p: (out / p).read_bytes() for p in files} == before


def test_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Missing file"."""
    script = copy_example(tmp_path / "src")
    (script.parent / "schematic.toml").unlink()
    code, _env, err = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
    error = json.loads(err.strip().splitlines()[-1])
    assert code == 3 and error["code"] == "FEN-3004" and "schematic.toml" in error["message"] + error["where"]


def test_bad_file_exits_3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = copy_example(tmp_path / "src")
    path = script.parent / "schematic.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("rotation = 90", "rotation = 45", 1), "utf-8")
    code, _env, err = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
    error = json.loads(err.strip().splitlines()[-1])
    assert code == 3 and error["code"] == "FEN-3004" and "rotation" in error["where"]


def test_placements_file_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Placements file ignored"."""
    script = copy_example(tmp_path / "src")
    (script.parent / "schematic-placements.toml").write_text('["U1"]\nx = 25.4\ny = 25.4\n', "utf-8")
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0, err
    ignored = [i for i in env["issues"] if i["code"] == "drawn.placements-ignored"]  # type: ignore[union-attr,index]
    assert len(ignored) == 1 and ignored[0]["severity"] == "warning"  # type: ignore[index]
    assert "schematic-placements.toml" in ignored[0]["message"]  # type: ignore[index]
    text = (out / "drawn.kicad_sch").read_text(encoding="utf-8")
    assert "(at 101.6 88.9 0)" in text  # U1 stands where the drawing puts it


def test_coverage_error_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = copy_example(tmp_path / "src")
    text = script.read_text(encoding="utf-8")
    script.write_text(
        text.replace('connect(Net("GND"), u1[10])', 'r9 = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603", '
                     'value="1k")\ndesign.add(r9)\nconnect(Net("GND"), u1[10], r9[1])'),
        "utf-8",
    )  # fmt: skip
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5 and not out.exists()
    assert "drawn.symbol-missing" in [i["code"] for i in env["issues"]]  # type: ignore[union-attr,index]
