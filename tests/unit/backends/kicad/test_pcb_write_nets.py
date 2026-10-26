# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Target policy, net forms and rows a target no longer writes (capabilities kicad-file-backend and
design-model, change c0017)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import FIXTURE, created_board, mm

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, walk
from fenolite.backends.kicad.versions import (
    DowngradeRefusedError,
    FileKind,
    FutureFormatError,
    LegacyEditRefusedError,
    LossyWriteError,
    check_emittable,
)
from fenolite.core.coords import Size
from fenolite.core.errors import Issue
from fenolite.model.board import Board, FootprintInstance, Pad, Track, Zone
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design

TOKENS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"
SKELETON = TOKENS / "skeleton.kicad_pcb"
TEARDROP = (
    '(zone (net 2) (net_name "B") (layer "F.Cu") (uuid "6f1d2c3e-0000-4000-8000-0000000000aa")'
    ' (name "$teardrop_padvia$") (hatch full 0.1) (priority 30000) (attr (teardrop (type padvia)))'
    " (connect_pads yes (clearance 0)) (min_thickness 0.0254) (fill yes (thermal_gap 0.5)"
    " (thermal_bridge_width 0.5)) (polygon (pts (xy 1 1) (xy 2 1) (xy 2 2))))"
)


def skeleton_with(*items: str, header: int | None = None) -> str:
    text = SKELETON.read_text(encoding="utf-8").rstrip().removesuffix(")") + " ".join(items) + ")\n"
    return text if header is None else text.replace("(version 20241229)", f"(version {header})")


def nets_design() -> Design:
    """Nets VIN, GND and LED_A (in that order), a pad on VIN, a track and a zone on GND."""
    design = created_board()
    nets = tuple(
        Net(id=f"net_00000000-0000-4000-8000-00000000000{i}", name=n)
        for i, n in enumerate(("VIN", "GND", "LED_A"), 1)
    )
    vin, gnd, _ = (n.id for n in nets)
    component = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="J1")
    pad = Pad(
        id="pad_00000000-0000-4000-8000-000000000001",
        number="1",
        shape="rect",
        size=Size(1, 1),
        position=mm(0, 0),
        layers=("F.Cu",),
        net_id=vin,
    )
    footprint = FootprintInstance(
        id="fp_00000000-0000-4000-8000-000000000001",
        component_id=component.id,
        lib_ref="x:y",
        position=mm(5, 5),
        pads=(pad,),
    )
    track = Track(
        id="trk_00000000-0000-4000-8000-000000000001",
        start=mm(1, 1),
        end=mm(2, 1),
        width=200_000,
        layer="F.Cu",
        net_id=gnd,
    )
    zone = Zone(
        id="zon_00000000-0000-4000-8000-000000000001",
        outline=(mm(0, 0), mm(1, 0), mm(1, 1)),
        layers=("B.Cu",),
        net_id=gnd,
    )
    board = Board(
        id="brd_00000000-0000-4000-8000-000000000001",
        layers=created_board().board.layers,
        footprints=(footprint,),
        tracks=(track,),
        zones=(zone,),
    )  # type: ignore[union-attr]
    circuit = Circuit(components=(component,), nets=nets)
    return dataclasses.replace(design, circuit=circuit, board=board)


def nodes(root: Node, head: str) -> list[tuple[str, Node]]:
    return [(loc, n) for loc, n in walk(root) if n.name == head]


# -- net form per target


def test_numbered_table_for_target_9() -> None:
    root = parse(write_board(nets_design(), target=9).text)
    table = [dumps(n, style="compact") for n in root.nodes("net")]
    assert table == ['(net 0 "")', '(net 1 "GND")', '(net 2 "LED_A")', '(net 3 "VIN")']
    (track,) = root.nodes("segment")
    assert track.find("net") == parse("(net 1)")
    (footprint,) = root.nodes("footprint")
    assert footprint.nodes("pad")[0].find("net") == parse('(net 3 "VIN")')
    (zone,) = root.nodes("zone")
    assert zone.find("net") == parse("(net 1)") and zone.find("net_name") == parse('(net_name "GND")')


def test_names_for_target_10() -> None:
    root = parse(write_board(nets_design(), target=10).text)
    assert root.nodes("net") == ()
    (footprint,) = root.nodes("footprint")
    assert footprint.nodes("pad")[0].find("net") == parse('(net "VIN")')
    (zone,) = root.nodes("zone")
    assert zone.find("net") == parse('(net "GND")') and zone.find("net_name") is None


