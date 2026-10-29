# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The local live server of the viewer (capability board-viewer, "Live server").

Routes: ``/`` the page, ``/panel/<name>`` the page showing one floated panel (change c0245),
``/project.json`` the tree, ``/scene/<id>.json`` the scene of one document (built on first request and
cached), ``/version/<id>`` its state, and ``/marks`` the review marks (change c0189): a ``POST`` of one mark
is written to the ``--marks`` file, and only when ``view`` was given one. A watcher checks the documents
whose scene was built: when a file's size and time change and then stay the same for one more check (a tool
or a sync client may still be writing), the scene is built again and the page reloads it, keeping its view. A
scene may be refined in the background after it is first served (the body models, change c0193): the
refined scene is a new version, which the page reloads. Only the loopback address is
bound; nothing leaves the machine.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, quote, unquote

from fenolite.core.errors import FormatError
from fenolite.view import review
from fenolite.view.compact import compact
from fenolite.view.export import page
from fenolite.view.project import Document, ProjectTree

HOST = "127.0.0.1"
PANEL_PATH = re.compile(r"/panel/[a-z][a-z0-9-]{0,31}")
"""The address of a floated panel window (change c0245, decision 4)."""
PERIOD = 2.0
MARK_BYTES = 64 * 1024
"""The largest body of a ``POST /marks``."""
REVIEW_HEADER = "X-Fenolite-Review"
"""The header a ``POST /marks`` must carry: a page of another site cannot send it without a preflight that
this server never answers, so it cannot write marks."""

SceneBuilder = Callable[[Path], dict[str, Any]]
"""Builds the scene of a board file (``cmd_view`` passes the backend read; tests pass their own)."""
SceneRefiner = Callable[[Path, dict[str, Any]], "dict[str, Any] | None"]
"""Refines a built scene in the background (``cmd_view`` places the body models, change c0193); ``None``
keeps the scene as it was."""


