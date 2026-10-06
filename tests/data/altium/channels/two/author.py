# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Write the authored two-channel project of change c0083 beside this script: ``two.PrjPcb``,
``two.SchDoc`` (a sheet symbol ``Repeat(CH,1,2)`` with the entries ``VCC`` and ``Repeat(OUT)``, the bus
``OUT[1..2]``) and ``two_ch.SchDoc`` (``R1``, ``C12``, the ports ``VCC`` and ``OUT``, the net ``MID``).

The records are those of ``tests/_altium_channels.py``, framed by the test builders and placed in a
compound file by the product's writer. Run from the repository root:

    uv run python tests/data/altium/channels/two/author.py

``tests/unit/backends/altium/adapter/test_channel_files.py`` keeps the files equal to what this writes.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

import _altium_channels as two  # noqa: E402 (the path above comes first)


def main() -> None:
    for name, data in two.files().items():
        (HERE / name).write_bytes(data)
        print(f"wrote {name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
