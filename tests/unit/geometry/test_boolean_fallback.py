# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boolean backend protocol, selection and the stdlib fallback (capability geometry-boolean-backends)."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from collections.abc import Iterator, Sequence
from types import ModuleType

import pytest

from fenolite.geometry import GeometryError, Point, Polygon, normalize_polygons
from fenolite.geometry.boolean import (
    BACKEND_ORDER,
    COORD_LIMIT,
    BooleanBackend,
    FallbackBackend,
    available_backends,
    select_backend,
)
from fenolite.geometry.errors import BackendUnavailable

P = Point


def square(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)))


class _BlockExtras(importlib.abc.MetaPathFinder):
    """Import hook that makes the geo extra look uninstalled."""

    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.split(".")[0] in ("shapely", "pyclipper"):
            raise ModuleNotFoundError(f"No module named {fullname!r} (blocked by the test)")
        return None


@pytest.fixture
def no_extras(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in list(sys.modules):
        if name.split(".")[0] in ("shapely", "pyclipper"):
            monkeypatch.delitem(sys.modules, name)
    blocker = _BlockExtras()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)


def test_fallback_satisfies_the_protocol() -> None:
    backend = FallbackBackend()
    assert isinstance(backend, BooleanBackend)
    assert backend.name == "fallback"
    assert backend.operations == frozenset({"intersection"})


def test_result_in_normal_form() -> None:
    first = Polygon((P(0, 10), P(10, 10), P(10, 0), P(0, 0)))
    result = FallbackBackend().intersection(first, square(5, 5, 15, 15))
    assert result == (Polygon((P(5, 5), P(10, 5), P(10, 10), P(5, 10))),)
    assert normalize_polygons(result) == result


def test_convex_intersection_without_extras(no_extras: None) -> None:
    result = select_backend().intersection([square(0, 0, 10, 10)], [square(5, 5, 15, 15)])
    assert result == (Polygon((P(5, 5), P(10, 5), P(10, 10), P(5, 10))),)


def test_touching_and_disjoint_are_empty() -> None:
    backend = FallbackBackend()
    assert backend.intersection(square(0, 0, 10, 10), square(10, 0, 20, 10)) == ()
    assert backend.intersection(square(0, 0, 10, 10), square(20, 0, 30, 10)) == ()


def test_sliver_collapses_on_rounding() -> None:
    triangle = Polygon((P(0, 10), P(30, 9), P(30, 20)))
    assert FallbackBackend().intersection(square(0, 0, 10, 10), triangle) == ()


@pytest.mark.parametrize("operation", ["union", "difference", "xor", "offset"])
def test_other_operations_unavailable(operation: str) -> None:
    backend = FallbackBackend()
    with pytest.raises(BackendUnavailable) as info:
        if operation == "union":
            backend.union([square(0, 0, 10, 10)])
        elif operation == "offset":
            backend.offset([square(0, 0, 10, 10)], 100)
        else:
            getattr(backend, operation)(square(0, 0, 10, 10), square(5, 5, 15, 15))
    assert info.value.issue.code == "geometry.backend-unavailable"
    assert "fenolite[geo]" in info.value.issue.hint


def test_concave_operand_refused() -> None:
    l_shape = Polygon((P(0, 0), P(20, 0), P(20, 10), P(10, 10), P(10, 20), P(0, 20)))
    with pytest.raises(BackendUnavailable) as info:
        FallbackBackend().intersection(square(0, 0, 5, 5), l_shape)
    assert info.value.issue.code == "geometry.backend-unavailable"
    assert "operand b" in info.value.issue.message
    with pytest.raises(BackendUnavailable):
        FallbackBackend().intersection([square(0, 0, 5, 5), square(6, 6, 7, 7)], square(0, 0, 9, 9))


def test_out_of_range_coordinate() -> None:
    far = Polygon((P(0, 0), P(2**31, 0), P(0, 10)))
    with pytest.raises(GeometryError) as info:
        FallbackBackend().intersection(far, square(0, 0, 10, 10))
    assert info.value.code == "geometry.out-of-range"
    assert COORD_LIMIT == 2**31 - 1
    edge = Polygon((P(0, 0), P(COORD_LIMIT, 0), P(0, 10)))
    assert FallbackBackend().intersection(edge, square(0, 0, 10, 10)) != ()
    with pytest.raises(GeometryError) as info:
        FallbackBackend().offset(edge, 1)
    assert info.value.code == "geometry.out-of-range"


def test_default_without_extras(no_extras: None) -> None:
    assert BACKEND_ORDER == ("fallback",)
    assert isinstance(select_backend(), FallbackBackend)
    assert available_backends() == ("fallback",)
    assert isinstance(select_backend("fallback"), FallbackBackend)


def test_unknown_backend_name() -> None:
    with pytest.raises(ValueError, match="fallback"):
        select_backend("cgal")
