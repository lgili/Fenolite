# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exact stimulus example on the block-testing page runs without a tool (c0270)."""

import subprocess
import sys
from pathlib import Path
from types import ModuleType

from fenolite.agent import guide
from fenolite.cli.blocksrc import import_file


def test_stimulus_guide_example(monkeypatch):
    module = ModuleType("divider")
    module.divider = import_file(Path(__file__).resolve().parents[2] / "data/blocks/lib/divider.py").divider
    monkeypatch.setitem(sys.modules, "divider", module)

    def refuse(*args, **kwargs):
        raise AssertionError("the guide example ran an external tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    (block,) = [b for b in guide.blocks(guide.page("block-testing")) if "def test_output():" in b.lines]
    scope = {}
    exec(compile("\n".join(block.lines), "guide-block-testing", "exec"), scope)
    scope["test_output"]()
