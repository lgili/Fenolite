# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mixed outline widths remain reported while supported short tables are explicit (c0281/c0324).

The authored CC0 two-sheet board is varied in tmp_path; no corpus data is used.
"""

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
    text = text.replace(
        '(width 0.2)\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "Edge.Cuts")',
        '(width 0.3)\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "Edge.Cuts")',
        1,
    )
    folder = tmp / "wide"
    folder.mkdir()
    target = folder / "wide.kicad_pcb"
    target.write_text(text, encoding="utf-8")
    return target


def test_mixed_outline_widths_and_short_layer_table(tmp_path: Path) -> None:
    """Scenario "Mixed outline widths and short layer table"."""
    source = variant(tmp_path)
    reply = imported(tmp_path, source, "--allow-lossy", "--confirm", out="lossy")
    assert reply.exit_code == 0, reply.error
    rows = {row["kind"]: row for row in (reply.envelope or {})["result"]["unexpressed"]}
    assert rows["outline-width"]["count"] == 4
    assert rows["outline-width"]["examples"] == [
        "200000 nm instead of 100000 nm",
        "300000 nm instead of 100000 nm",
    ]
    assert set(rows) == {"outline-width"}
    assert "technical_layers=" in (tmp_path / "lossy/design.py").read_text(encoding="utf-8")
    refused = imported(tmp_path, source)
    assert refused.exit_code == 7
