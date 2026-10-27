# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``safety`` tests import ``_checkcli`` (of the command tests)."""

from __future__ import annotations

import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "cli"  # ``_checkcli`` runs ``fenolite`` in-process
if str(CLI) not in sys.path:
    sys.path.insert(0, str(CLI))
