# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A thin, stdlib-only DSL to describe a design in Python (``docs/dsl.md``).

It records parts, nets, classes, interfaces, a board and placements, and ``to_model`` turns them into a
model design with ids keyed by names and paths. It reads no library, file or environment; the build
(``fenolite.lens.build``) resolves libraries and writes the KiCad project.
"""

from fenolite.dsl.convert import BOARD_ORIGIN, DSL_BACKEND, KEYS, placements, to_model
from fenolite.dsl.design import Design
from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import DiffPair, Interface, Power
from fenolite.dsl.module import Module
from fenolite.dsl.part import Net, Part, Placement, connect
from fenolite.dsl.units import Length, inch, mil, mm, nm

__all__ = [
    "BOARD_ORIGIN",
    "DSL_BACKEND",
    "KEYS",
    "Design",
    "DiffPair",
    "DslError",
    "Interface",
    "Length",
    "Module",
    "Net",
    "Part",
    "Placement",
    "Power",
    "connect",
    "inch",
    "mil",
    "mm",
    "nm",
    "placements",
    "to_model",
]
