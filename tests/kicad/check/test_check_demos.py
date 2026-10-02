# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` on the cached KiCad demo boards and projects (capability verification-loop, scenarios
"Demo boards untouched" and "Demo boards round-trip"). Copies are made in ``tmp_path`` only; nothing derived
from the corpus is kept. With ``FENOLITE_CHECK_EVIDENCE=<file>`` each run appends one JSON line of counts
(statuses, canary state, ``tool_writes`` names, time) for ``docs/evidence/kicad-check.md``."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS
from _checkrun import check, stage
from _corpus import CorpusItem, corpus_items, require
from _projects import STEM, demo_project, tree_snapshot

from fenolite.backends.kicad.pcb import opaque_count, read_board

pytestmark = [
    pytest.mark.needs_kicad,
    pytest.mark.needs_corpus,
    pytest.mark.slow,
    pytest.mark.kicad_min_major(10),
]
DEMOS = [item for item in READABLE_ITEMS if not item.heavy]


def _tag(item: CorpusItem) -> str:
    return re.sub(r"-(pcb|pro|dru)-\d+$", "", item.id)


def _pairs() -> list[tuple[CorpusItem, CorpusItem, CorpusItem | None]]:
    """``(project row, its board, its rules row or None)``, paired by tag and file stem."""
    boards = {(_tag(i), i.path.stem): i for i in DEMOS}
    rows = corpus_items("project")  # cached rows only: an empty cache skips the projects case
    rules = {(_tag(i), i.path.stem): i for i in rows if i.path.suffix == ".kicad_dru"}
    found = []
    for row in rows:
        key = (_tag(row), row.path.stem)
        if row.path.suffix == ".kicad_pro" and key in boards:
            found.append((row, boards[key], rules.get(key)))
    return found


def _record(kind: str, item: CorpusItem, env: dict[str, object], seconds: float) -> None:
    target = os.environ.get("FENOLITE_CHECK_EVIDENCE")
    if not target:
        return
    stages = {s["name"]: s["status"] for s in env["result"]["stages"]}  # type: ignore[index]
    drc = stage(env, "drc.kicad")["summary"]  # type: ignore[arg-type]
    line = {"kind": kind, "id": item.id, "stages": stages, "canary": drc["canary"],
            "canary_reason": drc["canary_reason"], "tool_writes": drc["tool_writes"],
            "seconds": round(seconds, 1)}  # fmt: skip
    with open(target, "a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")


@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_demo_boards(item: CorpusItem, tmp_path: Path) -> None:
    root = demo_project(tmp_path, item)
    before = tree_snapshot(root)
    started = time.monotonic()
    _, env, _, err = check(root)
    assert env, err
    _record("board", item, env, time.monotonic() - started)
    assert tree_snapshot(root) == before
    rt = stage(env, "roundtrip")
    text = (root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8")
    assert rt["status"] == "ok" and rt["summary"]["opaque_count"] == opaque_count(read_board(text))


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: p[0].id)
def test_demo_projects(pair: tuple[CorpusItem, CorpusItem, CorpusItem | None], tmp_path: Path) -> None:
    project, board, rules = pair
    root = tmp_path / project.id
    root.mkdir()
    shutil.copyfile(require(board), root / f"{STEM}.kicad_pcb")
    shutil.copyfile(require(project), root / f"{STEM}.kicad_pro")
    if rules is not None:
        shutil.copyfile(require(rules), root / f"{STEM}.kicad_dru")
    before = tree_snapshot(root)
    started = time.monotonic()
    _, env, _, err = check(root)
    assert env, err
    _record("project", project, env, time.monotonic() - started)
    assert tree_snapshot(root) == before
