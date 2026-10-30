# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parametric part selection (change c0254, ``docs/picking.md``).

Queries of the DSL (``resistor(...)``) and generator requests (``voltage_divider(...)``) are resolved here
against a local, versioned catalog of pickable rows; every pick is written to the ``[picks]`` section of the
design lock through plan/confirm and never changes by itself. The package imports ``core``, ``model`` and
``catalog`` only, opens no network connection and runs no subprocess.
"""

from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PICK-DETERMINISTIC",))
"""The evidence of a pick: matching, ranking and the lock round trip are proven by unit tests over authored
catalogs; a reply combines it with the evidence of each picked row (lowest wins)."""
GENERATOR_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-GEN-ENCLOSURE",))
"""The evidence of a generator's result: the achieved range encloses the exact one."""

__all__ = ["EVIDENCE", "GENERATOR_EVIDENCE"]
