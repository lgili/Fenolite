# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored reproductions of c0427 task 2.5, without private board inputs.

The remaining unsupported inputs refuse by default. Supported inputs retain their geometry through
import and build.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _importcode import BOARD, build, built_board, imported

from fenolite.api import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board
from fenolite.model.design import Design


def _case(kind: str) -> str:
    text = BOARD.read_text(encoding="utf-8")
    if kind in ("outline", "open-outline"):
        root = parse(text)
        without_edges = dumps(
            root.with_children(
                child
                for child in root.children
                if not (
                    isinstance(child, Node)
                    and child.name.startswith("gr_")
                    and (layer := child.find("layer")) is not None
                    and layer.atoms()[0].value == "Edge.Cuts"
                )
            )
        )
        if kind == "outline":
            return without_edges
        end = without_edges.rindex(")")
        edges = (
            "(gr_line (start 100 100) (end 110 100) (stroke (width 0.1) (type solid)) "
            '(layer "Edge.Cuts") (uuid "c0427000-0000-4000-8000-000000000004"))'
            "(gr_arc (start 110 100) (mid 112 102) (end 110 104) (stroke (width 0.2) (type solid)) "
            '(layer "Edge.Cuts") (uuid "c0427000-0000-4000-8000-000000000005"))'
        )
        return without_edges[:end] + edges + without_edges[end:]
    if kind in ("pad-net-unnumbered", "mixed-unnumbered-pads"):
        start = text.rindex("(footprint ", 0, text.index('"J1"'))
        at = text.index("\t\t(embedded_fonts no)", start)
        pad = (
            '(pad "" thru_hole circle (at -5 0) (size 1.8 1.8) (drill 0.9) '
            '(layers "*.Cu" "*.Mask") (net "GND") '
            '(uuid "c0427000-0000-4000-8000-000000000003"))\n'
        )
        if kind == "mixed-unnumbered-pads":
            pad = (
                pad.replace("(at -5 0)", "(at -7 0)")
                .replace('(net "GND") ', "")
                .replace("000000000003", "000000000006")
                + pad
                + pad.replace("(at -5 0)", "(at -3 0)")
                .replace('"GND"', '"PAD_ONLY"')
                .replace("000000000003", "000000000007")
            )
        return text[:at] + pad + text[at:]
    if kind == "negative-width-arc":
        return _case("zero-width-arc").replace(
            '(stroke (width 0) (type solid)) (layer "Dwgs.User")',
            '(stroke (width -0.000001) (type solid)) (fill yes) (layer "Dwgs.User")',
        )
    extra = {
        "copper-without-net": (
            '(via (at 110 150) (size 1) (drill 0.5) (layers "F.Cu" "B.Cu") '
            '(uuid "c0427000-0000-4000-8000-000000000001"))'
        ),
        "zero-width-arc": (
            "(gr_arc (start 110 150) (mid 112 148) (end 114 150) "
            '(stroke (width 0) (type solid)) (layer "Dwgs.User") '
            '(uuid "c0427000-0000-4000-8000-000000000002"))'
        ),
    }[kind]
    end = text.rindex(")")
    return text[:end] + extra + text[end:]


@pytest.mark.parametrize(
    ("kind", "reported"),
    [
        ("negative-width-arc", "drawing"),
    ],
)
def test_remaining_kind_is_reproducible_and_refused_without_loss_permission(
    tmp_path: Path, kind: str, reported: str
) -> None:
    source = tmp_path / "source" / f"{kind}.kicad_pcb"
    source.parent.mkdir()
    source.write_text(_case(kind), encoding="utf-8")
    before = source.read_bytes()
    refused = imported(tmp_path, source)
    assert refused.exit_code == 7, refused.error
    assert reported in str(refused.error)
    assert not (tmp_path / "out").exists()
    preview = imported(tmp_path, source, "--allow-lossy")
    assert preview.exit_code == 0, preview.error
    rows = preview.result["unexpressed"]
    assert [(row["kind"], row["count"]) for row in rows] == [(reported, 1)]
    assert source.read_bytes() == before
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("major", [9, 10])
def test_netless_via_import_preserves_geometry_and_no_net(tmp_path: Path, major: int) -> None:
    source = tmp_path / "source" / "netless-via.kicad_pcb"
    source.parent.mkdir()
    source.write_text(_case("copper-without-net"), encoding="utf-8")
    position = Point(110_000_000, 150_000_000)
    original = read_board(source).design.board
    assert original is not None
    (expected,) = [via for via in original.vias if via.position == position]
    assert expected.net_id is None

    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert not reply.result["unexpressed"]
    assert reply.result["equivalence"]["equivalent"]
    output = tmp_path / "out"
    result = build(output, "--kicad-version", str(major))
    assert result.exit_code == 0, result.error
    restored = built_board(output, "netless-via").design.board
    assert restored is not None
    assert len(restored.vias) == len(original.vias)
    (actual,) = [via for via in restored.vias if via.position == position]
    assert actual.net_id is None
    assert (actual.diameter, actual.drill, actual.layers, actual.via_type, actual.locked) == (
        expected.diameter,
        expected.drill,
        expected.layers,
        expected.via_type,
        expected.locked,
    )
    assert all(via.net_id is not None for via in restored.vias if via.position != position)


