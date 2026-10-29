# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The runner of ``fenolite view --serve``: what runs the page's read-only commands (change c0302) in a
child process (:mod:`fenolite.cli.childrun`, the core ``fenolite mcp`` uses).

A run's words come from the command's own parser through the MCP catalog (``Catalog.command_line``, built
read-only and only for ``fenolite.view.runs.ALLOWED``), so no word of the page's request reaches the command
line unparsed. Each job runs in a daemon thread in the project folder; ``cancel`` stops its process group and
the time limit ends it ``timeout``. The writing actions of change c0303 run their words, built by the server
from fixed templates, through the same core; this module also reads their staged plans, keeps their
receipts in the state folder and gives the board preview of a plan. The view package receives this runner
from ``cmd_view``: it imports nothing of ``cli``.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from fenolite.cli import plans
from fenolite.cli.api import Command
from fenolite.cli.childrun import ChildResult, run_child
from fenolite.core.state import state_dir
from fenolite.mcp.tools import Catalog, InputRefused, tool_name
from fenolite.view.runs import ALLOWED, Outcome, RunRequest

Json = dict[str, Any]
ProgressSink = Callable[[Json], None]
RECEIPTS = "view-receipts"
"""The folder of the state folder that holds the receipts of the page's writes (change c0303)."""


def outcome_of(done: ChildResult) -> Outcome:
    """The page's view of how a child ended."""
    if done.stopped is not None:
        return Outcome(done.stopped, done.exit, error=done.value)
    if done.exit in (0, 5):
        return Outcome("done", done.exit, envelope=done.value)
    return Outcome("failed", done.exit, error=done.value)


class ChildHandle:
    """One job: the child runs in a daemon thread; ``cancel`` sets its event, ``wait`` gives the outcome."""

    def __init__(self, words: Sequence[str], *, root: Path, timeout: float, on_progress: ProgressSink,
                 executable: Sequence[str] | None) -> None:  # fmt: skip
        self.cancelled = threading.Event()
        self._outcome: Outcome | None = None
        self._done = threading.Event()

        def work() -> None:
            try:
                self._outcome = outcome_of(
                    run_child(
                        words,
                        root=root,
                        timeout=timeout,
                        cancelled=self.cancelled,
                        progress=on_progress,
                        executable=executable,
                        where=words[0],
                    )  # fmt: skip
                )
            except OSError as exc:  # the interpreter could not be started
                self._outcome = Outcome("failed", error={"code": "FEN-1001", "message": str(exc)})
            finally:
                self._done.set()

        threading.Thread(target=work, daemon=True).start()

    def cancel(self) -> None:
        self.cancelled.set()

    def wait(self) -> Outcome:
        self._done.wait()
        assert self._outcome is not None
        return self._outcome


class ChildRunner:
    """The runner of the page's jobs in ``root``, each stopped after ``timeout`` seconds."""

    def __init__(
        self,
        commands: Mapping[str, Command],
        *,
        root: Path,
        timeout: float,
        executable: Sequence[str] | None = None,
        preview: Callable[[Path, Path], Json | None] | None = None,
    ) -> None:
        self.catalog = Catalog(commands, read_only=True, only=ALLOWED)
        self.root, self.timeout, self.executable = root.resolve(), timeout, executable
        self._preview = preview
        """``(staged file, board) -> changes``, given by ``cmd_view``."""

    def words(self, request: RunRequest) -> list[str]:
        """The command line of a validated run; ``InputRefused`` when the catalog does not accept it.
        ``roles`` has no read-only tool in the catalog: its words are the fixed ``roles --check -- BOARD``
        (change c0305)."""
        if request.command == "roles":
            return ["roles", "--check", "--", str(request.arguments["path"])]
        return self.catalog.command_line(tool_name(request.command), request.arguments, dry_run=False)

    def start(self, request: RunRequest, on_progress: ProgressSink) -> ChildHandle:
        try:
            words = self.words(request)
        except InputRefused as refused:
            raise ValueError(refused.error.message) from refused
        return self.start_words(words, on_progress)

    def start_words(self, words: Sequence[str], on_progress: ProgressSink) -> ChildHandle:
        """Run ``words`` (built by the server from a fixed template) as a job."""
        return ChildHandle(
            list(words),
            root=self.root,
            timeout=self.timeout,
            on_progress=on_progress,
            executable=self.executable,
        )

    # ------------------------------------------------------------------ actions (change c0303)

    def staged(self, plan_id: str) -> Json | None:
        """``{"command", "cwd", "writes"}`` of the staged plan ``plan_id``; ``None`` when the store holds none
        or it is damaged."""
        try:
            found = plans.load(state_dir(), plan_id)
        except plans.DamagedPlan:
            return None
        if found is None:
            return None
        return {"command": found.command, "cwd": found.cwd, "writes": [dict(row) for row in found.writes]}

    def staged_bytes(self, plan_id: str, row: Json) -> bytes | None:
        try:
            found = plans.load(state_dir(), plan_id)
            return None if found is None else found.data(row)
        except plans.DamagedPlan:
            return None

    def preview(self, board: Path, data: bytes) -> Json | None:
        """The changes of ``data`` (the staged bytes of ``board``) against ``board``; the bytes are read from
        a temporary file of the state folder with the board's suffix."""
        if self._preview is None:
            return None
        folder = _state() / "view-preview"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (hashlib.sha256(data).hexdigest()[:16] + board.suffix)
        path.write_bytes(data)
        try:
            return self._preview(path, board)
        finally:
            path.unlink(missing_ok=True)

    def receipt_file(self, receipt_id: str) -> Path:
        if not plans.PLAN_ID.fullmatch(receipt_id):
            raise ValueError(f"{receipt_id!r} is not a receipt id")
        return _state() / RECEIPTS / f"{receipt_id}.json"

    def keep_receipt(self, envelope: Json) -> Path:
        """Write the envelope of a confirmed write to ``view-receipts/<receipt id>.json`` of the state folder,
        where ``restore`` reads it."""
        receipt = cast("Json", envelope["receipt"])
        path = self.receipt_file(str(receipt["id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def _state() -> Path:
    folder = state_dir()
    if folder is None:
        raise OSError("the state folder is off (FENOLITE_STATE_DIR=off): the page cannot write")
    return folder


__all__ = ["ChildHandle", "ChildRunner", "outcome_of"]
