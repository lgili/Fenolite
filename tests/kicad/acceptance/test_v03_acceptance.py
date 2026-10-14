# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""H-A-ACC-V03: full acceptance on the CI KiCad 10 importer; never a prepared-only pass."""

import json

import pytest
from _v03acceptance import result

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_v03_acceptance() -> None:
    measured = result()
    assert measured["acceptance_complete"], json.dumps(measured, indent=2)
    assert all(step["passed"] for step in measured["steps"])