def test_opaque_net_reference_converted() -> None:
    design = read_board(skeleton_with(TEARDROP))
    root = parse(write_board(design, target=10).text)
    teardrop = next(z for z in root.nodes("zone") if z.find("attr") is not None)
    source = parse(TEARDROP)
    assert teardrop.find("net") == parse('(net "B")') and teardrop.find("net_name") is None
    rest = [c for c in source.children if not (isinstance(c, Node) and c.name in ("net", "net_name"))]
    assert [c for c in teardrop.children if not (isinstance(c, Node) and c.name == "net")] == rest
    nine = parse(write_board(design, target=9).text)
    teardrop = next(z for z in nine.nodes("zone") if z.find("attr") is not None)
    assert teardrop == source


SLASHED = "Net-(U1-P1{slash}XL1)"


def test_opaque_reference_to_a_net_stored_with_a_slash() -> None:
    """c0163: a teardrop's ``(net 2)`` resolves to the stored name of net 2, not to its model name."""
    text = skeleton_with(TEARDROP)
    for old in ('(net 2 "B")', '(net_name "B")'):
        text = text.replace(old, old.replace('"B"', f'"{SLASHED}"'))
    design = read_board(text)
    assert "Net-(U1-P1/XL1)" in [n.name for n in design.circuit.nets]
    nine_text = write_board(design, target=9).text
    ten_text = write_board(design, target=10).text
    assert "Net-(U1-P1/XL1)" not in nine_text and "Net-(U1-P1/XL1)" not in ten_text
    nine = parse(nine_text)
    (row,) = [n for n in nine.nodes("net") if n.atoms()[1].value == SLASHED]
    teardrop = next(z for z in nine.nodes("zone") if z.find("attr") is not None)
    assert teardrop.find("net") == Node(Atom.symbol("net"), (row.atoms()[0],))
    assert teardrop.find("net_name") == parse(f'(net_name "{SLASHED}")')
    ten = parse(ten_text)
    teardrop = next(z for z in ten.nodes("zone") if z.find("attr") is not None)
    assert teardrop.find("net") == parse(f'(net "{SLASHED}")') and teardrop.find("net_name") is None


def test_unknown_opaque_net_reference() -> None:
    segment = '(segment (start 0 0) (end 1 0) (width 0.25) (layer "F.Cu") (net 7) (uuid "{}"))'
    issues: list[Issue] = []
    design = read_board(skeleton_with(segment.format("6f1d2c3e-0000-4000-8000-0000000000bb")), issues=issues)
    assert "kicad.board.unknown-net" in [i.code for i in issues]
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=9, allow_lossy=True)
    (issue,) = info.value.issues
    assert info.value.droppable is False and issue.code == "kicad.board.opaque-net-ref"
    assert issue.where == "/kicad_pcb/segment[1]/net[0]"
    with pytest.raises(LossyWriteError):
        write_board(design, target=10)


def test_unconnected_rule_area_in_both_forms() -> None:
    design = read_board(FIXTURE)
    nine = parse(write_board(design, target=9).text)
    assert [n for n in nine.nodes("net") if n == parse('(net 0 "")')] == [parse('(net 0 "")')]
    rule = next(z for z in nine.nodes("zone") if z.find("keepout") is not None)
    assert rule.find("net") == parse("(net 0)") and rule.find("net_name") == parse('(net_name "")')
    ten = parse(write_board(design, target=10).text)
    empty = [n for _, n in nodes(ten, "net") if n.atoms() and n.atoms()[0].value in ("0", "")]
    assert empty == [] and nodes(ten, "net_name") == []


def test_nets_renumbered_by_name() -> None:
    design = read_board(FIXTURE)
    root = parse(write_board(design, target=9).text)
    table = [dumps(n, style="compact") for n in root.nodes("net")]
    assert table == ['(net 0 "")', '(net 1 "GND")', '(net 2 "LED_A")', '(net 3 "VCC")']
    reread = read_board(write_board(design, target=9).text)
    assert {n.name for n in reread.circuit.nets} == {n.name for n in design.circuit.nets}
    assert reread.by_net.keys() == design.by_net.keys()
    assert {k: len(v) for k, v in reread.by_net.items()} == {k: len(v) for k, v in design.by_net.items()}


