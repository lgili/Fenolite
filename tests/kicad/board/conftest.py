# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board oracle tests import their helpers (``_upgrade``, ``_frame``) from this folder."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
