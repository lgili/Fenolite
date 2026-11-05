# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Real authored processes: shared deadline, cancellation, hostile/partial adapter output."""

import os
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from _fakefreerouting import create_fake_jar, create_fake_java
from _fakerouter import create_fake_router
from _resources import posix_tools
from _searchbench import bench

from fenolite.routing.budget import Budget
from fenolite.routing.external_candidates import Adapter, MissingTool, generate_external
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter
from fenolite.routing.protocol import RouterStatus
from tests.unit.routing.test_routingtools import _job


def test_process_timeout_kills_descendant_before_it_can_write(tmp_path: Path):
    marker = tmp_path / "descendant"
    grandchild = f"import time; time.sleep(1.4); open({str(marker)!r}, 'w').close()"
    parent = (
        f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
        "print('partial',flush=True); time.sleep(30)"
    )
    began = time.monotonic()
    result = Budget(0.75).run([sys.executable, "-c", parent], cwd=tmp_path)
    assert result.cut and result.returncode is None
    assert "partial" in result.stdout, "the parent must actually spawn the descendant before timeout"
    assert time.monotonic() - began < 5
    time.sleep(1.5)
    assert not marker.exists()


def test_process_cancellation_is_polled_and_partial_bytes_are_not_success(tmp_path: Path):
    stop = threading.Event()
    timer = threading.Timer(0.2, stop.set)
    timer.start()
    try:
        result = Budget(30, cancelled=stop.is_set).run(
            [sys.executable, "-c", "import time; print('partial',flush=True); time.sleep(30)"], cwd=tmp_path
        )
    finally:
        timer.cancel()
    assert result.cut and result.returncode is None and result.seconds < 5


def test_process_already_cancelled_starts_nothing(tmp_path: Path):
    marker = tmp_path / "started"
    result = Budget(5, cancelled=lambda: True).run(
        [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"], cwd=tmp_path
    )
    assert result.cut and not result.started and not marker.exists()


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX background-parent fixture; native Windows evidence is pending"
)
def test_process_finished_parent_leaves_no_background_descendant(tmp_path: Path):
    marker = tmp_path / "background"
    child = f"import time; time.sleep(0.8); open({str(marker)!r},'w').close()"
    parent = (
        f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}], "
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    result = Budget(5).run([sys.executable, "-c", parent], cwd=tmp_path)
    assert not result.cut and result.returncode == 0
    time.sleep(0.9)
    assert not marker.exists()


def krt(tmp_path, monkeypatch):
    monkeypatch.setenv("FENOLITE_TEST_SOURCE", str(Path(__file__).resolve().parents[3] / "src"))
    checkout = create_fake_router(tmp_path)
    return KicadRoutingToolsRouter(checkout, sys.executable), checkout


def test_adapter_uses_supplied_budget_and_strict_delta(tmp_path, monkeypatch):
    router, _ = krt(tmp_path, monkeypatch)
    budget = Budget(5)
    job = _job()
    # This is the existing real subprocess adapter, not a mock of its return value.
    found = router.route(
        replace(
            job,
            extra={
                "external_candidate": True,
                "routing_budget": budget,
                "external_status": router.available(),
            },
        )
    )
    assert found.tracks and not any(i.severity == "error" for i in found.issues)
    assert budget.spent() > 0
    assert all(run.outcome == "done" for run in found.runs)


@pytest.mark.parametrize("mode", ["remove", "edit", "unselected", "malformed"])
def test_adapter_rejects_entire_hostile_board_before_lifting(mode, tmp_path, monkeypatch):
    router, checkout = krt(tmp_path, monkeypatch)
    route = checkout / "py_router" / "route.py"
    script = route.read_text()
    needle = "output.write_text(write_board(dataclasses.replace(design, board=board), target=10).text)"
    mutation = {
        "remove": "board = dataclasses.replace(board, footprints=())",
        "edit": (
            "board = dataclasses.replace(board, footprints=tuple("
            "dataclasses.replace(fp, position=Point(9999999,9999999)) for fp in board.footprints))"
        ),
        "unselected": (
            "wrong = next(n.id for n in design.circuit.nets if n.name != chosen[0].name)\n"
            "board = dataclasses.replace(board, tracks=tuple("
            "dataclasses.replace(t, net_id=wrong) for t in board.tracks))"
        ),
        "malformed": "output.write_text('invalid'); raise SystemExit(0)",
    }[mode]
    assert needle in script
    route.write_text(script.replace(needle, mutation + "\n" + needle))
    found = router.route(replace(_job(), extra={"external_candidate": True, "routing_budget": Budget(5)}))
    assert not found.tracks and any(i.code == "route.tool-failed" for i in found.issues)
    assert all(run.outcome == "failed" for run in found.runs)


