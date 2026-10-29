# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The local live server of the viewer (capability board-viewer, "Live server").

Routes: ``/`` the page, ``/project.json`` the tree, ``/scene/<id>.json`` the scene of one document (built on
first request and cached), ``/version/<id>`` its state, and ``/marks`` the review marks (change c0189): a
``POST`` of one mark is written to the ``--marks`` file, and only when ``view`` was given one. A watcher
checks the documents whose scene was built: when a file's size and time change and then stay the same for
one more check (a tool or a sync client may still be writing), the scene is built again and the page reloads
it, keeping its view. A scene may be refined in the background after it is first served (the body models,
change c0193): the refined scene is a new version, which the page reloads. Only the loopback address is
bound; nothing leaves the machine.

Change c0245 adds the run routes: ``GET /runs`` (what the page may run), ``POST /run`` (start one read-only
command of ``fenolite.view.runs.ALLOWED`` on a document of the tree), ``GET /run/<job>`` (its state,
progress and results) and ``POST /run/<job>/cancel``. Every ``POST`` passes one guard (:func:`guarded`): this
server's ``Host``, a same-server ``Origin`` when one is sent, the route's custom header, a JSON type and a
bounded body. The runner is injected by ``cmd_view``, as the scene builder is.
"""

from __future__ import annotations

import hmac
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

from fenolite.core.errors import FormatError
from fenolite.view import review, runs
from fenolite.view.compact import compact
from fenolite.view.export import page
from fenolite.view.jobs import Busy, Job, Jobs
from fenolite.view.project import Document, ProjectTree
from fenolite.view.runs import Choices, Outcome, ProgressSink, Runner, RunRefused, RunRequest

HOST = "127.0.0.1"
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
ResultDeriver = Callable[[Path, str, dict[str, Any]], dict[str, Any]]
"""What the server shows of a finished run (``cmd_view``; change c0245): given the document's file, the
command and its envelope, the keys ``check`` and ``review`` (a ``check`` run, merged by stage with the earlier
ones), ``overlays`` and ``groups`` (an ``analyze`` run) or ``findings`` (``ready``, ``equivalent``)."""
NO_RUN = "this page was served with --no-run: run fenolite check in a terminal and reopen with --check FILE"


class Refused(Exception):
    """A request the server answers with ``code`` and ``message`` (and ``extra`` keys)."""

    def __init__(self, code: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


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
        runner: Runner | None = None,
        runs_enabled: bool = True,
        choices: Choices | None = None,
        derive: ResultDeriver | None = None,
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
        self.written = 0
        """How many marks the server wrote (``result.serve.marks_written``)."""
        self.runner, self.choices, self.derive = runner, choices or Choices(), derive
        self.runs_enabled = runs_enabled and runner is not None
        self.jobs = Jobs()
        self.checks: dict[str, dict[str, Any]] = {}
        """The check findings of a document as placed by its last run (c0245), by document id."""

    # ------------------------------------------------------------------ runs (change c0245)

    def runs(self) -> dict[str, Any]:
        """``GET /runs``: whether the page may run commands, which, and the running job."""
        busy = self.jobs.running()
        out: dict[str, Any] = {
            "enabled": self.runs_enabled,
            "commands": runs.offered(self.choices) if self.runs_enabled else {},
            "busy": busy.to_json() if busy is not None else None,
        }
        if not self.runs_enabled:
            out["reason"] = NO_RUN
        return out

    def start_run(self, body: bytes) -> Job:
        """``POST /run``: validate the request and start its job; :class:`Refused` says why not."""
        runner = self.runner
        if not self.runs_enabled or runner is None:
            raise Refused(403, NO_RUN)
        found = runs.request(_json_body(body), self.tree, self.choices)
        if isinstance(found, RunRefused):
            raise Refused(400, found.reason)
        job = self._begin("run", found.command, found.doc)
        self.log(f"view: run {found.command} on {found.path.name}")
        self._launch(job, lambda sink: runner.start(found, sink), lambda j, o: self._after_run(j, o, found))
        return job

    def _begin(self, kind: str, command: str, doc: str, action: str | None = None) -> Job:
        try:
            return self.jobs.begin(kind, command, doc, action)
        except Busy as busy:
            raise Refused(409, "a job runs already; wait for it or cancel it", job=busy.job.id) from busy

    def _launch(
        self,
        job: Job,
        start: Callable[[ProgressSink], Any],
        after: Callable[[Job, Outcome], dict[str, Any]],
    ) -> None:
        """Start ``job`` through ``start`` and finish it in a daemon thread with what ``after`` derives."""

        def sink(record: dict[str, Any]) -> None:
            self.jobs.progress(job, record)

        try:
            handle = start(sink)
        except Exception as exc:  # the runner could not start the child: the job fails, the server stays
            self.jobs.finish(job, Outcome("failed", error={"message": f"{type(exc).__name__}: {exc}"}))
            return
        self.jobs.attach(job, handle)

        def finish() -> None:
            try:
                outcome = handle.wait()
            except Exception as exc:  # a fault of the runner ends the job, not the server
                outcome = Outcome("failed", error={"message": f"{type(exc).__name__}: {exc}"})
            derived: dict[str, Any] = {}
            try:
                derived = after(job, outcome)
            except Exception as exc:  # the job keeps its envelope; the page says the results were not placed
                derived = {"note": f"the results could not be shown: {type(exc).__name__}: {exc}"}
                self.log(f"view: {job.command}: {derived['note']}")
            self.jobs.finish(job, outcome, derived)

        threading.Thread(target=finish, daemon=True).start()

    def _after_run(self, job: Job, outcome: Outcome, found: RunRequest) -> dict[str, Any]:
        doc = self.tree.document(job.doc)
        if outcome.exit not in (0, 5) or outcome.envelope is None or self.derive is None or doc is None:
            return {}
        assert doc.file is not None
        derived = self.derive(doc.file, found.command, outcome.envelope)
        if "check" in derived:
            with self.lock:
                self.checks[job.doc] = derived["check"]
            others = [d for d in self.states if d != job.doc]
            if others:  # the other documents built so far take the merged reply when they are read again
                threading.Thread(target=self._rebuild_ids, args=(others,), daemon=True).start()
        return derived

    def _rebuild_ids(self, ids: list[str]) -> None:
        for doc_id in ids:
            doc, state = self.tree.document(doc_id), self.states.get(doc_id)
            if doc is not None and state is not None and doc.file is not None:
                self._rebuild(doc, state)

    def job(self, job_id: str) -> dict[str, Any] | None:
        """``GET /run/<job>``: the job's state, progress and results; ``None`` for an unknown id."""
        found = self.jobs.get(job_id)
        if found is None:
            return None
        with self.jobs.lock:
            return found.to_json()

    def cancel(self, job_id: str) -> dict[str, Any]:
        """``POST /run/<job>/cancel``: ask the job to stop; it ends ``cancelled``."""
        found = self.jobs.get(job_id)
        if found is None:
            raise Refused(404, "no job of that id")
        self.jobs.cancel(found)
        return {"job": found.id, "state": found.state}

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


