# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The live server of the viewer (capability board-viewer, "Live server"): loopback only, scenes on request,
a saved board read again after it settles."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.view import server
from fenolite.view.compact import expand
from fenolite.view.project import load_tree
from fenolite.view.runs import Choices, Outcome
from fenolite.view.scene import build_scene

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _build(path: Path) -> dict[str, Any]:
    backend = registry.for_path(path)
    assert backend is not None and isinstance(backend, BoardFrame)
    return build_scene(backend.read(path).design, backend, name=path.name, data=path.read_bytes())


def _get(port: int, route: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=10) as reply:
            return reply.status, reply.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def _segments(scene: dict[str, Any]) -> int:
    return sum(1 for p in expand(scene)["prims"] if str(p[5]).startswith("track "))


def test_saved_board_is_reloaded(tmp_path: Path) -> None:
    """Scenario "A saved board is reloaded"."""
    board = tmp_path / "board.kicad_pcb"
    shutil.copy(BOARD, board)
    live = server.Live(load_tree(board), _build)
    httpd = server.serve(live, 0)
    assert httpd.server_address[0] == server.HOST
    port = httpd.server_address[1]
    stop = threading.Event()
    thread = threading.Thread(target=server.run, args=(live, httpd), kwargs={"until": stop}, daemon=True)
    thread.start()
    try:
        code, body = _get(port, "/project.json")
        assert code == 200 and json.loads(body)["groups"][0]["documents"][0]["id"] == "doc1"
        code, body = _get(port, "/scene/doc1.json")
        before = json.loads(body)
        assert code == 200 and _segments(before) >= 1
        version = json.loads(_get(port, "/version/doc1")[1])["version"]
        text = board.read_text(encoding="utf-8")
        start = text.index("(segment")
        depth, end = 0, start
        for end in range(start, len(text)):
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            if depth == 0:
                break
        board.write_text(text[:start] + text[end + 1 :], encoding="utf-8")
        os.utime(board, ns=(1, 1))
        assert live.check() == [] and live.check() == ["doc1"]
        after = json.loads(_get(port, "/scene/doc1.json")[1])
        assert _segments(after) == _segments(before) - 1
        assert json.loads(_get(port, "/version/doc1")[1])["version"] != version
        assert _get(port, "/scene/doc9.json")[0] == 404
        page = _get(port, "/")[1].decode("utf-8")
        assert "const LIVE = true;" in page
    finally:
        stop.set()
        thread.join(timeout=10)


