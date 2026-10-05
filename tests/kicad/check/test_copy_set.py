# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC on the planned copy set equals DRC on a copy of the whole project folder (``H-K-CHECK-COPYSET``;
capability kicad-oracle, "Check project copy set", scenario "Copy set equals the folder")."""

from __future__ import annotations

import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


def test_copy_set_equals_folder() -> None:
    assert run("check-copyset") == "equal"


def test_copy_set_equals_folder_with_a_schematic() -> None:
    """The second proof of ``H-K-CHECK-COPYSET`` (change c0062): the folder holds a schematic, its symbol
    libraries and table, and the run asks for the parity test."""
    assert run("check-copyset-schematic") == "equal"
