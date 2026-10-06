# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The adapter from the Altium readers' records into the neutral model (change c0043, capability
``altium-import``).

Pure functions over records: nothing here parses a byte, opens a file or runs a tool. The backend
(``fenolite.backends.altium.backend``) reads the files and passes file names and hashes in.

- ``import_board``: a PCB document as a design (board, synthesised circuit, rules).
- ``import_circuit`` and ``netlist``: schematic sheets as a circuit and as a plain netlist.
- ``import_project``: the sheets and the PCB document of one project, linked.
- ``import_footprints`` and ``import_symbols``: libraries as library definitions.
"""

from __future__ import annotations

from fenolite.backends.altium.adapter.board import import_board
from fenolite.backends.altium.adapter.circuit import import_circuit
from fenolite.backends.altium.adapter.codes import IMPORT_ISSUE_CODES
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import EXT_KEYS
from fenolite.backends.altium.adapter.layers import LAYERS
from fenolite.backends.altium.adapter.library import import_footprints, import_symbols
from fenolite.backends.altium.adapter.netlist import (
    BusGroup,
    HarnessGroup,
    NetGroup,
    Netlist,
    NetOptions,
    PinKey,
    SheetInput,
    netlist,
)
from fenolite.backends.altium.adapter.pins import PIN_TYPES
from fenolite.backends.altium.adapter.project import BoardInput, ProjectInput, RulesInput, import_project

__all__ = [
    "EVIDENCE",
    "EXT_KEYS",
    "IMPORT_ISSUE_CODES",
    "LAYERS",
    "PIN_TYPES",
    "BoardInput",
    "BusGroup",
    "HarnessGroup",
    "NetGroup",
    "NetOptions",
    "Netlist",
    "PinKey",
    "ProjectInput",
    "RulesInput",
    "SheetInput",
    "import_board",
    "import_circuit",
    "import_footprints",
    "import_project",
    "import_symbols",
    "netlist",
]
