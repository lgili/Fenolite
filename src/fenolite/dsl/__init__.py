# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A thin, stdlib-only DSL to describe a design in Python (``docs/dsl.md``).

It records parts, nets, classes, interfaces, a board and placements, and ``to_model`` turns them into a
model design with ids keyed by names and paths. It reads no library, file or environment; the build
(``fenolite.lens.build``) resolves libraries and writes the KiCad project. A part placed from a device
(``Part(ref, device=...)``, change c0248) reads the device records of ``fenolite.catalog.devices``: the
shipped ones from the package, and the project ones that the script runner installed for the run.
"""

from fenolite.dsl import select, shape, stack
from fenolite.dsl.block import block
from fenolite.dsl.convert import (
    BOARD_ORIGIN,
    DSL_BACKEND,
    KEYS,
    drawing_sheet_source,
    drawn_schematic,
    fields,
    heights,
    module_moves,
    moves,
    net_moves,
    outline_locked,
    pad_zones,
    placements,
    planes,
    schematic_composition,
    stackup_locked,
    to_model,
    via_protection_locked,
)
from fenolite.dsl.design import Design
from fenolite.dsl.devices import PinNameError
from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.generate import GeneratedIntent, generated
from fenolite.dsl.impedance import Trace, trace
from fenolite.dsl.intents import (
    Anchor,
    AnchorRef,
    ArcStep,
    CopperIntent,
    MeanderIntent,
    PadEnd,
    PadRef,
    StitchIntent,
    TrackIntent,
    ViaIntent,
    ViaStep,
    arc_to,
    copper,
    meanders,
    protect,
    teardrop,
    via_step,
)
from fenolite.dsl.interfaces import I2C, SPI, UART, USB2, DiffPair, Harness, Interface, Power
from fenolite.dsl.items import RuleArea
from fenolite.dsl.module import Module
from fenolite.dsl.panel import Panel
from fenolite.dsl.part import FieldRequest, Net, PadZoneRequest, Part, Placement, connect, no_connect
from fenolite.dsl.quantity import (
    Quantity,
    Range,
    Tolerance,
    amp,
    between,
    celsius,
    farad,
    henry,
    hertz,
    kelvin,
    ohm,
    pct,
    second,
    volt,
    watt,
)
from fenolite.dsl.relative import column, grid, pack, row
from fenolite.dsl.rolecopper import RoleCopperIntent, role_copper
from fenolite.dsl.symbol import Symbol
from fenolite.dsl.units import Length, inch, mil, mm, nm
from fenolite.dsl.wiring import decouple, pull_down, pull_up, series
from fenolite.model.board import MechanicalIntent

__all__ = [
    "BOARD_ORIGIN",
    "DSL_BACKEND",
    "KEYS",
    "Anchor",
    "AnchorRef",
    "ArcStep",
    "CopperIntent",
    "MeanderIntent",
    "Design",
    "DiffPair",
    "DslError",
    "FieldRequest",
    "GeneratedIntent",
    "Footprint",
    "Harness",
    "Interface",
    "Length",
    "Module",
    "MechanicalIntent",
    "Net",
    "PadEnd",
    "PadRef",
    "PadZoneRequest",
    "RoleCopperIntent",
    "Panel",
    "Part",
    "PinNameError",
    "Placement",
    "Power",
    "StitchIntent",
    "Symbol",
    "Trace",
    "TrackIntent",
    "ViaIntent",
    "ViaStep",
    "arc_to",
    "block",
    "column",
    "connect",
    "copper",
    "decouple",
    "meanders",
    "drawing_sheet_source",
    "drawn_schematic",
    "schematic_composition",
    "fields",
    "generated",
    "grid",
    "heights",
    "inch",
    "mil",
    "mm",
    "module_moves",
    "moves",
    "net_moves",
    "nm",
    "no_connect",
    "outline_locked",
    "pack",
    "pad_zones",
    "placements",
    "planes",
    "protect",
    "pull_down",
    "pull_up",
    "role_copper",
    "row",
    "select",
    "series",
    "shape",
    "stack",
    "stackup_locked",
    "teardrop",
    "to_model",
    "trace",
    "via_protection_locked",
    "via_step",
    "I2C",
    "SPI",
    "UART",
    "USB2",
    "Quantity",
    "Range",
    "Tolerance",
    "between",
    "celsius",
    "kelvin",
    "pct",
    "RuleArea",
    "amp",
    "farad",
    "henry",
    "hertz",
    "ohm",
    "second",
    "volt",
    "watt",
]