def _json_body(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Refused(400, f"the request is not JSON: {exc}") from exc


def _hosts(handler: BaseHTTPRequestHandler) -> set[str]:
    port = int(cast("tuple[str, int]", handler.server.server_address)[1])
    return {f"{HOST}:{port}", f"localhost:{port}"}


def own_host(handler: BaseHTTPRequestHandler) -> bool:
    """Whether a request names this server as its ``Host`` and, when it sends one, as its ``Origin`` (the
    reads of the run and action routes check it)."""
    allowed, origin = _hosts(handler), handler.headers.get("Origin")
    return handler.headers.get("Host") in allowed and not (
        origin and origin.split("//", 1)[-1] not in allowed
    )


def guarded(
    handler: BaseHTTPRequestHandler, header: str, limit: int, *, extra: dict[str, str] | None = None
) -> bytes:
    """The body of a ``POST`` that passes the guard of this server's writes and runs: its ``Host`` is this
    server's, its ``Origin`` (when sent) the same, it carries ``header: 1`` (and every ``extra`` header with
    its value), it is JSON and its body is 1 to ``limit`` bytes; :class:`Refused` (403 or 413) otherwise. A
    page of another site cannot send a custom header without a preflight, which this server never answers,
    and the ``Host`` check stops a name that resolves to this address (DNS rebinding)."""
    if not own_host(handler):
        raise Refused(403, "accepted from this server's own page only")
    if handler.headers.get(header) != "1" or not str(handler.headers.get("Content-Type", "")).startswith(
        "application/json"
    ):
        raise Refused(403, f"a request is JSON sent with {header}: 1")
    for name, value in (extra or {}).items():
        sent = handler.headers.get(name) or ""
        if not value or not hmac.compare_digest(sent.encode("utf-8"), value.encode("utf-8")):
            raise Refused(403, f"the request lacks this session's {name}")
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        length = 0
    if not 0 < length <= limit:
        raise Refused(413, f"a request is 1 to {limit} bytes")
    return handler.rfile.read(length)


def serve(live: Live, port: int = 8765) -> ThreadingHTTPServer:
    """A server for ``live`` on the loopback address, not yet serving; ``port`` 0 takes a free port."""
    tree_json = live.tree.to_json() | {"open": live.open_id, "select": live.select}

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

        def _json(self, code: int, value: Any) -> None:
            self._send(code, json.dumps(value).encode("utf-8"), "application/json")

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
            elif path == "/runs" or path.startswith("/run/"):
                self._run_read(path)
            else:
                self._send(404, b"not found", "text/plain")

        def _run_read(self, path: str) -> None:
            if not own_host(self):
                self._refuse(403, "accepted from this server's own page only")
            elif path == "/runs":
                self._json(200, live.runs())
            else:
                found = live.job(path[len("/run/") :])
                if found is None:
                    self._refuse(404, "no job of that id")
                else:
                    self._json(200, found)

        def _refuse(self, code: int, message: str, **extra: Any) -> None:
            self._json(code, {"error": message, **extra})

        def do_POST(self) -> None:  # noqa: N802 - the name http.server calls
            path = unquote(self.path.split("?", 1)[0])
            try:
                if path == "/marks":
                    self._marks(guarded(self, REVIEW_HEADER, MARK_BYTES))
                elif path == "/run":
                    job = live.start_run(guarded(self, runs.RUN_HEADER, runs.RUN_BYTES))
                    self._json(202, {"job": job.id})
                elif path.startswith("/run/") and path.endswith("/cancel"):
                    guarded(self, runs.RUN_HEADER, runs.RUN_BYTES)
                    self._json(202, live.cancel(path[len("/run/") : -len("/cancel")]))
                else:
                    self._refuse(404, "not found")
            except Refused as refused:
                self._refuse(refused.code, refused.message, **refused.extra)

        def _marks(self, body: bytes) -> None:
            try:
                marks = live.post_mark(body)
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


__all__ = ["HOST", "Live", "Refused", "guarded", "own_host", "run", "serve"]
