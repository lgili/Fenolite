# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Imported empty values stay empty (capability import-python, "Imported empty values stay empty"; change
c0364). The authored two-sheet board with the value of one resistor cleared."""

from __future__ import annotations

from pathlib import Path

from _importcode import BOARD, imported


def test_empty_value_is_emitted_and_rebuilt(tmp_path: Path) -> None:
    text = BOARD.read_text(encoding="utf-8")
    assert '(property "Value" "1k"' in text
    folder = tmp_path / "cleared"
    folder.mkdir()
    board = folder / "cleared.kicad_pcb"
    board.write_text(text.replace('(property "Value" "1k"', '(property "Value" ""', 1), encoding="utf-8")
    dry = imported(tmp_path, board)
    assert dry.exit_code == 0, dry.error
    assert not [i for i in (dry.envelope or {})["issues"] if i["code"] == "import.unequal"]
    assert dry.result["equivalence"]["equivalent"] is True
    reply = imported(tmp_path, board, "--confirm", "--plan", dry.result["plan_id"])
    assert reply.exit_code == 0, reply.error
    code = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "out").rglob("*.py"))
    assert 'value=""' in code
