# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference boards of the net roles (``examples/roles``) for tests outside ``tests/unit/roles`` (change
c0273): ``reference_board(board, variant, out)`` builds a variant to KiCad with the fill of
``_roleboards.fill_as_outline`` and gives the board file; ``roles_reply(board)`` is the envelope of
``fenolite roles BOARD --check --json`` run in process."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROLES_TESTS = HERE / "unit" / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))

from _roleboards import BOARDS, VARIANTS, build  # noqa: E402

from fenolite.cli.main import invoke  # noqa: E402


def reference_board(board: str, variant: str, out: Path) -> Path:
    """The KiCad board of ``examples/roles/<board>/<variant>.py`` built into ``out``."""
    return build(board, variant, out).board


def roles_reply(board: Path, *extra: str) -> dict[str, Any]:
    """The reply of ``fenolite roles BOARD --check`` (and ``extra``), run in process in the board's folder."""
    code, envelope, error = invoke(["roles", board.name, "--check", "--json", *extra], cwd=board.parent)
    assert code in (0, 5) and envelope is not None, (code, error)
    return envelope


__all__ = ["BOARDS", "VARIANTS", "reference_board", "roles_reply"]
