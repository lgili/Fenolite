# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad backend: S-expression syntax layer, slots, format versions, library and board readers, the
board, footprint, custom-rules, project and drawing-sheet writers, and the ``kicad-cli`` runner.

Facts and sources: ``docs/formats/kicad/`` and ``PROVENANCE.md`` in this package.
"""

from fenolite.backends.kicad.cli import KicadCli, find_kicad_cli
from fenolite.backends.kicad.copper import resolve_copper
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.dru import read_rules, write_rules
from fenolite.backends.kicad.embed import footprint_extent, place_footprint
from fenolite.backends.kicad.frame import board_pads, find_pads, placed_extent, placed_extents
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, split_lib_id
from fenolite.backends.kicad.lowering import lower_minimums, lower_rules
from fenolite.backends.kicad.mod import board_footprints, read_footprint, write_footprint, write_pretty
from fenolite.backends.kicad.pcb import opaque_count, read_board, rebuild_board, write_board
from fenolite.backends.kicad.pro import (
    PROJECT_VERSIONS,
    apply_project,
    project_minimums,
    read_project,
    synthesize_project,
    update_project,
)
from fenolite.backends.kicad.sexpr import (
    MAX_DEPTH,
    Atom,
    AtomKind,
    Node,
    dumps,
    first_difference,
    load,
    parse,
    parse_bytes,
    parse_fragment,
    tree_equal,
    walk,
)
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import LegacyEditRefusedError, LossyWriteError
from fenolite.backends.kicad.wks import read_drawing_sheet, rebuild_drawing_sheet, write_drawing_sheet

__all__ = [
    "MAX_DEPTH",
    "PROJECT_VERSIONS",
    "Atom",
    "AtomKind",
    "KicadCli",
    "LegacyEditRefusedError",
    "LibraryConfig",
    "LibraryError",
    "LibraryResolver",
    "LossyWriteError",
    "Node",
    "apply_project",
    "board_footprints",
    "board_pads",
    "dumps",
    "find_kicad_cli",
    "find_pads",
    "first_difference",
    "footprint_extent",
    "load",
    "lower_minimums",
    "lower_rules",
    "opaque_count",
    "parse",
    "parse_bytes",
    "parse_fragment",
    "place_footprint",
    "placed_extent",
    "placed_extents",
    "project_minimums",
    "read_board",
    "read_drawing_sheet",
    "read_drc_report",
    "read_footprint",
    "read_project",
    "read_rules",
    "read_symbol_library",
    "rebuild_board",
    "rebuild_drawing_sheet",
    "resolve_copper",
    "resolve_extends",
    "synthesize_project",
    "split_lib_id",
    "tree_equal",
    "update_project",
    "walk",
    "write_board",
    "write_footprint",
    "write_pretty",
    "write_rules",
    "write_triad",
    "write_drawing_sheet",
]
