# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net highlights are model SVGs with reviewed deterministic writes."""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import _regionviewbench as rv
import pytest

from fenolite.api import run
from fenolite.backends.kicad.pcb import write_board


@pytest.fixture(autouse=True)
def no_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))

    def refuse(*a, **kw):
        raise AssertionError("external tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_ground_counts_no_tool(tmp_path: Path):
    board = tmp_path / "bench.kicad_pcb"
    board.write_text(write_board(rv.bench(), target=10).text)
    outputs = []
    for name in ("a", "b"):
        reply = run("render", str(board), "--net", "GND", "-o", str(tmp_path / name), "--confirm")
        assert reply.exit_code == 0, reply.error
        data = (tmp_path / name / "net-GND.svg").read_bytes()
        outputs.append(data)
        for element in ET.fromstring(data).iter():
            if element.get("data-item"):
                assert ("net-hi" in element.get("class", "")) == (element.get("data-net") == "GND")
        assert reply.result["region"]["nets"] == ["GND"]
        assert reply.result["region"]["highlighted"]["vias"] == 1
        assert reply.result["region"]["highlighted"]["zones"] == 1
    assert outputs[0] == outputs[1]
    reply = run(
        "render", str(board), "--net", "L1", "--net", "GND", "-o", str(tmp_path / "multi"), "--confirm"
    )
    assert reply.exit_code == 0 and reply.result["views"][0]["path"] == "nets.svg"
    assert reply.result["region"]["nets"] == ["GND", "L1"]


@pytest.mark.parametrize(
    "options,where",
    [
        (("--net", "GDN"), "--net"),
        (("--net", "GND", "--layers", "BAD"), "--layers"),
        (("--net", "GND", "--svg"), "--net"),
        (("--layers", "F.Cu", "--png"), "--layers"),
    ],
)
def test_usage(tmp_path: Path, options, where):
    board = tmp_path / "bench.kicad_pcb"
    board.write_text(write_board(rv.bench(), target=10).text)
    reply = run("render", str(board), *options, "-o", str(tmp_path / "views"), "--dry-run")
    assert reply.exit_code == 2 and reply.error["code"] == "FEN-2001", reply.error
    assert reply.error["where"] == where
    assert not (tmp_path / "views").exists()


def test_option_names_do_not_collide(tmp_path: Path):
    board = tmp_path / "bench.kicad_pcb"
    board.write_text(write_board(rv.bench(), target=10).text)
    plain = run("render", str(board), "--region", rv.REGION, "--nets", "-o", str(tmp_path / "a"), "--confirm")
    hi = run("render", str(board), "--net", "GND", "-o", str(tmp_path / "b"), "--confirm")
    assert plain.exit_code == hi.exit_code == 0
    assert plain.result["region"]["nets"] == []
    assert hi.result["region"]["counts"].get("label", 0) == 0


def test_script_render_and_refusals(tmp_path: Path):
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Part, Net, connect, mm\n"
        'design = Design("render_test")\n'
        "design.board(mm(20), mm(10))\n"
        'r = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603")\n'
        "design.add(r)\n"
        'connect(Net("GND"), r[1])\n'
        "r.place(mm(5), mm(5))\n"
    )
    replies = [
        run(
            "render",
            str(script),
            "--net",
            "GND",
            "-o",
            str(tmp_path / name),
            "--confirm",
            seed=0,
            timestamp="2026-01-01T00:00:00Z",
        )
        for name in ("a", "b")
    ]
    assert all(r.exit_code == 0 for r in replies), [r.error for r in replies]
    assert (tmp_path / "a/net-GND.svg").read_bytes() == (tmp_path / "b/net-GND.svg").read_bytes()
    assert replies[0].envelope["input"]["kind"] == "fenolite-dsl"
    assert not list(tmp_path.glob("*.kicad_pcb"))
    bad = run("render", str(script), "--svg", "-o", str(tmp_path / "bad"), "--dry-run")
    assert bad.exit_code == 2
    script.write_text('from fenolite.dsl import Design\ndesign = Design("empty")\n')
    bad = run("render", str(script), "--net", "GND", "-o", str(tmp_path / "bad"), "--dry-run")
    assert bad.exit_code == 5 and any(i["code"] == "build.no-board" for i in bad.envelope["issues"])
