# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Issue codes that the dispatcher itself reports, mapped to their severity."""

from fenolite.core.errors import Severity

ISSUE_CODES: dict[str, Severity] = {
    "plan.not-staged": "warning",
}

__all__ = ["ISSUE_CODES"]
