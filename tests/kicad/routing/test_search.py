# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0365 accepted two/four-layer search routes judged by KiCad; H-K-SEARCH-DRC."""

import os
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from _probes import major, runner
from _search_project import SEARCH, cli, project

pytestmark = pytest.mark.needs_kicad


def drc(board: Path):
    result = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert result.report is not None
    return (
        Counter(v.type for v in result.report.violations if not v.excluded),
        sum(not v.excluded for v in result.report.unconnected_items),
    )


@pytest.mark.parametrize(("layers", "bottom"), [(2, False), (4, False), (2, True), (4, True)])
def test_reviewed_search_closes_connection_and_rollback_preserves_board(
    tmp_path: Path, monkeypatch, layers: int, bottom: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(runner().path))
    built = project(tmp_path, layers, bottom=bottom)
    if major() != 10:
        out = tmp_path / "oracle"
        code, _, err = cli(
            "build",
            str(tmp_path / "search_maze.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major()),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
    search_options = tuple(
        "search-max-vias=1" if word == "search-max-vias=0" and bottom else word for word in SEARCH
    )
    before = built.board.read_bytes()
    violations, opens = drc(built.board)
    words = ("route", str(built.board), "--router", "octilinear")
    code, reply, err = cli(*words, "--propose", "--nets", "SIG", *search_options)
    assert code == 0, err
    assert built.board.read_bytes() == before
    candidate = reply["result"]["proposals"][0]["candidates"][0]
    assert candidate["source"] == "search"
    assert candidate["facts"]["vias"] == int(bottom)
    assert candidate["facts"]["open"]["after"] < candidate["facts"]["open"]["before"]
    code, planned, err = cli(
        *words, "--accept", candidate["id"], *search_options, "--gate", "drc", "--dry-run"
    )
    assert code == 0, err
    assert built.board.read_bytes() == before
    plan = planned["result"]["plan_id"]
    record = tmp_path / planned["result"]["record"]
    prior_record = record.read_bytes() if record.is_file() else None
    real_replace = os.replace
    triggered = []

    def fail_record(src, dst, *args, **kwargs):
        if Path(dst) == record and not triggered:
            triggered.append(True)
            raise PermissionError(13, "authored search rollback test")
        return real_replace(src, dst, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(os, "replace", fail_record)
        code, _, err = cli(
            *words, "--accept", candidate["id"], *search_options, "--gate", "drc", "--confirm", "--plan", plan
        )
        assert code == 1 and "FEN-1002" in err
    assert triggered and built.board.read_bytes() == before
    assert (record.read_bytes() if record.is_file() else None) == prior_record
    code, reply, err = cli(
        *words, "--accept", candidate["id"], *search_options, "--gate", "drc", "--confirm", "--plan", plan
    )
    assert code == 0, err
    after, remaining = drc(built.board)
    assert remaining == opens - 1, (opens, remaining)
    assert all(after[k] <= violations[k] for k in after), (violations, after)
