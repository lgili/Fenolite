# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix rows of the Specctra codec (capability backend-protocol, "Evidence matrix rows";
change c0067).

This module states no level: every cell is an evidence constant of a module of this package. The codec
writes a design file and reads a session file; it detects nothing and round-trips nothing. A route read
from a session is judged by the check that follows it, not by these cells.
"""

from __future__ import annotations

from fenolite.backends.base import MatrixRow
from fenolite.backends.specctra import dsn, ses

NAME = "specctra"

MATRIX: tuple[MatrixRow, ...] = (
    MatrixRow(NAME, "specctra_dsn", write=dsn.EVIDENCE),
    MatrixRow(NAME, "specctra_ses", read=ses.EVIDENCE),
)

__all__ = ["MATRIX", "NAME"]
