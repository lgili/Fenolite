# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout reuse: copy the placement and the copper of a block of a reference board onto parts of another
board, fitted by their pads (capability layout-reuse; ``docs/placement.md``, "Layout reuse"; command
``fenolite place --strategy reuse``).

The package imports ``model``, ``geometry`` and ``backends.base`` only: the boards come with their
board-frame pad records, and the command moves the footprints, prunes and checks the copper."""

from __future__ import annotations

from fenolite.reuse.codes import EVIDENCE, HYPOTHESIS, ISSUE_CODES
from fenolite.reuse.copper import (
    REBUILT,
    CopiedItem,
    Copper,
    CopperCopy,
    Dropped,
    copy_copper,
    layer_map,
    outline_of,
    with_copper,
    with_outlines,
)
from fenolite.reuse.fit import (
    DEFAULT_TOLERANCE,
    BlockFit,
    Layout,
    PadMatch,
    PartFit,
    Placement,
    Rigid,
    fit_block,
    fit_rigid,
    moved_placement,
    placement_transform,
)

__all__ = [
    "DEFAULT_TOLERANCE",
    "EVIDENCE",
    "HYPOTHESIS",
    "ISSUE_CODES",
    "REBUILT",
    "BlockFit",
    "CopiedItem",
    "Copper",
    "CopperCopy",
    "Dropped",
    "Layout",
    "PadMatch",
    "PartFit",
    "Placement",
    "Rigid",
    "copy_copper",
    "fit_block",
    "fit_rigid",
    "layer_map",
    "moved_placement",
    "outline_of",
    "placement_transform",
    "with_copper",
    "with_outlines",
]
