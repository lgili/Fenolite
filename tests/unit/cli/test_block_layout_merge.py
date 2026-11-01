# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Persistent owned-copy observations (c0271): all copper kinds, deletion and cache independence."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
from _blocklayoutbench import MM, built_model, make_bench

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli._blocklayout_merge import BASE_FILE
from fenolite.core.coords import Point
from fenolite.model.board import Arc, Track, Via, Zone
from fenolite.reuse.blocklayout import read_block_layout, write_block_layout


def all_kinds(bench) -> None:  # type: ignore[no-untyped-def]
    path = bench.folder / "divider.toml"
    layout = read_block_layout(path)
    b = Track(
        id="back",
        start=Point(0, 900_000),
        end=Point(0, 1_600_000),
        width=250_000,
        layer="B.Cu",
        net_id="port:OUT",
    )
    a = Arc(
        id="arc",
        start=Point(0, 800_000),
        mid=Point(200_000, 1_250_000),
        end=Point(0, 1_700_000),
        width=250_000,
        layer="F.Cu",
        net_id="port:OUT",
    )
    vias = tuple(
        Via(
            id=f"via-{y}",
            position=Point(0, y),
            diameter=500_000,
            drill=200_000,
            layers=("F.Cu", "B.Cu"),
            net_id="port:OUT",
        )
        for y in (900_000, 1_600_000)
    )
    z = Zone(
        id="zone",
        outline=(
            Point(-400_000, 600_000),
            Point(400_000, 600_000),
            Point(400_000, 1_900_000),
            Point(-400_000, 1_900_000),
        ),
        layers=("F.Cu",),
        net_id="port:OUT",
    )
    layout = dataclasses.replace(layout, tracks=(*layout.tracks, b), arcs=(a,), vias=vias, zones=(z,))
    path.write_bytes(write_block_layout(layout))


def edit_board(bench, *, delete: bool = False) -> None:  # type: ignore[no-untyped-def]
    model = bench.read()
    board = model.board
    assert board is not None
    board = dataclasses.replace(
        board,
        tracks=()
        if delete
        else tuple(dataclasses.replace(t, width=t.width + 20_000, locked=False) for t in board.tracks),
        arcs=()
        if delete
        else tuple(dataclasses.replace(a, width=a.width + 20_000, locked=False) for a in board.arcs),
        vias=()
        if delete
        else tuple(dataclasses.replace(v, diameter=v.diameter + 20_000, locked=False) for v in board.vias),
        zones=() if delete else tuple(dataclasses.replace(z, priority=4, locked=False) for z in board.zones),
    )
    bench.board.write_text(write_board(dataclasses.replace(model, board=board)).text)


def assert_edited(bench) -> None:  # type: ignore[no-untyped-def]
    board = built_model(bench).board
    assert board is not None
    assert len(board.tracks) == 2 and {t.width for t in board.tracks} == {270_000}
    assert len(board.arcs) == 1 and board.arcs[0].width == 270_000
    assert len(board.vias) == 2 and {v.diameter for v in board.vias} == {520_000}
    assert len(board.zones) == 1 and board.zones[0].priority == 4
    assert all(i.locked for i in (*board.tracks, *board.arcs, *board.vias, *board.zones))


def test_cad_edits_all_kinds_survive_twice_without_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert (bench.out / BASE_FILE).is_file()
    edit_board(bench)
    shutil.rmtree(bench.out / ".fenolite")
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        assert_edited(bench)


def test_cad_deletions_all_kinds_survive_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    edit_board(bench, delete=True)
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        board = built_model(bench).board
        assert board
        assert not (*board.tracks, *board.arcs, *board.vias, *board.zones)


def test_unchanged_cad_follows_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    file = bench.folder / "divider.toml"
    text = (
        file.read_text()
        .replace('width = "0.25mm"', 'width = "0.3mm"')
        .replace('size = "0.5mm"', 'size = "0.55mm"')
        .replace("priority = 0", "priority = 2")
    )
    file.write_text(text)
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        board = built_model(bench).board
        assert board
        assert {t.width for t in (*board.tracks, *board.arcs)} == {300_000}
        assert {v.diameter for v in board.vias} == {550_000}
        assert board.zones[0].priority == 2


