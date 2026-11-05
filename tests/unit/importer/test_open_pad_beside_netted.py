# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A pad on no net beside a pad of its number on a net (capability board-to-code; change c0425). The DSL
joins a pin to every pad of its number, so the code would put the open pad on the net: the import declares
it as ``pad-net-conflict`` and its self-check takes that row as the reason of the level 2 difference. The
authored two-sheet board with a second pad ``1`` on no net added to ``J1``, made in the test's temporary
folder."""

from __future__ import annotations

import json
from pathlib import Path

from _importcode import BOARD, imported

from fenolite.api import read_board
from fenolite.checks.equivalence import compare_designs

OPEN_PAD = """		(pad "1" thru_hole circle
			(at -2.54 0 90)
			(size 1.8 1.8)
			(drill 0.9)
			(layers "*.Cu" "*.Mask")
			(remove_unused_layers no)
			(uuid "c0425000-0000-4000-8000-000000000001")
		)
"""


def with_open_pad(tmp: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    start = text.rindex("(footprint ", 0, text.index('"J1"'))
    at = text.index("\t\t(embedded_fonts no)", start)
    folder = tmp / "open_pad"
    folder.mkdir()
    target = folder / "open_pad.kicad_pcb"
    target.write_text(text[:at] + OPEN_PAD + text[at:], encoding="utf-8")
    return target


def test_open_pad_beside_a_netted_pad_is_a_declared_loss(tmp_path: Path) -> None:
    """Scenario "A pad on no net beside a pad of its number on a net"."""
    source = with_open_pad(tmp_path)
    refused = imported(tmp_path, source)
    assert refused.exit_code == 7, refused.error
    assert "pad-net-conflict" in json.dumps(refused.error)
    reply = imported(tmp_path, source, "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    issues = reply.envelope["issues"]  # type: ignore[index]
    (row,) = [
        i for i in issues if i["code"] == "import.item-unexpressed" and i["where"] == "pad-net-conflict"
    ]
    assert "J1.1" in row["message"]
    assert not [i for i in issues if i["code"] == "import.unequal"], issues


def test_open_pad_beside_a_netted_pad_compares_equal(tmp_path: Path) -> None:
    """Level 2 maps the labels of such a pad through the other pads' nets, so a board equals itself and a
    conversion that keeps both pads reports no ``net`` difference (the c0425 ``convert.unexplained``)."""
    source = with_open_pad(tmp_path)
    report = compare_designs(read_board(source).design, read_board(source).design, level=2)
    assert report.levels[1].differences == ()
