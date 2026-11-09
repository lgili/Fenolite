# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The code imported from an Altium project builds the source drawing (change c0470, task 6.2; capability
import-python, "Altium import to Python keeps the source drawing", scenarios "Authored flat project" and
"Authored hierarchical project").

The source drawing is the one of the Altium extractor (design D1); the built drawing is read back from the
KiCad sheets the imported code builds, with their carriers. Level S finds no difference."""

from __future__ import annotations

from pathlib import Path

import pytest
from _drawings import BLINK, altium_drawing, hier_board

from fenolite.api import run
from fenolite.backends.kicad.drawn import refs_to_paths
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.convert import schematic as drawing_lib
from fenolite.importer.source import read_kicad

pytestmark = pytest.mark.long_flow

STAMP = "2026-11-07T00:00:00Z"


@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_imported_code_builds_the_source_drawing(name: str, tmp_path: Path) -> None:
    project = BLINK if name == "blink" else hier_board(tmp_path / "altium")
    imported = run(
        "import", str(project), "--to", "python", "--out", "code", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert imported.exit_code == 0, (imported.error, (imported.envelope or {}).get("issues"))
    assert 'design.load_schematic("schematic.toml"' in (tmp_path / "code" / "design.py").read_text()
    built = run("build", "code/design.py", "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP)
    assert built.exit_code == 0, (built.error, (built.envelope or {}).get("issues"))
    assert built.result["schematic"]["source"] == "drawn"
    folder = tmp_path / "built"
    files = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    circuit = read_kicad(next(folder.glob("*.kicad_pro"))).design.circuit
    back, pins, issues = drawing_lib.read_kicad_drawing(files, refs_to_paths(circuit))
    assert [i.message for i in issues if i.severity == "error"] == []
    source = altium_drawing(project)
    found = compare_drawn(source.drawn, back, pins_a=source.pins, pins_b=pins)
    assert found.differences == ()
    assert sum(len(sheet.sheet_refs) for sheet in back.sheets) == (0 if name == "blink" else 2)
