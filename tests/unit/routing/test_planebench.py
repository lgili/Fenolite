# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plane bench builds, and its pads and zones are those of the design (change c0107, task 1.2;
capability kicad-oracle, "Plane routing passes the oracle"). No KiCad library and no external tool."""

from __future__ import annotations

from pathlib import Path

import _planebench as pb
import pytest

from fenolite.backends.kicad.pcb import read_board


@pytest.fixture(autouse=True)
def hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("target", [9, 10])
def test_bench_builds_with_planes(tmp_path: Path, target: int) -> None:
    found = pb.load(pb.build_project(tmp_path, target=target))
    board = found.design.board
    assert board is not None and found.plane_layers == pb.PLANE_LAYERS
    nets = {net.id: net.name for net in found.design.circuit.nets}
    assert {(nets[z.net_id or ""], z.layers) for z in board.zones} == {
        ("GND", ("In1.Cu",)),
        ("VCC", ("In2.Cu",)),
    }
    assert all(len(zone.outline) == 4 for zone in board.zones)
    smd = [f"{p.ref}-{p.number}" for p in found.pads if p.net in ("GND", "VCC") and not p.drill]
    assert sorted(smd) == sorted(pb.PLANE_PADS)
    drilled = sorted(f"{p.ref}-{p.number}" for p in found.pads if p.net in ("GND", "VCC") and p.drill)
    assert drilled == ["J1-1", "J1-2", "J2-3", "J2-4"]
    classes = {c.name: (c.track_width, c.clearance) for c in found.design.circuit.netclasses}
    assert classes["PWR"] == (400_000, 200_000) and classes["SIG"] == (200_000, 200_000)
    assert classes["HV"] == (500_000, 300_000)
    assert found.design.rules is not None
    kinds = sorted((rule.kind, rule.min) for rule in found.design.rules.rules)
    assert ("clearance", pb.HV_SIG) in kinds and ("edge_clearance", pb.EDGE_CLEARANCE) in kinds
    assert not board.tracks and not board.vias
    assert len(found.outline) == 1 and len(found.outline[0]) == 4


def test_bench_without_planes_differs_in_the_two_rows(tmp_path: Path) -> None:
    with_planes = pb.build_project(tmp_path / "a").read_text(encoding="utf-8")
    without = pb.build_project(tmp_path / "b", planes=False).read_text(encoding="utf-8")
    assert '(4 "In1.Cu" power)' in with_planes and '(6 "In2.Cu" power)' in with_planes
    typed = without.replace('(4 "In1.Cu" signal)', '(4 "In1.Cu" power)')
    assert typed.replace('(6 "In2.Cu" signal)', '(6 "In2.Cu" power)') == with_planes
    bare = pb.load(pb.build_project(tmp_path / "c", planes=False, rules=False)).design
    assert bare.rules is None or bare.rules.rules == ()
    assert [c.name for c in bare.circuit.netclasses if c.name != "Default"] == []


def test_dogbones_and_edge_bench(tmp_path: Path) -> None:
    found = pb.with_dogbones(pb.load(pb.build_project(tmp_path)))
    board = found.design.board
    assert board is not None and len(board.tracks) == 6 and len(board.vias) == 6
    assert {via.net_id for via in board.vias} == {found.net_id("GND"), found.net_id("VCC")}
    starts = [track.start for track in board.tracks]
    assert starts == [found.pad(where).position for where in pb.DOGBONES]
    edge = pb.edge_bench()
    assert len(edge.outline) == 2 and edge.design.rules is not None
    plain = pb.edge_bench(None).design.rules
    assert plain is None or plain.rules == ()
    assert read_board(pb.build_project(tmp_path / "t9", target=9)).board is not None
