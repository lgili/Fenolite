# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``net`` reads a board of any ``BoardFrame`` backend (capability cli, "Net command"; change c0495, (b))."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run

DATA = Path(__file__).resolve().parents[2] / "data"


def test_an_altium_pcb_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "An Altium PCB document"."""
    code, envelope, _, _ = run(monkeypatch, DATA / "altium" / "routed", "net", "routed.PcbDoc")
    assert code == 0
    assert envelope["input"]["kind"] == "pcbdoc" and envelope["input"]["path"] == "routed.PcbDoc"
    names = [row["name"] for row in envelope["result"]["nets"]]
    assert "GND" in names and names == sorted(names)


def test_a_file_no_backend_reads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The error names the file without its folder and lists the suffixes that are read."""
    (tmp_path / "notes.txt").write_text("not a board", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "net", str(tmp_path / "notes.txt"))
    assert code == 2 and error["code"] == "FEN-2001"
    assert error["message"] == "notes.txt is not a board Fenolite reads"
    assert ".kicad_pcb" in error["hint"] and ".PcbDoc" in error["hint"]
    assert str(tmp_path) not in error["message"] + error["hint"] + error["where"]
