# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fixed exit-code vocabulary of the ``fenolite`` command (frozen at 1.0)."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes. The first digit of every ``FEN-NNNN`` error code equals one of these."""

    OK = 0
    INTERNAL = 1
    USAGE = 2
    INPUT = 3
    CONFIRM_REQUIRED = 4
    FINDINGS = 5
    TOOL = 6
    LOSSY = 7


__all__ = ["ExitCode"]
