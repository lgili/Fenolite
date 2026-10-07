# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reporter behind ``--progress``: one record per line on stderr (capability cli-contract, "Progress
on stderr").

A record says that a unit of work started (``step``), that it ended (``done``), or only that the command
still runs (``alive``, written by a daemon thread at least every ``interval`` seconds). Records carry
times, so no determinism rule covers them; they hold no path of the machine.
"""

from __future__ import annotations

import json
import threading
import time
from typing import TextIO

from fenolite.cli.output import OutputMode

INTERVAL = 10.0
"""Seconds between two records at most, while a command runs."""
EVENTS = ("step", "done", "alive")


class StderrProgress:
    """Writes progress records of ``command`` on ``stream``. ``start()`` begins the heartbeat and
    ``close()`` ends it; after ``close()`` nothing is written, so an error object stays the last line."""

    def __init__(self, mode: OutputMode, stream: TextIO, command: str, interval: float = INTERVAL) -> None:
        self.mode = mode
        self.stream = stream
        self.command = command
        self.interval = interval
        self._lock = threading.Lock()
        self._started = time.perf_counter()
        self._last = self._started
        self._current = ""
        self._closed = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None and not self._closed:
            self._thread = threading.Thread(target=self._beat, name="fenolite-progress", daemon=True)
            self._thread.start()

    def close(self) -> None:
        """Stop the heartbeat and write nothing more. Safe to call twice."""
        with self._lock:
            self._closed = True
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self.interval))
        self._thread = None

    def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
        self._current = name
        self._write("step", name, index, total, "")

    def done(self, name: str, *, detail: str = "") -> None:
        self._write("done", name, None, None, detail)
        if self._current == name:
            self._current = ""

    def _beat(self) -> None:
        while not self._stop.wait(self.interval / 4):
            if time.perf_counter() - self._last >= self.interval / 2:
                self._write("alive", self._current, None, None, "")

    def _write(self, event: str, step: str, index: int | None, total: int | None, detail: str) -> None:
        with self._lock:
            if self._closed:
                return
            now = time.perf_counter()
            self._last = now
            elapsed = max(0, round((now - self._started) * 1000))
            if self.mode == "json":
                record = {
                    "command": self.command,
                    "event": event,
                    "step": step,
                    "index": index,
                    "total": total,
                    "detail": detail,
                    "elapsed_ms": elapsed,
                }
                line = json.dumps({"progress": record}, ensure_ascii=False)
            else:
                count = f" [{index}/{total}]" if index is not None and total is not None else ""
                what = f" {step}" if step else ""
                tail = f": {detail}" if detail else ""
                line = f"progress: {self.command}: {event}{what}{count}{tail} ({elapsed} ms)"
            try:
                self.stream.write(line + "\n")
                self.stream.flush()
            except (OSError, ValueError):  # a closed stderr never fails the command
                self._closed = True


__all__ = ["EVENTS", "INTERVAL", "StderrProgress"]
