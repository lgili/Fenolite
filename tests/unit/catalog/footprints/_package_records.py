# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored package records of tests/data/packages for the footprint generator tests (change c0260)."""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from fenolite.catalog.footprints.record import Package, package_from

PACKAGES = Path(__file__).resolve().parents[3] / "data" / "packages"
RECORDS = tuple(sorted(path.stem for path in PACKAGES.glob("*.toml")))
"""The stems of every authored test record, one or more per family."""

Raw = dict[str, Any]


def raw_record(stem: str) -> Raw:
    """The parsed TOML table of ``tests/data/packages/<stem>.toml``."""
    return tomllib.loads((PACKAGES / f"{stem}.toml").read_text(encoding="utf-8"), parse_float=Decimal)


def edited(stem: str, edit: Callable[[Raw], None] | None = None) -> Package:
    """The record ``stem`` after ``edit`` changed its parsed table in place."""
    raw = copy.deepcopy(raw_record(stem))
    if edit is not None:
        edit(raw)
    return package_from(raw, file=f"{stem}.toml")
