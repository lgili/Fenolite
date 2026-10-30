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
EXAMPLE_SILK = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/silk/row.kicad_pcb")
"""The designator bench of ``tests/_silkbench.py`` (``row()``) written for KiCad 10: ten two-pad parts in a
row at 1.6 mm, every designator over its pads (``fenolite silk``). A test keeps it equal to a fresh write."""
EXAMPLE_TIDY = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/tidy/stub.kicad_pcb")
"""The copper-tidy bench of ``tests/_tidybench.py`` written for KiCad 10: a routed net with a stub, a dead
lead with its via and a right angle (``fenolite tidy``). A test keeps it equal to a fresh write."""

EXAMPLE_SCHEMATIC = str(
    Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/schematic/flat.kicad_sch"
)
"""The authored flat schematic of the test data (``fenolite netlist``)."""

EXAMPLE_PARITY = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/parity/agree")
"""A committed board and schematic of the blink, as ``build`` writes them for target 10: they agree
(``fenolite parity``). A test keeps them equal to a fresh build."""

EXAMPLE_READY = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/kicad/ready/blink.kicad_pcb")
"""The starter of ``fenolite init``, built and routed: a project that ``fenolite ready`` finds ready."""

EXAMPLE_SCRIPT = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/slots/design.py")
"""A committed design script: ``fenolite edit`` with its own text as the content plans nothing."""

EXAMPLE_PICKS = str(Path(fenolite.__file__).resolve().parents[2] / "examples/picks")
"""The parametric-pick example (change c0254) with its committed design lock: ``fenolite pick`` lists it."""

EXAMPLE_FAMILIES = str(Path(fenolite.__file__).resolve().parents[2] / "examples/families")
"""The grammar-family example (change c0263): illustrative ``fenolite.family.v1`` files in ``devices/`` beside
a design script that picks exact MPNs from them (``fenolite family``)."""

__all__ = [
    "EXAMPLE_BOARD",
    "EXAMPLE_FAMILIES",
    "EXAMPLE_PICKS",
    "EXAMPLE_SCRIPT",
    "EXAMPLE_PARITY",
    "EXAMPLE_READY",
    "EXAMPLE_SCHEMATIC",
    "EXAMPLE_SILK",
    "EXAMPLE_TIDY",
    "EXAMPLE_UNFILLED",
    "EXAMPLE_REFILLED",
    "EXAMPLE_UNROUTED",
]
