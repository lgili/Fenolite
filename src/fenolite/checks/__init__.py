# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check``'s stages: model validation, ERC and DRC findings through an oracle, the copper
check, the assignment comparison, RT1 and RT2 (capability verification-loop), and the copper check as a
library function (capability copper-check). The three ERC lite rules stay as a function for the document
pipeline.

This package imports only ``core``, ``model``, ``geometry`` and ``backends.base``.
"""

from __future__ import annotations

from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.copper import CopperReport, check_copper
from fenolite.checks.stages import (
    DEFAULT_STAGES,
    ORACLE_STAGES,
    STAGE_ORDER,
    CheckReport,
    StageResult,
    run_checks,
)

__all__ = [
    "DEFAULT_STAGES",
    "ISSUE_CODES",
    "ORACLE_STAGES",
    "STAGE_ORDER",
    "CheckReport",
    "CopperReport",
    "StageResult",
    "check_copper",
    "run_checks",
]
