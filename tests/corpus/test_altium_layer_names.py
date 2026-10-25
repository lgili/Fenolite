# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native layer names and pad openings of the public Altium boards (capability altium-board-view, scenario
"Public boards"; change c0181).

The boards of S-0174 (``-pcbdoc-05``) and S-0187 (``-pcbdoc-08``, a heavy row) are read from the corpus
cache; only counts are kept.
"""

from __future__ import annotations

import pytest
from _corpus import manifest_items, require

from fenolite.cli.cmd_view import scene_of

pytestmark = pytest.mark.needs_corpus
BOARDS = {item.id: item for item in manifest_items("rta") if "-pcbdoc-" in item.id}
MANUAL = {"altium-third-party-pcbdoc-05": (0, 32), "altium-third-party-pcbdoc-08": (950, 365)}
"""Pads whose solder-mask, and whose paste, expansion is manual (census of 2026-10-25, change c0181)."""


@pytest.mark.parametrize("row", sorted(MANUAL))
def test_public_board(row: str) -> None:
    scene = scene_of(require(BOARDS[row]))
    for layer in scene["layers"]:
        if layer["kind"] != "view":
            assert layer["name"] != layer["id"], layer["id"]
            assert "tab" in layer, layer["id"]
    pads = scene["pads"]
    assert all("mask_src" in pad and "paste_src" in pad for pad in pads)
    manual = (sum(p["mask_src"] == "manual" for p in pads), sum(p["paste_src"] == "manual" for p in pads))
    assert manual == MANUAL[row]
