# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The live server of the viewer (capability board-viewer, "Live server"): loopback only, scenes on request,
a saved board read again after it settles."""

from __future__ import annotations

import json
import os
import shutil
import threading
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
