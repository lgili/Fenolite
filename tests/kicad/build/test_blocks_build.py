# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The block example read back through ``kicad-cli`` (capability design-dsl, "Built boards read back with the
same connectivity" and "Block sheets in KiCad"; change c0251): the netlist that KiCad exports from the
generated hierarchy holds the connectivity of the script, local nets and port nets included, and the
board agrees with the schematic."""

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
EXPECTED = (  # (reference, pad) as the netlist names its nodes
    {("J1", "1"), ("R1", "1"), ("R2", "1"), ("R3", "1"), ("R4", "1")},  # VIN through the VIN ports
    {("J1", "2"), ("C1", "2"), ("C2", "2"), ("D1", "1"), ("D2", "1")},  # GND, the LED cathodes on pad 1
    {("R1", "2"), ("C1", "1")},  # ch0/FB, also the optional port EN
    {("R3", "2"), ("C2", "1")},  # ch1/FB
    {("R2", "2"), ("D1", "2")},  # ch0/led/A, the anode on pad 2 (pad_map)
    {("R4", "2"), ("D2", "2")},  # ch1/led/A
)


def test_block_example_reads_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    files = {
        path.relative_to(out).as_posix(): path.read_bytes()
        for path in out.rglob("*")
        if path.is_file() and ".fenolite" not in path.parts
    }
    root = files["blocks_demo.kicad_sch"].decode("utf-8")
    assert '"Sheetname" "ch0 (channel)"' in root and '"Sheetname" "ch1 (channel)"' in root
    nets = _erc.netlist(runner(), "blocks_demo.kicad_sch", files)
    groups = [frozenset(nodes) for nodes in nets.values()]
    for expected in EXPECTED:
        assert frozenset(expected) in groups, (expected, nets)
    parity = _erc.parity(_erc.run_parity(runner(), "blocks_demo.kicad_pcb", files))
    print(f"blocks read back: {len(nets)} nets on kicad-cli {major()}, parity {len(parity)}")
    assert parity == []
