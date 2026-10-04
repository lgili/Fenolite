# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``checks`` tests import ``fakes`` (here) and ``_checkcli`` (of the command tests)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "cli"):  # ``_checkcli`` of the command tests runs ``fenolite`` in-process
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
