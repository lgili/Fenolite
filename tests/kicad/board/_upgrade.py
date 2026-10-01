# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``kicad-cli`` for the board oracle tests, and ``pcb upgrade --force`` copies made once per session.

Upgraded copies stay in memory and are never written to the repository (capability corpus-policy,
"Upgraded copies keep their origin").
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return KicadCli(Path(path), timeout=600)


@cache
def upgraded(path: Path) -> str:
    """The board at ``path`` re-saved by ``pcb upgrade --force`` in the running version's format."""
    return runner().upgrade_board(path).decode("utf-8")