def test_adapter_killed_partial_board_is_never_read(tmp_path, monkeypatch):
    router, checkout = krt(tmp_path, monkeypatch)
    route = checkout / "py_router" / "route.py"
    script = route.read_text()
    # The tool writes a complete but untrusted board, then hangs before a successful exit.
    route.write_text(script + "\nimport time; time.sleep(30)\n")
    found = router.route(replace(_job(), extra={"external_candidate": True, "routing_budget": Budget(0.3)}))
    assert not found.tracks and found.runs and found.runs[0].outcome == "cut"


def test_dispatch_reports_clock_truncated_unattempted_subset():
    job, subject, _ = bench()
    called = []
    budget = Budget(5, cancelled=lambda: True)
    adapter = Adapter(
        "kicadroutingtools", "board", lambda _: called.append(True), lambda _: called.append(True)
    )
    result = generate_external(job, (subject,), (adapter,), budget=budget, judge=lambda *_: "")
    assert result.not_attempted == ((subject.key, adapter.name),) and not called


def test_missing_explicit_tool_is_not_a_successful_empty_fallback():
    job, subject, _ = bench()
    adapter = Adapter(
        "kicadroutingtools",
        "board",
        lambda _: RouterStatus(False, reason="missing authored tool"),
        lambda _: pytest.fail("must not route"),
    )
    with pytest.raises(MissingTool, match="missing authored tool"):
        generate_external(job, (subject,), (adapter,), budget=Budget(5), judge=lambda *_: "")


@posix_tools
def test_java_preflight_and_routing_use_one_budget(tmp_path, monkeypatch):
    from tests.unit.routing.test_freerouting import SESSION
    from tests.unit.routing.test_freerouting import _job as session_job

    monkeypatch.setenv("FAKE_JAVA_SESSION", str(SESSION))
    router = FreeroutingRouter(create_fake_jar(tmp_path), create_fake_java(tmp_path))
    budget = Budget(5)
    status = router.candidate_status(budget)
    assert status.available
    monkeypatch.setattr(router, "available", lambda: pytest.fail("unbudgeted availability rerun"))
    job = session_job()
    found = router.route(
        replace(
            job,
            extra={
                **job.extra,
                "external_candidate": True,
                "external_status": status,
                "routing_budget": budget,
            },
        )
    )
    assert found.tracks and all(run.outcome == "done" for run in found.runs)
    assert budget.spent() > 0


def test_container_candidate_preflight_never_pulls_or_starts_process(monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("container process"))
    assert not FreeroutingRouter("docker:authored").candidate_status(Budget(5)).available


def test_process_windows_tree_command_and_failed_cleanup_are_explicit(monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fenolite.routing import budget as module

    child = Mock(pid=1234)
    child.poll.return_value = None
    run = Mock()
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(subprocess, "run", run)
    module._kill_tree(child)
    assert run.call_args.args[0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert run.call_args.kwargs["timeout"] == 10
    run.side_effect = subprocess.TimeoutExpired("taskkill", 10)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        module._kill_tree(child)
    child.kill.assert_called_once()
    child.wait.assert_called_once_with(timeout=10)


@pytest.mark.parametrize("mutation", ["unknown-net", "unknown-state", "moved"])
def test_session_scope_checked_before_any_copper_filter(mutation):
    from _specctra import two_pads

    from tests.unit.routing.test_freerouting import SESSION

    session = SESSION.read_text()
    if mutation == "unknown-net":
        session = session.replace("(net A", "(net UNKNOWN")
    elif mutation == "unknown-state":
        session = session.replace("(network_out", "(unrecognized protected-state) (network_out")
    else:
        session = session.replace("100000 -100000 front", "100001 -100000 front")
    result = FreeroutingRouter()._copper(session, two_pads().write(), ("A",), strict=True)
    assert isinstance(result, str) or (not result[0] and any(i.severity == "error" for i in result[2]))
