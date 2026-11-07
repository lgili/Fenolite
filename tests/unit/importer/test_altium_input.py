# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium inputs of an import (capability board-to-code, "Altium inputs of an import"; change c0275): the
document Fenolite writes for the blink is read by Fenolite's Altium reader, converted in memory and emitted
by the one emitter; the code builds for KiCad to a board equal to the Altium source."""

from __future__ import annotations

from pathlib import Path

from _importcode import ROOT, STAMP, imported

from fenolite.api import equivalent, run


def test_fenolite_written_altium_document(tmp_path: Path) -> None:
    script = ROOT / "examples" / "blink_2layer" / "design.py"
    made = run(
        "build", str(script), "--target", "altium", "--out", "alt", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert made.exit_code == 0, made.error
    reply = imported(tmp_path, tmp_path / "alt" / "blink.PrjPcb", "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["source"]["backend"] == "altium" and reply.result["unexpressed"] == []
    assert reply.result["equivalence"] == {"levels": [1, 2, 3, 4], "equivalent": True}
    inputs = [
        row["file"]
        for row in __import__("json").loads((tmp_path / "out" / "PROVENANCE.json").read_text())["inputs"]
    ]
    assert "blink.PcbDoc" in inputs and "blink.PrjPcb" in inputs
    codes = {i["code"] for i in (reply.envelope or {})["issues"]}
    assert "import.symbol-regenerated" in codes
    built = run("build", "design.py", "--out", "built", "--confirm", cwd=tmp_path / "out", timestamp=STAMP)
    assert built.exit_code == 0, built.error
    result = equivalent(
        tmp_path / "alt" / "blink.PcbDoc", tmp_path / "out" / "built" / "blink.kicad_pcb", level=4
    )
    assert result.equivalent, result.to_json()


def test_adopt_refused_for_altium(tmp_path: Path) -> None:
    (tmp_path / "board.PcbDoc").write_bytes(b"")
    reply = imported(tmp_path, tmp_path / "board.PcbDoc", "--adopt")
    assert reply.exit_code == 2
    assert reply.error is not None and reply.error["code"] == "FEN-2001"
