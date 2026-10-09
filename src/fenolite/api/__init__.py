# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's public Python surface (capability design-equivalence, "Public equivalence API"; change
c0158).

``fenolite.api`` sits on top of the packages: it may import the model, the backends, ``checks``,
``analysis``, ``convert`` and ``lens``, and only ``cli``, ``agent`` and the root modules may import it
(capability package-layering, "Allowed import edges"). ``import fenolite`` does not import it.
"""

from __future__ import annotations

from fenolite.api.equivalence import EquivalenceResult, Side, equivalent
from fenolite.api.sides import SideError, SideMissingError, SideUsageError, ToolMajorError, ToolMissingError

__all__ = [
    "EquivalenceResult",
    "Side",
    "SideError",
    "SideMissingError",
    "SideUsageError",
    "ToolMajorError",
    "ToolMissingError",
    "equivalent",
]
