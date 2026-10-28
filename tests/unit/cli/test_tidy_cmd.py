# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite tidy`` (changes c0208 and c0214; capability copper-tidy, "Tidy command" and "Tidy report
option"), on the bench of ``tests/_tidybench.py`` written as a KiCad board. Hermetic: ``--drc`` runs
against a fake tool."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _groundties import _box, _p, _zone
from _projects import tree_snapshot
from _tidybench import acute, bench, staircase

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import CliRun, DrcRun
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import cmd_tidy
from fenolite.cli._examples import EXAMPLE_TIDY
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.tidy import TidyResult


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _write(tmp_path: Path, design: Design) -> Path:
    """The board, and beside it a project with the bench's 0.3 mm clearance unless one is there."""
    board = tmp_path / "tidy.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    project = board.with_suffix(".kicad_pro")
    if not project.exists():
        text = synthesize_project(design, target=10, board_name="tidy")
        project.write_text(text, encoding="utf-8", newline="\n")
    return board


def tidy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str, design: Design | None = None
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    board = _write(tmp_path, design if design is not None else bench())
    code, env, err, _ = run(monkeypatch, tmp_path, "tidy", board.name, *args)
    return code, env, err


def _tracks(path: Path) -> list[Track]:
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    assert design.board is not None
    return list(design.board.tracks)


def test_the_example_board_is_the_bench() -> None:
    """``EXAMPLE_TIDY`` is ``bench()`` as ``write_board`` writes it for KiCad 10."""
    assert Path(EXAMPLE_TIDY).read_text(encoding="utf-8") == write_board(bench(), target=10).text


