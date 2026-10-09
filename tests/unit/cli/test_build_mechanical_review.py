# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored mechanical build regressions from the c0096 review.

Holes and keep-outs of a script are declared with ``hole()`` (c0102) and ``rule_area()`` (c0103), the
maintainer's decision 2 of 2026-10-07; what c0096 adds to a build is the locked anchor's intent, which is
conversion metadata only."""

from pathlib import Path

import pytest
from _checkcli import run


def _anchor_script() -> str:
    return (
        "from fenolite.dsl import Design, Part, MechanicalIntent\n"
        'design = Design("mechanical")\n'
        'design.board("20mm", "20mm")\n'
        'part = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603")\n'
        "design.add(part)\n"
        'part.place("10mm", "10mm", locked=True, anchor=MechanicalIntent("fixed"))\n'
        'design.rule_area("area", [("1mm", "1mm"), ("3mm", "1mm"), ("3mm", "3mm")], forbid=("pads",))\n'
    )


@pytest.mark.parametrize("target", ["kicad", "altium"])
def test_intent_metadata_is_conversion_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str
) -> None:
    import json

    import fenolite.cli.cmd_build as command

    original = command.build_design
    outputs = []

    def observe(*args, **kwargs):
        built = original(*args, **kwargs)
        outputs.append(built)
        return built

    monkeypatch.setattr(command, "build_design", observe)
    script = tmp_path / "design.py"
    script.write_text(_anchor_script(), encoding="utf-8")
    args = ("build", str(script), "--out", "out", "--target", target, "--confirm")
    for _ in range(2):
        code, reply, error, _ = run(monkeypatch, tmp_path, *args)
        assert code == 0, (reply, error)
        cached = json.loads((tmp_path / "out" / ".fenolite" / "board.json").read_text(encoding="utf-8"))
        assert all("intent" not in area for area in cached.get("keepouts", []))
        assert all("anchor" not in part for part in cached.get("footprints", []))
    for built in outputs:
        assert all(part.anchor is None for part in built.design.board.footprints)
        assert all(area.intent is None for area in built.design.board.keepouts)
