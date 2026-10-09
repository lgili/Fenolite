# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Example inputs of the read-only commands (change c0013 Decision 19): absolute, so the consistency suite
runs their ``example_args`` from any working directory of a source checkout."""

from __future__ import annotations

from pathlib import Path

import fenolite

EXAMPLE_BOARD = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/board/two_layer.kicad_pcb"
)
"""The authored two-layer board of the test data."""

EXAMPLE_UNFILLED = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/fill/triad_t9.kicad_pcb"
)
EXAMPLE_REFILLED = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/fill/triad_t9_refilled.kicad_pcb"
)
EXAMPLE_UNROUTED = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/routing/two_pads.kicad_pcb"
)

EXAMPLE_SCHEMATIC = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/schematic/flat.kicad_sch"
)
"""The authored flat schematic of the test data (``fenolite netlist``)."""

EXAMPLE_PARITY = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/parity/agree")
"""A committed board and schematic of the blink, as ``build`` writes them for target 10: they agree
(``fenolite parity``). A test keeps them equal to a fresh build."""

EXAMPLE_READY = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/ready/blink.kicad_pcb")
"""The starter of ``fenolite init``, built and routed: a project that ``fenolite ready`` finds ready."""

__all__ = [
    "EXAMPLE_BOARD",
    "EXAMPLE_PARITY",
    "EXAMPLE_READY",
    "EXAMPLE_SCHEMATIC",
    "EXAMPLE_UNFILLED",
    "EXAMPLE_REFILLED",
    "EXAMPLE_UNROUTED",
]
