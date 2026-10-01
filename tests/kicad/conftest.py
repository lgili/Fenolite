# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Oracle tests import their helpers (``_probes``, and ``_triad`` and ``_bench`` of ``board/``)."""

from __future__ import annotations

import sys
from pathlib import Path

for folder in (Path(__file__).resolve().parent, Path(__file__).resolve().parent / "board"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