@dataclass
class _State:
    scene: bytes = b""
    generation: int = 0
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
        marks_file: Path | None = None,
        select: str | None = None,
        refine: SceneRefiner | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        self.tree, self.build, self.overlays, self.open_id, self.log = (
            tree,
            build,
            overlays or [],
            open_id,
            log,
        )
        self.refine = refine
        self.states: dict[str, _State] = {}
        self.lock = threading.Lock()
        self.marks_file, self.select = marks_file, select
        self.settings: dict[str, Any] = settings or {}
        """The workbench options of change c0245 that the page reads from ``/project.json``."""
        self.written = 0
        """How many marks the server wrote (``result.serve.marks_written``)."""

    def marks(self) -> list[dict[str, Any]]:
        """The marks of the ``--marks`` file; empty without one."""
        if self.marks_file is None:
            return []
        return [dict(m) for m in review.to_json(review.load(self.marks_file))]

    def post_mark(self, body: bytes) -> list[dict[str, Any]]:
        """Add, replace or remove one mark in the ``--marks`` file, in one atomic replace; ``FormatError`` for
        a malformed mark, ``PermissionError`` when ``view`` was given no file."""
        if self.marks_file is None:
            raise PermissionError("this page was served without --marks: marks are kept in the browser")
        try:
            raw: Any = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise FormatError(f"the mark is not JSON: {exc}") from exc
        with self.lock:
            found = review.with_mark(review.load(self.marks_file), raw)
            review.write_atomic(self.marks_file, review.dumps(found))
            self.written += 1
        self.log(f"view: review marks saved to {self.marks_file.name}")
        return [dict(m) for m in review.to_json(found)]

    @staticmethod
    def _signature(path: Path) -> tuple[int, int] | None:
        try:
            s = path.stat()
        except OSError:
            return None
        return (s.st_size, s.st_mtime_ns)

    def _store(self, state: _State, scene: dict[str, Any], generation: int) -> bool:
        data = json.dumps(compact(scene), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        with self.lock:
            if state.generation != generation:
                return False
            state.scene = data
            state.version = f"{scene['meta'].get('sha256', '')[:12]}-{time.time_ns()}"
            state.error = None
            state.updated = datetime.now().strftime("%H:%M:%S")
            return True

    def _rebuild(self, doc: Document, state: _State) -> None:
        with self.lock:
            state.generation += 1
            generation = state.generation
            state.building = True
        try:
            assert doc.file is not None
            scene = self.build(doc.file)
            scene["overlays"] = list(scene.get("overlays", [])) + self.overlays
            stored = self._store(state, scene, generation)
            if stored and self.refine is not None:
                threading.Thread(
                    target=self._refine, args=(doc, state, scene, generation), daemon=True
                ).start()
        except Exception as exc:  # keep serving the last good scene, and say why the new one failed
            error = f"{type(exc).__name__}: {exc}"
            with self.lock:
                if state.generation == generation:
                    state.error = error
            self.log(f"view: {doc.name} could not be read: {error}")
        finally:
            with self.lock:
                if state.generation == generation:
                    state.building = False

    def _refine(self, doc: Document, state: _State, scene: dict[str, Any], generation: int) -> None:
        """Publish only in the generation captured by the rebuild, even if this worker starts late."""
        assert doc.file is not None and self.refine is not None
        try:
            refined = self.refine(doc.file, scene)
        except Exception as exc:  # the scene already served stays; the reason is logged
            self.log(f"view: {doc.name}: models not placed: {type(exc).__name__}: {exc}")
            return
        if refined is not None:
            self._store(state, refined, generation)

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
    tree_json = live.tree.to_json() | {"open": live.open_id, "select": live.select}
    if live.settings:
        tree_json["settings"] = live.settings
    hosts = {f"{HOST}:{{port}}", "localhost:{port}"}

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
                body = tree_json | {"marks_file": live.marks_file is not None, "marks": live.marks()}
                self._send(200, json.dumps(body).encode("utf-8"), "application/json")
            elif path == "/marks":
                self._send(200, json.dumps({"marks": live.marks()}).encode("utf-8"), "application/json")
            elif path.startswith("/scene/") and path.endswith(".json"):
                body = live.scene(path[len("/scene/") : -len(".json")])
                if body is None:
                    self._send(404, b"no viewable document of that id", "text/plain")
                else:
                    self._send(200, body, "application/json")
            elif path.startswith("/version/"):
                state = live.version(path[len("/version/") :])
                self._send(200, json.dumps(state).encode("utf-8"), "application/json")
            elif PANEL_PATH.fullmatch(path):
                # c0245: a panel floated into its own window is the same page, told which panel to show
                self.send_response(302)
                query = dict(parse_qsl(self.path.split("?", 1)[1])) if "?" in self.path else {}
                doc = "&doc=" + quote(query["doc"], safe="") if query.get("doc") else ""
                self.send_header("Location", "/#float=" + path[len("/panel/") :] + doc)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._send(404, b"not found", "text/plain")

        def _refuse(self, code: int, message: str) -> None:
            self._send(code, json.dumps({"error": message}).encode("utf-8"), "application/json")

        def do_POST(self) -> None:  # noqa: N802 - the name http.server calls
            port = int(cast("tuple[str, int]", self.server.server_address)[1])
            allowed = {h.format(port=port) for h in hosts}
            origin = self.headers.get("Origin")
            if unquote(self.path.split("?", 1)[0]) != "/marks":
                self._refuse(404, "not found")
            elif self.headers.get("Host") not in allowed or (
                origin and origin.split("//", 1)[-1] not in allowed
            ):
                self._refuse(403, "marks are accepted from this server's own page only")
            elif self.headers.get(REVIEW_HEADER) != "1" or not str(
                self.headers.get("Content-Type", "")
            ).startswith("application/json"):
                self._refuse(403, f"a mark is JSON sent with {REVIEW_HEADER}: 1")
            else:
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= MARK_BYTES:
                    self._refuse(413, f"a mark is at most {MARK_BYTES} bytes")
                    return
                try:
                    marks = live.post_mark(self.rfile.read(length))
                except PermissionError as exc:
                    self._refuse(403, str(exc))
                except FormatError as exc:
                    self._refuse(400, str(exc))
                except OSError as exc:
                    self._refuse(500, f"the review file was not written: {type(exc).__name__}")
                else:
                    self._send(200, json.dumps({"marks": marks}).encode("utf-8"), "application/json")

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
