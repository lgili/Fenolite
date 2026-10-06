# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix rows of the Altium package (capability backend-protocol, "Evidence matrix rows";
change c0067).

This module states no level: every cell is an evidence constant of a module of this package, or
``Evidence.combine`` of such constants.

- ``read`` is what the registered backend does with a file: its reader, then the import adapter. The cell
  combines the reader's constant with ``import_evidence.EVIDENCE``, which the backend returns for every
  read; the lowest level wins and the ids of both are listed.
- ``detect`` is ``import_evidence.EVIDENCE``, the evidence of the backend's report, whose operations are
  ``detect`` and ``read``: the backend names a file by its suffix, and no register row is about that alone.
- ``write`` is the constant of the writer modules behind each write kind of the two experimental features
  of ``build --target altium``. Every ``write`` is experimental.
- The output job and the sheet template (change c0087) have a ``write`` cell only: the backend reads
  neither as a design, and their own readers are not a second opinion.
- The PCB document's ``write`` also names ``lower.EVIDENCE``: a model that holds a board is written
  without a script (change c0090).
- No round-trip cell is set. ``roundtrip_exact`` says that a file read and written back keeps its whole
  content, modelled or not. Altium files are read and written back since change c0090, and what the
  levels support is less than that: ``ROUND_TRIP_NOTES`` names, per kind, the highest level that holds
  over the public corpus and its hypothesis. A cell is set only when RT-A3 holds over the corpus with
  nothing unwritten for the kind, and never from files that Fenolite wrote itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.backends.altium import (
    binary,
    hierarchy,
    import_evidence,
    lower,
    outjob,
    pcbdoc,
    pcblib,
    pcbrecords,
    project,
    rulemap,
    schdot,
    schlib,
)
from fenolite.backends.altium.read import pcb as read_pcb
from fenolite.backends.altium.read import pcblib as read_pcblib
from fenolite.backends.altium.read import project as read_project
from fenolite.backends.altium.read import sch as read_sch
from fenolite.backends.base import MatrixRow
from fenolite.core.evidence import Evidence

NAME = "altium"
IMPORT = import_evidence.EVIDENCE
SCHEMATIC_READ = Evidence.combine(read_sch.EVIDENCE, IMPORT)
WRITE = ("write",)

MATRIX: tuple[MatrixRow, ...] = (
    MatrixRow(NAME, project.HARNESS_KIND, write=hierarchy.EVIDENCE, experimental=WRITE),
    MatrixRow(NAME, outjob.OUTJOB_KIND, write=outjob.EVIDENCE, experimental=WRITE),
    MatrixRow(
        NAME,
        project.PCBDOC_KIND,
        detect=IMPORT,
        read=Evidence.combine(read_pcb.EVIDENCE, IMPORT),
        # the rules of the design are written by kind and scope (change c0084, the H-A-RULE-* rows)
        # a model with a board is written from the model alone (change c0090, ``lower``)
        write=Evidence.combine(pcbrecords.EVIDENCE, pcbdoc.EVIDENCE, rulemap.EVIDENCE, lower.EVIDENCE),
        experimental=WRITE,
    ),
    MatrixRow(
        NAME,
        project.PCBLIB_KIND,
        detect=IMPORT,
        read=Evidence.combine(read_pcblib.EVIDENCE, IMPORT),
        write=Evidence.combine(pcbrecords.EVIDENCE, pcblib.EVIDENCE),
        experimental=WRITE,
    ),
    MatrixRow(
        NAME,
        "altium_prjpcb",
        detect=IMPORT,
        read=Evidence.combine(read_project.EVIDENCE, IMPORT),
        write=project.EVIDENCE,
        experimental=WRITE,
    ),
    MatrixRow(NAME, schdot.SCHDOT_KIND, write=schdot.EVIDENCE, experimental=WRITE),
    MatrixRow(
        NAME,
        "altium_schdoc_ascii",
        detect=IMPORT,
        read=SCHEMATIC_READ,
        write=project.EVIDENCE,
        experimental=WRITE,
    ),
    MatrixRow(
        NAME,
        "altium_schdoc_binary",
        detect=IMPORT,
        read=SCHEMATIC_READ,
        write=Evidence.combine(project.EVIDENCE, binary.EVIDENCE),
        experimental=WRITE,
    ),
    MatrixRow(
        NAME,
        project.SCHLIB_KIND,
        detect=IMPORT,
        read=SCHEMATIC_READ,
        write=schlib.EVIDENCE,
        experimental=WRITE,
    ),
)

RT_A1_NOTE = "RT-A1 (H-A-VER-RTA1): every typed stream gives equal records after an encode and a read"
ROUND_TRIP_NOTES: Mapping[str, str] = MappingProxyType(
    {
        project.PCBDOC_KIND: (
            "RT-A3 inside the written scope (H-A-VER-RTA3): a public PCB document that is read, written "
            "from its model and read again gives an equal model for what the write carries; the rewrite "
            "leaves out what docs/evidence/altium-roundtrip.md counts per kind, so roundtrip_exact is empty"
        ),
        "altium_prjpcb": (
            "RT-A3 inside the written scope (H-A-VER-RTA3-PRJ) on the project sets whose circuit the "
            "schematic writer takes; the schematic of a rewrite is generated, so roundtrip_exact is empty"
        ),
        project.PCBLIB_KIND: RT_A1_NOTE,
        "altium_schdoc_ascii": RT_A1_NOTE,
        "altium_schdoc_binary": RT_A1_NOTE,
        project.SCHLIB_KIND: RT_A1_NOTE,
    }
)
"""Read kind → the highest round-trip level that holds over the public corpus, with its hypothesis
(capability altium-verification, "Round-trip claims of the Altium kinds"; change c0090). The matrix has
no column for a note: its round-trip cells say ``exact`` or nothing, and these kinds have nothing."""

__all__ = ["MATRIX", "NAME", "ROUND_TRIP_NOTES"]
