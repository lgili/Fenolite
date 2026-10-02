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
