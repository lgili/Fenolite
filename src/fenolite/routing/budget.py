# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The one wall-clock budget of a routing job (capability routing, "Routing time budget"; change c0109).

A plugin builds one ``Budget`` at the start of its ``route()`` and starts every process through it: each
process gets the time that is left, and is killed when that time is spent. A process that was killed
gives no output the plugin may read: neither external router documents what it leaves behind when it is
stopped.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.errors import Issue

_REAP = 10.0
"""Seconds to wait for a killed process to release its pipes before its output is given up."""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """How one process ended. ``cut`` is true when the budget ended first; then ``returncode`` is
    ``None`` and the output is what was read before the kill. ``started`` is false when the budget was
    already spent and no process was started."""

    returncode: int | None
    stdout: str
    stderr: str
    seconds: float
    cut: bool
    started: bool = True


class Budget:
    """``seconds`` of wall-clock time on a monotonic clock that starts when the object is built."""

    def __init__(self, seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        if not seconds > 0:
            raise ValueError(f"a routing budget must be positive, got {seconds!r}")
        self.seconds = float(seconds)
        self._clock = clock
        self._start = clock()

    def spent(self) -> float:
        """Seconds since the budget started."""
        return self._clock() - self._start

    def left(self) -> float:
        """Seconds that remain, never below zero."""
        return max(0.0, self.seconds - self.spent())

    def run(
        self, args: Sequence[str], *, cwd: str | Path, env: Mapping[str, str] | None = None
    ) -> RunOutcome:
        """Run ``args`` with the time that is left and kill the process when it is spent.

        No process is started once the budget is spent. ``OSError`` of the start is the caller's.
        """
        limit = self.left()
        if limit <= 0:
            return RunOutcome(None, "", "", 0.0, cut=True, started=False)
        began = self._clock()
        process = subprocess.Popen(
            list(args),
            cwd=cwd,
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = process.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            # ``kill`` is SIGKILL on POSIX and TerminateProcess on Windows: no signal the tool may catch.
            process.kill()
            try:
                stdout, stderr = process.communicate(timeout=_REAP)
            except subprocess.TimeoutExpired:  # a grandchild still holds a pipe: give the output up
                stdout, stderr = "", ""
            return RunOutcome(None, stdout or "", stderr or "", self._clock() - began, cut=True)
        return RunOutcome(process.returncode, stdout or "", stderr or "", self._clock() - began, cut=False)


def exhausted(seconds: float, cut: int, not_attempted: int, where: str = "") -> Issue:
    """The one ``route.budget-exhausted`` warning of a job whose budget ended before every run was done:
    it names the budget, the nets of the run that was stopped and the nets of the runs never started."""
    return Issue(
        "route.budget-exhausted",
        "warning",
        f"the routing budget of {seconds:g} s ended: the run under way was stopped ({cut} net(s)) and "
        f"{not_attempted} net(s) were not attempted; the copper of the finished runs is kept",
        where,
        hint="run route again to continue with the open nets, or raise --timeout",
    )


__all__ = ["Budget", "RunOutcome", "exhausted"]
