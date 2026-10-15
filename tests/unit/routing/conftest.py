# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Controlled external-process boundary for plugin scheduling tests."""

from __future__ import annotations

import contextlib
import io
import runpy
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from fenolite.routing.budget import Budget, RunOutcome
from fenolite.routing.plugins.kicad import routingtools


@pytest.fixture
def controlled_router_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the authored stand-in in process; its sleep spends a controlled budget.

    Real OS process startup/kill remains covered by the separate Budget tests.
    """
    now = [100.0]

    class ControlledBudget(Budget):
        def __init__(self, seconds: float) -> None:
            super().__init__(seconds, clock=lambda: now[0])

        def run(
            self, args: Sequence[str], *, cwd: str | Path, env: Mapping[str, str] | None = None
        ) -> RunOutcome:
            limit = self.left()
            if limit <= 0:
                return RunOutcome(None, "", "", 0.0, cut=True, started=False)
            stdout, stderr = io.StringIO(), io.StringIO()

            def timeout(_seconds: float) -> None:
                raise subprocess.TimeoutExpired(list(args), limit)

            with monkeypatch.context() as child:
                child.setattr(sys, "argv", list(args[1:]))
                child.setattr(sys, "path", sys.path.copy())
                child.setattr(time, "sleep", timeout)
                child.chdir(cwd)
                for key, value in (env or {}).items():
                    child.setenv(key, value)
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    try:
                        runpy.run_path(args[1], run_name="__main__")
                    except subprocess.TimeoutExpired:
                        now[0] += limit
                        return RunOutcome(None, stdout.getvalue(), stderr.getvalue(), limit, cut=True)
                    except SystemExit as exit_code:
                        code = exit_code.code if isinstance(exit_code.code, int) else 1
                    else:
                        code = 0
            spent = min(0.5, limit)
            now[0] += spent
            return RunOutcome(code, stdout.getvalue(), stderr.getvalue(), spent, cut=False)

    monkeypatch.setattr(routingtools, "Budget", ControlledBudget)
