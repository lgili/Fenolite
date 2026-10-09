# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-tie groups on boards and footprints (capability kicad-file-backend, "Net-tie groups on boards and
footprints"; change c0114).

The ``net_tie_pad_groups`` child of a footprint is projected into ``net_ties`` and stays a projected slot:
a read board is written back byte for byte, and an edited field is refused. The footprint texts are
authored here in the form KiCad's own net-tie library writes (S-0018, S-0042); the two spellings are those
of KiCad's demo boards (S-0058).
"""

from __future__ import annotations

import dataclasses

import pytest
from _ties import MM, TieBoard, row, tie_footprint

from fenolite.backends.kicad._fpmap import net_tie_groups, net_tie_node
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.mod import READ_ONLY_CODE, read_footprint, write_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design

GROUP = (("1", "2"),)
OFFICIAL = """(footprint "NetTie-2_SMD_Pad0.5mm"
\t(version 20241229)
\t(generator "pcbnew")
\t(generator_version "9.0")
\t(layer "F.Cu")
\t(descr "Net tie, 2 pin, 0.5mm square SMD pads")
\t(tags "net tie")
\t(property "Reference" "NT**"
\t\t(at 0 -1.2 0)
\t\t(layer "F.SilkS")
\t\t(uuid "00000000-0000-4000-8000-00000000a001")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(property "Value" "NetTie-2_SMD_Pad0.5mm"
\t\t(at 0 1.2 0)
\t\t(layer "F.Fab")
\t\t(uuid "00000000-0000-4000-8000-00000000a002")
\t\t(effects (font (size 1 1) (thickness 0.15)))
\t)
\t(attr exclude_from_pos_files exclude_from_bom allow_soldermask_bridges)
\t(net_tie_pad_groups GROUPS)
\t(fp_poly
\t\t(pts (xy -0.5 -0.25) (xy 0.5 -0.25) (xy 0.5 0.25) (xy -0.5 0.25))
\t\t(stroke (width 0) (type solid))
\t\t(fill yes)
\t\t(layer "F.Cu")
\t\t(uuid "00000000-0000-4000-8000-00000000a003")
\t)
\t(pad "1" smd circle (at -0.5 0) (size 0.5 0.5) (layers "F.Cu")
\t\t(uuid "00000000-0000-4000-8000-00000000a004")
\t)
\t(pad "2" smd circle (at 0.5 0) (size 0.5 0.5) (layers "F.Cu")
\t\t(uuid "00000000-0000-4000-8000-00000000a005")
\t)
)
"""
"""Authored for this test in the layout of a KiCad 9 footprint file: the token follows ``attr``."""


def official(groups: str = '"1, 2"') -> str:
    return OFFICIAL.replace("GROUPS", groups)


def board_with(defn_text: str) -> str:
    """A board text holding the footprint placed as ``NT1`` with its pads on nets ``A`` and ``B``."""
    defn = read_footprint(defn_text, library="NetTie")
    board = TieBoard()
    component = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="NT1", value="tie")
    placed = place_footprint(defn, component=component, at=Point(20 * MM, 20 * MM), key="NT1")
    nets = {"1": board.net("A"), "2": board.net("B")}
    placed = dataclasses.replace(
        placed, pads=tuple(dataclasses.replace(pad, net_id=nets[pad.number]) for pad in placed.pads)
    )
    board.components.append(component)
    board.footprints.append(placed)
    return write_board(board.build(), target=9).text


def only_footprint(design: Design) -> FootprintInstance:
    assert design.board is not None
    (placed,) = design.board.footprints
    return placed


def test_read_official_form_and_write_it_back() -> None:
    """Scenario "Official form read": the groups are projected and the unchanged board keeps its bytes."""
    text = board_with(official())
    assert '(net_tie_pad_groups "1, 2")' in text
    design = read_board(text)
    assert only_footprint(design).net_ties == GROUP
    assert write_board(design, target=9).text == text


@pytest.mark.parametrize(
    ("written", "groups"),
    [
        ('"1,2"', (("1", "2"),)),
        ('"1, 2" "3, 4"', (("1", "2"), ("3", "4"))),
        ('"1, 2, 3"', (("1", "2", "3"),)),
        ('" 1 ,2 ,"', (("1", "2"),)),
        ('""', ()),
    ],
)
def test_read_spelling_and_several_groups(written: str, groups: tuple[tuple[str, ...], ...]) -> None:
    """Scenario "Spelling and several groups": a string is split at commas, spaces and empty parts are
    dropped; the child is kept as written."""
    defn = read_footprint(official(written), library="NetTie")
    assert defn.net_ties == groups
    text = board_with(official(written))
    assert f"(net_tie_pad_groups {written})" in text
    assert only_footprint(read_board(text)).net_ties == groups
    (child,) = [
        c for c in parse(official(written)).children if isinstance(c, Node) and c.name.startswith("net")
    ]
    assert net_tie_groups(child) == groups
    assert net_tie_node((("1", "2"), ("3", "4"))).atoms()[1].value == "3, 4"


def test_read_footprint_without_the_child_has_no_groups() -> None:
    plain = official().replace('\t(net_tie_pad_groups "1, 2")\n', "")
    assert read_footprint(plain, library="NetTie").net_ties == ()
    assert only_footprint(read_board(board_with(plain))).net_ties == ()


def test_edited_groups_are_refused_on_a_board() -> None:
    """Scenario "Edited groups refused"."""
    design = read_board(board_with(official()))
    assert design.board is not None
    edited = dataclasses.replace(only_footprint(design), net_ties=(("1",),))
    changed = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(edited,)))
    with pytest.raises(LossyWriteError) as caught:
        write_board(changed, target=10)
    (issue,) = caught.value.issues
    assert issue.code == "kicad.board.projection-read-only" and "net_ties" in issue.message
    assert "footprint" in issue.where and caught.value.droppable is False


def test_groups_added_to_a_read_footprint_are_refused() -> None:
    plain = official().replace('\t(net_tie_pad_groups "1, 2")\n', "")
    design = read_board(board_with(plain))
    assert design.board is not None
    edited = dataclasses.replace(only_footprint(design), net_ties=GROUP)
    changed = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(edited,)))
    with pytest.raises(LossyWriteError) as caught:
        write_board(changed, target=10)
    assert [(i.code, "net_ties" in i.message) for i in caught.value.issues] == [
        ("kicad.board.projection-read-only", True)
    ]


def test_library_definition_keeps_its_child_and_refuses_an_edit() -> None:
    defn = read_footprint(official(), library="NetTie")
    assert '(net_tie_pad_groups "1, 2")' in write_footprint(defn, target=9)
    with pytest.raises(LossyWriteError) as caught:
        write_footprint(dataclasses.replace(defn, net_ties=(("1", "2"), ("3", "4"))), target=9)
    assert [(i.code, "net_ties" in i.message) for i in caught.value.issues] == [(READ_ONLY_CODE, True)]
    plain = read_footprint(official().replace('\t(net_tie_pad_groups "1, 2")\n', ""), library="NetTie")
    with pytest.raises(LossyWriteError):
        write_footprint(dataclasses.replace(plain, net_ties=GROUP), target=9)


def test_placed_library_net_tie_keeps_its_groups() -> None:
    """Scenario "Placed library net tie keeps its groups": ``place_footprint`` carries the child of a
    library definition, and the board frame that the copper guard reads sees the groups."""
    design = read_board(board_with(official()))
    placed = only_footprint(design)
    assert placed.net_ties == GROUP
    pads = KicadBackend().board_pads(design)
    assert {pad.footprint_id for pad in pads} == {placed.id} and sorted(pad.number for pad in pads) == [
        "1",
        "2",
    ]


@pytest.mark.parametrize("target", [9, 10])
def test_authored_net_tie_reaches_the_board(target: int) -> None:
    board = TieBoard()
    board.place("NT1", tie_footprint("Two", row(2, 4 * MM // 5), groups=GROUP), Point(20 * MM, 20 * MM))
    text = write_board(board.build(), target=target).text
    assert text.count('(net_tie_pad_groups "1, 2")') == 1
    assert only_footprint(read_board(text)).net_ties == GROUP