def test_dry_run_of_the_three_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Dry run of the steps": the L of ``SIG`` is straightened, the T-joint of ``BUS``
    gets its 45° entry."""
    code, env, err = tidy(monkeypatch, tmp_path, "--dry-run")
    before = tree_snapshot(tmp_path)
    assert code == 0, err
    result = env["result"]
    assert [entry["path"] for entry in result["plan"]] == ["tidy.kicad_pcb"]
    assert result["steps"] == ["prune", "straighten", "chamfer"] and result["changed"] is True
    assert [(edit["step"], edit["reason"]) for edit in result["edits"]] == [
        ("prune", "free-end"),
        ("prune", "via-under-two-layers"),
        ("prune", "free-end"),
        ("straighten", "fewer-turns"),
        ("chamfer", "t-joint"),
    ]
    assert result["counts"] == {
        "chamfer.t-joint": 1,
        "prune.free-end": 2,
        "prune.via-under-two-layers": 1,
        "straighten.fewer-turns": 1,
    }
    counts = {"joints_45": 0, "joints_90": 0, "acute": 0, "other": 0, "jogs": 0, "vias": 0}
    assert result["style"] == {
        "before": {**counts, "joints_90": 1, "vias": 1},
        "after": {**counts, "joints_45": 2},
    }
    assert result["copper_check"] == {"before": 0, "after": 0, "new": 0} and result["drc"] is None
    assert [found["code"] for found in env["issues"]] == ["tidy.kept"]
    assert env["evidence"]["level"] == "INFERRED" and "H-K-TIDY-DRC" in env["evidence"]["hypotheses"]
    assert tree_snapshot(tmp_path) == before


def test_confirm_writes_and_a_second_run_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, env, err = tidy(monkeypatch, tmp_path, "--confirm")
    assert code == 0, err and env["receipt"]["written"]
    board = tmp_path / "tidy.kicad_pcb"
    ends = {(t.start, t.end) for t in _tracks(board)}
    assert (_p(20, 10), _p(20, 12)) not in ends and (_p(10, 10), _p(20, 20)) in ends
    assert (_p(18, 30.5), _p(17.5, 30)) in ends
    code, env, _, _ = run(monkeypatch, tmp_path, "tidy", board.name, "--dry-run")
    assert code == 0 and env["result"]["changed"] is False and "plan" not in env["result"]


def test_one_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = tidy(monkeypatch, tmp_path, "--chamfer", "--leg", "1mm", "--dry-run")
    assert code == 0 and env["result"]["steps"] == ["chamfer"]
    edits = env["result"]["edits"]
    assert [(edit["net"], edit["reason"], edit["at"]["x"]) for edit in edits] == [
        ("BUS", "t-joint", 18_000_000),
        ("SIG", "t-joint", 15_000_000),
        ("SIG", "t-joint", 20_000_000),
        ("SIG", "right-angle", 30_000_000),
    ]
    assert edits[-1]["at"] == {"x": 30_000_000, "y": 10_000_000} and edits[-1]["layer"] == "F.Cu"
    code, env, _ = tidy(monkeypatch, tmp_path, "--straighten", "--nets", "SIG", "--dry-run")
    assert code == 0 and env["result"]["edits"] == []  # the stubs touch the L between its ends
    code, env, _ = tidy(monkeypatch, tmp_path, "--prune", "--straighten", "--nets", "SIG", "--dry-run")
    assert code == 0 and env["result"]["steps"] == ["prune", "straighten"]
    assert [edit["step"] for edit in env["result"]["edits"]] == ["prune", "prune", "prune", "straighten"]
    code, env, _ = tidy(monkeypatch, tmp_path, "--prune", "--nets", "BUS", "--dry-run")
    assert code == 0 and env["result"]["edits"] == [] and env["result"]["nets"] == 1


@pytest.mark.parametrize(
    "args",
    [
        ("--prune", "--leg", "1mm"),
        ("--leg", "1"),
        ("--leg", "0mm"),
        ("--out", str(Path("/abs.kicad_pcb").resolve())),
        ("--prune", "--zones"),
        ("--report", "--prune"),
        ("--compare", "tidy.kicad_pcb", "--zones"),
        ("--report", "--drc"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err = tidy(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_script_copper_stays(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design = bench(lead=False, bus=False)
    assert design.board is not None
    stub = next(t for t in design.board.tracks if t.start == _p(20, 10))
    marked = dataclasses.replace(stub, native_ids={"kicad": copper_uuid("stub", "seg[0]")})
    tracks = tuple(marked if t.id == stub.id else t for t in design.board.tracks)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=tracks))
    code, env, _ = tidy(monkeypatch, tmp_path, "--prune", "--dry-run", design=design)
    assert code == 0 and env["result"]["edits"] == []


def test_a_chamfer_too_close_is_undone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design = bench(stub=False, lead=False, bus=False, intruder=True)
    code, env, _ = tidy(monkeypatch, tmp_path, "--chamfer", "--dry-run", design=design)
    assert code == 0 and env["result"]["changed"] is False
    assert [found["code"] for found in env["issues"]] == ["tidy.chamfer-undone"]


def test_filled_zones_go_stale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design = bench(lead=False, bus=False)
    assert design.board is not None
    zone = dataclasses.replace(_zone(1, design.circuit.nets[0].id, _box(40, 30, 50, 38)), layers=("F.Cu",))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))
    code, env, _ = tidy(monkeypatch, tmp_path, "--prune", "--dry-run", design=design)
    assert code == 0 and env["result"]["fills_stale"] is True
    assert "tidy.fill-stale" in [found["code"] for found in env["issues"]]


def test_an_unreadable_project_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "tidy.kicad_pro").write_text("{ not json", encoding="utf-8")
    code, env, _ = tidy(monkeypatch, tmp_path, "--dry-run")
    assert code == 0 and "tidy.project-unread" in [found["code"] for found in env["issues"]]


def test_a_new_finding_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The final guard: a step that made a short (here a stand-in for ``prune``) gives
    ``tidy.check-failed`` and no write."""

    def shorting(design: Design, **_: object) -> TidyResult:
        assert design.board is not None
        bus = next(net.id for net in design.circuit.nets if net.name == "BUS")
        cross = Track(
            id="trk_00000000-0000-4000-8000-000000000099",
            start=_p(20, 5),
            end=_p(20, 15),
            width=250_000,
            layer="F.Cu",
            net_id=bus,
        )
        board = dataclasses.replace(design.board, tracks=(*design.board.tracks, cross))
        return TidyResult(
            dataclasses.replace(design, board=board), (cmd_tidy.Edit("prune", "x", "BUS", "F.Cu", _p(20, 5)),)
        )

    monkeypatch.setattr(cmd_tidy, "prune", shorting)
    code, env, err = tidy(monkeypatch, tmp_path, "--prune", "--dry-run")
    assert code == 5 and err["code"] == "FEN-5001"
    assert "tidy.check-failed" in [found["code"] for found in env["issues"]]
    assert "plan" not in env["result"]


