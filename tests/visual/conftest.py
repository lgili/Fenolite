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


@pytest.fixture(scope="session")
def buck_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The exported page of c0222's `bad` buck reference board (examples/roles, authored for Fenolite)."""
    from _visual import ROOT, _cli, browser_missing, export

    if browser_missing():
        pytest.skip("the browser is missing")
    folder = tmp_path_factory.mktemp("buck")
    script = ROOT / "examples" / "roles" / "buck_shunt" / "bad.py"
    plan = _cli("build", str(script), "--out", str(folder / "build"), "--dry-run", "--json")["result"][
        "plan_id"
    ]
    _cli("build", str(script), "--out", str(folder / "build"), "--confirm", "--plan", plan, "--json")
    return export(folder / "build" / "buck_shunt_bad.kicad_pro", folder / "buck.html", "--no-models")


@pytest.fixture(scope="session")
def buck_roles_page(buck_page: Path) -> Path:
    """The bad buck exported in its Net Roles workspace (change c0245)."""
    from _visual import export

    project = buck_page.parent / "build" / "buck_shunt_bad.kicad_pro"
    return export(project, buck_page.parent / "buck_roles.html", "--no-models", "--workspace", "roles")
