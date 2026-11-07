# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every shipped block carries runnable tests, usage and reviewed golden bytes (c0270)."""

import ast

import pytest

from fenolite.cli.blocksrc import find_blocks
from fenolite.testing.blocks import convention

SHIPPED = tuple(entry for entry in find_blocks() if entry.id.startswith("Fenolite:"))


@pytest.mark.parametrize("entry", SHIPPED, ids=lambda entry: entry.id)
def test_shipped_block_convention(entry):
    paths = convention(entry.definition)
    assert all(paths.paths().values()), (entry.id, paths.paths())
    tests = paths.path("tests")
    tree = ast.parse(tests.read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in tree.body)


def test_catalog_never_imports_convention_packages(tmp_path, monkeypatch):
    import fenolite.blocks

    for name in ("usage", "tests"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "__init__.py").write_text('raise AssertionError("convention package imported")')
    monkeypatch.setattr(fenolite.blocks, "__path__", [str(tmp_path)])
    monkeypatch.setattr(fenolite.blocks, "__all__", [])
    assert find_blocks() == ()
