# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-outs and placement marks on the public Altium boards (capability board-annotations-view, change
c0183). Counts only; the boards are read from the corpus cache."""

from __future__ import annotations

import re

import pytest
from _corpus import manifest_items, require

from fenolite.cli.cmd_view import scene_of
from fenolite.view.scene import CHECKS

pytestmark = pytest.mark.needs_corpus
BOARDS = {item.id: item for item in manifest_items("rta") if "-pcbdoc-" in item.id}
EXPECTED = {
    "altium-third-party-pcbdoc-01": (0, 5),
    "altium-third-party-pcbdoc-02": (0, 0),
    "altium-third-party-pcbdoc-03": (0, 0),
    "altium-third-party-pcbdoc-04": (1, 1),
    "altium-third-party-pcbdoc-05": (0, 0),
    "altium-third-party-pcbdoc-06": (2, 0),
    "altium-third-party-pcbdoc-07": (0, 0),
    "altium-third-party-pcbdoc-08": (0, 4),
}
"""Per board: the hatched regions of the Keep-Out Layer (free cut-outs are the outline's), and the overlaps of
pad-made extents the notes count (census of 2026-10-25)."""


@pytest.mark.parametrize("row", sorted(EXPECTED))
def test_public_board(row: str) -> None:
    scene = scene_of(require(BOARDS[row]))
    hatched = sum(1 for p in scene["prims"] if p[1] == "h" and p[0] == "Altium.KeepOut")
    noted = [int(m.group(1)) for n in scene["meta"]["notes"] if (m := re.match(r"(\d+) overlap", n))]
    assert (hatched, sum(noted)) == EXPECTED[row]
    assert not [p for p in scene["prims"] if p[0] == CHECKS]  # no Altium courtyard is exact here
