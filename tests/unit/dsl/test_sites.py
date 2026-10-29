# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""User creation locations survive sibling helpers; prompt objects have no records."""

from pathlib import Path

from fenolite.cli._script import run_design_script
from fenolite.dsl import Net
from fenolite.dsl._sites import recording


def test_sibling_sites_and_outside_scope(tmp_path: Path):
    (tmp_path / "parts.py").write_text(
        'from fenolite.dsl import Part\ndef make():\n    return Part("R5", "Fenolite:Resistor")\n'
    )
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Net\n"
        "from parts import make\n"
        'design = Design("sites")\n'
        "r = make()\n"
        'spare = Net("SPARE")\n'
    )
    run = run_design_script(script)
    assert [(s.name, s.where) for s in run.unattached] == [
        ("SPARE", "design.py:line:5"),
        ("R5", "parts.py:line:3"),
    ]
    Net("OUTSIDE")
    with recording(tmp_path) as recorder:
        Net("OTHER_FOLDER")
    assert recorder.records == []


def test_sites_weak_records_and_context_reset(tmp_path: Path):
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Net\n"
        'design = Design("sites")\n'
        'Net("COLLECTED")\n'
        'attached = Net("KEPT")\n'
        "design.add(attached)\n"
    )
    assert not run_design_script(script).unattached
