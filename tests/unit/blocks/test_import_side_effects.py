# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Importing the shipped blocks is clean (capability block-library, "Catalog sources of blocks", scenario
"Import of the shipped blocks is clean"; change c0268): in a fresh process, importing ``fenolite.blocks``
and its modules creates no design, opens no file and imports no third-party module."""

from __future__ import annotations

import json
import subprocess
import sys

PROBE = r"""
import builtins, io, json, pkgutil, sys
import fenolite.dsl.design as design_module
before = set(sys.modules)
opened = []
made = []
real_open, real_io_open = builtins.open, io.open
def watch(file, *args, **kwargs):
    opened.append(str(file))
    return real_open(file, *args, **kwargs)
builtins.open = io.open = watch
real_init = design_module.Design.__init__
def init(self, *args, **kwargs):
    made.append(args)
    real_init(self, *args, **kwargs)
design_module.Design.__init__ = init
import importlib
package = importlib.import_module("fenolite.blocks")
for info in pkgutil.walk_packages(package.__path__, "fenolite.blocks."):
    importlib.import_module(info.name)
builtins.open, io.open = real_open, real_io_open
after = {name.split(".")[0] for name in set(sys.modules) - before}
own = ("fenolite", "_fenolite")
third = sorted(name for name in after if name not in sys.stdlib_module_names and name not in own)
print(json.dumps({"opened": [p for p in opened if not p.endswith(".py")], "made": len(made), "third": third}))
"""


def test_import_of_the_shipped_blocks_is_clean() -> None:
    """Scenario "Import of the shipped blocks is clean"."""
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"opened": [], "made": 0, "third": []}
