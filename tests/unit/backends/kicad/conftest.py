# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad backend tests that run ``fenolite`` in-process import ``_checkcli`` of the command tests."""

from __future__ import annotations

import sys
from pathlib import Path

CLI_TESTS = Path(__file__).resolve().parents[2] / "cli"
if str(CLI_TESTS) not in sys.path:
    sys.path.insert(0, str(CLI_TESTS))
