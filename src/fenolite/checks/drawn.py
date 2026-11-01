# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stage ``schematic.drawn``: the drawn schematic of a built project, as it is on disk, compared with the
recorded circuit (change c0276; capability verification-loop, "Drawn schematic stage" and "Drawn schematic
stage issue codes"; ``docs/drawn-schematic.md``).

``checks`` imports no backend: ``fenolite check`` reads the sheets, extracts and resolves them
(``fenolite.backends.kicad.drawn.resolve_sheets``) and passes the result, a ``DrawnInput``, as it passes the
judge of ``roles.rules``. The stage compares it with the circuit through ``drawn_connect.compare``; it writes
nothing and runs no tool. ``fenolite check`` lists it only for built input whose ``.fenolite/build.json``
records a drawn schematic.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Circuit
from fenolite.model.drawn_connect import DrawnNetlist, compare

NAME = "schematic.drawn"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DRAWN-CONNECT", "H-K-DRAWN-NAMES"))
"""``INFERRED`` until the KiCad CI job measures the resolver against ``kicad-cli sch export netlist``."""


@dataclass(frozen=True)
class DrawnInput:
    """What the stage judges: the nets of the sheets on disk, the circuit the build recorded, and the issues
    of the extraction and the resolver (unknown symbols, dangling wire ends, unmatched sheet pins)."""

    netlist: DrawnNetlist
    circuit: Circuit
    issues: tuple[Issue, ...] = ()


def drawn_stage(netlist: DrawnNetlist, circuit: Circuit, *, issues: tuple[Issue, ...] = ()) -> StageResult:
    """The stage on an injected drawn netlist: ``drawn.netlist-differs`` and the other codes of
    ``drawn_connect.ISSUE_CODES``; an error makes the stage ``errors``."""
    found = [*(i for i in issues if i.code.startswith("drawn.")), *compare(netlist, circuit)]
    summary = {"nets": len(netlist.nets), "pins": len(netlist.pins), "open": len(netlist.open)}
    return ran(NAME, found, EVIDENCE, summary)


__all__ = ["EVIDENCE", "NAME", "DrawnInput", "drawn_stage"]
