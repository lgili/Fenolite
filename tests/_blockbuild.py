# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builds of block designs on Fenolite's own catalog, for the tests of block sheets (change c0269)."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

from _buildhelp import build

from fenolite.cli.cmd_build import _catalog_definitions  # pyright: ignore[reportPrivateUsage]
from fenolite.dsl import Design, block_schematics, to_model
from fenolite.lens.build import BuildOutput

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / "examples" / "blocks" / "design.py"


def blocks_example() -> Design:
    design = runpy.run_path(str(BLOCKS))["design"]
    assert isinstance(design, Design)
    return design


def catalog_build(design: Design, target: int = 10, **kwargs: Any) -> BuildOutput:
    """``build`` of ``design`` with the catalog definitions it uses and its block-local groups."""
    footprints, symbols, _ = _catalog_definitions(to_model(design), {}, {})
    groups = {found.path: found.groups for found in block_schematics(design) if found.groups}
    return build(
        design,
        target,
        authored_footprints=footprints,
        authored_symbols=symbols,
        schematic_groups=groups,
        **kwargs,
    )
