# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""CLI tests import ``_checkcli`` (here)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from _result_contract import document_problems, result_problems

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture(autouse=True)
def declared_result_contract():
    """Every real, complete reply built by these unit tests must name all its structured fields."""
    from fenolite.cli import main

    perform, envelope = main._perform, main._envelope
    projections: list[bool] = []
    problems: list[str] = []

    def checked_envelope(command, outcome, result, **kwargs):
        if not projections or not projections[-1]:
            problems.extend(result_problems(command.name, result))
            problems.extend(document_problems(outcome.writes))
        return envelope(command, outcome, result, **kwargs)

    def checked_perform(command, args, ctx, started):
        projections.append(bool(getattr(args, "fields", None)))
        try:
            return perform(command, args, ctx, started)
        finally:
            projections.pop()

    # Keep this patch scope independent of the test's monkeypatch fixture and its cache cleanup.
    with pytest.MonkeyPatch.context() as contract_patch:
        contract_patch.setattr(main, "_perform", checked_perform)
        contract_patch.setattr(main, "_envelope", checked_envelope)
        yield
    assert not problems, "undeclared command result:\n" + "\n".join(problems)
