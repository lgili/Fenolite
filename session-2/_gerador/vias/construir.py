# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""Build a sample script that binds ``KIT`` and ``kit_model`` the way ``fenolite kit build`` builds a kit
sample (``fenolite.cli._kit.build_sample``), and write its Altium files into a folder.

The ``build`` command gives such a script the copper of its DSL board (two or four layers); the stack of
six layers with two planes comes from ``KIT`` and ``kit_model``, which only the kit's build reads. This is
how ``board6/`` of Part O was built too (change c0138, design, "Found on 2026-10-07", 3).

Run from the root of a Fenolite checkout:

    uv run python <this file> <design.py> <output folder>
"""

from __future__ import annotations

import sys
from pathlib import Path

from fenolite.cli._kit import build_sample  # pyright: ignore[reportPrivateUsage]


def main() -> None:
    script, out = Path(sys.argv[1]), Path(sys.argv[2])
    sample = build_sample(script)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(sample.files.items()):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"{name} {len(data)}")


if __name__ == "__main__":
    main()