def test_both_changes_refuse_and_discard_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    edit_board(bench)
    file = bench.folder / "divider.toml"
    file.write_text(file.read_text().replace('width = "0.25mm"', 'width = "0.3mm"'))
    before = bench.board.read_bytes()
    for flags in ((), ("--take", "cad"), ("--take", "code")):
        code, env, _ = bench.build("--confirm", *flags)
        assert code == 5
        assert any(i["code"] == "reuse.layout-conflict" for i in env["issues"])
        assert bench.board.read_bytes() == before
    code, env, err = bench.build("--confirm", "--discard-layout")
    assert code == 0, err
    assert {t.width for t in built_model(bench).board.tracks} == {300_000}


def test_missing_or_tampered_snapshot_refuses_ambiguous_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for mode in ("missing", "tampered"):
        bench = make_bench(tmp_path / mode, monkeypatch)
        assert bench.build("--confirm")[0] == 0
        edit_board(bench)
        base = bench.out / BASE_FILE
        if mode == "missing":
            base.unlink()
        else:
            base.write_text(base.read_text().replace("250000", "250001"))
        code, env, _ = bench.build("--confirm")
        assert code == 5
        assert any(i["code"] == "reuse.layout-conflict" for i in env["issues"])


def test_edited_copper_follows_mirrored_pose_without_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    edit_board(bench)
    shutil.rmtree(bench.out / ".fenolite")
    bench.edit_script("dut.place(mm(10), mm(8))", 'dut.place(mm(10), mm(8), side="bottom")')
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert_edited(bench)
    board = built_model(bench).board
    assert board
    assert all(f.side == "bottom" for f in board.footprints)
    assert board.arcs[0].layer == "B.Cu" and board.arcs[0].mid.x == 110 * MM - 200_000
    assert bench.build("--confirm")[0] == 0
    assert_edited(bench)


def test_code_deletion_removes_all_owned_kinds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    path = bench.folder / "divider.toml"
    layout = dataclasses.replace(read_block_layout(path), tracks=(), arcs=(), vias=(), zones=())
    path.write_bytes(write_block_layout(layout))
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        board = built_model(bench).board
        assert board and not (*board.tracks, *board.arcs, *board.vias, *board.zones)


def test_recapture_resolves_chosen_cad_geometry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    import fenolite.cli.main as cli

    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    edit_board(bench)
    path = bench.folder / "divider.toml"
    path.write_text(path.read_text().replace('width = "0.25mm"', 'width = "0.3mm"'))
    assert bench.build("--dry-run")[0] == 5
    monkeypatch.chdir(bench.folder)
    output, errors = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", output)
        patch.setattr("sys.stderr", errors)
        code = cli.main(
            [
                "blocks",
                "capture",
                str(bench.out),
                "--instance",
                "dut",
                "-o",
                "divider.toml",
                "--confirm",
                "--json",
            ]
        )
    assert code == 0, errors.getvalue()
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        assert built_model(bench).board.tracks[0].width == 270_000


def test_missing_matching_snapshot_can_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    (bench.out / BASE_FILE).unlink()
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert (bench.out / BASE_FILE).is_file()


def test_corrupt_observation_is_an_explained_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import json

    from fenolite.model import canonical

    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    path = bench.out / BASE_FILE
    data = json.loads(path.read_text())
    next(iter(data["copies"]["dut"].values()))["out"] = "invalid geometry"
    body = {key: value for key, value in data.items() if key != "sha256"}
    data["sha256"] = "sha256:" + hashlib.sha256(canonical.dumps(body).encode()).hexdigest()
    path.write_text(json.dumps(data))
    code, env, err = bench.build("--dry-run")
    assert code == 5, err
    assert any(i["code"] == "reuse.layout-conflict" for i in env["issues"])


def test_cache_pose_cannot_override_persistent_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    edit_board(bench)
    path = bench.out / ".fenolite/build.json"
    data = json.loads(path.read_text())
    data["layout"]["poses"]["dut"] = [999 * MM, 888 * MM, 90_000_000]
    path.write_text(json.dumps(data))
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert built_model(bench).board.tracks[0].width == 270_000
    assert built_model(bench).board.tracks[0].start == Point(110 * MM, 108_800_000)


