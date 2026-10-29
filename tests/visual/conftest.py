# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the visual tests, written once per run (change c0191)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    from _visual import browser_missing, pages

    if browser_missing():
        pytest.skip("the browser is missing")  # the tests themselves skip, or fail, with the reason
    return pages(tmp_path_factory.mktemp("pages"))


@pytest.fixture(scope="session")
def stress_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The exported page of the authored stress board (change c0245, decision 7)."""
    from _stress_board import write
    from _visual import browser_missing, export

    if browser_missing():
        pytest.skip("the browser is missing")
    folder = tmp_path_factory.mktemp("stress")
    board = write(folder / "stress.kicad_pcb")
    return export(board, folder / "stress.html", "--no-models")
