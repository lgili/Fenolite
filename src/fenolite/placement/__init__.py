# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement: the legality check and the grid strategy (capability placement; ``docs/placement.md``).

The package works on plain data of ``backends.base`` (``PlacedExtent``), ``geometry`` and ``model``. It
imports no backend module, uses no random generator and no clock, and gives equal results for equal
inputs.
"""

from __future__ import annotations

from fenolite.placement.codes import EVIDENCE, ISSUE_CODES
from fenolite.placement.grid import Box, GridResult, place
from fenolite.placement.legality import TOUCHING_OVERLAPS, check

__all__ = ["EVIDENCE", "ISSUE_CODES", "TOUCHING_OVERLAPS", "Box", "GridResult", "check", "place"]
