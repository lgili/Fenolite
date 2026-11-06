# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Items ``import --to python`` left out as ``import.item-unexpressed`` are expressed, or kept as written
(change c0427). Every case is authored on the committed project ``tests/data/import_python/two_sheet``."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, built_board, copy_project, imported

from fenolite.backends.kicad.dru import read_rules
from fenolite.core.coords import Point


def _rules(tmp_path: Path, text: str) -> Path:
    source = copy_project(tmp_path)
    source.with_suffix(".kicad_dru").write_text("(version 1)\n" + text)
    return source


def _kinds(reply: object) -> dict[str, int]:
    rows = reply.result.get("unexpressed", [])  # type: ignore[attr-defined]
    return {row["kind"]: row["count"] for row in rows}


def test_a_rule_the_dsl_cannot_say_is_kept_with_its_kind_in_file_order(tmp_path: Path) -> None:
    """A clearance rule on an undeclared net class has no ``design.rules`` call; it and the other clearance
    rule are kept as written, in their order (the later one governs); the track width minimum stays code."""
    source = _rules(
        tmp_path,
        '(rule "ghost"\n\t(condition "A.NetClass == \'Ghost\'")\n\t(constraint clearance (min 0.3mm))\n)\n'
        '(rule "wide"\n\t(constraint clearance (min 0.2mm))\n)\n'
        '(rule "narrow"\n\t(constraint track_width (min 0.2mm))\n)\n',
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert "custom-rule" not in _kinds(reply)
    script = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert script.index('"rule/1"') < script.index('(rule "ghost"') < script.index('"rule/2"')
    assert script.index('"rule/2"') < script.index('(rule "wide"')
    assert 'design.rules.minimum(track_width=mm("0.2"))' in script  # the plain minimum stays code
    assert build(tmp_path / "out").exit_code == 0
    held = read_rules((tmp_path / "out" / "built" / "two_sheet.kicad_dru").read_text(encoding="utf-8"))
    clearance = [rule.name for rule in held.rules if rule.kind == "clearance"]
    assert clearance == ["ghost", "wide"]


def _drawn(tmp_path: Path, item: str) -> Path:
    source = copy_project(tmp_path)
    board = source.with_suffix(".kicad_pcb")
    text = board.read_text(encoding="utf-8")
    end = text.rindex(")")
    board.write_text(text[:end] + item + text[end:], encoding="utf-8")
    return source


def test_a_net_only_a_copper_graphic_names_gets_a_variable(tmp_path: Path) -> None:
    """A copper polygon on a net no pad, track or schematic names (an Altium fill or region on a board-only
    net) is code with its net; before change c0427 it was left out as a ``drawing``."""
    source = _drawn(
        tmp_path,
        "\t(gr_poly (pts (xy 10 10) (xy 12 10) (xy 12 12)) (stroke (width 0) (type solid)) (fill yes) "
        '(layer "F.Cu") (net "ISLAND") (uuid "6c1e3d0a-0427-4b01-8000-000000000021"))\n',
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert _kinds(reply) == {}
    assert reply.result["equivalence"]["equivalent"] is True  # type: ignore[index]
    script = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'island = Net("ISLAND")' in script and "net=island," in script
    assert build(tmp_path / "out").exit_code == 0
    built = (tmp_path / "out" / "built" / "two_sheet.kicad_pcb").read_text(encoding="utf-8")
    assert '(net "ISLAND")' in built


def test_a_paste_layer_polygon_is_code(tmp_path: Path) -> None:
    """An Altium paste region is a filled polygon on a paste layer, which a drawing may be on (c0427)."""
    source = _drawn(
        tmp_path,
        "\t(gr_poly (pts (xy 10 10) (xy 12 10) (xy 12 12)) (stroke (width 0) (type solid)) (fill yes) "
        '(layer "B.Paste") (uuid "6c1e3d0a-0427-4b01-8000-000000000022"))\n',
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert _kinds(reply) == {}
    assert 'layer="B.Paste"' in (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert build(tmp_path / "out").exit_code == 0
    built = (tmp_path / "out" / "built" / "two_sheet.kicad_pcb").read_text(encoding="utf-8")
    assert '(layer "B.Paste")' in built


def test_a_negative_silk_clearance_is_code(tmp_path: Path) -> None:
    """An Altium silk to silk rule may hold a negative gap; KiCad reads it (``H-K-DRU-NEG-SILK``)."""
    source = _rules(tmp_path, '(rule "silk"\n\t(constraint silk_clearance (min -0.254mm))\n)\n')
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    script = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert 'design.rules.rule("silk", "silk_clearance"' in script
    assert build(tmp_path / "out").exit_code == 0
    held = read_rules((tmp_path / "out" / "built" / "two_sheet.kicad_dru").read_text(encoding="utf-8"))
    assert [(rule.kind, rule.min) for rule in held.rules] == [("silk_clearance", -254_000)]


def test_a_straight_arc_is_the_line_it_draws(tmp_path: Path) -> None:
    """An arc whose three points lie on one line, the middle one between the ends, is the line it draws
    (an Altium arc of a tiny sweep, rounded to the nanometre); before change c0427 it was a ``drawing``. An
    arc of one point, or whose middle point lies beyond an end, draws no line and stays one."""
    arc = (
        '\t(gr_arc (start {0}) (mid {1}) (end {2}) (stroke (width 0.2) (type solid)) (layer "Dwgs.User") '
        '(uuid "6c1e3d0a-0427-4b01-8000-00000000003{3}"))\n'
    )
    points = (("10 10", "11 10", "12 10"), ("20 10", "20 10", "20 10"), ("30 10", "34 10", "32 10"))
    source = _drawn(tmp_path, "".join(arc.format(*row, n) for n, row in enumerate(points, 1)))
    reply = imported(tmp_path, source, "--confirm", "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    assert _kinds(reply) == {"drawing": 2}
    script = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert '"Dwgs.User/arc/1"' in script and '"Dwgs.User/arc/2"' not in script and "design.arc(" not in script
    assert build(tmp_path / "out").exit_code == 0
    built = built_board(tmp_path / "out").design.board
    assert built is not None
    lines = [(g.kind, g.points, g.width) for g in built.graphics if g.layer == "Dwgs.User"]
    assert lines == [("line", (Point(10_000_000, 10_000_000), Point(12_000_000, 10_000_000)), 200_000)]
