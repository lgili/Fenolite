# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's public Python surface (capability design-equivalence, "Public equivalence API"; change
c0158; capability design-conversion, "Conversion verified by equivalence"; change c0159; capability
python-api; change c0206). Every name of ``__all__`` is documented in ``docs/api.md`` and frozen for 1.0.

``run`` runs any command in this process and returns the envelope that ``fenolite --json`` prints; the
typed functions return the records of the packages that compute them.

``fenolite.api`` sits on top of the packages: it may import the model, the backends, ``checks``,
``analysis``, ``convert`` and ``lens``, and ``cli`` inside ``run`` only; only ``cli``, ``agent`` and the
root modules may import it (capability package-layering, "Allowed import edges" and "Public API runs the
commands lazily"). ``import fenolite`` does not import it, and importing it loads no command module.
"""

from __future__ import annotations

from fenolite.api.board import (
    Board,
    ExtraMissingError,
    analyze_current,
    analyze_distances,
    connectivity,
    read_board,
    read_design,
)
from fenolite.api.commands import Reply, run
from fenolite.api.conversion import ConversionResult, convert
from fenolite.api.equivalence import EquivalenceResult, Side, equivalent
from fenolite.api.sides import (
    ReadSide,
    SideError,
    SideMissingError,
    SideUsageError,
    ToolMajorError,
    ToolMissingError,
)
from fenolite.api.trials import trial

__all__ = [
    "Board",
    "ConversionResult",
    "EquivalenceResult",
    "ExtraMissingError",
    "ReadSide",
    "Reply",
    "Side",
    "SideError",
    "SideMissingError",
    "SideUsageError",
    "ToolMajorError",
    "ToolMissingError",
    "analyze_current",
    "analyze_distances",
    "connectivity",
    "convert",
    "equivalent",
    "read_board",
    "read_design",
    "run",
    "trial",
]
