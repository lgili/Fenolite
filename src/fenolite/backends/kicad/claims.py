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
- ``kicad_sch`` is written for created sheets only (``sch.write_schematic`` of the sheet that ``schgen``
  generates for a build, change c0061); a sheet read from a file is rebuilt at its own version.
- ``kicad_lib_table`` is the pair ``fp-lib-table`` and ``sym-lib-table``.
"""

from __future__ import annotations

from dataclasses import replace

from fenolite.backends.base import MatrixRow, VersionEvidence
from fenolite.backends.kicad import dru, libs, lowering, mod, pcb, pro, sch, schgen, sym, versions, wks
from fenolite.core.evidence import Evidence

NAME = "kicad"
LIB_TABLE_KIND = "kicad_lib_table"
PROJECT_KIND = "kicad_pro"

RAW_MATRIX: tuple[MatrixRow, ...] = (
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
        write=Evidence.combine(sch.WRITE_EVIDENCE, schgen.EVIDENCE),
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

# These scopes preserve the generic cell level. They name the existing pinned oracle jobs and
# actual tests, not a fresh run of the working tree. Tests guard the tool pins against ci.yml.
ORACLE_TOOLS = {9: "kicad-cli 9.0.9", 10: "kicad-cli 10.0.6"}
VERSION_SOURCES: dict[str, dict[str, str]] = {
    "kicad_pcb": {
        "read": "tests/kicad/board/test_board_loads.py",
        "write": "tests/kicad/board/test_triad.py",
        "roundtrip_exact": "tests/kicad/check/test_corpus_rt.py",
        "roundtrip_modified": "tests/kicad/check/test_corpus_rt.py",
    },
    "kicad_mod": {
        "read": "tests/kicad/libs/test_mini_oracle.py",
        "write": "tests/kicad/libs/test_mod_write_oracle.py",
    },
    "kicad_dru": {
        "read": "tests/kicad/rules/test_rule_dialect.py",
        "write": "tests/kicad/rules/test_rule_kinds.py",
    },
    "kicad_sch": {
        "read": "tests/kicad/schematic/test_corpus_rt2.py",
        "write": "tests/kicad/schematic/test_generated_oracle.py",
        "roundtrip_exact": "tests/kicad/schematic/test_corpus_rt2.py",
    },
}


def _versioned(row: MatrixRow) -> MatrixRow:
    declared = VERSION_SOURCES.get(row.kind, {})
    if not declared:
        return row
    kind = versions.FileKind(row.kind)
    scopes = {
        operation: tuple(
            VersionEvidence(str(versions.FORMAT_VERSIONS[kind][major]), tool, cell.level, declared[operation])
            for major, tool in ORACLE_TOOLS.items()
        )
        for operation, cell in row.cells()
        if operation in declared
    }
    return replace(row, versions=scopes)


MATRIX = tuple(_versioned(row) for row in RAW_MATRIX)

__all__ = ["LIB_TABLE_KIND", "MATRIX", "NAME", "ORACLE_TOOLS", "PROJECT_KIND", "VERSION_SOURCES"]
