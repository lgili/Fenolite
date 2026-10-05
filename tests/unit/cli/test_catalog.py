# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog CLI shares metadata with the Python API and is fully offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.cli.main import main


def test_catalog_list_and_show(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "list", "--kind", "symbol", "--query", "passive"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["result"]["count"] == 9
    assert all(item["category"] == "Passive" for item in listed["result"]["entries"])
    assert any(item["lib_id"] == "Fenolite:Common_Mode_Choke" for item in listed["result"]["entries"])

    assert main(["--json", "catalog", "show", "Fenolite:Resistor"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["result"]["definition"]["pins"] == [
        {"number": "1", "name": "A", "etype": "passive"},
        {"number": "2", "name": "B", "etype": "passive"},
    ]


def test_build_uses_catalog_offline_and_exact_project_overrides(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Footprint, Part, Symbol, mm\n"
        "design = Design('catalog_demo')\n"
        "design.board(mm(20), mm(15))\n"
        "symbol = Symbol('Fenolite', 'Resistor', reference='R')\n"
        "symbol.pin('1', 'A', at=(mm(-5), mm(0)), length=mm(2.5), rotation=180)\n"
        "symbol.pin('2', 'B', at=(mm(5), mm(0)), length=mm(2.5))\n"
        "symbol.line((mm(-2), mm(0)), (mm(2), mm(0)))\n"
        "footprint = Footprint('Fenolite', 'Chip_0603', kind='smd')\n"
        "footprint.pad('1', at=(mm(-1), mm(0)), size=(mm(.8), mm(.8)))\n"
        "footprint.pad('2', at=(mm(1), mm(0)), size=(mm(.8), mm(.8)))\n"
        "part = Part('R1', 'Fenolite:Resistor', footprint='Fenolite:Chip_0603')\n"
        "design.add_footprint(footprint)\n"
        "design.add(symbol, part)\n"
        "part.place(mm(10), mm(7))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["--json", "build", str(script), "--out", "out", "--dry-run"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    files = {Path(path).as_posix() for path in envelope["result"]["files"]}
    assert envelope["result"]["libraries"] == {
        "Fenolite:Chip_0603": "authored",
        "Fenolite:Resistor": "authored",
    }
    assert "out/lib/Fenolite.kicad_sym" in files
    assert "out/lib/Fenolite.pretty/Chip_0603.kicad_mod" in files


def test_build_resolves_catalog_without_global_libraries(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Part, mm\n"
        "design = Design('offline_catalog')\n"
        "design.board(mm(20), mm(15))\n"
        "part = Part('R1', 'Fenolite:Resistor', footprint='Fenolite:Chip_0603')\n"
        "design.add(part)\n"
        "part.place(mm(10), mm(7))\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["--json", "build", str(script), "--out", "out", "--dry-run"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    files = {Path(path).as_posix() for path in envelope["result"]["files"]}
    assert envelope["result"]["libraries"] == {
        "Fenolite:Chip_0603": "builtin",
        "Fenolite:Resistor": "builtin",
    }
    assert "out/lib/Fenolite.kicad_sym" in files
    assert "out/lib/Fenolite.pretty/Chip_0603.kicad_mod" in files