def _post(port: int, body: bytes, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/marks", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def test_marks_are_written_by_the_server_only(tmp_path: Path) -> None:
    """Change c0189: a mark the page posts goes to the --marks file, in one atomic replace; a post without the
    review header, from another origin or to a server without a file is refused and writes nothing."""
    marks = tmp_path / "review.json"
    live = server.Live(load_tree(BOARD), _build, marks_file=marks)
    bare = server.Live(load_tree(BOARD), _build)
    servers = [server.serve(live, 0), server.serve(bare, 0)]
    stop = threading.Event()
    for httpd, state in zip(servers, (live, bare), strict=True):
        threading.Thread(target=server.run, args=(state, httpd), kwargs={"until": stop}, daemon=True).start()
    port, bare_port = (int(h.server_address[1]) for h in servers)
    ok = {"Content-Type": "application/json", server.REVIEW_HEADER: "1"}
    mark = {"id": "m1", "doc": BOARD.name, "x_nm": 1_000_000, "y_nm": -2_500_000, "note": "check this gap"}
    try:
        assert json.loads(_get(port, "/project.json")[1])["marks_file"] is True
        assert _post(port, json.dumps(mark).encode(), {"Content-Type": "application/json"})[0] == 403
        assert _post(port, json.dumps(mark).encode(), ok | {"Origin": "http://evil.example"})[0] == 403
        assert _post(port, b"{", ok)[0] == 400 and not marks.exists()
        assert _post(bare_port, json.dumps(mark).encode(), ok)[0] == 403
        code, reply = _post(port, json.dumps(mark).encode(), ok)
        assert (
            code == 200
            and reply["marks"][0]["note"] == "check this gap"
            and reply["marks"][0]["y_mm"] == -2.5
        )
        stored = json.loads(marks.read_text(encoding="utf-8"))
        assert stored["schema"] == "fenolite.review.v0" and stored["marks"][0]["x_nm"] == 1_000_000
        code, reply = _post(port, json.dumps({"id": "m1", "note": None}).encode(), ok)
        assert code == 200 and reply["marks"] == [] and live.written == 2
        assert [p.name for p in tmp_path.iterdir()] == ["review.json"]  # no temporary file left
    finally:
        stop.set()


class _DeferredThread:
    """Capture background work so the test controls when its first instruction runs."""

    jobs: list[_DeferredThread] = []

    def __init__(self, *, target: Any, args: tuple[Any, ...], daemon: bool) -> None:
        self.target, self.args = target, args
        self.jobs.append(self)

    def start(self) -> None:
        pass

    def run(self) -> None:
        self.target(*self.args)


def test_delayed_refiner_does_not_adopt_a_newer_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """An old worker may first run after the second build; it must not publish over that build."""
    _DeferredThread.jobs = []
    monkeypatch.setattr(server.threading, "Thread", _DeferredThread)
    serial = 0

    def build(_path: Path) -> dict[str, Any]:
        nonlocal serial
        serial += 1
        return {"meta": {"sha256": str(serial)}}

    def refine(_path: Path, scene: dict[str, Any]) -> dict[str, Any]:
        return scene | {"refined": True}

    live = server.Live(load_tree(BOARD), build, refine=refine)
    live.scene("doc1")
    doc = live.tree.document("doc1")
    assert doc is not None
    live._rebuild(doc, live.states["doc1"])
    latest = live.scene("doc1")
    version = live.version("doc1")
    _DeferredThread.jobs[0].run()
    assert live.scene("doc1") == latest and live.version("doc1") == version
    _DeferredThread.jobs[1].run()
    assert json.loads(live.scene("doc1") or b"{}")["refined"] is True
    assert json.loads(live.scene("doc1") or b"{}")["meta"]["sha256"] == "2"


def test_refinement_publication_checks_generation_under_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A newer scene may publish while old refined bytes are being serialized, before the store lock."""
    entered, release = threading.Event(), threading.Event()
    original_compact, original_thread = server.compact, threading.Thread
    workers: list[threading.Thread] = []
    serial = 0

    def build(_path: Path) -> dict[str, Any]:
        nonlocal serial
        serial += 1
        return {"meta": {"sha256": str(serial)}}

    def refine(_path: Path, scene: dict[str, Any]) -> dict[str, Any] | None:
        return scene | {"refined": True} if scene["meta"]["sha256"] == "1" else None

    def compact(scene: dict[str, Any]) -> dict[str, Any]:
        if scene.get("refined"):
            entered.set()
            assert release.wait(10), "the test did not release the paused refinement"
        return original_compact(scene)

    def thread(**kwargs: Any) -> threading.Thread:
        worker = original_thread(**kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(server, "compact", compact)
    monkeypatch.setattr(server.threading, "Thread", thread)
    live = server.Live(load_tree(BOARD), build, refine=refine)
    try:
        live.scene("doc1")
        assert entered.wait(10), "refinement did not reach serialization"
        doc = live.tree.document("doc1")
        assert doc is not None
        live._rebuild(doc, live.states["doc1"])
        latest = live.scene("doc1")
        version = live.version("doc1")
    finally:
        release.set()
        for worker in workers:
            worker.join(10)
            assert not worker.is_alive()
    assert live.scene("doc1") == latest and live.version("doc1") == version
    assert json.loads(latest or b"{}")["meta"]["sha256"] == "2"


# ---------------------------------------------------------------------------------------------- runs (c0302)

RUN_OK = {"Content-Type": "application/json", "X-Fenolite-Run": "1"}


class _Handle:
    def __init__(self, runner: _FakeRunner) -> None:
        self.runner, self.cancelled = runner, threading.Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def wait(self) -> Outcome:
        while not self.cancelled.wait(0.02):
            if self.runner.release.is_set():
                return Outcome("done", 5, self.runner.reply)
        return Outcome("cancelled", 1, error={"code": "FEN-1003", "message": "the call was cancelled"})


class _FakeRunner:
    """Blocks each job until ``release`` is set (then ends with ``reply``) or the job is cancelled."""

    def __init__(self, reply: dict[str, Any] | None = None) -> None:
        self.release = threading.Event()
        self.reply = reply or {"command": "check", "issues": [], "result": {"stages": []}}
        self.started: list[Any] = []

    def start(self, request: Any, on_progress: Any) -> _Handle:
        self.started.append(request)
        on_progress({"command": getattr(request, "command", "?"), "event": "step", "step": "drc.kicad"})
        return _Handle(self)


def _serve_runs(live: server.Live) -> tuple[int, threading.Event]:
    httpd = server.serve(live, 0)
    stop = threading.Event()
    threading.Thread(target=server.run, args=(live, httpd), kwargs={"until": stop}, daemon=True).start()
    return int(httpd.server_address[1]), stop


def _call(port: int, route: str, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{route}",
        data=data,
        headers=headers or {},
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:
            return reply.status, json.loads(reply.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def _until(port: int, job: str, *, seconds: float = 10) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = _call(port, f"/run/{job}")[1]
        if state["state"] != "running":
            return state
        time.sleep(0.02)
    raise AssertionError(f"job {job} did not end")


def _live_runs(tmp_path: Path, runner: Any, **kwargs: Any) -> server.Live:
    board = tmp_path / BOARD.name
    shutil.copy(BOARD, board)
    choices = Choices(stages=("drc.kicad", "copper.clearance", "model.validate"))
    return server.Live(load_tree(board), _build, runner=runner, choices=choices, **kwargs)


CHECK_DRC = {"command": "check", "doc": "doc1", "options": {"stages": ["drc.kicad"]}}


def test_run_guard_refuses_other_origins_and_starts_nothing(tmp_path: Path) -> None:
    """Scenario "A request from another origin"."""
    runner = _FakeRunner()
    port, stop = _serve_runs(_live_runs(tmp_path, runner))
    try:
        assert _call(port, "/run", CHECK_DRC, RUN_OK | {"Origin": "http://evil.example"})[0] == 403
        assert _call(port, "/run", CHECK_DRC, {"Content-Type": "application/json"})[0] == 403
        assert _call(port, "/run", CHECK_DRC, RUN_OK | {"Content-Type": "text/plain"})[0] == 403
        assert _call(port, "/run", CHECK_DRC, RUN_OK | {"Host": f"evil.example:{port}"})[0] == 403
        assert _call(port, "/run", b"x" * (17 * 1024), RUN_OK)[0] == 413
        assert _call(port, "/runs", None, {"Host": "rebound.example"})[0] == 403
        assert runner.started == []
    finally:
        stop.set()


def test_run_one_at_a_time_and_cancel(tmp_path: Path) -> None:
    """Scenarios "One run at a time" and "Cancel a blocked run"."""
    runner = _FakeRunner()
    live = _live_runs(tmp_path, runner)
    port, stop = _serve_runs(live)
    try:
        offer = _call(port, "/runs")[1]
        assert offer["enabled"] is True and offer["busy"] is None and "check" in offer["commands"]
        code, started = _call(port, "/run", CHECK_DRC, RUN_OK)
        assert code == 202
        job = started["job"]
        code, busy = _call(port, "/run", CHECK_DRC, RUN_OK)
        assert code == 409 and busy["job"] == job
        running = _call(port, f"/run/{job}")[1]
        assert running["state"] == "running" and running["progress"][0]["step"] == "drc.kicad"
        assert _call(port, "/runs")[1]["busy"]["job"] == job
        assert _call(port, f"/run/{job}/cancel", {}, RUN_OK)[0] == 202
        ended = _until(port, job)
        assert ended["state"] == "cancelled" and "review" not in ended and live.checks == {}
        code, again = _call(port, "/run", CHECK_DRC, RUN_OK)
        assert code == 202 and again["job"] != job
        runner.release.set()
        assert _until(port, again["job"])["state"] == "done"
        assert _call(port, "/run/" + "0" * 32)[0] == 404
        assert _call(port, "/run", {"command": "tidy", "doc": "doc1"}, RUN_OK)[0] == 400
        assert live.jobs.counts == {"cancelled": 1, "done": 1}
    finally:
        stop.set()


def test_run_refused_with_no_run(tmp_path: Path) -> None:
    """``--no-run``: the run routes answer 403 and ``GET /runs`` says why."""
    runner = _FakeRunner()
    port, stop = _serve_runs(_live_runs(tmp_path, runner, runs_enabled=False))
    bare_port, bare_stop = _serve_runs(server.Live(load_tree(BOARD), _build))
    try:
        offer = _call(port, "/runs")[1]
        assert offer["enabled"] is False and "--no-run" in offer["reason"]
        assert _call(port, "/run", CHECK_DRC, RUN_OK)[0] == 403
        assert _call(bare_port, "/run", CHECK_DRC, RUN_OK)[0] == 403
        assert runner.started == []
    finally:
        stop.set()
        bare_stop.set()


def test_run_result_fills_review_and_check_of_its_document_only(tmp_path: Path) -> None:
    """A finished run's derived results: the review and the check of its own document (a stale document's
    result does not replace another's), with the reply's evidence unchanged."""
    reply = {
        "command": "check",
        "issues": [{"code": "kicad.drc.clearance", "severity": "error", "message": "gap", "where": "@1,2"}],
        "result": {
            "stages": [{"name": "drc.kicad", "status": "errors", "evidence": {"level": "KICAD-VERIFIED"}}]
        },
        "evidence": {"level": "KICAD-VERIFIED", "oracle": "kicad-cli 10.0.7"},
    }
    runner = _FakeRunner(reply)
    seen: list[tuple[str, str]] = []

    def derive(path: Path, command: str, envelope: dict[str, Any]) -> dict[str, Any]:
        seen.append((path.name, command))
        cards = [{"id": "drc", "state": "failed"}]
        return {"check": {"findings": envelope["issues"]}, "review": {"cards": cards}}

    folder = tmp_path / "a"
    folder.mkdir()
    shutil.copy(BOARD, folder / BOARD.name)
    (folder / "b.kicad_pcb").write_bytes(BOARD.read_bytes())
    live = server.Live(
        load_tree(folder), _build, runner=runner, choices=Choices(stages=("drc.kicad",)), derive=derive
    )
    port, stop = _serve_runs(live)
    try:
        runner.release.set()
        job = _call(port, "/run", CHECK_DRC | {"doc": "doc2"}, RUN_OK)[1]["job"]
        state = _until(port, job)
        assert state["doc"] == "doc2" and state["exit"] == 5
        assert state["review"]["cards"][0]["state"] == "failed"
        assert state["check"]["findings"][0]["code"] == "kicad.drc.clearance"
        assert state["envelope"]["evidence"]["oracle"] == "kicad-cli 10.0.7"
        assert list(live.checks) == ["doc2"] and seen == [(BOARD.name, "check")]
    finally:
        stop.set()


def test_run_check_with_the_real_runner_keeps_each_stage_evidence(tmp_path: Path) -> None:
    """Scenario "A check run from the page": the real child-process runner runs ``check --stages
    model.validate,copper.clearance`` and the review holds those two stages with their evidence."""
    from fenolite.cli._viewrun import ChildRunner
    from fenolite.cli.api import discover
    from fenolite.view import check_overlay, project_review

    board = tmp_path / BOARD.name
    shutil.copy(BOARD, board)
    tree = load_tree(board)
    session: dict[str, Any] = {}

    def derive(path: Path, command: str, envelope: dict[str, Any]) -> dict[str, Any]:
        scene = _build(path)
        session["reply"] = project_review.merge(session.get("reply"), envelope)
        return {
            "check": check_overlay.overlay(session["reply"], scene),
            "review": project_review.status(scene, session["reply"]),
        }

    runner = ChildRunner(discover(), root=tree.root, timeout=300)
    choices = Choices(stages=("model.validate", "copper.clearance", "drc.kicad"))
    live = server.Live(tree, _build, runner=runner, choices=choices, derive=derive)
    port, stop = _serve_runs(live)
    try:
        body = {
            "command": "check",
            "doc": "doc1",
            "options": {"stages": ["model.validate", "copper.clearance"]},
        }
        code, started = _call(port, "/run", body, RUN_OK)
        assert code == 202, started
        state = _until(port, started["job"], seconds=300)
        assert state["state"] == "done" and state["exit"] in (0, 5), state
        assert state["progress"], "the --progress records reach the job"
        stages = {s["name"]: s for s in state["review"]["stages"]}
        assert set(stages) == {"model.validate", "copper.clearance"}
        recorded = {s["name"]: s for s in state["envelope"]["result"]["stages"]}
        for name, stage in stages.items():
            assert stage["evidence"] == project_review.evidence(recorded[name]["evidence"])
        cards = {c["id"]: c["state"] for c in state["review"]["cards"]}
        assert cards["drc"] == "not-run" and cards["model"] != "not-run" and cards["clearance"] != "not-run"
    finally:
        stop.set()


def test_roles_run_with_the_real_runner(tmp_path: Path) -> None:
    """Change c0305: the run ``roles`` is ``fenolite roles --check`` on the board in a child process; its
    reply becomes the board's role data."""
    from _roles import reference_board

    from fenolite.cli._viewrun import ChildRunner
    from fenolite.cli.api import discover
    from fenolite.view import roles
    from fenolite.view.runs import RunRequest

    board = reference_board("buck_shunt", "bad", tmp_path / "out")
    tree = load_tree(board)
    doc = tree.document(board.name)
    assert doc is not None

    def derive(path: Path, command: str, envelope: dict[str, Any]) -> dict[str, Any]:
        assert command == "roles"
        return {"roles": roles.overlay(envelope, _build(path))}

    runner = ChildRunner(discover(), root=tree.root, timeout=300)
    assert runner.words(RunRequest("roles", doc.id, board, {"path": board.name})) == [
        "roles",
        "--check",
        "--",
        board.name,
    ]
    live = server.Live(tree, _build, runner=runner, choices=Choices(), derive=derive)
    port, stop = _serve_runs(live)
    try:
        code, started = _call(port, "/run", {"command": "roles", "doc": doc.id}, RUN_OK)
        assert code == 202, started
        state = _until(port, started["job"], seconds=300)
        assert state["state"] == "done" and state["exit"] in (0, 5), state
        data = state["roles"]
        assert data["schema"] == roles.SCHEMA and {g["name"] for g in data["groups"]} >= {
            "hot_SW",
            "kelvin_R12",
        }
        assert len(data["findings"]) == len(state["envelope"]["issues"])
    finally:
        stop.set()


# ------------------------------------------------------------------------------------------ actions (c0303)

ACTION_OK = {"Content-Type": "application/json", "X-Fenolite-Action": "1"}
SILK = {"action": "silk", "doc": "doc1", "options": {"designators": True}}


class _FakeTools(_FakeRunner):
    """A fake runner that also answers the action tools; ``words`` records every command line."""

    def __init__(self) -> None:
        super().__init__({"command": "silk", "issues": [], "result": {}})
        self.words: list[list[str]] = []

    def start_words(self, words: list[str], on_progress: Any) -> _Handle:
        self.words.append(list(words))
        return _Handle(self)

    def staged(self, plan_id: str) -> dict[str, Any] | None:
        return None

    def staged_bytes(self, plan_id: str, row: dict[str, Any]) -> bytes | None:
        return None

    def preview(self, board: Path, data: bytes) -> dict[str, Any] | None:
        return None

    def keep_receipt(self, envelope: dict[str, Any]) -> Path:
        return Path("unused")

    def receipt_file(self, receipt_id: str) -> Path:
        return Path("unused")


def test_actions_off_refuses_every_action_route(tmp_path: Path) -> None:
    """Scenario "Actions not allowed"."""
    runner = _FakeTools()
    port, stop = _serve_runs(_live_runs(tmp_path, runner))
    try:
        offer = _call(port, "/actions?doc=doc1", None, {"X-Fenolite-Action": "1"})[1]
        assert offer["enabled"] is False and "--allow-actions" in offer["reason"] and "token" not in offer
        for route in ("/action/plan", "/action/confirm", "/action/undo"):
            assert _call(port, route, SILK, ACTION_OK | {"X-Fenolite-Token": "x"})[0] == 403
        assert runner.words == [] and runner.started == []
    finally:
        stop.set()


def test_action_guard_needs_the_token_and_one_job_at_a_time(tmp_path: Path) -> None:
    """Scenario "A request without the token"."""
    runner = _FakeTools()
    live = _live_runs(tmp_path, runner, actions=runner)
    port, stop = _serve_runs(live)
    try:
        bare = _call(port, "/actions?doc=doc1")[1]
        assert bare["enabled"] is True and "token" not in bare
        assert _call(port, "/actions", None, {"X-Fenolite-Action": "1", "Host": "evil.example"})[0] == 403
        offer = _call(port, "/actions?doc=doc1", None, {"X-Fenolite-Action": "1"})[1]
        token = offer["token"]
        assert len(token) == 32 and offer["actions"]["silk"]["available"] is True
        assert _call(port, "/action/plan", SILK, ACTION_OK)[0] == 403
        assert _call(port, "/action/plan", SILK, ACTION_OK | {"X-Fenolite-Token": "0" * 32})[0] == 403
        signed = ACTION_OK | {"X-Fenolite-Token": token}
        assert _call(port, "/action/plan", SILK, signed | {"Origin": "http://evil.example"})[0] == 403
        assert (
            _call(
                port, "/action/plan", SILK, {"Content-Type": "application/json", "X-Fenolite-Token": token}
            )[0]
            == 403
        )
        assert runner.words == []
        code, started = _call(port, "/run", CHECK_DRC, RUN_OK)
        assert code == 202
        code, busy = _call(port, "/action/plan", SILK, signed)
        assert code == 409 and busy["job"] == started["job"] and runner.words == []
        assert _call(port, "/action/confirm", {"job": started["job"]}, signed)[0] in (400, 409)
        runner.release.set()
        _until(port, started["job"])
        code, planned = _call(port, "/action/plan", SILK, signed)
        assert code == 202
        assert runner.words == [["silk", "--designators", "--dry-run", "--", BOARD.name]]
        state = _until(port, planned["job"])
        assert state["kind"] == "plan" and state["plan"] is None  # the fake reply holds no plan
        code, refused = _call(port, "/action/confirm", {"job": planned["job"]}, signed)
        assert code == 400 and "cannot be confirmed" in refused["error"]
        assert _call(port, "/action/confirm", {"job": "f" * 32}, signed)[0] == 400
        assert _call(port, "/action/undo", {"receipt": "0123456789abcdef"}, signed)[0] == 400
        assert _call(port, "/action/plan", SILK | {"options": {"no_backup": True}}, signed)[0] == 400
    finally:
        stop.set()
