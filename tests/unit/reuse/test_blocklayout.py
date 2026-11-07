# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact block layout files and digests (c0271; block-layouts)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _blocklayoutbench import LAYOUT, MM, built_model, make_bench

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.cli import place_group
from fenolite.core.coords import Point
from fenolite.geometry.transform import Transform
from fenolite.model.board import Arc, Via, Zone, ZoneHatch, ZoneSettings
from fenolite.reuse.blocklayout import (
    BlockLayoutError,
    capture_block_layout,
    nets_digest,
    parts_digest,
    read_block_layout,
    write_block_layout,
)


def test_read_exact_layout() -> None:
    layout = read_block_layout(LAYOUT)
    assert layout.parts["top"].at == Point(0, 0)
    assert layout.parts["bot"].at == Point(0, 2_500_000)
    assert {p.rotation for p in layout.parts.values()} == {90_000_000}
    assert layout.tracks[0].net_id == "port:OUT" and layout.tracks[0].width == 250_000
    assert layout.pads[layout.tracks[0].id] == ("bot.1", "top.2")


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ('evidence = "INFERRED"', 'evidence = "INFERRED"\ncolour = "blue"', "colour"),
        ('at = ["0mm", "0mm"]', 'at = ["0.0000001mm", "0mm"]', "at"),
        ('rotation = "90deg"', 'rotation = "0.0000001deg"', "rotation"),
        ('side = "top"', 'side = "left"', "side"),
        ('width = "0.25mm"', "width = 0.25", "width"),
    ],
)
def test_read_rejects_unknown_and_inexact(tmp_path: Path, old: str, new: str, key: str) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(LAYOUT.read_text().replace(old, new))
    with pytest.raises(BlockLayoutError) as error:
        read_block_layout(path)
    assert error.value.code == "FEN-3004" and key in str(error.value) and path.name in str(error.value)


def test_read_higher_schema(tmp_path: Path) -> None:
    path = tmp_path / "future.toml"
    path.write_text(LAYOUT.read_text().replace("block-layout.v0", "block-layout.v2"))
    with pytest.raises(BlockLayoutError) as error:
        read_block_layout(path)
    assert error.value.code == "FEN-3002"


def test_write_canonical_round_trip(tmp_path: Path) -> None:
    layout = read_block_layout(LAYOUT)
    assert write_block_layout(layout) == LAYOUT.read_bytes()
    path = tmp_path / "round.toml"
    path.write_bytes(write_block_layout(layout))
    assert read_block_layout(path) == layout


def test_write_all_copper_and_settings(tmp_path: Path) -> None:
    layout = read_block_layout(LAYOUT)
    layout = dataclasses.replace(
        layout,
        arcs=(
            Arc(
                id="a",
                start=Point(1, 2),
                mid=Point(3, 5),
                end=Point(8, 9),
                width=321,
                layer="F.Cu",
                net_id="net:sub/FB",
            ),
        ),
        vias=(
            Via(
                id="v",
                position=Point(77, 88),
                diameter=600_001,
                drill=300_001,
                layers=("F.Cu", "B.Cu"),
                net_id="port:LO",
            ),
        ),
        zones=(
            Zone(
                id="z",
                outline=(Point(0, 0), Point(MM, 0), Point(0, MM)),
                layers=("B.Cu",),
                net_id="port:LO",
                settings=ZoneSettings(
                    clearance=123, fill_mode="hatched", hatch=ZoneHatch(orientation=33_123_456)
                ),
            ),
        ),
    )
    path = tmp_path / "all.toml"
    path.write_bytes(write_block_layout(layout))
    second = read_block_layout(path)
    assert second.arcs[0].width == 321 and second.vias[0].drill == 300_001
    assert second.zones[0].settings == layout.zones[0].settings
    assert second.zones[0].fills == ()
    assert write_block_layout(second) == path.read_bytes()


