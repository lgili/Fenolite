# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog CLI shares metadata with the Python API and is fully offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.catalog import list_entries
from fenolite.cli.main import main


def test_catalog_cli_discovers_all_100_footprints(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "list", "--kind", "footprint"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["result"]["count"] == 100
    assert {e["lib_id"] for e in envelope["result"]["entries"]} == {
        e.lib_id for e in list_entries(kind="footprint")
    }
    assert envelope["evidence"]["level"] == "INFERRED"


def test_catalog_list_and_show(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "list", "--kind", "symbol", "--query", "passive"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["result"]["count"] == 14
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


def test_cli_lists_all_49_symbols_offline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Catalog discovery attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert main(["--json", "catalog", "list", "--kind", "symbol"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["result"]["count"] == 49
    assert {e["lib_id"] for e in envelope["result"]["entries"]} == {
        e.lib_id for e in list_entries(kind="symbol")
    }
    assert envelope["evidence"]["level"] == "INFERRED"


# -- devices (change c0248, capability fenolite-component-catalog, "Devices in the catalog list and show")

SHIPPED_DEVICES = [
    "Fenolite:C_0402",
    "Fenolite:C_0603",
    "Fenolite:C_0805",
    "Fenolite:C_1206",
    "Fenolite:Conn_1x2_P2.54",
    "Fenolite:LED_0603",
    "Fenolite:R_0402",
    "Fenolite:R_0603",
    "Fenolite:R_0805",
    "Fenolite:R_1206",
]


def test_list_devices(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "list", "--kind", "device"]) == 0
    entries = json.loads(capsys.readouterr().out)["result"]["entries"]
    assert [entry["id"] for entry in entries] == SHIPPED_DEVICES
    assert all(
        entry["kind"] == "device" and entry["evidence"] == "INFERRED" and entry["sources"]
        for entry in entries
    )
    assert main(["--json", "catalog", "list"]) == 0
    kinds = {entry["kind"] for entry in json.loads(capsys.readouterr().out)["result"]["entries"]}
    assert kinds == {"symbol", "footprint", "device"}
    assert main(["--json", "catalog", "list", "--kind", "device", "--query", "led"]) == 0
    assert [e["id"] for e in json.loads(capsys.readouterr().out)["result"]["entries"]] == [
        "Fenolite:LED_0603"
    ]


def test_show_a_device(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "show", "Fenolite:R_0603", "--kind", "device"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    result = envelope["result"]
    assert (
        result["record"]["id"] == "Fenolite:R_0603" and result["record"]["footprint"] == "Fenolite:Chip_0603"
    )
    assert len(result["digest"]) == 64 and result["edited"] is False and result["shadowed"] == []
    assert envelope["issues"] == [] and "H-G-DEVICE-RECORD" in envelope["evidence"]["hypotheses"]
    # without --kind, a device is shown when no symbol or footprint has the id
    assert main(["--json", "catalog", "show", "Fenolite:LED_0603"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["kind"] == "device"
    assert main(["--json", "catalog", "show", "Fenolite:Resistor", "--kind", "device"]) == 3


def test_device_options_need_import(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "catalog", "list", "--symbol", "Fenolite:Resistor"]) == 2
    assert main(["--json", "catalog", "list", "--pin", "A=1"]) == 2
    capsys.readouterr()
