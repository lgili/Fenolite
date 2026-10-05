# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix rows of the KiCad backend (capability backend-protocol, "Evidence matrix rows";
change c0067).

This module states no level: every cell is an evidence constant of a module of this package, or
``Evidence.combine`` of such constants, so a level changes in the module that owns the claim. A label
states what holds for an arbitrary file of the kind, which is why most cells are ``INFERRED`` although the
rows they name are stronger.

- ``detect`` is ``versions.EVIDENCE`` for the kinds of ``versions.FileKind``, named from a file's suffix
  or its root token.
- A round-trip cell is set only where a test of the repository proves the property for the kind, and
  takes the constant of the module that implements it: the board by ``roundtrip.rt1`` (RT1), the
  schematic by ``sch.roundtrip_schematic``, the drawing sheet by ``wks.rebuild_drawing_sheet`` and the
  project file by ``pro.write_project_text`` of ``pro.read_project_text``.
- ``kicad_sym`` has a writer for the symbols a design authors (``sym.write_symbol_library``), which no
  register row covers yet, so its ``write`` is experimental and the kind is not a write kind of the
  backend's report.
- ``kicad_lib_table`` is the pair ``fp-lib-table`` and ``sym-lib-table``.
"""

from __future__ import annotations

from fenolite.backends.base import MatrixRow
from fenolite.backends.kicad import dru, libs, lowering, mod, pcb, pro, sch, sym, versions, wks
from fenolite.core.evidence import Evidence

NAME = "kicad"
LIB_TABLE_KIND = "kicad_lib_table"
PROJECT_KIND = "kicad_pro"

MATRIX: tuple[MatrixRow, ...] = (
    MatrixRow(
        NAME,
        versions.FileKind.RULES.value,
        detect=versions.EVIDENCE,
        read=dru.EVIDENCE,
        write=Evidence.combine(dru.EVIDENCE, lowering.EVIDENCE),
    ),
    MatrixRow(NAME, LIB_TABLE_KIND, read=libs.EVIDENCE, write=libs.WRITE_EVIDENCE),
    MatrixRow(
        NAME,
        versions.FileKind.FOOTPRINT.value,
        detect=versions.EVIDENCE,
        read=mod.EVIDENCE,
        write=mod.AUTHORING_EVIDENCE,
    ),
    MatrixRow(
        NAME,
        versions.FileKind.BOARD.value,
        detect=versions.EVIDENCE,
        read=pcb.EVIDENCE,
        write=pcb.WRITE_EVIDENCE,
        roundtrip_exact=pcb.EVIDENCE,
        roundtrip_modified=Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE),
    ),
    MatrixRow(NAME, PROJECT_KIND, read=pro.EVIDENCE, write=pro.EVIDENCE, roundtrip_exact=pro.EVIDENCE),
    MatrixRow(
        NAME,
        versions.FileKind.SCHEMATIC.value,
        detect=versions.EVIDENCE,
        read=sch.EVIDENCE,
        roundtrip_exact=sch.EVIDENCE,
    ),
    MatrixRow(
        NAME,
        versions.FileKind.SYMBOL_LIB.value,
        detect=versions.EVIDENCE,
        read=sym.EVIDENCE,
        write=sym.WRITE_EVIDENCE,
        experimental=("write",),
    ),
    MatrixRow(
        NAME,
        versions.FileKind.WORKSHEET.value,
        detect=versions.EVIDENCE,
        read=wks.EVIDENCE,
        write=wks.WRITE_EVIDENCE,
        roundtrip_exact=wks.EVIDENCE,
    ),
)

__all__ = ["LIB_TABLE_KIND", "MATRIX", "NAME", "PROJECT_KIND"]
