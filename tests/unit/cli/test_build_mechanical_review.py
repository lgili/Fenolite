# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored mechanical build regressions from the c0096 review."""

from pathlib import Path

import pytest
from _checkcli import run


@pytest.mark.parametrize("target", ["kicad", "altium"])
def test_board_hole_build_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str) -> None:
    script = tmp_path / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Part\n"
        'design = Design("mechanical")\n'
        'design.board("20mm", "20mm")\n'
        'part = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603")\n'
        "design.add(part)\n"
        'part.place("10mm", "10mm")\n'
        'design.hole("mount", "5mm", "5mm", "2mm")\n',
        encoding="utf-8",
    )
    code, reply, error, _ = run(
        monkeypatch,
        tmp_path,
        "build",
        str(script),
        "--out",
        "out",
        "--target",
        target,
        "--dry-run" if target == "kicad" else "--confirm",
    )
    if target == "kicad":
        assert code == 3, (reply, error)
        assert error["code"] == "FEN-3004"
        assert "mount" in error["message"] and "footprint" in error["message"]
        assert error["where"] == str(script)
        assert not (tmp_path / "out").exists()
    else:
        assert code == 0, (reply, error)
        assert (tmp_path / "out" / "mechanical.PcbDoc").is_file()
        from fenolite.backends.altium.backend import AltiumBackend

        imported = AltiumBackend().read(tmp_path / "out" / "mechanical.PcbDoc")
        assert imported.design is not None and imported.design.board is not None
        drills = [
            pad
            for footprint in imported.design.board.footprints
            for pad in footprint.pads
            if pad.kind == "np_thru_hole"
        ]
        assert len(drills) == 1 and drills[0].net_id is None
        assert abs(drills[0].drill - 2_000_000) <= 5


def _keepout_script(x: int = 1, *, extra: bool = False) -> str:
    text = (
        "from fenolite.dsl import Design, Part, MechanicalIntent\n"
        'design = Design("mechanical")\n'
        'design.board("20mm", "20mm")\n'
        'part = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603")\n'
        "design.add(part)\n"
        'part.place("10mm", "10mm", locked=True, anchor=MechanicalIntent("fixed"))\n'
        f'design.keepout("area", [("{x}mm", "1mm"), ("{x + 2}mm", "1mm"), '
        f'("{x + 2}mm", "3mm")], no_pads=True, source="authored", status="measured")\n'
    )
    if extra:
        text += 'design.keepout("added", [("1mm", "5mm"), ("3mm", "5mm"), ("3mm", "7mm")], no_tracks=True)\n'
    return text


def test_rebuild_keeps_board_keepouts_without_merge_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fenolite.backends.kicad.pcb import read_board

    script = tmp_path / "design.py"
    script.write_text(_keepout_script(), encoding="utf-8")
    args = ("build", str(script), "--out", "out", "--confirm")
    code, reply, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, (reply, error)
    path = tmp_path / "out" / "mechanical.kicad_pcb"
    first = read_board(path).board.keepouts
    assert len(first) == 1
    script.write_text(_keepout_script(5, extra=True), encoding="utf-8")
    code, reply, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, (reply, error)
    assert read_board(path).board.keepouts == first
    assert not any(issue["code"] == "layout.keepouts-kept" for issue in reply["issues"])


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
    script.write_text(_keepout_script(), encoding="utf-8")
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
