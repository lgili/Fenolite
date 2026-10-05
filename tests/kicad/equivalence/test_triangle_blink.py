# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The equivalence triangle on the committed PCB document (capability design-equivalence, "Triangle
oracle" and "Triangle evidence over the corpus"; change c0045; ``H-G-EQ-L1`` to ``H-G-EQ-L4``,
``H-G-EQ-ROT``, ``H-G-EQ-SHIFT``).

``tests/data/altium/blink/blink.PcbDoc`` is written by Fenolite from its authored CC0 library, so this
test needs no corpus. It is read by Fenolite's Altium backend and converted by ``kicad-cli pcb import``
(a subprocess, on a copy). The counts are recorded in ``docs/evidence/equivalence-triangle.md``."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _triangle import counts_line, measure, profile_for, report, sides

import fenolite.cli.main as cli_main

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
PCBDOC = Path(__file__).resolve().parents[2] / "data" / "altium" / "blink" / "blink.PcbDoc"


def test_levels(capsys: pytest.CaptureFixture[str]) -> None:
    found = sides(PCBDOC)
    result = report(found)
    with capsys.disabled():
        print("\n" + counts_line("blink", result))
    assert [level.compared for level in result.levels] == [3, 36, 36, 3]
    assert result.differences == () and result.excluded == () and result.equivalent
    assert result.frame == "relative" and result.translation != (0, 0)
    refs = {c.ref: c for c in found.b.circuit.components}
    assert sorted(refs) == ["D1", "R1", "U1"]


def test_measured_differences(capsys: pytest.CaptureFixture[str]) -> None:
    """The document holds lengths in units of 2.54 nm and KiCad in steps of 10 nm: nothing differs by
    more than the profile's tolerance, and no angle differs (``D1`` is on the bottom side)."""
    found = sides(PCBDOC)
    got = measure(found)
    with capsys.disabled():
        print(f"\nblink: {got}")
    assert (got.footprints, got.bottom) == (3, 1)
    assert got.length <= profile_for(found.version).tolerance_nm
    assert (got.rotation, got.pad_rotation) == (0, 0)
    bare = report(found, rules=False)
    assert bare.differences == ()


def test_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["equivalent", str(PCBDOC), "--against", "kicad-import", "--json"])
    envelope = json.loads(out.getvalue())
    result = envelope["result"]
    assert code == 0, err.getvalue()
    assert (result["equivalent"], result["level"], result["frame"]) == (True, 4, "relative")
    assert result["profile"]["name"] == "kicad-import"
    assert envelope["evidence"]["oracle"] == "kicad-cli"
    assert result["sides"]["b"]["backend"] == "kicad-import"
    assert result["sides"]["b"]["tool_version"].startswith("10.")
    assert {i["code"] for i in envelope["issues"] if i["code"].startswith("equiv.")} <= {
        "equiv.import-message"
    }
    assert list(tmp_path.iterdir()) == []
