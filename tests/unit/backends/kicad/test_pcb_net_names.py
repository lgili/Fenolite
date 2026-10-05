# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net names in KiCad's stored form on boards (capability kicad-file-backend, "Net names in KiCad's
stored form"; change c0061)."""

from __future__ import annotations

import re

import pytest
from _boards import FIXTURE, SCENARIOS, board, rt1_problems, segment
from _buildhelp import build
from _layout_edit import add_items, mm, pad_position
from _preserve_help import rebuild
from _schbuild import SLASH_NET, blink_slash

from fenolite.backends.kicad.pcb import read_board, rebuild_board, stored_net_name, write_board
from fenolite.backends.kicad.sexpr import parse, tree_equal
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Net

STORED = "mod{slash}LED_A"


def written(target: int) -> str:
    """The blink with the net ``mod/LED_A``, built without a schematic: a created design."""
    output = build(blink_slash(), target, schematic="skip")
    assert write_board(output.design, target=target).text == output.files["blink.kicad_pcb"].decode("utf-8")
    return output.files["blink.kicad_pcb"].decode("utf-8")


def test_created_net_with_a_slash() -> None:
    ten, nine = written(10), written(9)
    assert ten.count(f'(net "{STORED}")') == 2  # the pads of R1 and D1
    assert len(re.findall(rf'^\t\(net \d+ "{re.escape(STORED)}"\)$', nine, flags=re.M)) == 1
    assert SLASH_NET not in ten and SLASH_NET not in nine


@pytest.mark.parametrize("target", [9, 10])
def test_reads_back_with_the_slash(target: int) -> None:
    text = written(target)
    design = read_board(text)
    (net,) = [n for n in design.circuit.nets if "LED_A" in n.name]
    assert net.name == SLASH_NET and net.id == derived_id("net", "kicad", f"net:{STORED}")
    assert len(net.members) == 2 and stored_net_name(net) == STORED
    assert tree_equal(rebuild_board(design), parse(text))
    assert tree_equal(parse(write_board(design, target=target).text), parse(text))
    assert not rt1_problems(text)


def test_hierarchical_net_is_untouched() -> None:
    text = FIXTURE.read_text(encoding="utf-8").replace('"VCC"', '"/power/VCC"')
    assert '"/power/VCC"' in text
    design = read_board(text)
    (net,) = [n for n in design.circuit.nets if n.name.endswith("VCC")]
    assert net.name == "/power/VCC" and stored_net_name(net) == "/power/VCC"
    out = write_board(design, target=9).text
    assert '"/power/VCC"' in out and "{slash}" not in out
    assert not rt1_problems(text)


def test_collision_keeps_the_stored_spelling() -> None:
    text = SCENARIOS["net-collision"]
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert [n.name for n in design.circuit.nets] == ["a/b", "a{slash}b"]
    found = [i for i in issues if i.code == "kicad.board.net-name-collision"]
    assert [(i.severity,) for i in found] == [("info",)] and "a/b" in found[0].message
    assert tree_equal(rebuild_board(design), parse(text))
    assert [stored_net_name(n) for n in design.circuit.nets] == ["a/b", "a{slash}b"]
    alone = read_board(board(segment(1, net="(net 1)"), nets=("", "a{slash}b")))
    assert [n.name for n in alone.circuit.nets] == ["a/b"]


def test_a_sheet_path_and_a_label_slash_in_one_name() -> None:
    """``/cpu/A{slash}B``: the net of a label ``A/B`` on the sheet ``/cpu/``. The model name unescapes the
    label's slash, and the written name is the stored spelling again, not ``{slash}cpu{slash}…``."""
    mixed = "/cpu/A{slash}B"
    text = board(segment(1, net="(net 1)"), nets=("", mixed))
    design = read_board(text)
    (net,) = design.circuit.nets
    assert net.name == "/cpu/A/B" and stored_net_name(net) == mixed
    assert tree_equal(rebuild_board(design), parse(text)) and not rt1_problems(text)
    assert f'"{mixed}"' in write_board(design, target=9).text


def test_created_and_read_nets_are_told_apart() -> None:
    created = Net(id=derived_id("net", "dsl", "net:x/y"), name="x/y")
    read = Net(id=derived_id("net", "kicad", "net:x/y"), name="x/y")
    escaped = Net(id=derived_id("net", "kicad", "net:x{slash}y"), name="x/y")
    assert [stored_net_name(n) for n in (created, read, escaped)] == ["x{slash}y", "x/y", "x{slash}y"]


@pytest.mark.parametrize("target", [9, 10])
def test_board_of_an_older_build(target: int) -> None:
    """A board that stored the net with a raw slash, with a track on it, is rewritten with the stored
    form and keeps the track."""
    first = written(target)
    old = first.replace(STORED, SLASH_NET)
    assert STORED not in old and SLASH_NET in old
    start, end = pad_position(old, "R1", "2"), pad_position(old, "D1", "2")
    uuid = "00000000-0000-4000-8000-0000000e0061"
    row = re.search(rf'^\t\(net (\d+) "{re.escape(SLASH_NET)}"\)', old, flags=re.M)  # the raw spelling
    raw_ref = f"(net {row.group(1)})" if row is not None else f'(net "{SLASH_NET}")'
    track = (
        f"(segment (start {mm(start.x)} {mm(start.y)}) (end {mm(end.x)} {mm(start.y)}) "
        f'(width 0.25) (layer "F.Cu") {raw_ref} (uuid "{uuid}"))'
    )
    again = rebuild(blink_slash(), add_items(old, track), target)
    text = again.files["blink.kicad_pcb"].decode("utf-8")
    assert uuid in text and STORED in text and f'"{SLASH_NET}"' not in text
    assert not [i for i in again.issues if i.code == "layout.net-removed"]
    design = read_board(text)
    (net,) = [n for n in design.circuit.nets if n.name == SLASH_NET]
    assert design.board is not None
    assert [t.net_id for t in design.board.tracks if t.native_ids.get("kicad") == uuid] == [net.id]
