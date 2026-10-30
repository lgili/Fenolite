# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block sheets read by ``kicad-cli`` (capability kicad-schematic, "Sheet pins and hierarchical labels
written", scenario "KiCad reads the block netlist"; change c0269): the hierarchical labels and sheet pins
written from the ports of ``examples/blocks`` keep every net under its circuit name (``H-K-SCH-BLOCK-PINS``),
and ERC reports nothing about sheet pins or hierarchical labels (``H-K-SCH-BLOCK-ERC``)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import _erc
import pytest
from _probes import major, runner

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_kicad
EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "blocks"
EXPECTED = {  # circuit net (as KiCad stores it) → (reference, pad)
    "VIN": {("J1", "1"), ("R1", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1")},
    "GND": {("J1", "2"), ("C1", "2"), ("C2", "2"), ("D1", "1"), ("D2", "1")},
    "ch0{slash}FB": {("R1", "2"), ("C1", "1")},
    "ch1{slash}FB": {("R3", "2"), ("C2", "1")},
    "ch0{slash}led{slash}A": {("R2", "2"), ("D1", "2")},
    "ch1{slash}led{slash}A": {("R4", "2"), ("D2", "2")},
}
SHEET_TYPES = ("hier", "sheet", "label")
"""ERC violation types about sheet pins and labels contain one of these words."""


def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / "ex"
    folder.mkdir()
    shutil.copy(EXAMPLE / "design.py", folder / "design.py")
    shutil.copy(EXAMPLE / "design.lock", folder / "design.lock")
    out = tmp_path / "out"
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        args = ["--kicad-version", str(major()), "build", str(folder / "design.py"), "--out", str(out)]
        code = cli_main.main([*args, "--confirm", "--json"])
    assert code == 0, stderr.getvalue()
    assert json.loads(stdout.getvalue())["issues"] == []
    return {
        path.relative_to(out).as_posix(): path.read_bytes()
        for path in out.rglob("*")
        if path.is_file() and ".fenolite" not in path.parts
    }


def test_kicad_reads_the_block_netlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    files = built(tmp_path, monkeypatch)
    child = files["sheets/ch0.kicad_sch"].decode("utf-8")
    assert (
        '(hierarchical_label "VIN"' in child and '(pin "VIN" input' in files["blocks_demo.kicad_sch"].decode()
    )
    nets = _erc.netlist(runner(), "blocks_demo.kicad_sch", files)
    for name, nodes in EXPECTED.items():
        assert nets.get(name) == nodes, (name, nets)
    report = _erc.run_erc(runner(), "blocks_demo.kicad_sch", files)
    found = [
        v for v in _erc.violations(report) if any(word in str(v.get("type", "")) for word in SHEET_TYPES)
    ]
    counted = dict(_erc.types(_erc.violations(report)))
    print(f"block sheets on kicad-cli {major()}: {len(nets)} nets, ERC {counted}")
    assert found == []
