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
- No round-trip cell is set: no Altium file is read and written back.
"""

from __future__ import annotations

from fenolite.backends.altium import (
    binary,
    hierarchy,
    import_evidence,
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
        write=Evidence.combine(pcbrecords.EVIDENCE, pcbdoc.EVIDENCE, rulemap.EVIDENCE),
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

__all__ = ["MATRIX", "NAME"]
