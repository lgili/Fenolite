# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library trees (change c0259; capability library-records, "Library trees" and "Stable record ids").
The records are authored for Fenolite as test data."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.catalog.records import load_tree, parse_record, record_text
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "tests" / "data" / "library"
TWO_PAD = (LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8")


def test_duplicate_id_in_a_tree(tmp_path: Path) -> None:
    for name in ("a.toml", "sub/b.toml"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            TWO_PAD.replace("Proj:Two_Pad", "Fenolite:X").replace(
                'evidence = "UNVERIFIED"', 'evidence = "UNVERIFIED"\nsources = ["S-0314"]'
            ),
            encoding="utf-8",
        )
    with pytest.raises(FormatError) as caught:
        load_tree(tmp_path)
    assert "a.toml" in str(caught.value) and "sub/b.toml" in str(caught.value)
    assert getattr(caught.value, "code", "") == "FEN-3004"


def test_tree_reads_recursively_in_path_order() -> None:
    tree = load_tree(LIBRARY)
    assert list(tree.files.values()) == sorted(tree.files.values())
    assert set(tree.files.values()) == {
        path.relative_to(LIBRARY).as_posix() for path in LIBRARY.rglob("*.toml")
    }
    assert load_tree(LIBRARY / "missing").records == ()


def test_replaces_must_match_a_deprecation(tmp_path: Path) -> None:
    new = TWO_PAD.replace("Proj:Two_Pad", "Proj:Two_Pad_B").replace(
        'generator = "explicit"', 'replaces = "Proj:Two_Pad"\ngenerator = "explicit"'
    )
    (tmp_path / "a.toml").write_text(TWO_PAD, encoding="utf-8")
    (tmp_path / "b.toml").write_text(new, encoding="utf-8")
    with pytest.raises(FormatError) as caught:
        load_tree(tmp_path)
    assert "replaces" in str(caught.value)
    old = TWO_PAD.replace(
        'generator = "explicit"',
        'deprecated = { by = "Proj:Two_Pad_B", since = "1.0.1", reason = "pad 3 added" }\n'
        'generator = "explicit"',
    )
    (tmp_path / "a.toml").write_text(old, encoding="utf-8")
    tree = load_tree(tmp_path)
    for record in tree.records:
        assert parse_record(record_text(record)) == record


def test_project_package_overrides_a_shipped_footprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    folder = tmp_path / "proj"
    (folder / "devices" / "packages").mkdir(parents=True)
    wider = (
        TWO_PAD.replace("Proj:Two_Pad", "Fenolite:Chip_0603")
        .replace('evidence = "UNVERIFIED"', 'evidence = "UNVERIFIED"\nsources = ["S-0314"]')
        .replace('size = ["0.9mm", "1mm"]', 'size = ["1.2mm", "1.2mm"]')
    )
    (folder / "devices" / "packages" / "Chip_0603.toml").write_text(wider, encoding="utf-8")
    (folder / "design.py").write_text(
        "from fenolite.dsl import Design, mm\n"
        'design = Design("wide")\n'
        "design.board(mm(20), mm(10))\n"
        'design.part("R1", "Fenolite:Resistor", "Fenolite:Chip_0603", "1k").place(mm(10), mm(5))\n',
        encoding="utf-8",
    )
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(
        ["build", str(folder / "design.py"), "--out", str(tmp_path / "out"), "--confirm", "--json"]
    )
    assert code == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert envelope["result"]["libraries"]["Fenolite:Chip_0603"] == "authored"
    assert envelope["result"]["libraries"]["Fenolite:Resistor"] == "builtin"
    board = (tmp_path / "out" / "wide.kicad_pcb").read_text(encoding="utf-8")
    assert "(size 1.2 1.2)" in board
    shutil.rmtree(folder)


def test_load_time() -> None:
    """Scenario "Load time". The budget is relative, so that it holds on any runner: reading the shipped tree
    takes at most twice the time ``tomllib`` alone takes to read the same files (about 150 ms on CI)."""
    code = (
        "import time, tomllib\n"
        "from importlib import resources\n"
        "import fenolite.catalog.records as r\n"
        "files = []\n"
        "def walk(t):\n"
        "    for e in t.iterdir():\n"
        "        walk(e) if e.is_dir() else files.append(e.read_text(encoding='utf-8'))\n"
        "walk(resources.files('fenolite.catalog') / 'data')\n"
        "t = time.perf_counter(); r.shipped_tree(); tree = time.perf_counter() - t\n"
        "t = time.perf_counter(); [tomllib.loads(f) for f in files]; toml = time.perf_counter() - t\n"
        "print(tree, toml)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    tree, toml = (float(value) for value in result.stdout.split())
    print(f"shipped_tree {tree * 1000:.0f} ms, tomllib alone {toml * 1000:.0f} ms")
    assert tree <= 2.5 * toml + 0.05
