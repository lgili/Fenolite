# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Passive families described by their ordering-code grammar (change c0263, ``docs/picking.md``,
"Families with ordering codes").

A ``fenolite.family.v1`` record describes a whole manufacturer series once: the fields of its ordering
code, the attributes of each code, the value code and the validity matrix. ``schema`` reads it, ``lint``
proves statically that every MPN parses one way, ``expand`` lists its candidates lazily (pruned by a c0254
query), ``decode`` reads an MPN back into its parameters, and ``candidates`` turns a candidate into an
in-memory c0248 device that c0254 picks like any other row. Nothing here opens a network connection or runs
a subprocess, and the core package ships no real series.
"""

from fenolite.pick.grammar.codes import EVIDENCE, ISSUE_CODES

EXPANSION_LIMIT = 100_000
"""The largest pruned product an expansion visits; above it the expansion is refused
(``family.expansion-limit``) before its first step, so a pick never depends on where an iteration stopped."""

__all__ = ["EVIDENCE", "EXPANSION_LIMIT", "ISSUE_CODES"]
