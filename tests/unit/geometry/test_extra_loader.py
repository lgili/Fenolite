# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The single loader of the geo extra (capability geometry-boolean-backends)."""

from __future__ import annotations

import sys

import pytest

from fenolite.geometry.boolean._extra import GEO_MODULES, load_extra
from fenolite.geometry.errors import BackendUnavailable


def test_geo_modules() -> None:
    assert GEO_MODULES == ("pyclipper", "shapely")


@pytest.mark.parametrize("name", GEO_MODULES)
def test_extra_missing(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setitem(sys.modules, name, None)  # makes the import fail like an absent package
    with pytest.raises(BackendUnavailable) as info:
        load_extra(name)
    assert info.value.issue.code == "geometry.backend-unavailable"
    assert info.value.issue.severity == "error"
    assert "fenolite[geo]" in info.value.issue.hint


def test_name_outside_the_extra() -> None:
    with pytest.raises(ValueError, match="GEO_MODULES"):
        load_extra("numpy")


def test_loads_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    fake = types.ModuleType("shapely")
    monkeypatch.setitem(sys.modules, "shapely", fake)
    assert load_extra("shapely") is fake