@pytest.mark.parametrize("major", [9, 10])
def test_zero_width_user_arc_keeps_points_and_literal_width(tmp_path: Path, major: int) -> None:
    source = tmp_path / "source" / "zero-width-arc.kicad_pcb"
    source.parent.mkdir()
    before = _case("zero-width-arc").encode()
    source.write_bytes(before)
    original = read_board(source).design.board
    assert original is not None
    (expected,) = [g for g in original.graphics if g.kind == "arc" and g.layer == "Dwgs.User"]
    assert expected.width == 0

    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert reply.result["equivalence"]["equivalent"]
    output = tmp_path / "out"
    result = build(output, "--kicad-version", str(major))
    assert result.exit_code == 0, result.error
    restored = built_board(output, "zero-width-arc").design.board
    assert restored is not None
    (arc,) = [g for g in restored.graphics if g.kind == "arc" and g.layer == expected.layer]
    assert (arc.points, arc.width) == (expected.points, 0)
    assert source.read_bytes() == before


@pytest.mark.parametrize("major", [9, 10])
@pytest.mark.parametrize("kind", ["outline", "open-outline"])
def test_missing_closed_outline_keeps_only_source_edges(tmp_path: Path, major: int, kind: str) -> None:
    source = tmp_path / "source" / f"{kind}.kicad_pcb"
    source.parent.mkdir()
    before = _case(kind).encode()
    source.write_bytes(before)
    original = read_board(source).design.board
    assert original is not None

    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert reply.result["equivalence"]["equivalent"]
    output = tmp_path / "out"
    assert "design.board(outline=()" in (output / "design.py").read_text(encoding="utf-8")
    result = build(output, "--kicad-version", str(major))
    assert result.exit_code == 0, result.error
    restored = built_board(output, kind).design.board
    assert restored is not None

    def edges(board: Board) -> list[tuple[str, tuple[Point, ...], int]]:
        return sorted((g.kind, g.points, g.width) for g in board.graphics if g.layer == "Edge.Cuts")

    assert restored.outline is None
    assert len(edges(original)) == (2 if kind == "open-outline" else 0)
    assert edges(restored) == edges(original)
    assert source.read_bytes() == before


@pytest.mark.parametrize("major", [9, 10])
def test_unnumbered_pads_keep_nets_without_symbol_pins(tmp_path: Path, major: int) -> None:
    source = tmp_path / "source" / "mixed-unnumbered-pads.kicad_pcb"
    source.parent.mkdir()
    before = _case("mixed-unnumbered-pads").encode()
    source.write_bytes(before)

    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert reply.result["equivalence"]["equivalent"]
    output = tmp_path / "out"
    result = build(output, "--kicad-version", str(major))
    assert result.exit_code == 0, result.error
    original = read_board(source).design
    restored = built_board(output, "mixed-unnumbered-pads").design

    def pads(design: Design) -> dict[Point, tuple[str | None, str, Size, int | None, tuple[str, ...]]]:
        assert design.board is not None
        nets = {net.id: net.name for net in design.circuit.nets}
        (part,) = [c for c in design.circuit.components if c.ref == "J1"]
        (footprint,) = [fp for fp in design.board.footprints if fp.component_id == part.id]
        return {
            p.position: (nets.get(p.net_id or ""), p.kind, p.size, p.drill, p.layers)
            for p in footprint.pads
            if not p.number
        }

    expected = pads(original)
    assert {point: fields[0] for point, fields in expected.items()} == {
        Point(-7_000_000, 0): None,
        Point(-5_000_000, 0): "GND",
        Point(-3_000_000, 0): "PAD_ONLY",
    }
    assert pads(restored) == expected
    (pad_only,) = [net for net in restored.circuit.nets if net.name == "PAD_ONLY"]
    assert pad_only.members == ()
    rebuild = build(output, "--kicad-version", str(major))
    assert rebuild.exit_code == 0, rebuild.error
    assert pads(built_board(output, "mixed-unnumbered-pads").design) == expected
    if major == 10:
        built_path = output / "built" / source.name
        assert restored.board is not None
        (first,) = [
            pad
            for fp in restored.board.footprints
            for pad in fp.pads
            if not pad.number and pad.position == Point(-5_000_000, 0)
        ]
        text = built_path.read_text(encoding="utf-8")
        native_id = first.native_ids["kicad"]
        assert text.count(native_id) == 1
        built_path.write_text(
            text.replace(native_id, "c0427000-0000-4000-8000-000000000008"), encoding="utf-8"
        )
        rebuild = build(output, "--kicad-version", str(major))
        assert rebuild.exit_code == 0, rebuild.error
        assert pads(built_board(output, "mixed-unnumbered-pads").design) == expected

        script = output / "design.py"
        python = script.read_text(encoding="utf-8")
        call = ".unnumbered_pad_net(2, pad_only)"
        assert python.count(call) == 1
        script.write_text(python.replace(call, ".unnumbered_pad_net(3, pad_only)"), encoding="utf-8")
        built_before = built_path.read_bytes()
        refused = build(output, "--kicad-version", str(major), "--dry-run")
        assert refused.exit_code == 5, refused.error
        assert any(issue["code"] == "build.pad-unknown" for issue in refused.envelope["issues"])
        assert built_path.read_bytes() == built_before
    assert source.read_bytes() == before
