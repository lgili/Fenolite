# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A KiCad 9 project converted to KiCad 10 (capability design-conversion, "KiCad to KiCad direction",
scenario "Version 9 project to KiCad 10"; ``H-K-CONV-RETARGET``; change c0159).

On a 9.0.9 runner the sources (three committed ones, and the KiCad 9.0.9.1 demo boards of the corpus) give
the DRC violation types recorded in ``_convcases.SOURCE_TYPES_9``; on a 10.0.6 runner their conversions to
10 load and give the same types, and the same counts as the sources read by 10.0.6. No ERC runs: a
schematic of another major is not converted (change c0162), so a converted project of 10 holds none.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import _convcases
import _probes
import pytest

import fenolite.cli.main as cli_main

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("name", sorted(_convcases.RETARGETS))
def test_violation_types(name: str) -> None:
    if _probes.major() == 9:
        found = _convcases.source_types(name)
        print(f"{name} on {_probes.version()}: {found}")
        assert found == _convcases.SOURCE_TYPES_9[name]
        return
    converted = _convcases.converted_types(name)
    print(f"{name} converted, on {_probes.version()}: {converted}")
    assert _convcases.kinds(converted) == _convcases.kinds(_convcases.SOURCE_TYPES_9[name])
    assert converted == _convcases.source_types(name)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("name", sorted(_convcases.DEMO_RETARGETS))
def test_demo_projects(name: str) -> None:
    """The KiCad 9.0.9.1 demo boards of the corpus, with the project file of their stem where the corpus
    holds one: the same check as the committed sources."""
    test_violation_types(name)


@pytest.mark.kicad_min_major(10)
def test_version_9_project_to_kicad_10(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Version 9 project to KiCad 10": the command writes the project, the board's header is that
    of 10, and DRC in 10.0.6 gives the types of the source in 9.0.9."""
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    source = _convcases.RETARGETS["blink"]
    argv = ["--kicad-version", "10", "convert", str(source), "--to", "kicad", "--out", "out", "--confirm"]
    assert cli_main.main([*argv, "--json"]) == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    assert envelope["result"]["equivalence"]["equivalent"] is True
    board = tmp_path / "out" / "blink.kicad_pcb"
    assert "(version 20260206)" in board.read_text(encoding="utf-8").splitlines()[1]
    found = _convcases.drc_types(board, source)
    assert _convcases.kinds(found) == _convcases.kinds(_convcases.SOURCE_TYPES_9["blink"])


def test_probe() -> None:
    outcome = _probes.run("convert-retarget")
    print(f"convert-retarget: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"
