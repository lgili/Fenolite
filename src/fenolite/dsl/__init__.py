# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A thin, stdlib-only DSL to describe a design in Python (``docs/dsl.md``).

It records parts, nets, classes, interfaces, a board and placements, and ``to_model`` turns them into a
model design with ids keyed by names and paths. It reads no library, file or environment; the build
(``fenolite.lens.build``) resolves libraries and writes the KiCad project.
"""

from fenolite.dsl.convert import (
    BOARD_ORIGIN,
    DSL_BACKEND,
    KEYS,
    fields,
    moves,
    placements,
    planes,
    to_model,
)
from fenolite.dsl.design import Design
from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.intents import (
    CopperIntent,
    PadEnd,
    PadRef,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    copper,
    via_step,
)
from fenolite.dsl.interfaces import DiffPair, Harness, Interface, Power
from fenolite.dsl.module import Module
from fenolite.dsl.part import FieldRequest, Net, Part, Placement, connect, no_connect
from fenolite.dsl.symbol import Symbol
from fenolite.dsl.units import Length, inch, mil, mm, nm

__all__ = [
    "BOARD_ORIGIN",
    "DSL_BACKEND",
    "KEYS",
    "CopperIntent",
    "Design",
    "DiffPair",
    "DslError",
    "FieldRequest",
    "Footprint",
    "Harness",
    "Interface",
    "Length",
    "Module",
    "Net",
    "PadEnd",
    "PadRef",
    "Part",
    "Placement",
    "Power",
    "StitchIntent",
    "Symbol",
    "TrackIntent",
    "ViaIntent",
    "ViaStep",
    "connect",
    "copper",
    "fields",
    "inch",
    "mil",
    "mm",
    "moves",
    "nm",
    "no_connect",
    "placements",
    "planes",
    "to_model",
    "via_step",
]
