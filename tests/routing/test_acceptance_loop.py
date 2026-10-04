# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.1 acceptance loop on both examples and both KiCad majors (capability release-gate, "Acceptance
loop" and "Agent guide is executable"; change c0025).

The loop runs on the local ``kicad-cli`` with Freerouting. With ``FENOLITE_ACCEPTANCE_WRITE=1`` each
finished project is written to ``tests/data/acceptance/<example>_t<major>/``; without it the test writes
nothing in the repository.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from _acceptloop import EXAMPLES, ROOT, ROUTER, LoopRun, build_args, run_cli, run_loop

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_freerouting, pytest.mark.kicad_min_major(10)]

WRITE = "FENOLITE_ACCEPTANCE_WRITE"
RECORDED = ROOT / "tests" / "data" / "acceptance"
# Left out of a recorded project: KiCad's local state and Fenolite's derived cache (rebuilt by any build).
NOT_RECORDED = ("*.kicad_prl", "*-backups", "fp-info-cache", ".fenolite")
# The stages of ``check`` that the acceptance reads, and what each must report.
JUDGED = ("model.validate", "erc.lite", "drc.kicad", "netlist.assignment_compare", "roundtrip")


def stages(run: LoopRun) -> dict[str, dict[str, object]]:
    found = run.result("check")["stages"]
    assert isinstance(found, list)
    return {stage["name"]: stage for stage in found}


def assert_finished(run: LoopRun) -> None:
    """What "the loop closed" means: every judged stage ran and is ok, and KiCad's DRC reports no
    violation and no unconnected item."""
    by_name = stages(run)
    for name in JUDGED:
        assert name in by_name, (name, sorted(by_name))
        assert by_name[name]["status"] == "ok", by_name[name]
    drc = by_name["drc.kicad"]["summary"]
    assert isinstance(drc, dict)
    assert drc["violations"] == 0 and drc["unconnected"] == 0 and drc["canary"] == "fired", drc
    errors = [issue for issue in run.envelopes["check"]["issues"] if issue["severity"] == "error"]  # type: ignore[union-attr]
    assert not errors, errors


def project_bytes(project: Path) -> dict[str, bytes]:
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in sorted(project.rglob("*"))
        if path.is_file() and path.suffix != ".kicad_prl" and ".fenolite" not in path.parts
    }


def settle(run: LoopRun, example: str, target: int) -> None:
    """Rebuild the finished project until a build changes no byte, at most twice. The first rebuild after
    routing may reorder the script's own vias among the router's (the same items, another order); the
    recorded project is the settled one, so that "a rebuild is the identity" can be checked on it."""
    folder = run.project.parent
    for _ in range(2):
        before = project_bytes(run.project)
        code, envelope, error = run_cli(folder, *build_args(example, run.project, target))
        assert code == 0, error or envelope
        if project_bytes(run.project) == before:
            return
    raise AssertionError(f"{example} (KiCad {target}): two rebuilds in a row still change the project")


def record(run: LoopRun, example: str, target: int) -> None:
    """Copy the finished project into the repository (only with the write flag)."""
    settle(run, example, target)
    folder = RECORDED / f"{example}_t{target}"
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(
        run.project,
        folder,
        ignore=shutil.ignore_patterns(*NOT_RECORDED),
    )


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("example", sorted(EXAMPLES))
def test_loop(example: str, target: int, tmp_path: Path) -> None:
    """Scenarios "Loop closes on the blink" and "Loop closes on forty parts"."""
    run = run_loop(tmp_path, example, target)
    route = run.result("route")
    assert route["router"] == ROUTER and not route["unrouted"], route
    script = (ROOT / "examples" / example / "design.py").read_text(encoding="utf-8")
    scripted = sum(script.count(call) for call in ("design.track(", "design.via(", "design.stitch("))
    selected, routed = route["selected"], route["routed"]
    assert isinstance(selected, list) and isinstance(routed, list)
    closed = f"{len(routed)} of {len(selected)} net(s) closed by {ROUTER}"
    print(f"{example} t{target}: {closed}, {scripted} script copper call(s)")
    assert_finished(run)
    export, render = run.result("export"), run.result("render")
    assert export["artifacts"] and render["views"], (export, render)
    for step, envelope in run.envelopes.items():
        evidence = envelope["evidence"]
        assert isinstance(evidence, dict) and evidence["level"], step
    if os.environ.get(WRITE) == "1":
        record(run, example, target)
