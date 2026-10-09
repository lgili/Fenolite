# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence of an Altium import (capability altium-import, "Adapter package"; change c0043). It lives
outside the adapter package so that the backend can name it without loading a reader: every registered
``H-A-IMP-*`` row, at the lowest level among them and among the readers' evidence."""

from __future__ import annotations

from fenolite.core.evidence import Evidence, Level, min_level

HYPOTHESES = (
    "H-A-IMP-NETLIST",
    "H-A-IMP-WIRE",
    "H-A-IMP-PIN-MID",
    "H-A-IMP-PORT-ENDS",
    "H-A-IMP-RPT-BOARD",
    "H-A-IMP-RPT-FORMAT",
    "H-A-IMP-RPT-COUNT",
    "H-A-IMP-RPT-NETS",
    "H-A-IMP-RPT-ANNOT",
    "H-A-IMP-PINMAP",
    "H-A-IMP-PINMAP-MULTI",
    "H-A-IMP-SCOPE",
    "H-A-IMP-POWER-LOCAL",
    "H-A-IMP-OFFSHEET",
    "H-A-IMP-DUP-NAME",
    "H-A-IMP-NAME-TIE",
    "H-A-IMP-NAME-AUTO",
    "H-A-IMP-HIDDEN-PIN",
    "H-A-IMP-BUS",
    "H-A-IMP-HARN-NAME",
    "H-A-IMP-LINK",
    "H-A-IMP-FRAME",
    "H-A-IMP-LAYERS",
    "H-A-IMP-PADSTACK",
    "H-A-IMP-ZONE",
    "H-A-IMP-ZONE-HOLES",
    "H-A-IMP-PLANE-CUT",
    "H-A-IMP-VIA-PADLESS",
    "H-A-IMP-BODY",
    "H-A-IMP-BODY-Z",
    "H-A-IMP-SYMFRAME",
    "H-A-IMP-FPGFX",
)
"""Every ``H-A-IMP-*`` row of ``docs/hypotheses.md``."""
LEVELS: dict[str, Level] = dict.fromkeys(HYPOTHESES, Level.INFERRED) | {
    "H-A-IMP-NETLIST": Level.CORPUS_VERIFIED,
    "H-A-IMP-WIRE": Level.CORPUS_VERIFIED,
    "H-A-IMP-RPT-BOARD": Level.CORPUS_VERIFIED,
    "H-A-IMP-RPT-FORMAT": Level.INFERRED,
    "H-A-IMP-SCOPE": Level.CORPUS_VERIFIED,
    "H-A-IMP-LINK": Level.CORPUS_VERIFIED,
    "H-A-IMP-FRAME": Level.ORACLE_VERIFIED,
    "H-A-IMP-LAYERS": Level.ORACLE_VERIFIED,
    "H-A-IMP-ZONE": Level.ORACLE_VERIFIED,
    "H-A-IMP-ZONE-HOLES": Level.ORACLE_VERIFIED,
    "H-A-IMP-PLANE-CUT": Level.ORACLE_VERIFIED,
    "H-A-IMP-VIA-PADLESS": Level.ALTIUM_VERIFIED_AUTHOR_REPORT,
}
"""The level of each row, as the register states it (``test_package.py`` keeps both equal)."""
READER_LEVELS = (Level.INFERRED, Level.CORPUS_VERIFIED, Level.CORPUS_VERIFIED)
"""The levels of ``read.sch.EVIDENCE``, ``read.pcb.EVIDENCE`` and ``read.pcblib.EVIDENCE``, repeated here so
that importing the evidence loads no reader; ``test_package.py`` compares them with the readers' values."""
MAPPING_HYPOTHESES = ("H-A-PCB-CU-VIATENT",)
"""Rows of the writer that the import rests on too: the two tenting flags of a via record become
``Via.protection`` (change c0112), and the same author report settles what they mean."""
EVIDENCE = Evidence(
    min_level(*LEVELS.values(), *READER_LEVELS), hypotheses=(*HYPOTHESES, *MAPPING_HYPOTHESES)
)
"""``INFERRED`` while any row is: the lowest level wins."""

__all__ = ["EVIDENCE", "HYPOTHESES", "LEVELS", "MAPPING_HYPOTHESES", "READER_LEVELS"]
