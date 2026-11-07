# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fast suite runs every shipped block through the same tool-free runner (c0270)."""

import subprocess

import pytest

from fenolite.cli.blocksrc import find_blocks
from fenolite.testing.blocks import run_block_tests

SHIPPED = tuple(entry for entry in find_blocks() if entry.id.startswith("Fenolite:"))


@pytest.mark.parametrize("entry", SHIPPED, ids=lambda entry: entry.id)
def test_shipped_block(entry, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a shipped block test ran an external tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    result = run_block_tests((entry,))
    assert result.exit_code == 0, result.issues
    assert result.blocks[0]["usage"] == "passed" and result.blocks[0]["golden"] == "equal"
