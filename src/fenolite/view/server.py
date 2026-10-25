# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The local live server of the viewer (capability board-viewer, "Live server").

Routes: ``/`` the page, ``/project.json`` the tree, ``/scene/<id>.json`` the scene of one document (built on
first request and cached), ``/version/<id>`` its state. A watcher checks the documents whose scene was built:
when a file's size and time change and then stay the same for one more check (a tool or a sync client may
still be writing), the scene is built again and the page reloads it, keeping its view. Only the loopback
address is bound; nothing leaves the machine.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fenolite.view.compact import compact
from fenolite.view.export import page
from fenolite.view.project import Document, ProjectTree

HOST = "127.0.0.1"
PERIOD = 2.0

SceneBuilder = Callable[[Path], dict[str, Any]]
"""Builds the scene of a board file (``cmd_view`` passes the backend read; tests pass their own)."""


@dataclass
class _State:
    scene: bytes = b""
    version: str | None = None
    building: bool = False
    error: str | None = None
    updated: str | None = None
    signature: tuple[int, int] | None = None
    pending: tuple[int, int] | None = None


class Live:
    """The documents of a tree and the scenes built so far, with their versions."""

    def __init__(
        self,
        tree: ProjectTree,
        build: SceneBuilder,
        *,
        overlays: list[dict[str, Any]] | None = None,
        open_id: str | None = None,
        log: Callable[[str], None] = lambda _m: None,
    ) -> None:
        self.tree, self.build, self.overlays, self.open_id, self.log = (
            tree,
            build,
            overlays or [],
            open_id,
            log,
        )
        self.states: dict[str, _State] = {}
        self.lock = threading.Lock()

    @staticmethod
    def _signature(path: Path) -> tuple[int, int] | None:
        try:
            s = path.stat()
        except OSError:
            return None
        return (s.st_size, s.st_mtime_ns)

    def _rebuild(self, doc: Document, state: _State) -> None:
        state.building = True
        try:
            assert doc.file is not None
            scene = self.build(doc.file)
            scene["overlays"] = list(scene.get("overlays", [])) + self.overlays
            data = json.dumps(compact(scene), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            with self.lock:
                state.scene = data
                state.version = f"{scene['meta'].get('sha256', '')[:12]}-{time.time_ns()}"
                state.error = None
                state.updated = datetime.now().strftime("%H:%M:%S")
        except Exception as exc:  # keep serving the last good scene, and say why the new one failed
            state.error = f"{type(exc).__name__}: {exc}"
            self.log(f"view: {doc.name} could not be read: {state.error}")
        finally:
            state.building = False

    def scene(self, doc_id: str) -> bytes | None:
        """The scene of a viewable document, built when first asked for; ``None`` for any other id."""
        doc = self.tree.document(doc_id)
        if doc is None or not doc.viewable or doc.file is None or not doc.present:
            return None
        state = self.states.get(doc.id)
        if state is None:
            state = self.states[doc.id] = _State(signature=self._signature(doc.file))
            self._rebuild(doc, state)
        return state.scene

    def version(self, doc_id: str) -> dict[str, Any]:
        state = self.states.get(doc_id)
        if state is None:
            return {"version": None, "building": False, "error": None, "updated": None}
        return {
            "version": state.version,
            "building": state.building,
            "error": state.error,
            "updated": state.updated,
        }

    def check(self) -> list[str]:
        """One watcher step: the ids whose scene was built again."""
        rebuilt: list[str] = []
        for doc_id, state in list(self.states.items()):
            doc = self.tree.document(doc_id)
            if doc is None or doc.file is None:
                continue
            sig = self._signature(doc.file)
            if sig is None or sig == state.signature:
                state.pending = None
                continue
            if state.pending == sig:
                state.signature, state.pending = sig, None
                self.log(f"view: {doc.name} changed; reading it again")
                self._rebuild(doc, state)
                rebuilt.append(doc_id)
            else:
                state.pending = sig
        return rebuilt

    def watch(self, stop: threading.Event, period: float = PERIOD) -> None:
        while not stop.wait(period):
            self.check()


def serve(live: Live, port: int = 8765) -> ThreadingHTTPServer:
    """A server for ``live`` on the loopback address, not yet serving; ``port`` 0 takes a free port."""
    tree_json = live.tree.to_json() | {"open": live.open_id}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the silent request log
            pass

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
            path = unquote(self.path.split("?", 1)[0])
            if path in ("/", "/index.html"):
                self._send(200, page(live=True).encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/project.json":
                self._send(200, json.dumps(tree_json).encode("utf-8"), "application/json")
            elif path.startswith("/scene/") and path.endswith(".json"):
                body = live.scene(path[len("/scene/") : -len(".json")])
                if body is None:
                    self._send(404, b"no viewable document of that id", "text/plain")
                else:
                    self._send(200, body, "application/json")
            elif path.startswith("/version/"):
                state = live.version(path[len("/version/") :])
                self._send(200, json.dumps(state).encode("utf-8"), "application/json")
            else:
                self._send(404, b"not found", "text/plain")

    return ThreadingHTTPServer((HOST, port), Handler)


def run(live: Live, httpd: ThreadingHTTPServer, *, until: threading.Event | None = None) -> None:
    """Serve ``httpd`` and watch ``live`` until ``until`` is set or the process is interrupted."""
    stop = until or threading.Event()
    watcher = threading.Thread(target=live.watch, args=(stop,), daemon=True)
    watcher.start()
    server = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    server.start()
    try:
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()


__all__ = ["HOST", "Live", "run", "serve"]
