# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Test-point placement (capability assembly-test-features, "Test-point placement" and "Placed test
points"; change c0229). Hermetic: the boards are the authored benches of ``tests/_tpbench.py``, and no
tool runs (``tests/kicad/assembly/test_testpoint_place_oracle.py`` runs KiCad's DRC)."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _tpbench import MM, blocked, covered

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.checks.copper import check_copper
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.exports.codes import ISSUE_CODES
from fenolite.exports.testpoint_place import sites
from fenolite.model.design import Design


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _write(folder: Path, design: Design, name: str = "probes") -> Path:
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    return board


def run(
    monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(folder)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["testpoints", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def _copper_findings(design: Design) -> int:
    backend = KicadBackend()
    return len(check_copper(design, pads=backend.board_pads(design), min_clearance=200_000).findings)


def test_cover_every_net(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Coverage raised to every net": six nets from 0 to 6 covered from the bottom."""
    board = _write(tmp_path, covered())
    before = read_board(board.read_text(encoding="utf-8"))
    code, env, err = run(monkeypatch, tmp_path, board.name, "--place", "--side", "bottom", "--confirm")
    assert code == 0, err
    place = env["result"]["place"]
    assert place["before"] == {"eligible": 6, "covered": 0}
    assert place["after"] == {"eligible": 6, "covered": 6}
    assert [p["ref"] for p in place["probes"]] == [f"TP{n}" for n in range(1, 7)]
    assert env["result"]["coverage"]["covered"] == 6 and place["unplaced"] == []
    assert [found["code"] for found in env["issues"]] == ["testpoint.board-only"]
    assert env["evidence"]["level"] == "INFERRED" and "H-K-TP-PLACE" in env["evidence"]["hypotheses"]
    written = read_board(board.read_text(encoding="utf-8"))
    assert written.board is not None and before.board is not None
    assert len(written.board.footprints) == len(before.board.footprints) + 6
    assert len(written.board.tracks) == 6
    probes = [fp for fp in written.board.footprints if fp.lib_ref.startswith("Fenolite_Assembly:TestPoint")]
    assert {fp.side for fp in probes} == {"bottom"}
    assert all("fenolite.path" not in str(fp.ext) for fp in probes)
    # no copper finding is added, and the probes keep the pitch and a grid site
    assert _copper_findings(written) == _copper_findings(before)
    at = [Point(*p["position"]) for p in place["probes"]]
    assert all(p.x % 2_540_000 == 0 and p.y % 2_540_000 == 0 for p in at)
    assert all(
        (a.x - b.x) ** 2 + (a.y - b.y) ** 2 >= 1_270_000**2 for i, a in enumerate(at) for b in at[i + 1 :]
    )
    # a second run has nothing left to place and writes nothing
    code, env, err = run(monkeypatch, tmp_path, board.name, "--place", "--side", "bottom", "--dry-run")
    assert code == 0, err
    assert env["result"]["place"]["probes"] == [] and env["result"]["place"]["before"]["covered"] == 6


def test_no_site_names_the_body(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A net without room": the net under a part's courtyard stays uncovered."""
    board = _write(tmp_path, blocked())
    code, env, err = run(monkeypatch, tmp_path, board.name, "--place", "--side", "bottom", "--dry-run")
    assert code == 0, err
    place = env["result"]["place"]
    assert place["after"] == {"eligible": 7, "covered": 6}
    assert place["unplaced"] == [
        {"net": "HIDDEN", "site": [25_400_000, 45_720_000], "blocker": "the courtyard of U1"}
    ]
    found = [f for f in env["issues"] if f["code"] == "testpoint.no-site"]
    assert len(found) == 1 and found[0]["where"] == "HIDDEN" and "U1" in found[0]["message"]
    assert env["result"]["coverage"]["uncovered"] == ["HIDDEN"]


def test_nets_glob_and_top_side(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _write(tmp_path, covered())
    code, env, err = run(
        monkeypatch, tmp_path, board.name, "--place", "--side", "top", "--nets", "N1*", "--dry-run"
    )
    assert code == 0, err
    assert [p["net"] for p in env["result"]["place"]["probes"]] == ["N1A", "N1B"]
    assert env["result"]["place"]["after"]["covered"] == 2


@pytest.mark.parametrize(
    ("args", "where"),
    [
        (("--place",), "--side"),
        (("--grid", "1mm"), "--grid"),
        (("--drc",), "--drc"),
        (("--place", "--side", "top", "--reach", "0mm"), "--reach"),
    ],
)
def test_refusals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...], where: str) -> None:
    board = _write(tmp_path, covered())
    code, _, err = run(monkeypatch, tmp_path, board.name, *args)
    assert code == 2 and err["code"] == "FEN-2001" and where in err["message"]


def test_sites_nearest_first() -> None:
    found = sites([Point(1 * MM, 1 * MM)], 1 * MM, 1 * MM)
    assert [site for _, site, _ in found] == [
        Point(1 * MM, 1 * MM),
        Point(1 * MM, 0),
        Point(0, 1 * MM),
        Point(2 * MM, 1 * MM),
        Point(1 * MM, 2 * MM),
    ]


def test_codes_registered() -> None:
    assert ISSUE_CODES["testpoint.no-site"] == "warning"
    assert ISSUE_CODES["testpoint.check-failed"] == "warning"
    assert ISSUE_CODES["testpoint.drc-new"] == "error"
    assert ISSUE_CODES["testpoint.board-only"] == "info"


def test_rebuild_keeps_the_probes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A rebuild keeps the probes": board-only footprints and their tracks stay."""
    from _buildhelp import blink
    from _preserve_help import fresh, rebuild

    output = fresh()
    for name, data in output.files.items():
        if "/" not in name:
            (tmp_path / name).write_bytes(data)
    code, env, err = run(monkeypatch, tmp_path, "blink.kicad_pcb", "--place", "--side", "top", "--confirm")
    assert code == 0, err
    probes = {p["ref"]: p for p in env["result"]["place"]["probes"]}
    assert probes
    placed = (tmp_path / "blink.kicad_pcb").read_text(encoding="utf-8")
    again = rebuild(blink(), placed)
    assert any(found.code == "layout.board-only" for found in again.issues)
    design = read_board(again.files["blink.kicad_pcb"].decode("utf-8"))
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    kept = {refs.get(fp.component_id) for fp in design.board.footprints}
    assert set(probes) <= kept
    ends = {(t.start.x, t.start.y) for t in design.board.tracks}
    assert all(tuple(p["position"]) in ends for p in probes.values() if p["track_length"])
