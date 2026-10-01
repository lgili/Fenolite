# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad backend: S-expression syntax layer and slots (typed readers and writers come later).

Facts and sources: ``docs/formats/kicad/`` and ``PROVENANCE.md`` in this package.
"""

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

__all__ = [
    "MAX_DEPTH",
    "Atom",
    "AtomKind",
    "Node",
    "dumps",
    "first_difference",
    "load",
    "parse",
    "parse_bytes",
    "parse_fragment",
    "tree_equal",
    "walk",
]