def test_named_changes_only() -> None:
    """design-model "Slots for lossless round-trip": a 9 → 9 write changes only ``net`` nodes."""
    swapped = SKELETON.read_text(encoding="utf-8").replace('(net 1 "A")', '(net 1 "Z")')
    swapped = swapped.replace('(net 1 "Z")\n\t(net 2 "B")', '(net 1 "Z")\n\t(net 2 "B")')
    source = parse(swapped)
    written = parse(write_board(read_board(swapped), target=9).text)

    def strip(node: Node) -> Node:
        kept = [
            strip(c) if isinstance(c, Node) else c
            for c in node.children
            if not (isinstance(c, Node) and c.name == "net")
        ]
        return node.with_children(kept)

    assert strip(written) == strip(source)
    assert [dumps(n, style="compact") for n in written.nodes("net")] == [
        '(net 0 "")',
        '(net 1 "B")',
        '(net 2 "Z")',
    ]
    (segment,) = written.nodes("segment")
    assert segment.find("net") == parse("(net 2)")


# -- rows a target no longer writes


def test_read_board_upgraded_to_target_10() -> None:
    result = write_board(read_board(SKELETON), target=10)
    root = parse(result.text)
    assert root.find("version") == parse("(version 20260206)")
    assert root.find("generator_version") == parse('(generator_version "10.0")')
    gone = (
        "hpglpennumber",
        "hpglpenspeed",
        "hpglpendiameter",
        "plotinvisibletext",
        "filled_areas_thickness",
        "net_name",
    )
    assert all(nodes(root, head) == [] for head in gone) and root.nodes("net") == ()
    counts = {i.hint.removeprefix("row "): i.message.split(" ", 1)[0] for i in result.issues}
    assert all(i.code == "kicad.board.obsolete-dropped" and i.severity == "info" for i in result.issues)
    assert counts == {
        "board-net-table": "3",
        "zone-net-name": "1",
        "zone-filled-areas-thickness": "1",
        "plot-hpglpennumber": "1",
        "plot-hpglpenspeed": "1",
        "plot-hpglpendiameter": "1",
        "plot-plotinvisibletext": "1",
    }


def test_created_board_has_no_obsolete_infos() -> None:
    assert write_board(created_board(), target=10).issues == ()


# -- target policy


def test_downgrade_refused() -> None:
    with pytest.raises(DowngradeRefusedError) as info:
        write_board(read_board(TOKENS / "future.kicad_pcb"), target=9)
    assert info.value.cli_code == "FEN-7002"


def test_future_board_refused() -> None:
    text = (TOKENS / "future.kicad_pcb").read_text(encoding="utf-8").replace("20260206", "20990101")
    with pytest.raises(FutureFormatError):
        write_board(read_board(text), target=10)


def test_kicad_8_board_refused() -> None:
    design = read_board(TOKENS / "old" / "old.kicad_pcb")
    for target in (9, 10):
        with pytest.raises(LegacyEditRefusedError) as info:
            write_board(design, target=target)
        assert info.value.cli_code == "FEN-7003" and "kicad-cli pcb upgrade" in info.value.hint
        assert info.value.kind is FileKind.BOARD and info.value.version == 20240108


def test_development_header_of_9_is_writable() -> None:
    root = parse(write_board(read_board(skeleton_with(header=20241030)), target=9).text)
    assert root.find("version") == parse("(version 20241229)")


def test_ten_source_written_for_ten() -> None:
    root = parse(write_board(read_board(TOKENS / "future.kicad_pcb"), target=10).text)
    assert root.find("version") == parse("(version 20260206)") and root.nodes("net") == ()


# -- emit check


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("copper", [2, 4])
def test_emit_check_is_clean(target: int, copper: int) -> None:
    root = parse(write_board(created_board(copper), target=target).text)  # type: ignore[arg-type]
    assert check_emittable(root, FileKind.BOARD, target) == ()


def test_skeleton_emit_check_is_clean() -> None:
    for target in (9, 10):
        assert (
            check_emittable(
                parse(write_board(read_board(SKELETON), target=target).text), FileKind.BOARD, target
            )
            == ()
        )


def test_root_table_follows_setup_without_a_source_table() -> None:
    text = (TOKENS / "future.kicad_pcb").read_text(encoding="utf-8")
    text = text.replace("(version 20260206)", "(version 20241229)").replace('"10.0"', '"9.0"')
    root = parse(write_board(read_board(text), target=9).text)
    heads = [c.name for c in root.children if isinstance(c, Node)]
    assert heads[heads.index("setup") + 1] == "net"
    assert root.nodes("net") == (Node(Atom.symbol("net"), (Atom.integer(0), Atom.string(""))),)
