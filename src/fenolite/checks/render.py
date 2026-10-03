# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``render`` stage (capability verification-loop, "Render stage"): whether the board plots.

Opt-in: it runs only when ``--stages`` names it. It reports the views the injected ``Plotter`` produced,
by size and hash, and a warning for each view it could not produce. A render is never a gate, so the
stage never reports an error and writes nothing.
"""

from __future__ import annotations

from fenolite.backends.base import Plotter, ProjectSet
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran


def render_stage(plotter: Plotter, project: ProjectSet) -> StageResult:
    """One plot of ``project``: the views in the summary, ``render.failed`` for each missing view."""
    outcome = plotter.plot(project)
    detail = f": {outcome.message}" if outcome.message else ""
    issues = [
        issue("render.failed", f"{name} was not produced{detail}", where=name)
        for name in sorted(outcome.failed)
    ]
    summary = {
        "tool_version": outcome.tool_version,
        "views": [
            {"name": v.name, "bytes": v.bytes, "sha256": v.sha256}
            for v in sorted(outcome.views, key=lambda v: v.name)
        ],
    }
    return ran("render", issues, outcome.evidence, summary)


__all__ = ["render_stage"]
