# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad 10.0.6 demo projects of format 10 converted for KiCad 9 (change c0162, ``H-K-DOWN-DEMOS``;
capability design-conversion, "KiCad downgrade direction", scenario "Demo project for KiCad 9").

Run once per pinned image with the corpus cached. On 10.0.6 each source project gives the DRC and ERC
violation types of ``_downbench.DEMO_TYPES`` and the board its conversion writes, re-saved by 10.0.6,
equals the source at level 5; on 9.0.9 the converted project loads and gives the same types. The design
rows the report names (the component classes and tuning profiles every KiCad 10 project holds, and no
construct that DRC or ERC reads) change no violation type.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import _downbench
import _probes
import pytest

import fenolite.cli.main as cli_main

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]


@pytest.mark.parametrize("name", sorted(_downbench.DEMOS))
def test_demo_project(name: str) -> None:
    outcome = _probes.run(f"down-demo-{name}")
    print(f"down-demo-{name}: {outcome} on {_probes.version()}")
    assert outcome == "equal"


def test_probe() -> None:
    outcome = _probes.run("down-demos")
    print(f"down-demos: {outcome} on {_probes.version()}")
    assert outcome == "equal"


def test_demo_project_for_kicad_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Demo project for KiCad 9": the command converts ``pic_programmer`` with consent to its
    losses, exits 0, and the written board loads in the running ``kicad-cli``."""
    folder = _downbench.demo_folder(tmp_path / "source", "pic_programmer")
    if folder is None:
        pytest.skip("the demo project is not cached")
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    argv = ["--kicad-version", "9", "--allow-lossy", "convert", str(folder), "--to", "kicad", "--out", "out"]
    assert cli_main.main([*argv, "--confirm", "--json"]) == 0, err.getvalue()
    envelope = json.loads(out.getvalue())
    rows = {row["kind"]: row for row in envelope["result"]["report"]["rows"]}
    assert (
        rows["downgrade:footprint-units"]["lost"] == 63
        and rows["downgrade:footprint-units"]["loss"] == "report"
    )
    assert rows["downgrade:tenting-front"]["changed"] == 1
    assert envelope["result"]["equivalence"]["unexplained"] == 0
    board = tmp_path / "out" / "pic_programmer.kicad_pcb"
    assert "(version 20241229)" in board.read_text(encoding="utf-8").splitlines()[1]
    assert _probes.runner().drc(board).report is not None
