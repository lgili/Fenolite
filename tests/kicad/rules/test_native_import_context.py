# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native loading of byte-preserved authored imported DRU9/10 (c0359)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _rulebench as rb
import pytest
from _importcode import copy_project
from _resources import kicad_cli

from fenolite import api
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad

RULES = (
    b"(version 1)\n"
    b"# Fenolite-authored CC0 profile and native loading control.\n"
    b'(rule "Authored width" (layer outer) (condition "A.Type == \'track\' && B.Typ'
    b'e == A.Type") (constraint clearance (min 0.1mm)))\n'
    b'(rule "Authored text" (layer "?.Silkscreen") (condition "A.Type == \'Text\' |'
    b"| A.Type == 'Text Box'\") (constraint text_height (min 1mm)))\n"
    b'(rule "Authored fabrication" (condition "A.Type == \'pad\' && A.Fabrication_P'
    b"roperty == 'Castellated pad'\") (constraint hole_size (min 0.2mm)))\n"
    b'(rule "Authored plated nets" (condition "A.isPlated() && B.isPlated() && A.'
    b'Net != B.Net") (constraint hole_to_hole (min 0.2mm)))\n'
    b'(rule "Authored silk" (layer outer) (condition "A.Type == \'pad\' && B.Layer '
    b"== '?.Silkscreen'\") (constraint silk_clearance (min 0.1mm)))\n"
    b'(rule "Authored mechanical" (condition "!A.isPlated()") (constraint hole_si'
    b"ze (min 0.5mm)))\n"
)


def test_original_and_emitted_rules_really_load_with_native_canary(tmp_path: Path):
    executable = kicad_cli()
    assert executable is not None
    runner = KicadCli(executable)
    major = runner.major()
    assert major in (9, 10)
    source = copy_project(tmp_path, native_target=major)
    source.with_suffix(".kicad_dru").write_bytes(RULES)
    args = (
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "code",
        "--licence",
        "CC0-1.0",
        "--kicad-version",
        str(major),
    )
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    confirmed = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    args = ("build", "code/design.py", "--out", "built", "--kicad-version", str(major))
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    confirmed = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    generated_rules = next((tmp_path / "built").glob("*.kicad_dru"))
    assert generated_rules.read_bytes() == RULES
    native_boards = [source.with_suffix(".kicad_pcb"), next((tmp_path / "built").glob("*.kicad_pcb"))]
    canary = rb.builder().build()
    for board in native_boards:
        original = board.read_bytes()
        design = read_board(original.decode(), file=board.name)
        assert design.board is not None and canary.design.board is not None
        combined = dataclasses.replace(
            design,
            circuit=dataclasses.replace(
                design.circuit, nets=(*design.circuit.nets, *canary.design.circuit.nets)
            ),
            board=dataclasses.replace(
                design.board, tracks=(*design.board.tracks, *canary.design.board.tracks)
            ),
        )
        bench = rb.Bench(combined, canary.items)
        # Private authored canary copies only. The original/source outputs stay byte-identical.
        baseline = rb.drc(
            runner, bench, RULES.decode(), major, project=board.with_suffix(".kicad_pro").read_text()
        )
        assert baseline is not None and not rb.canary_fired(baseline, bench)
        loaded = rb.drc(
            runner,
            bench,
            RULES.decode() + "\n" + rb.canary_rule(),
            major,
            project=board.with_suffix(".kicad_pro").read_text(),
        )
        rb.require_canary(loaded, bench)
        assert board.read_bytes() == original
