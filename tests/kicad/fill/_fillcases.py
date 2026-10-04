# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored zone-fill oracle cases for KiCad 10 and the target-9 load check."""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path

from _buildcases import _folder
from _buildhelp import build, pour_variant
from _projects import authored_project

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.fill import fill_board
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.dsl import moves, placements, to_model
from fenolite.lens.preserve import ExistingProject, prepare
from fenolite.model.design import Design

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "kicad" / "fill"


def refill(cli: KicadCli, board: Path) -> bytes | None:
    project = project_set(board)
    files = {k: v for k, v in project.files.items() if k != project.board}
    run = cli.refill(project.files[project.board], files=files)
    return run.board if run.run.ok else None


def fills(design: Design) -> tuple[tuple[str, bool, tuple], ...]:
    assert design.board is not None
    return tuple((zone.id, zone.filled, zone.fills) for zone in design.board.zones)


def direct_lift(original: Design, saved: Design) -> Design:
    assert original.board is not None and saved.board is not None
    replacement = {zone.id: zone for zone in saved.board.zones}
    assert replacement.keys() == {zone.id for zone in original.board.zones}
    zones = tuple(
        dataclasses.replace(z, fills=replacement[z.id].fills, filled=replacement[z.id].filled)
        for z in original.board.zones
    )
    return dataclasses.replace(original, board=dataclasses.replace(original.board, zones=zones))


def save_case(target: int) -> str:
    from _probes import runner

    with tempfile.TemporaryDirectory() as tmp:
        root = authored_project(Path(tmp), major=target, decoys=False)
        board = root / "board.kicad_pcb"
        original = read_board(board)
        data = refill(runner(), board)
    if data is None:
        return "absent"
    saved = read_board(data.decode("utf-8"))
    assert original.board is not None and saved.board is not None
    same_ids = {z.id for z in original.board.zones} == {z.id for z in saved.board.zones}
    return "present" if same_ids and any(z.fills for z in saved.board.zones) else "different"


def repeat_case() -> str:
    from _probes import runner

    for built in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = authored_project(Path(tmp), major=10, built=built, decoys=False)
            board = root / "board.kicad_pcb"
            saved = [refill(runner(), board) for _ in range(3)]
        if any(data is None for data in saved):
            return "absent"
        if len({fills(read_board(data.decode("utf-8"))) for data in saved if data is not None}) != 1:
            return "different"
    return "equal"


def lift_case(target: int) -> str:
    from _probes import runner

    with tempfile.TemporaryDirectory() as tmp:
        root = authored_project(Path(tmp), major=target, decoys=False)
        board = root / "board.kicad_pcb"
        data = refill(runner(), board)
        if data is None:
            return "absent"
        filled = fill_board(board.read_text(encoding="utf-8"), data.decode("utf-8"))
        assert filled.text is not None
        lifted = read_board(filled.text)
        board.write_text(filled.text, encoding="utf-8")
        second = refill(runner(), board)
    if second is None:
        return "absent"
    return "equal" if fills(lifted) == fills(read_board(second.decode("utf-8"))) else "different"


def load9_case() -> str:
    from _probes import runner

    filled = FIXTURES / "triad_t9_filled.kicad_pcb"
    unfilled = FIXTURES / "triad_t9.kicad_pcb"
    reports = []
    for board in (unfilled, filled):
        run = runner().drc(board)
        if run.report is None:
            return "reject"
        reports.append({v.type for v in (*run.report.violations, *run.report.unconnected_items)})
    return "load" if reports[1] - reports[0] <= {"isolated_copper"} else "different"


def kept_case() -> str:
    """A filled blink keeps current copper on an unchanged rebuild, then drops it on a class edit."""
    from _probes import runner

    design = pour_variant()
    built = build(design, 10)
    if any(issue.severity == "error" for issue in built.issues):
        return "reject"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _folder(built.files, root)
        board = root / "blink.kicad_pcb"
        saved = refill(runner(), board)
        if saved is None:
            return "reject"
        filled = fill_board(board.read_text(encoding="utf-8"), saved.decode("utf-8"))
        if filled.text is None:
            return "reject"
        project_text = built.files["blink.kicad_pro"].decode("utf-8")
        rules_text = built.files["blink.kicad_dru"].decode("utf-8")

        def rebuild(board_text: str, project: str) -> tuple[str, tuple[str, ...]]:
            existing = ExistingProject(board_text, project, rules_text)
            ready = prepare(to_model(design), placements(design), existing, name="blink", moves=moves(design))
            result = build(design, 10, prepared=ready, placements_override=ready.placements)
            return result.files["blink.kicad_pcb"].decode("utf-8"), tuple(i.code for i in result.issues)

        kept, kept_issues = rebuild(filled.text, project_text)
        board.write_text(kept, encoding="utf-8")
        after = refill(runner(), board)
        if after is None or "zone.fill-stale" in kept_issues:
            return "different"
        current = fills(read_board(kept)) == fills(read_board(after.decode("utf-8")))
        changed_project = json.loads(project_text)
        for entry in changed_project["net_settings"]["classes"]:
            if entry["name"] == "PWR":
                entry["clearance"] = 5.0
        stale, issues = rebuild(kept, json.dumps(changed_project))
        if "zone.fill-stale" not in issues or any(zone.fills for zone in read_board(stale).board.zones):
            return "different"
        board.write_text(stale, encoding="utf-8")
        newer = refill(runner(), board)
        if newer is None:
            return "reject"
        newly_filled = fill_board(stale, newer.decode("utf-8"))
        if newly_filled.text is None:
            return "reject"
        board.write_text(newly_filled.text, encoding="utf-8")
        confirmed = refill(runner(), board)
        if confirmed is None:
            return "reject"
        fresh = fills(read_board(newly_filled.text)) == fills(read_board(confirmed.decode("utf-8")))
        return "equal" if current and fresh else "different"


def fill_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    return {
        "fill-save-t9": (lambda: save_case(9), (10,)),
        "fill-save-t10": (lambda: save_case(10), (10,)),
        "fill-repeat": (repeat_case, (10,)),
        "fill-lift-t9": (lambda: lift_case(9), (10,)),
        "fill-lift-t10": (lambda: lift_case(10), (10,)),
        "fill-load9": (load9_case, (9,)),
        "fill-kept": (kept_case, (10,)),
    }
