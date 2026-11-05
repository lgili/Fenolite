# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded scale measurements of ``route --propose`` on the authored acceptance boards (change c0370, task 7;
capability routing, "Reviewed completion acceptance").

Each case builds ``examples/routing/acceptance.py`` (fixed seed 1) for the running KiCad major, records
KiCad's own unconnected count of the board as built, then runs one proposal pass, with the built-in shapes
and with the bounded search. Deterministic counters (A* calls, expanded and discovered states, subjects per
completion state, candidates) and the wall-clock time, kept apart as telemetry, are written as one JSON line
per case to ``$FENOLITE_SCALE_RECORD`` (CI uploads it) or to the test's folder. The assertions are the
contract, never a speed: exit 0, no byte written, every open subject in exactly one completion state,
``complete`` false, each search call within its explicit state bound. Thresholds are set only from
recorded CI measurements (``docs/evidence/router-completion.md``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _probes import major, runner
from _search_project import cli

import fenolite.routing.search as search_module
from fenolite.cli._propose import REASONS

pytestmark = pytest.mark.needs_kicad
ROOT = Path(__file__).resolve().parents[3]
SEED = 1
MAX_STATES = 50_000
TIMEOUT = {"shapes": "600", "search": "300"}
"""Seconds of the one job budget. Local measurement 2026-11-04 (one core): 150 parts took 212-228 s with
the shapes and 306 s (two layers) or the whole 600 s (four layers) with the search; a cut run reports its
subjects ``unknown`` and is never called exhaustive."""
SEARCH = (
    "--router-option",
    "search=only",
    "--router-option",
    "search-grid=0.5mm",
    "--router-option",
    f"search-max-states={MAX_STATES}",
    "--router-option",
    "max-length=60mm",
)
MODES = {"shapes": (), "search": SEARCH}


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_route_acceptance", ROOT / "examples/routing/acceptance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ beside the example
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def _record(row: dict[str, Any], folder: Path) -> None:
    target = Path(os.environ.get("FENOLITE_SCALE_RECORD") or folder / "scale.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, sort_keys=True) + "\n")


def _unconnected(board: Path) -> int:
    result = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert result.report is not None
    return sum(not v.excluded for v in result.report.unconnected_items)


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize(("layers", "parts"), [(2, 40), (4, 40), (2, 150), (4, 150)])
def test_bounded_proposal_pass_on_an_acceptance_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layers: int, parts: int, mode: str
) -> None:
    monkeypatch.chdir(tmp_path)
    text = _generator().script(seed=SEED, layers=layers, parts=parts)
    (tmp_path / "board.py").write_text(text, encoding="utf-8")
    code, _env, err = cli("build", "board.py", "--out", "out", "--kicad-version", str(major()), "--confirm")
    assert code == 0, err
    (board,) = sorted((tmp_path / "out").glob("*.kicad_pcb"))
    native = _unconnected(board)
    before = board.read_bytes()

    counters = Counter[str]()
    largest = 0
    real = search_module.astar

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal largest
        found = real(*args, **kwargs)
        counters.update(calls=1, expanded=found.expanded, discovered=found.discovered)
        largest = max(largest, found.discovered)
        return found

    monkeypatch.setattr(search_module, "astar", counted)
    extra = (
        (*MODES[mode], "--router-option", f"search-max-vias={0 if layers == 2 else 2}") if MODES[mode] else ()
    )
    started = time.monotonic()
    code, env, err = cli(
        "route",
        str(board),
        "--router",
        "octilinear",
        "--propose",
        "--candidates",
        "1",
        "--timeout",
        TIMEOUT[mode],
        *extra,
    )
    wall = time.monotonic() - started
    assert code == 0, err
    assert board.read_bytes() == before, "a proposal pass writes nothing"

    result = env["result"]
    done = result["completion"]
    keys = [key for state in done["subjects"].values() for key in state]
    assert len(keys) == len(set(keys)), "a subject is in exactly one state"
    assert {p["subject"] for p in result["proposals"]} <= set(keys)
    assert done["complete"] is False and done["checks"] == "not-run"
    assert done["state"] == ("open" if done["open"] else "unchecked")
    reasons = Counter(p["reason"] for p in result["proposals"])
    assert set(reasons) - {None} <= set(REASONS), reasons
    assert largest <= MAX_STATES, largest
    if mode == "shapes":
        assert counters["calls"] == 0

    _record(
        {
            "change": "c0370",
            "seed": SEED,
            "layers": layers,
            "parts": parts,
            "mode": mode,
            "script_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "kicad_major": major(),
            "kicad_unconnected_as_built": native,
            "open": done["open"],
            "fill": done["fill"],
            "subjects": {state: len(found) for state, found in done["subjects"].items()},
            "candidates": sum(len(p["candidates"]) for p in result["proposals"]),
            "reasons": {str(k): v for k, v in sorted(reasons.items(), key=lambda kv: str(kv[0]))},
            "search": {
                "max_states": MAX_STATES if MODES[mode] else None,
                **counters,
                "largest_call": largest,
            },
            "timeout_seconds": float(TIMEOUT[mode]),
            "telemetry": {"wall_seconds": round(wall, 3), "python": platform.python_version()},
        },
        tmp_path,
    )
