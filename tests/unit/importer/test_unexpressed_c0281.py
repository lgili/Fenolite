# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The outline width and the layer table are reported (capability board-to-code, "Outline width and layer
table reported"; change c0281, issues 4 and 5 of the board library's conversion report). The authored
two-sheet board with its outline drawn 0.2 mm wide and without ``Eco1.User`` and ``Eco2.User``."""

from __future__ import annotations

import re
from pathlib import Path

from _importcode import BOARD, imported


def variant(tmp: Path) -> Path:
    text = BOARD.read_text(encoding="utf-8")
    text = text.replace('\t\t(21 "Eco1.User" user "User.Eco1")\n', "").replace(
        '\t\t(23 "Eco2.User" user "User.Eco2")\n', ""
    )
    text, count = re.subn(
        r'\(width 0\.1\)(\s*\(type \w+\)\s*\)\s*\(layer "Edge\.Cuts"\))', r"(width 0.2)\1", text
    )
    assert count == 4
    folder = tmp / "wide"
    folder.mkdir()
    target = folder / "wide.kicad_pcb"
    target.write_text(text, encoding="utf-8")
    return target


def test_wide_outline_and_short_layer_table(tmp_path: Path) -> None:
    """Scenario "Wide outline and short layer table"."""
    source = variant(tmp_path)
    reply = imported(tmp_path, source, "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    rows = {row["kind"]: row for row in (reply.envelope or {})["result"]["unexpressed"]}
    assert rows["outline-width"]["count"] == 4
    assert rows["outline-width"]["examples"] == ["200000 nm instead of 100000 nm"]
    assert rows["layer-table"]["count"] == 2
    assert rows["layer-table"]["examples"] == ["the source lacks Eco1.User, Eco2.User"]
    refused = imported(tmp_path, source)
    assert refused.exit_code == 7
