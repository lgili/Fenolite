# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block capture plans bind the board and write deterministic checked assets (c0271)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _blocklayoutbench import LAYOUT, ROOT, make_bench

import fenolite.cli.main as cli
from fenolite.backends.kicad import sexpr
from fenolite.core.coords import Point
from fenolite.reuse.blocklayout import read_block_layout


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli.main(["blocks", "capture", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def test_bench_round_trip_plan_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, layout=False)
    assert bench.build("--confirm")[0] == 0
    # The authored board also has a free ground via, outside every group joined to block pads.
    bench.board.write_bytes((ROOT / "tests/data/blocks/bench/divider.kicad_pcb").read_bytes())
    monkeypatch.chdir(tmp_path)
    args = (str(bench.out), "--instance", "dut", "-o", "captured.toml")
    code, env, err = run(monkeypatch, *args, "--dry-run")
    assert code == 0, err
    assert not (tmp_path / "captured.toml").exists()
    capture = env["result"]["capture"]
    assert capture["tracks"] == 1 and capture["parts"] == 2 and capture["vias"] == 0
    assert capture["block"] == "Test:divider"
    plan = env["result"]["plan_id"]
    code, env, err = run(monkeypatch, *args, "--confirm", "--plan", plan)
    assert code == 0, err
    assert (tmp_path / "captured.toml").read_bytes() == LAYOUT.read_bytes()
    assert env["receipt"]["written"][0]["sha256"]
    code, env, err = run(monkeypatch, *args, "--confirm")
    assert code == 0, err
    assert (tmp_path / "captured.toml").read_bytes() == LAYOUT.read_bytes()


def test_usage_unknown_and_no_output_for_external_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    code, _, err = run(monkeypatch, str(bench.out), "--instance", "dutt", "--dry-run")
    assert code == 2 and "FEN-2001" in err and "dut" in err
    # This build happened outside the command's original cwd, so no writable source folder is recorded.
    code, _, err = run(monkeypatch, str(bench.out), "--instance", "dut", "--dry-run")
    assert code == 2 and "-o" in err


def test_default_output_inside_working_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    code, env, err = run(monkeypatch, str(bench.out), "--instance", "dut", "--no-copper", "--confirm")
    assert code == 0, err
    assert env["result"]["capture"]["file"] == "src/layouts/divider.toml"
    assert (bench.folder / "layouts/divider.toml").is_file()


def test_unplaced_part_makes_no_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    doc = sexpr.parse(bench.board.read_text())
    footprints = doc.nodes("footprint")
    removed = footprints[0]
    doc = doc.with_children(c for c in doc.children if c is not removed)
    bench.board.write_text(sexpr.dumps(doc))
    monkeypatch.chdir(tmp_path)
    code, env, err = run(monkeypatch, str(bench.out), "--instance", "dut", "-o", "bad.toml", "--dry-run")
    assert code == 5, err
    assert any(i["code"] == "blocks.capture-unplaced" for i in env["issues"])
    assert "plan_id" not in env["result"] and not (tmp_path / "bad.toml").exists()


def test_round_trip_failure_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    import fenolite.cli._blocks_capture as capture
    from fenolite.reuse.fit import BlockFit

    monkeypatch.setattr(
        capture, "fit_block", lambda *args, **kwargs: BlockFit(None, "R1", False, 1000, (), ())
    )
    monkeypatch.chdir(tmp_path)
    code, env, err = run(monkeypatch, str(bench.out), "--instance", "dut", "-o", "bad.toml", "--dry-run")
    assert code == 5, err
    assert any(i["code"] == "blocks.capture-check-failed" for i in env["issues"])
    assert not (tmp_path / "bad.toml").exists()


def test_bottom_pose_capture_and_anchor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, bottom=True)
    assert bench.build("--confirm")[0] == 0
    monkeypatch.chdir(tmp_path)
    code, env, err = run(monkeypatch, str(bench.out), "--instance", "dut", "-o", "bottom.toml", "--confirm")
    assert code == 0, err
    assert (tmp_path / "bottom.toml").read_bytes() == LAYOUT.read_bytes()
    code, env, err = run(
        monkeypatch,
        str(bench.out),
        "--instance",
        "dut",
        "-o",
        "anchor.toml",
        "--origin",
        "anchor",
        "--anchor",
        "top",
        "--confirm",
    )
    assert code == 0, err
    layout = read_block_layout(tmp_path / "anchor.toml")
    assert layout.parts["top"].at == Point(0, 0) and layout.parts["top"].side == "bottom"


def test_capture_plan_refuses_changed_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    monkeypatch.chdir(tmp_path)
    args = (str(bench.out), "--instance", "dut", "-o", "captured.toml")
    code, env, err = run(monkeypatch, *args, "--dry-run")
    assert code == 0, err
    plan = env["result"]["plan_id"]
    bench.board.write_text(bench.board.read_text() + "\n")
    code, _, err = run(monkeypatch, *args, "--confirm", "--plan", plan)
    assert code == 4 and "FEN-4002" in err and not (tmp_path / "captured.toml").exists()


def test_copper_crossing_outside_pads_stays_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from fenolite.backends.kicad.backend import KicadBackend
    from fenolite.backends.kicad.pcb import write_board
    from fenolite.model import canonical
    from fenolite.model.board import Track

    bench = make_bench(tmp_path, monkeypatch)
    bench.script.write_text(
        bench.script.read_text() + '\nx = design.part("R99", "Fenolite:Resistor", '
        'footprint="Fenolite:Chip_0603", value="1k")\n'
        "x.place(mm(14),mm(8))\nconnect(dut.OUT,x[1])\n"
    )
    assert bench.build("--confirm")[0] == 0
    model = canonical.load_dir(bench.out / ".fenolite")
    assert model.board
    outside = next(p for p in KicadBackend().board_pads(model) if p.ref == "R99" and p.number == "1")
    start = model.board.tracks[0].start
    route = Track(
        id="authored-external-track",
        start=start,
        end=outside.position,
        layer="F.Cu",
        width=250_000,
        net_id=outside.net_id,
    )
    actual = dataclasses.replace(
        model, board=dataclasses.replace(model.board, tracks=(*model.board.tracks, route))
    )
    bench.board.write_text(write_board(actual).text)
    monkeypatch.chdir(tmp_path)
    code, env, err = run(monkeypatch, str(bench.out), "--instance", "dut", "-o", "left.toml", "--confirm")
    assert code == 0, err
    assert env["result"]["capture"]["tracks"] == 0
    assert env["result"]["capture"]["left"] == ["OUT"]
    assert any(i["code"] == "blocks.capture-copper-left" for i in env["issues"])


def test_usage_shipped_block_always_needs_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    bench = make_bench(tmp_path, monkeypatch, layout=False)
    text = bench.script.read_text()
    decorator = next(line for line in text.splitlines() if line.startswith("@block("))
    text = text.replace(decorator + "\n", "")
    declaration = (
        decorator.removeprefix("@")
        .replace('id="Test:divider"', 'id="Fenolite:divider"')
        .replace('licence="CC0-1.0"', 'licence="Apache-2.0", sources=("S-0001",)')
    )
    text = text.replace(
        "design = Design(",
        'divider.__module__ = "fenolite.blocks.authored_layout"\n'
        f"divider = {declaration}(divider)\n\ndesign = Design(",
    )
    bench.script.write_text(text)
    assert bench.build("--confirm")[0] == 0
    code, _, err = run(monkeypatch, str(bench.out), "--instance", "dut", "--dry-run")
    assert code == 2 and "-o" in err
