# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Oracle tests import their helpers (``_probes``, ``_triad`` and ``_bench`` of ``board/``,
``_rulebench`` of ``rules/``, ``_procases`` of ``project/``, ``_buildcases`` of ``build/``, and ``_svg``
and ``_sheet_bench`` of ``sheets/``, ``_checkcases`` of ``check/`` and ``_exportcases`` of ``export/``)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (
    HERE,
    HERE / "board",
    HERE / "rules",
    HERE / "project",
    HERE / "build",
    HERE / "sheets",
    HERE / "check",
    HERE / "lens",
    HERE / "export",
    HERE / "frame",
):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
