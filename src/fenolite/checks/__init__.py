# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check``'s stages: model validation, ERC lite, DRC through an oracle, and RT1 (capability
verification-loop). This package imports only ``core``, ``model``, ``geometry`` and ``backends.base``."""

from __future__ import annotations

from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.stages import STAGE_ORDER, CheckReport, StageResult, run_checks

__all__ = ["ISSUE_CODES", "STAGE_ORDER", "CheckReport", "StageResult", "run_checks"]
