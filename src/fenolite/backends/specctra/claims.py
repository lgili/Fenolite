# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix rows of the Specctra codec (capability backend-protocol, "Evidence matrix rows";
change c0067).

This module states no level: every cell is an evidence constant of a module of this package. The codec
writes a design file and reads a session file; it detects nothing and round-trips nothing. A route read
from a session is judged by the check that follows it, not by these cells.
"""

from __future__ import annotations

from dataclasses import replace

from fenolite.backends.base import MatrixRow
from fenolite.backends.specctra import dsn, ses

NAME = "specctra"

_ROWS: tuple[MatrixRow, ...] = (
    MatrixRow(NAME, "specctra_dsn", write=dsn.EVIDENCE),
    MatrixRow(NAME, "specctra_ses", read=ses.EVIDENCE),
)

READBACKS = {
    "specctra_dsn": "tests/unit/backends/specctra/test_dsn.py",
}
MODEL_ROUNDTRIPS: dict[str, str] = {}
MATRIX = tuple(
    replace(row, readback=READBACKS.get(row.kind, ""), model_roundtrip=MODEL_ROUNDTRIPS.get(row.kind, ""))
    for row in _ROWS
)

__all__ = ["MATRIX", "NAME"]
