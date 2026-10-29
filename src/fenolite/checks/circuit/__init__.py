# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The circuit rules of ``fenolite check`` (stage ``circuit.rules``) and of ``fenolite build``: the one home
of every ``circuit.*`` judge. c0252 judges the rails, logic levels, pull-ups and ports (``rails``); c0253
adds the electrical contracts: applied values (``values``), ratings and operating ranges (``ratings``),
expectations (``expect``), the rig's corners (``corners``) and the requirement table (``table``). The judges
read the model and the device records the command passes, and run no tool."""

from __future__ import annotations

from collections.abc import Mapping

from fenolite.checks.circuit.rails import circuit_evidence, has_parameters, rail_counts
from fenolite.checks.circuit.table import circuit_issues, has_contracts, judge_circuit
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.model.design import Design
from fenolite.model.library import DeviceDef

STAGE = "circuit.rules"


def circuit_stage(
    model: Design | None,
    *,
    built: bool,
    cache_error: str = "",
    devices: Mapping[str, DeviceDef] | None = None,
    classes: Mapping[str, str] | None = None,
) -> StageResult:
    """The stage ``circuit.rules``: skipped with ``cache-unreadable`` when a built project's model cannot be
    read, with ``no-model`` without a model (a native board), and with ``no-parameters`` when the model holds
    nothing for either half (no parameter for c0252's rails, and no device part, expectation or rig for
    c0253's contracts: ``no-contracts``); otherwise ``judge_circuit`` with the device records and classes the
    command resolved, ``summary.halves`` naming the state of each half and ``summary.requirements`` the
    requirement table."""
    if built and (cache_error or model is None):
        return skipped(STAGE, "cache-unreadable")
    if model is None:
        return skipped(STAGE, "no-model")
    rails, contracts = has_parameters(model), has_contracts(model)
    if not rails and not contracts:
        return skipped(STAGE, "no-parameters")
    result = judge_circuit(model, devices=devices, classes=classes)
    summary: dict[str, object] = {
        **rail_counts(model),
        "halves": {
            "rails": "ran" if rails else "no-parameters",
            "contracts": "ran" if contracts else "no-contracts",
        },
        **result.summary,
    }
    return ran(STAGE, result.issues, result.evidence, summary)


__all__ = [
    "STAGE",
    "circuit_evidence",
    "circuit_issues",
    "circuit_stage",
    "has_contracts",
    "has_parameters",
    "judge_circuit",
]
