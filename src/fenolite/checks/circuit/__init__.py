# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The circuit rules of ``fenolite check`` (stage ``circuit.rules``) and of ``fenolite build``: the one home
of every ``circuit.*`` judge (change c0252; c0253 adds its modules here). The judges read the model only and
run no tool."""

from __future__ import annotations

from fenolite.checks.circuit.rails import circuit_evidence, circuit_issues, has_parameters, rail_counts
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.model.design import Design

STAGE = "circuit.rules"


def circuit_stage(model: Design | None, *, built: bool, cache_error: str = "") -> StageResult:
    """The stage ``circuit.rules``: skipped with ``cache-unreadable`` when a built project's model cannot be
    read, with ``no-model`` without a model (a native board), and with ``no-parameters`` when the model
    holds nothing to judge; otherwise ``circuit_issues``, with ``summary.halves`` naming the state of each
    half (the contract half is c0253's)."""
    if built and (cache_error or model is None):
        return skipped(STAGE, "cache-unreadable")
    if model is None:
        return skipped(STAGE, "no-model")
    if not has_parameters(model):
        return skipped(STAGE, "no-parameters")
    summary: dict[str, object] = {
        **rail_counts(model),
        "halves": {"rails": "ran", "contracts": "no-contracts"},
    }
    return ran(STAGE, circuit_issues(model), circuit_evidence(model), summary)


__all__ = ["STAGE", "circuit_evidence", "circuit_issues", "circuit_stage", "has_parameters"]
