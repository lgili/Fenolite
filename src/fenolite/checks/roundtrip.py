# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip`` stage (capability verification-loop, "Round-trip stage"): RT1 of the board, the layout
authority, for native and built input alike."""

from __future__ import annotations

from fenolite.backends.base import Validation
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue


def roundtrip_stage(validation: Validation) -> StageResult:
    """The reader's own issues (``model.*`` findings left out) and ``check.rt1-failed`` when RT1 fails."""
    rt = validation.roundtrip
    issues: list[Issue] = [i for i in validation.read.issues if not i.code.startswith("model.")]
    if not rt.passed:
        issues.append(issue("check.rt1-failed", "the board does not rebuild to itself", where=rt.difference))
    summary = {
        "level": rt.level,
        "tree_equal": rt.tree_equal,
        "model_equal": rt.model_equal,
        "opaque_equal": rt.opaque_equal,
        "opaque_count": rt.opaque_count,
    }
    return ran("roundtrip", issues, validation.read.evidence, summary)


__all__ = ["roundtrip_stage"]
