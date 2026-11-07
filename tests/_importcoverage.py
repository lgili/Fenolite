# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source-emission measurement tool and its count-only observation file, shared by proofs."""

from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOL = runpy.run_path(str(ROOT / "tools" / "measure_import_coverage.py"))
measure = TOOL["measure"]
counts = TOOL["counts"]
digest = TOOL["digest"]
declared = TOOL["declared"]
table = TOOL["table"]
PREFIX = TOOL["PREFIX"]
OUTPUT = TOOL["OUTPUT"]
PAGE = TOOL["PAGE"]


def observation() -> dict[str, Any]:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def recorded() -> dict[str, list[dict[str, Any]]]:
    return {row["id"].removeprefix(PREFIX): row["unexpressed"] for row in observation()["rows"]}
