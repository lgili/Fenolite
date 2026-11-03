# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independently authored empty/literal-number native symbol and connected two-pin sheet (c0353)."""

from __future__ import annotations

import uuid

from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind


def identity(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "fenolite:authored-empty-number:" + name))


def library(source, number=None, *, unit=1, style=1, empty_name=False):
    number = ("~" if source == 9 else "") if number is None else number
    name = ("~" if source == 9 else "") if empty_name else "AUTH_EMPTY"
    return f'''(kicad_symbol_lib (version {FORMAT_VERSIONS[FileKind.SYMBOL_LIB][source]})
      (generator "fenolite")
      (symbol "Blank" (pin_names (offset 0)) (in_bom yes) (on_board yes)
        (property "Reference" "J" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
        (property "Value" "Blank" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
        (symbol "Blank_{unit}_{style}"
          (pin passive line (at -5.08 0 0) (length 2.54)
            (name "{name}" (effects (font (size 1.27 1.27))))
            (number "{number}" (effects (font (size 1.27 1.27)))))
          (pin passive line (at 5.08 0 180) (length 2.54)
            (name "AUTH_CONTROL" (effects (font (size 1.27 1.27))))
            (number "2" (effects (font (size 1.27 1.27))))) )))'''


def definition(source, number=None, **kwargs):
    return read_symbol_library(library(source, number, **kwargs), library="Author")[0]


def schematic(source, embedded=None, *, number=None, empty_name=False):
    if embedded is None:
        item = parse(library(source, number, empty_name=empty_name)).find("symbol")
        item = item.with_children((Atom.string("Author:Blank"), *item.children[1:]))
    else:
        item = embedded.node
    root = identity("root")
    header = FORMAT_VERSIONS[FileKind.SCHEMATIC][source]
    return f'''(kicad_sch (version {header}) (generator "fenolite")
      (uuid "{root}") (paper "A4") (lib_symbols {dumps(item)})
      (symbol (lib_id "Author:Blank") (at 100 100 0) (unit 1)
        (in_bom yes) (on_board yes) (dnp no) (uuid "{identity("component")}")
        (property "Reference" "J1" (at 100 105.08 0) (effects (font (size 1.27 1.27))))
        (property "Value" "Blank" (at 100 102.54 0) (effects (font (size 1.27 1.27))))
        (instances (project "tiny" (path "/{root}" (reference "J1") (unit 1)))))
      (label "AUTH_EMPTY" (at 94.92 100 0) (effects (font (size 1.27 1.27)))
        (uuid "{identity("empty-label")}"))
      (label "AUTH_CONTROL" (at 105.08 100 0) (effects (font (size 1.27 1.27)))
        (uuid "{identity("control-label")}"))
      (sheet_instances (path "/" (page "1"))))'''
