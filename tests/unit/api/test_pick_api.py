# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.run("pick", ...)`` (change c0254, task 4.3; python-api, "In-process command runner")."""

from __future__ import annotations

from pathlib import Path

from fenolite.api import run

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "picks"


def test_pick_runs_in_process() -> None:
    reply = run("pick", str(EXAMPLE))
    assert reply.ok and reply.result is not None
    assert {pick["state"] for pick in reply.result["picks"]} == {"ok"}
    assert reply.envelope is not None and reply.envelope["command"] == "pick"
