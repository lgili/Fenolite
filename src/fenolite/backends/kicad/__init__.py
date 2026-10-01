# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad backend: S-expression syntax layer, slots, format versions, library and board readers, and
the ``kicad-cli`` runner.

Facts and sources: ``docs/formats/kicad/`` and ``PROVENANCE.md`` in this package.
"""

from fenolite.backends.kicad.cli import KicadCli, find_kicad_cli
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, split_lib_id
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import opaque_count, read_board, rebuild_board
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

__all__ = [
    "MAX_DEPTH",
    "Atom",
    "AtomKind",
    "KicadCli",
    "LibraryConfig",
    "LibraryError",
    "LibraryResolver",
    "Node",
    "dumps",
    "find_kicad_cli",
    "first_difference",
    "load",
    "opaque_count",
    "parse",
    "parse_bytes",
    "parse_fragment",
    "read_board",
    "read_footprint",
    "read_symbol_library",
    "rebuild_board",
    "resolve_extends",
    "split_lib_id",
    "tree_equal",
    "walk",
]
