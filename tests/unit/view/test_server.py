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
