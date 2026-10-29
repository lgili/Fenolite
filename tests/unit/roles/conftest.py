# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tests of the net roles import ``_rolecircuits`` and ``_roleboards`` (here)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from collections.abc import Callable  # noqa: E402

import pytest  # noqa: E402
from _roleboards import Built, build  # noqa: E402


@pytest.fixture(scope="session")
def reference(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., Built]:
    """``reference(board, variant, target="kicad")``: the variant built once per session (a KiCad build with
    the fill of ``fill_as_outline``). Tests copy a build before they change it."""
    made: dict[tuple[str, str, str], Built] = {}

    def get(board: str, variant: str, target: str = "kicad") -> Built:
        key = (board, variant, target)
        if key not in made:
            out = tmp_path_factory.mktemp(f"{board}_{variant}_{target}") / "out"
            made[key] = build(board, variant, out, target=target)
        return made[key]

    return get


@pytest.fixture(scope="session")
def role_copper(tmp_path_factory: pytest.TempPathFactory) -> Callable[..., Built]:
    """``role_copper(board, variant, target="kicad")``: the role-copper script ``<variant>_roles.py`` of a
    reference board (change c0243) built once per session, its zones left unfilled as KiCad leaves a new
    zone (the judge reads the simulated pour). The planner's outcome of the build is kept in
    ``OUTCOMES[built.out]``. Tests copy a build before they change it."""
    from _roleboards import EXAMPLES
    from _rolecopper import build_role

    made: dict[tuple[str, str, str], Built] = {}

    def get(board: str, variant: str, target: str = "kicad") -> Built:
        key = (board, variant, target)
        if key not in made:
            out = tmp_path_factory.mktemp(f"{board}_{variant}_roles_{target}") / "out"
            made[key] = build_role(EXAMPLES / board / f"{variant}_roles.py", out, target=target)
        return made[key]

    return get
