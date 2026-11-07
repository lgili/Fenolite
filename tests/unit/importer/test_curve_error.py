# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Importer emission keeps explicit target-project geometry configuration (c0340)."""

from __future__ import annotations

import ast
import dataclasses

from _importcode import PROJECT

from fenolite.importer.emit import Options, emit
from fenolite.importer.provenance import Provenance
from fenolite.importer.source import read_kicad


def test_importer_emits_explicit_curve_error_only_when_present() -> None:
    original = read_kicad(PROJECT)
    assert original.design.board is not None
    for value in (None, 10_000):
        board = dataclasses.replace(original.design.board, max_curve_error=value)
        source = dataclasses.replace(original, design=dataclasses.replace(original.design, board=board))
        made = emit(source, Options("authored_geometry", Provenance(date="2026-11-02"), target=9))
        module = ast.parse(made.files["design.py"])
        call = next(
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "board"
        )
        setting = next((keyword.value for keyword in call.keywords if keyword.arg == "max_curve_error"), None)
        if value is None:
            assert setting is None
        else:
            assert isinstance(setting, ast.Call)
            assert isinstance(setting.func, ast.Name) and setting.func.id == "mm"
            assert len(setting.args) == 1 and isinstance(setting.args[0], ast.Constant)
            assert setting.args[0].value == "0.01"
