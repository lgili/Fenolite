# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block layout application, mismatches, precedence and mirrored copper (c0271)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _blocklayoutbench import MM, built_model, make_bench
from _layout_edit import move_footprint

import fenolite.cli.main as cli
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point


def test_placed_from_layout_and_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    paths = bench.paths()
    positions = bench.positions()
    assert positions[paths["dut/top"]] == (Point(110 * MM, 108 * MM), 90_000_000, "top")
    assert positions[paths["dut/bot"]] == (Point(110 * MM, 110_500_000), 90_000_000, "top")
    layout = env["result"]["placement"]["blocks"][0]["layout"]
    assert layout["status"] == "applied" and len(layout["sha256"]) == 64
    record = json.loads((bench.out / ".fenolite/build.json").read_text())
    assert record["layout"]["files"]["dut"] == layout


def test_locked_edit_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    bench.script.write_text(bench.script.read_text() + '\ndut.part("bot").place(mm(4),mm(6),locked=True)\n')
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert bench.positions()[bench.paths()["dut/bot"]][0] == Point(114 * MM, 114 * MM)
    assert bench.positions()[bench.paths()["dut/top"]][0] == Point(110 * MM, 108 * MM)


def test_stale_case_stages_and_another_block_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    bench.edit_script(
        'dut = design.use(divider, "dut")', 'dut = design.use(divider, "dut", footprint="Fenolite:Chip_0402")'
    )
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    found = [i for i in env["issues"] if i["code"] == "reuse.layout-stale"]
    assert len(found) == 1 and "Chip_0402" in found[0]["message"]
    assert env["result"]["placement"]["blocks"][0]["layout"]["status"] == "stale"
    assert sorted(env["result"]["staged"]) == ["dut/bot", "dut/top"]
    assert not built_model(bench).board.tracks
    bench = make_bench(tmp_path / "another", monkeypatch)
    file = bench.folder / "divider.toml"
    file.write_text(file.read_text().replace("Test:divider", "Test:other"))
    code, env, _ = bench.build("--confirm")
    assert code == 5
    assert any(i["code"] == "reuse.layout-block" for i in env["issues"])
    assert not bench.board.exists()


def test_older_and_nets_differ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    bench.edit_script('version="1.0.0"', 'version="1.1.0"')
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert any(i["code"] == "reuse.layout-older" for i in env["issues"])
    bench = make_bench(tmp_path / "nets", monkeypatch)
    file = bench.folder / "divider.toml"
    text = file.read_text()
    digest = text.split('nets_digest = "')[1].split('"')[0]
    file.write_text(text.replace(digest, "sha256:" + "0" * 64))
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert any(i["code"] == "reuse.layout-nets" for i in env["issues"])
    assert not built_model(bench).board.tracks
    assert not env["result"]["staged"]


def test_copper_follows_ports_locked_and_drops_lost_pad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    bench.edit_script('("HI", "OUT", "LO")', '("HI", "OUT", "LO")')
    bench.script.write_text(
        bench.script.read_text().replace("net = Net(name)", 'net = Net("ADC0" if name == "OUT" else name)')
    )
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    model = built_model(bench)
    track = model.board.tracks[0]
    assert next(n.name for n in model.circuit.nets if n.id == track.net_id) == "ADC0"
    assert track.locked and track.layer == "F.Cu"
    assert track.start == Point(110 * MM, 108_800_000) and track.end == Point(110 * MM, 109_700_000)
    assert not any(i["code"] == "reuse.copper-dropped" for i in env["issues"])
    bench = make_bench(tmp_path / "lost", monkeypatch)
    # Same digest, changed land position: contacts prevent copying a now-disconnected route.
    bench.edit_script('mm("-0.8")', 'mm("-1.8")')
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not built_model(bench).board.tracks
    assert any(i["code"] == "reuse.copper-dropped" and "pad-lost" in i["message"] for i in env["issues"])


def test_flipped_kept_parts_and_copper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    before = built_model(bench)
    pads_before = KicadBackend().board_pads(before)
    bench.edit_script("dut.place(mm(10), mm(8))", 'dut.place(mm(10), mm(8), side="bottom")')
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    after = built_model(bench)
    pads_after = KicadBackend().board_pads(after)
    assert all(fp.side == "bottom" for fp in after.board.footprints)
    assert after.board.tracks and {t.layer for t in after.board.tracks} == {"B.Cu"}
    assert any(i["code"] == "layout.block-moved" for i in env["issues"])
    by_id = {(p.footprint_id, p.number): p.position for p in pads_after}
    for p in pads_before:
        goal = Point(220 * MM - p.position.x, p.position.y)
        assert by_id[(p.footprint_id, p.number)] == goal


def test_show_record_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    text = bench.script.read_text().replace(
        "    hi, out, lo =", '    b.layout(reuse="layouts/divider.toml")\n    hi, out, lo ='
    )
    bench.script.write_text(text)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli.main(["blocks", "show", "Test:divider", "--from", str(bench.script), "--json"])
    assert code == 0, err.getvalue()
    assert json.loads(out.getvalue())["result"]["block"]["layout"] == "layouts/divider.toml"


def test_changed_layout_follows_code_and_notices_kept_cad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch, copper=False)
    assert bench.build("--confirm")[0] == 0
    refs = bench.paths()
    bench.board.write_text(move_footprint(bench.board.read_text(), refs["dut/bot"], MM, 0))
    path = bench.folder / "divider.toml"
    path.write_text(path.read_text().replace('at = ["0mm", "2.5mm"]', 'at = ["3mm", "2.5mm"]'))
    code, env, err = bench.build("--confirm", "--take", "cad")
    assert code == 0, err
    assert bench.positions()[refs["dut/bot"]][0] == Point(111 * MM, 110_500_000)
    assert any(i["code"] == "reuse.layout-changed" for i in env["issues"])


def test_placement_edit_drops_copper_that_loses_its_pad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    refs = bench.paths()
    bench.board.write_text(move_footprint(bench.board.read_text(), refs["dut/top"], MM * 4, 0))
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not built_model(bench).board.tracks
    assert any(i["code"] == "reuse.copper-dropped" and "pad-lost" in i["message"] for i in env["issues"])


def test_copper_unknown_layer_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    path = bench.folder / "divider.toml"
    path.write_text(path.read_text().replace('layer = "F.Cu"', 'layer = "In99.Cu"'))
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not built_model(bench).board.tracks
    assert any(i["code"] == "reuse.copper-dropped" and "layer-unknown" in i["message"] for i in env["issues"])
