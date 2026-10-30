# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Design equivalence: two designs compared level by level, with located differences (capability
design-equivalence; ``docs/equivalence.md``).

The package imports only the standard library, ``fenolite.core``, ``fenolite.model``,
``fenolite.geometry``, ``fenolite.backends.base`` and ``fenolite.checks``, and names no backend.
"""

from __future__ import annotations

from fenolite.checks.equivalence.codes import EQUIVALENCE_CODES, difference_issues
from fenolite.checks.equivalence.drawn import compare_drawn
from fenolite.checks.equivalence.exclusions import (
    Profile,
    Rule,
    accepted_rules,
    load_profiles,
    select_profile,
)
from fenolite.checks.equivalence.levels import compare_designs, max_level
from fenolite.checks.equivalence.model import (
    ALL_LEVEL_NAMES,
    LEVEL_NAMES,
    LEVELS,
    PRESENTATION_LEVEL,
    SCHEMATIC_LEVEL,
    Difference,
    EquivalenceReport,
    Excluded,
    LevelResult,
    Tolerances,
)

__all__ = [
    "ALL_LEVEL_NAMES",
    "EQUIVALENCE_CODES",
    "LEVELS",
    "LEVEL_NAMES",
    "PRESENTATION_LEVEL",
    "SCHEMATIC_LEVEL",
    "Difference",
    "EquivalenceReport",
    "Excluded",
    "LevelResult",
    "Profile",
    "Rule",
    "Tolerances",
    "accepted_rules",
    "compare_designs",
    "compare_drawn",
    "difference_issues",
    "load_profiles",
    "max_level",
    "select_profile",
]
