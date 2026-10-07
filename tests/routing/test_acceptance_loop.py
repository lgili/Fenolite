# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.1 acceptance loop on both examples and both KiCad majors (capability release-gate, "Acceptance
loop"; change c0025). The loop block of the agent guide runs in
``tests/kicad/acceptance/test_skill_block.py`` since change c0079.

The loop runs on the local ``kicad-cli`` with Freerouting. With ``FENOLITE_ACCEPTANCE_WRITE=1`` each
finished project is written to ``tests/data/acceptance/<example>_t<major>/``; without it the test writes
nothing in the repository.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

import pytest
from _acceptloop import EXAMPLES, ROOT, ROUTER, LoopRun, build_args, run_cli, run_loop

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_freerouting, pytest.mark.kicad_min_major(10)]

WRITE = "FENOLITE_ACCEPTANCE_WRITE"
RECORDED = ROOT / "tests" / "data" / "acceptance"
# Left out of a recorded project: KiCad's local state and Fenolite's derived cache (rebuilt by any build).
NOT_RECORDED = ("*.kicad_prl", "*-backups", "fp-info-cache", ".fenolite")
# The stages of ``check`` that the acceptance reads, and what each must report.
# ``erc.kicad`` is KiCad's own ERC of the schematic that the build writes (change c0062).
JUDGED = ("model.validate", "erc.kicad", "drc.kicad", "netlist.assignment_compare", "roundtrip")


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


def _counting(folder: Path, name: str, real: str) -> tuple[Path, Path]:
    """A launcher that appends its arguments to a log and runs ``real``: the launcher and its log."""
    log = folder / f"{name}.calls"
    script = folder / f"{name}-counted"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nexec "{real}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    return script, log


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.is_file() else []


@pytest.mark.skipif(sys.platform == "win32", reason="the counting launchers are shell scripts")
def test_loop_plan_reviewed_then_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One pass of the 40-part example in which every writing step is reviewed with ``--dry-run`` and
    written with ``--confirm --plan`` (capability cli-contract, "Staged plans"; change c0120): no tool
    runs for the write, and the written hashes equal the plan rows."""
    from _resources import freerouting_jar, kicad_cli

    real_kicad, jar, java = kicad_cli(), freerouting_jar(), shutil.which("java")
    assert real_kicad is not None and jar is not None and java is not None
    kicad, kicad_log = _counting(tmp_path, "kicad-cli", str(real_kicad))
    counted_java, java_log = _counting(tmp_path, "java", java)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(kicad))
    monkeypatch.setenv("FENOLITE_JAVA", str(counted_java))
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(jar))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    example, target = "board_40parts", 10
    project = tmp_path / "project"
    name = f"{EXAMPLES[example]}.kicad_pcb"
    outputs = tmp_path / "outputs"
    stamp = ["--seed", "250025", "--timestamp", "2026-10-04T00:00:00Z", "--no-backup"]
    script = ROOT / "examples" / example / "design.py"
    steps: list[tuple[str, Path, list[str]]] = [
        ("build", tmp_path, ["build", str(script), "--out", str(project), "--kicad-version", str(target)]),
        ("place", project, ["place", name, "--strategy", "grid", "--margin", "3mm", "--gap", "2mm"]),
        ("route", project, ["route", name, "--router", ROUTER, "--timeout", "600"]),
        ("fill", project, ["fill", name]),
        ("export", project, ["export", name, "-o", str(outputs / "fab"), "--all", "--manifest"]),
        ("render", project, ["render", name, "-o", str(outputs / "views"), "--svg", "--png"]),
    ]
    for step, cwd, args in steps:
        code, reviewed, error = run_cli(cwd, *args, *stamp, "--dry-run", timeout=900)
        assert code == 0, f"{step} --dry-run: {error or reviewed}"
        result = reviewed["result"]
        assert isinstance(result, dict)
        plan, rows = result["plan_id"], result["plan"]
        assert isinstance(plan, str) and isinstance(rows, list) and rows, step
        tools = (_calls(kicad_log), _calls(java_log))
        if step == "route":
            assert len([line for line in tools[1] if "-de" in line.split()]) == 1, "one router run"
        code, written, error = run_cli(cwd, *args, *stamp, "--confirm", "--plan", plan, timeout=900)
        assert code == 0, f"{step} --confirm --plan: {error or written}"
        assert (_calls(kicad_log), _calls(java_log)) == tools, f"{step}: a tool ran for the write"
        receipt = written["receipt"]
        assert isinstance(receipt, dict) and receipt["plan"] == plan
        planned = {row["path"]: row["sha256"] for row in rows}
        assert {w["path"]: w["sha256"] for w in receipt["written"]} == planned, step
        for path, digest in planned.items():
            assert hashlib.sha256((cwd / path).read_bytes()).hexdigest() == digest, (step, path)
        print(f"{step}: {len(planned)} file(s) written as reviewed, plan {plan}")
    assert not list((tmp_path / "state" / "plans").iterdir()), "every written plan was removed"
    code, checked, error = run_cli(project, "check", name)
    assert code == 0, error or checked
    assert_finished(LoopRun(project, project / name, {"check": checked}))