def test_no_asset_keeps_old_output_surface_and_saved_bytes_are_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = make_bench(tmp_path / "plain", monkeypatch, layout=False)
    assert plain.build("--confirm")[0] == 0
    assert not (plain.out / BASE_FILE).exists()
    bench = make_bench(tmp_path / "asset", monkeypatch)
    assert bench.build("--confirm")[0] == 0
    first = (bench.out / BASE_FILE).read_bytes()
    assert bench.build("--confirm")[0] == 0
    assert (bench.out / BASE_FILE).read_bytes() == first
    edit_board(bench)
    assert bench.build("--confirm")[0] == 0
    edited = (bench.out / BASE_FILE).read_bytes()
    assert bench.build("--confirm")[0] == 0
    assert (bench.out / BASE_FILE).read_bytes() == edited


@pytest.mark.parametrize("flip", [False, True], ids=["kept", "mirrored"])
def test_unchanged_zone_keeps_derived_board_fill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flip: bool
) -> None:
    from fenolite.model.board import ZoneFill

    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    assert bench.build("--confirm")[0] == 0
    model = bench.read()
    assert model.board
    zone = model.board.zones[0]
    zone = dataclasses.replace(zone, filled=True, fills=(ZoneFill(zone.layers[0], zone.outline),))
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, zones=(zone,)))
    bench.board.write_text(write_board(model).text)
    assert bench.read().board.zones[0].fills
    if flip:
        shutil.rmtree(bench.out / ".fenolite")
        bench.edit_script("dut.place(mm(10), mm(8))", 'dut.place(mm(10), mm(8), side="bottom")')
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        assert built_model(bench).board.zones[0].fills


def test_missing_snapshot_does_not_use_cache_to_move_owned_copper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    (bench.out / BASE_FILE).unlink()
    bench.edit_script("dut.place(mm(10), mm(8))", "dut.place(mm(20), mm(8))")
    before = bench.board.read_bytes()
    code, env, err = bench.build("--confirm")
    assert code == 5, err
    assert any(i["code"] == "reuse.layout-conflict" for i in env["issues"])
    assert bench.board.read_bytes() == before


def test_settled_candidate_is_not_a_saved_cad_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    request = '\ndut.part("bot").place(mm(4), mm(6))\n'
    bench.script.write_text(bench.script.read_text() + request)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not built_model(bench).board.tracks
    bench.script.write_text(bench.script.read_text().replace(request, ""))
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert len(built_model(bench).board.tracks) == 1


def test_kept_cad_points_do_not_drift_in_a_turned_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    bench.edit_script("dut.place(mm(10), mm(8))", "dut.place(mm(10), mm(8), rot=33)")
    assert bench.build("--confirm")[0] == 0
    model = bench.read()
    assert model.board
    track = model.board.tracks[0]
    track = dataclasses.replace(
        track,
        start=Point(track.start.x + 50_000, track.start.y),
        end=Point(track.end.x + 50_000, track.end.y),
        locked=False,
    )
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, tracks=(track,)))
    bench.board.write_text(write_board(model).text)
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        assert (built_model(bench).board.tracks[0].start, built_model(bench).board.tracks[0].end) == (
            track.start,
            track.end,
        )


@pytest.mark.parametrize("delete", [False, True], ids=["cad-edited-copy", "cad-deleted-copy"])
def test_owned_copy_survives_host_intents_and_cacheless_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delete: bool
) -> None:
    import json

    bench = make_bench(tmp_path, monkeypatch)
    all_kinds(bench)
    bench.script.write_text(
        bench.script.read_text()
        + """
design.track("host", dut.part("top").pad(1), dut.part("top").pad(1).at(mm(2), mm(0)), width=mm("0.25"))
"""
    )
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not any(i["code"] == "kicad.copper.stale" for i in env["issues"])
    owned = set(json.loads((bench.out / BASE_FILE).read_text())["copies"]["dut"])
    edit_board(bench, delete=delete)
    shutil.rmtree(bench.out / ".fenolite")
    for _ in range(2):
        code, env, err = bench.build("--confirm")
        assert code == 0, err
        assert not any(i["code"] == "kicad.copper.stale" for i in env["issues"])
        board = built_model(bench).board
        assert board is not None
        copied = [t for t in board.tracks if t.native_ids.get("kicad") in owned]
        host = [t for t in board.tracks if t.native_ids.get("kicad") not in owned]
        assert len(host) == 1 and host[0].width == 250_000
        assert len(copied) == (0 if delete else 2)
        assert all(t.width == 270_000 for t in copied)
