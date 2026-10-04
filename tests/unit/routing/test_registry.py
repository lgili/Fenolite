# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Entry-point loading failures and duplicate router names remain inspectable, not fatal."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from fenolite.routing import registry
from fenolite.routing.protocol import RouterStatus, RoutingJob, RoutingResult


@dataclass
class StubRouter:
    name: str = "sample"
    description: str = "test router"
    sends_data_offsite: bool = False

    def available(self) -> RouterStatus:
        return RouterStatus(True)

    def route(self, job: RoutingJob) -> RoutingResult:
        return RoutingResult()


class FakePoint:
    def __init__(self, name: str, value: str, loaded: object | None = None, error: Exception | None = None):
        self.name, self.value, self.loaded, self.error = name, value, loaded, error

    def load(self) -> object:
        if self.error:
            raise self.error
        assert self.loaded is not None
        return self.loaded


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_BUILTINS", {})
    monkeypatch.setattr(registry, "_UNAVAILABLE", {})
    monkeypatch.setattr(registry, "_loaded", False)


def test_loads_entry_points_and_keeps_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    points = [
        FakePoint("good", "pkg:Good", StubRouter("good")),
        FakePoint("broken", "pkg:Broken", error=ImportError("missing optional package")),
    ]
    monkeypatch.setattr(registry, "entry_points", lambda: SimpleNamespace(select=lambda *, group: points))

    assert tuple(registry.routers()) == ("good",)
    assert "missing optional package" in registry.unavailable()["broken"]


def test_builtin_router_names_are_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    points = [
        FakePoint("direct", "fenolite.routing.direct:DirectRouter", StubRouter("direct")),
        FakePoint(
            "kicadroutingtools",
            "fenolite.routing.plugins.kicad.routingtools:KicadRoutingToolsRouter",
            StubRouter("kicadroutingtools"),
        ),
    ]
    monkeypatch.setattr(registry, "entry_points", lambda: SimpleNamespace(select=lambda *, group: points))
    assert tuple(registry.routers()) == ("direct", "kicadroutingtools")


def test_ignores_duplicate_router_names_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    points = [
        FakePoint("first", "pkg:first", StubRouter("sample")),
        FakePoint("second", "pkg:second", StubRouter("sample")),
    ]
    monkeypatch.setattr(registry, "entry_points", lambda: SimpleNamespace(select=lambda *, group: points))

    with pytest.warns(UserWarning, match="duplicate router entry point"):
        loaded = registry.routers()
    assert tuple(loaded) == ("sample",)
    assert "duplicate router name 'sample'" in registry.unavailable()["second"]
