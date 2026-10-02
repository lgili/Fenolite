# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad backend: S-expression syntax layer, slots, format versions, library and board readers, the
board, footprint and custom-rules writers, and the ``kicad-cli`` runner.

Facts and sources: ``docs/formats/kicad/`` and ``PROVENANCE.md`` in this package.
"""

from fenolite.backends.kicad.cli import KicadCli, find_kicad_cli
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.dru import read_rules, write_rules
from fenolite.backends.kicad.embed import footprint_extent, place_footprint
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, split_lib_id
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.mod import board_footprints, read_footprint, write_footprint, write_pretty
from fenolite.backends.kicad.pcb import opaque_count, read_board, rebuild_board, write_board
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
from fenolite.backends.kicad.versions import LegacyEditRefusedError, LossyWriteError

__all__ = [
    "MAX_DEPTH",
    "Atom",
    "AtomKind",
    "KicadCli",
    "LegacyEditRefusedError",
    "LibraryConfig",
    "LibraryError",
    "LibraryResolver",
    "LossyWriteError",
    "Node",
    "board_footprints",
    "dumps",
    "find_kicad_cli",
    "first_difference",
    "footprint_extent",
    "load",
    "lower_rules",
    "opaque_count",
    "parse",
    "parse_bytes",
    "parse_fragment",
    "place_footprint",
    "read_board",
    "read_drc_report",
    "read_footprint",
    "read_rules",
    "read_symbol_library",
    "rebuild_board",
    "resolve_extends",
    "split_lib_id",
    "tree_equal",
    "walk",
    "write_board",
    "write_footprint",
    "write_pretty",
    "write_rules",
]
