# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The jobs of the viewer's live server: runs of read-only commands (change c0302) and the plans, confirms
and undos of writing actions (change c0303), one at a time.

A job has a 128-bit random id, a kind (``run``, ``plan``, ``confirm`` or ``undo``), the command and the
document it works on, its last progress records and, once it ends, its state (``done``, ``failed``,
``cancelled`` or ``timeout``), exit code, envelope or error object and what the server derived from them.
:class:`Jobs` refuses a new job while one runs (:class:`Busy`) and keeps at most :data:`KEEP` finished jobs;
a finished job is dropped when a job of the same kind, command, action and document starts. Standard
library only.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from fenolite.view.runs import Handle, Outcome

KEEP = 16
"""The finished jobs a server keeps."""
PROGRESS = 50
"""The progress records a job keeps (the last ones)."""
Json = dict[str, Any]


class Busy(Exception):
    """A job runs already; :attr:`job` is that job."""

    def __init__(self, job: Job) -> None:
        super().__init__(f"job {job.id} ({job.command}) runs")
        self.job = job


def _records() -> deque[Json]:
    return deque(maxlen=PROGRESS)


@dataclass
class Job:
    """One job of the page (module docstring)."""

    id: str
    kind: str
    command: str
    doc: str
    action: str | None = None
    started: float = field(default_factory=time.monotonic)
    started_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    state: str = "running"
    progress: deque[Json] = field(default_factory=_records)
    outcome: Outcome | None = None
    derived: Json = field(default_factory=lambda: cast("Json", {}))
    handle: Handle | None = None
    cancel_asked: bool = False
    ended: float | None = None
    private: Json = field(default_factory=lambda: cast("Json", {}))
    """What the server keeps for itself (the words of a plan, its plan id); never sent to the page."""

    def to_json(self) -> Json:
        out: Json = {
            "job": self.id,
            "kind": self.kind,
            "state": self.state,
            "command": self.command,
            "action": self.action,
            "doc": self.doc,
            "started": self.started_at,
            "elapsed": round((self.ended or time.monotonic()) - self.started, 1),
            "progress": list(self.progress),
        }
        if self.outcome is not None:
            out["exit"] = self.outcome.exit
            if self.outcome.envelope is not None:
                out["envelope"] = self.outcome.envelope
            if self.outcome.error is not None:
                out["error"] = self.outcome.error
        return out | self.derived


class Jobs:
    """The job table of one server (module docstring)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.jobs: OrderedDict[str, Job] = OrderedDict()
        self.counts: Counter[str] = Counter()
        """Finished runs (kind ``run``) by final state (``result.serve.runs``)."""

    def running(self) -> Job | None:
        return next((job for job in self.jobs.values() if job.state == "running"), None)

    def begin(self, kind: str, command: str, doc: str, action: str | None = None) -> Job:
        """A new running job; :class:`Busy` while another runs."""
        with self.lock:
            busy = self.running()
            if busy is not None:
                raise Busy(busy)
            same = [
                key
                for key, job in self.jobs.items()
                if (job.kind, job.command, job.action, job.doc) == (kind, command, action, doc)
            ]
            for key in same:
                del self.jobs[key]
            job = Job(secrets.token_hex(16), kind, command, doc, action)
            self.jobs[job.id] = job
            while len(self.jobs) > KEEP:
                oldest = next(key for key, kept in self.jobs.items() if kept.state != "running")
                del self.jobs[oldest]
            return job

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def progress(self, job: Job, record: Json) -> None:
        with self.lock:
            job.progress.append(dict(record))

    def finish(self, job: Job, outcome: Outcome, derived: Json | None = None) -> None:
        with self.lock:
            job.outcome, job.state, job.ended = outcome, outcome.state, time.monotonic()
            job.derived = dict(derived or {})
            if job.kind == "run":
                self.counts[outcome.state] += 1

    def cancel(self, job: Job) -> bool:
        """Ask a running job to stop; ``False`` when it already ended."""
        with self.lock:
            if job.state != "running":
                return False
            job.cancel_asked = True
            handle = job.handle
        if handle is not None:
            handle.cancel()
        return True

    def attach(self, job: Job, handle: Handle) -> None:
        """Record the handle of a started job, cancelling it at once when the cancel came first."""
        with self.lock:
            job.handle = handle
            asked = job.cancel_asked
        if asked:
            handle.cancel()


__all__ = ["KEEP", "PROGRESS", "Busy", "Job", "Jobs"]
