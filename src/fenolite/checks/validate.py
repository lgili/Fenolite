# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``model.validate`` stage (capability verification-loop, "Model validation stage"): the model's own
findings, and components without a footprint or, on built input, without a symbol. A built component
without the ``fenolite.path`` key is board-only (a footprint added in KiCad that a rebuild keeps; change
c0019) and is asked for no symbol."""

from __future__ import annotations

from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

PATH_KEY = "fenolite.path"
"""The property that marks a part of the script; equal to ``backends.kicad.embed.PATH_PROPERTY``, spelled
as a literal because ``checks`` may not import ``backends.kicad`` (``package-layering``)."""
BUILT_EVIDENCE = Evidence(Level.INFERRED)
"""Built input is judged by Fenolite's own structural rules: no format claim."""


def validate_stage(design: Design, *, built: bool, evidence: Evidence) -> StageResult:
    """The ``model.*`` findings of ``design``, plus ``check.footprint-unresolved`` and, when ``built``,
    ``check.symbol-unresolved``."""
    issues: list[Issue] = list(design.validate())
    placed: set[str] = (
        {fp.component_id for fp in design.board.footprints} if design.board is not None else set()
    )
    for component in design.circuit.components:
        if not component.dnp and (not component.lib_footprint_ref or component.id not in placed):
            issues.append(issue("check.footprint-unresolved", "no footprint reference or instance",
                                where=component.ref))  # fmt: skip
        if built and not component.lib_symbol_ref and PATH_KEY in component.properties:
            issues.append(issue("check.symbol-unresolved", "no symbol reference", where=component.ref))
    summary = {"components": len(design.circuit.components), "nets": len(design.circuit.nets)}
    return ran("model.validate", issues, evidence, summary)


__all__ = ["BUILT_EVIDENCE", "PATH_KEY", "validate_stage"]
