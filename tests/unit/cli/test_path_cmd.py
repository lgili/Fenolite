# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite path`` (change c0501, requirement "Path command"): a return trace written into an authored
Altium document through an edit session, the opt-in it needs, and a channel on the authored KiCad board."""

from __future__ import annotations

import contextlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _route_benches import return_trace

from fenolite.api.board import read_board
from fenolite.cli import main as cli_main
from fenolite.geometry import Thick, thick_gap_floor

EXAMPLE = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _cli(*args: str) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


@pytest.fixture
def bench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return return_trace(tmp_path)


def _copper(document: Path) -> Counter[str]:
    code, envelope, _ = _cli("check", str(document), "--stages", "copper.clearance")
    assert code in (0, 5), envelope
    return Counter(i["code"] for i in envelope["issues"] if i["code"].startswith("copper."))


ARGS = ("--net", "GND", "--from", "C1-2", "--to", "C2-2", "--width", "0.5mm", "--grid", "0.25mm")


def test_route_a_return_trace_on_an_altium_document_written(bench: Path) -> None:
    """Scenario "Route a return trace on an Altium document", and task 5.2: the written document reads back
    with the found tracks, and the copper check finds nothing new."""
    before = bench.read_bytes()
    code, envelope, err = _cli("path", str(bench), *ARGS, "--gate", "clone", "--dry-run")
    assert code == 0, (envelope, err)
    result = envelope["result"]
    runs = result["path"]["runs"]
    assert runs and result["refusal"] is None and bench.read_bytes() == before
    assert any(i["code"] == "route.altium-edit-unconfirmed" for i in envelope["issues"])
    xs = [x for run in runs for x, _ in run["points"]]
    pads = {f"{p.ref}-{p.number}": p for p in read_board(bench).pads or ()}
    keepout_x = pads["C1-2"].position.x + 3_800_001  # the band from x = 10 to 11 mm of the script
    assert min(xs) < keepout_x < max(xs)
    for run in runs:
        for p, q in zip(run["points"], run["points"][1:], strict=False):
            segment = Thick(tuple(_point(v) for v in (p, q)), 500_000)
            for name in ("R1-1", "R1-2", "C1-1", "C2-1"):
                for copper in pads[name].copper:
                    shape = Thick(copper.core, copper.width, copper.filled)
                    assert thick_gap_floor(segment, shape) >= 200_000
    plan = envelope["result"]["plan_id"]
    assert [row["path"] for row in envelope["result"]["plan"]] == [f"built/{bench.name}"]
    code, written, err = _cli("path", str(bench), *ARGS, "--gate", "clone", "--confirm", "--plan", plan)
    assert code == 0, (written, err)
    assert written["receipt"]["written"][0]["path"].endswith("bench.PcbDoc")
    after = read_board(bench).design
    assert after.board is not None
    tracks = sum(len(run["points"]) - 1 for run in runs)
    assert len(after.board.tracks) >= tracks + 1 and bench.read_bytes() != before
    source = bench.with_name("source.PcbDoc")
    source.write_bytes(before)
    assert _copper(bench) - _copper(source) == Counter()


def _point(value: list[int]) -> Any:
    from fenolite.core.coords import Point

    return Point(value[0], value[1])


def test_a_pcbdoc_write_without_the_opt_in(bench: Path) -> None:
    """Scenario "A PcbDoc write without the opt-in"."""
    code, _, err = _cli("path", str(bench), *ARGS, "--dry-run")
    assert code == 2 and "--gate clone" in json.loads(err.strip().splitlines()[-1])["hint"]


def test_a_channel_on_the_kicad_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A channel"."""
    monkeypatch.chdir(tmp_path)
    args = ("--net", "GND", "--from", "D1-1", "--to", "30,15@F.Cu", "--widest", "--grid", "0.5mm")
    code, envelope, err = _cli("path", str(EXAMPLE), *args, "--resolution", "0.5mm", "--max-states", "3000")
    assert code == 0, (envelope, err)
    channel = envelope["result"]["channel"]
    assert channel["low"] is not None and channel["low"] <= channel["high"]
    assert "plan" not in envelope["result"] and envelope["receipt"] is None


def test_an_unknown_pad_names_the_closest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = _cli("path", str(EXAMPLE), "--net", "GND", "--from", "D1-9", "--to", "D1-1", "--widest")
    assert code == 2 and "D1-1" in json.loads(err.strip().splitlines()[-1])["hint"]
