# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The good variant of ``examples/sensor_rails`` read back through ``kicad-cli`` (capability design-dsl,
"Built boards read back with the same connectivity"; change c0252): the nets that whole interfaces joined
(``connect(v33, mcu.vdd, sen.vdd)``, ``connect(bus, mcu.i2c1, sen.i2c)``, the block's ports and the pull-ups)
are the nets KiCad exports, and the board agrees with the schematic."""

from __future__ import annotations

import io
import json
from pathlib import Path

import _erc
import pytest
from _probes import major, runner
from _sensor_rails import copy_example

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_kicad
EXPECTED = (  # (reference, pad) as the netlist names its nodes; refs from good.lock
    {("J1", "1"), ("U1", "1"), ("U1", "3"), ("C2", "1")},  # V12: the input, VIN and EN of the regulator
    {("U1", "5"), ("C3", "1"), ("U2", "1"), ("U2", "2"), ("U3", "1"), ("R1", "2"), ("R2", "2"), ("C1", "1")},
    {("U2", "6"), ("U3", "3"), ("R1", "1")},  # SDA
    {("U2", "5"), ("U3", "4"), ("R2", "1")},  # SCL
    {("U3", "5"), ("U2", "4")},  # INT
    {("J1", "2"), ("U1", "2"), ("C2", "2"), ("C3", "2"), ("U2", "3"), ("U3", "2"), ("U3", "6"), ("C1", "2")},
)


def test_sensor_rails_reads_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    folder = copy_example(tmp_path / "ex")
    out = tmp_path / "out"
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        args = ["--kicad-version", str(major()), "build", str(folder / "good.py"), "--out", str(out)]
        code = cli_main.main([*args, "--confirm", "--json"])
    assert code == 0, stderr.getvalue()
    # two infos are expected and nothing else: the block's port members that share one net keep global labels
    # (build.block-port-merged, change c0269), and the shipped devices carry no ratings
    # (circuit.rating-missing, change c0253)
    found = {(i["code"], i["severity"]) for i in json.loads(stdout.getvalue())["issues"]}
    assert found <= {("build.block-port-merged", "info"), ("circuit.rating-missing", "info")}, found
    files = {
        path.relative_to(out).as_posix(): path.read_bytes()
        for path in out.rglob("*")
        if path.is_file() and ".fenolite" not in path.parts
    }
    nets = _erc.netlist(runner(), "sensor_rails.kicad_sch", files)
    groups = [frozenset(nodes) for nodes in nets.values()]
    for expected in EXPECTED:
        assert frozenset(expected) in groups, (expected, nets)
    parity = _erc.parity(_erc.run_parity(runner(), "sensor_rails.kicad_pcb", files))
    print(f"sensor_rails read back: {len(nets)} nets on kicad-cli {major()}, parity {len(parity)}")
    assert parity == []