class FakeTool:
    """A ``kicad-cli`` stand-in whose DRC reports ``counts[i]`` clearance violations on its ``i``-th run."""

    def __init__(self, counts: tuple[int, int]) -> None:
        self.counts = list(counts)
        self.boards: list[object] = []

    def version(self) -> str:
        return "10.0.7"

    def drc(self, board: Path, *, files: dict[str, object]) -> DrcRun:
        self.boards.append(files.get(board.name))
        count = self.counts.pop(0)
        report = DrcReport(
            "tidy.kicad_pcb",
            "",
            "10.0.7",
            "mm",
            violations=tuple(DrcViolation("clearance", "too close", "error") for _ in range(count)),
        )
        return DrcRun(CliRun("exit", 0, "", "", {}), report)


def test_drc_confirms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = FakeTool((1, 1))
    monkeypatch.setattr(cmd_tidy, "preflight", lambda *args, **kwargs: tool)
    code, env, _ = tidy(monkeypatch, tmp_path, "--drc", "--dry-run")
    assert code == 0 and env["result"]["drc"] == {
        "tool_version": "10.0.7",
        "before": 1,
        "after": 1,
        "new": [],
    }
    assert env["evidence"] == {
        "level": "KICAD-VERIFIED",
        "oracle": "kicad-cli 10.0.7",
        "hypotheses": ["H-K-TIDY-DRC"],
    }
    assert tool.boards[0] is None and isinstance(tool.boards[1], bytes)


def test_drc_finds_something_new(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cmd_tidy, "preflight", lambda *args, **kwargs: FakeTool((0, 2)))
    code, env, err = tidy(monkeypatch, tmp_path, "--drc", "--dry-run")
    assert code == 5 and err["code"] == "FEN-5001" and "plan" not in env["result"]
    (found,) = (found for found in env["issues"] if found["code"] == "tidy.drc-new")
    assert found["where"] == "clearance" and env["evidence"]["level"] == "INFERRED"


def test_drc_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, err = tidy(monkeypatch, tmp_path, "--drc", "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001"


def test_acute_joints_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Acute joints reported": ``--report`` plans nothing and needs no ``--dry-run``."""
    code, env, err = tidy(monkeypatch, tmp_path, "--report", design=acute())
    before_files = tree_snapshot(tmp_path)
    assert code == 0, err
    result = env["result"]
    assert "plan" not in result and result["steps"] == [] and result["compare"] is None
    assert result["report"]["counts"]["acute"] == 1
    (row,) = result["report"]["rows"]
    assert (row["netclass"], row["layer"], row["acute"]) == ("Default", "F.Cu", 1)
    (found,) = env["issues"]
    assert (found["code"], found["severity"]) == ("tidy.acute", "warning")
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["hypotheses"] == ["H-G-TIDY-STYLE"]
    assert tree_snapshot(tmp_path) == before_files


def test_a_style_compared(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A style compared": the reference's table comes beside the board's."""
    reference = tmp_path / "ref.kicad_pcb"
    reference.write_text(write_board(staircase(), target=10).text, encoding="utf-8", newline="\n")
    code, env, err = tidy(monkeypatch, tmp_path, "--compare", "ref.kicad_pcb")
    assert code == 0, err
    result = env["result"]
    assert "plan" not in result and result["compare"]["board"] == "ref.kicad_pcb"
    assert result["compare"]["counts"]["joints_90"] == 16 and result["compare"]["counts"]["jogs"] == 8
    assert result["report"]["counts"]["joints_90"] == 1 and result["report"]["counts"]["vias"] == 1


def test_zone_corners_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--chamfer --zones --confirm`` writes the cut outline without a fill."""
    design = bench(lead=False, bus=False)
    assert design.board is not None
    net = design.circuit.nets[0].id
    zone = dataclasses.replace(_zone(1, net, _box(40, 30, 50, 38)), layers=("F.Cu",))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))
    code, env, err = tidy(monkeypatch, tmp_path, "--chamfer", "--zones", "--confirm", design=design)
    assert code == 0, err
    assert env["result"]["counts"]["chamfer.zone-corner"] == 4
    assert all(edit["layer"] is None for edit in env["result"]["edits"] if edit["reason"] == "zone-corner")
    written = read_board((tmp_path / "tidy.kicad_pcb").read_text(encoding="utf-8"), file="tidy.kicad_pcb")
    assert written.board is not None
    (cut,) = written.board.zones
    assert len(cut.outline) == 8 and cut.fills == () and _p(41, 30) in cut.outline