def test_digests_values_case_and_net_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, layout=False)
    assert bench.build("--confirm")[0] == 0
    model = built_model(bench)
    expected = read_block_layout(LAYOUT)
    assert parts_digest(model, "dut") == expected.parts_digest
    assert nets_digest(model, "dut") == expected.nets_digest
    components = tuple(dataclasses.replace(c, value="64k9") for c in model.circuit.components)
    other = dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))
    assert (parts_digest(other, "dut"), nets_digest(other, "dut")) == (
        expected.parts_digest,
        expected.nets_digest,
    )
    components = tuple(dataclasses.replace(c, lib_footprint_ref="Fenolite:Chip_0402") for c in components)
    other = dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))
    assert parts_digest(other, "dut") != expected.parts_digest
    renamed = dataclasses.replace(
        model,
        circuit=dataclasses.replace(
            model.circuit,
            nets=tuple(
                dataclasses.replace(n, name="ADC0" if n.name == "OUT" else n.name) for n in model.circuit.nets
            ),
        ),
    )
    assert nets_digest(renamed, "dut") == expected.nets_digest


def test_capture_inverse_frame_and_copper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch)
    code, env, err = bench.build("--confirm")
    assert code == 0, (env, err)
    model = built_model(bench)
    assert model.board
    pads = KicadBackend().board_pads(model)
    selected = place_group.moving_copper(model, pads, {f.id for f in model.board.footprints})
    capture = capture_block_layout(
        model, "dut", pose=Transform.translation(110 * MM, 108 * MM), pads=pads, selected=selected
    )
    assert capture.layout and not capture.issues
    assert write_block_layout(capture.layout) == LAYOUT.read_bytes()


def test_capture_anchor_and_unplaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, layout=False)
    assert bench.build("--confirm")[0] == 0
    model = built_model(bench)
    capture = capture_block_layout(model, "dut", origin="anchor", anchor="top")
    assert capture.layout and capture.layout.parts["top"].at == Point(0, 0)
    assert model.board
    model = dataclasses.replace(
        model, board=dataclasses.replace(model.board, footprints=model.board.footprints[:1])
    )
    capture = capture_block_layout(model, "dut")
    assert capture.layout is None and capture.issues[0].code == "blocks.capture-unplaced"


def test_capture_escape_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = make_bench(tmp_path, monkeypatch, layout=False)
    assert bench.build("--confirm")[0] == 0
    model = built_model(bench)
    model = dataclasses.replace(
        model,
        circuit=dataclasses.replace(
            model.circuit, ports=tuple(p for p in model.circuit.ports if p.name != "OUT")
        ),
    )
    capture = capture_block_layout(model, "dut")
    assert capture.layout and any(i.code == "blocks.capture-escape" for i in capture.issues)


def test_layout_incomplete_tables_with_forged_digest_are_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.reuse.blocklayout import apply_block_layout

    bench = make_bench(tmp_path, monkeypatch, layout=False)
    assert bench.build("--confirm")[0] == 0
    layout = dataclasses.replace(
        read_block_layout(LAYOUT), parts={"top": read_block_layout(LAYOUT).parts["top"]}
    )
    application = apply_block_layout(layout, built_model(bench), "dut", Transform())
    assert application.status == "stale" and not application.parts


def test_capture_refuses_unrepresentable_via_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.model.board import ViaProtection

    bench = make_bench(tmp_path, monkeypatch)
    assert bench.build("--confirm")[0] == 0
    model = built_model(bench)
    assert model.board
    net = next(n.id for n in model.circuit.nets if n.name == "OUT")
    via = Via(
        id="protected-via",
        position=Point(110 * MM, 109 * MM),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
        net_id=net,
        protection=ViaProtection(filling=True),
    )
    model = dataclasses.replace(model, board=dataclasses.replace(model.board, vias=(via,)))
    capture = capture_block_layout(model, "dut", selected=frozenset({via.id}))
    assert capture.layout is None
    assert any(i.code == "blocks.capture-check-failed" and "protection" in i.message for i in capture.issues)
