# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference boards of the net roles on ``kicad-cli`` (change c0222, task 3.3): each variant is built for
the running KiCad major. KiCad 10 fills it (``fenolite fill``): the ``good`` variants pass KiCad's DRC with
no violation, and on every variant the role findings and loop areas on KiCad's fill equal those on the fill
that the unit tests give a zone (``fill_as_outline`` of ``tests/unit/roles/_boards.py``), within 0.01 mm² per
loop. ``kicad-cli`` 9 refills no zone (``FEN-6002``): there the ``good`` variants pass DRC on the unit
tests' fill, which shows that fill clear of every other net by its clearance.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

import pytest
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "unit" / "roles"))
from _boards import BOARDS, EXAMPLES, VARIANTS, Built, fill_as_outline, read  # noqa: E402

from fenolite.model.canonical import load_dir  # noqa: E402
from fenolite.roles.judge import Judged, run, split_roles  # noqa: E402

pytestmark = pytest.mark.needs_kicad
CASES = [(board, variant) for board in BOARDS for variant in VARIANTS]
TOLERANCE_NM2 = 10_000_000_000
"""0.01 mm² in square nanometres."""


def _fenolite(*args: str) -> tuple[int, dict[str, object]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {"stderr": stderr.getvalue()}


def _build(board: str, variant: str, out: Path) -> Built:
    major = kicad_cli_major()
    assert major is not None
    script = EXAMPLES / board / f"{variant}.py"
    code, envelope = _fenolite(
        "build", str(script), "--out", str(out), "--kicad-version", str(major), "--confirm"
    )
    assert code == 0, envelope
    return Built(out, out / f"{board}_{variant}.kicad_pcb")


def _judge(built: Built) -> Judged:
    design, pads = read(built)
    model = load_dir(built.out / ".fenolite")
    declared, confirmed = split_roles(model.rules.roles if model.rules is not None else None)
    return run(design, pads, circuit=model.circuit, stored=confirmed, declared=declared)


def _loops(judged: Judged) -> dict[str, int]:
    return {m.subject: int(m.values["area_nm2"]) for m in judged.measured.measures if m.kind == "loop"}


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_reference_board_on_kicad(tmp_path: Path, board: str, variant: str) -> None:
    cli = kicad_cli()
    assert cli is not None
    built = _build(board, variant, tmp_path / "kicad")
    emulated = tmp_path / "emulated"
    shutil.copytree(built.out, emulated)
    board_file = emulated / built.board.name
    board_file.write_text(fill_as_outline(board_file.read_text(encoding="utf-8")), encoding="utf-8")

    major = kicad_cli_major()
    assert major is not None
    checked = built if major >= 10 else Built(emulated, board_file)
    if major >= 10:
        code, envelope = _fenolite("fill", str(built.out), "--kicad-cli", cli, "--confirm")
        assert code == 0, envelope
    code, envelope = _fenolite("check", str(checked.out), "--stages", "drc.kicad", "--kicad-cli", cli)
    issues = envelope.get("issues", [])
    assert isinstance(issues, list)
    if variant == "good":
        assert code == 0, issues
        assert [i for i in issues if i["severity"] in ("warning", "error")] == []
    if major < 10:
        return

    on_kicad, on_outline = _judge(built), _judge(Built(emulated, board_file))
    assert sorted((i.code, i.where) for i in on_kicad.issues) == sorted(
        (i.code, i.where) for i in on_outline.issues
    )
    kicad_loops, outline_loops = _loops(on_kicad), _loops(on_outline)
    assert kicad_loops.keys() == outline_loops.keys()
    for name, area in kicad_loops.items():
        assert abs(area - outline_loops[name]) < TOLERANCE_NM2, (name, area, outline_loops[name])
