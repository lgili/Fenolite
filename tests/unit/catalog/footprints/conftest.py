# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint generator tests import ``_package_records`` (here) and get the fixture ``record``."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _package_records import edited  # noqa: E402  (imported after the sys.path setup above)

from fenolite.catalog.footprints.record import Package  # noqa: E402


@pytest.fixture
def record() -> Callable[..., Package]:
    """``record(stem, edit=None)``: the authored record ``stem``, edited in place by ``edit``."""
    return edited
