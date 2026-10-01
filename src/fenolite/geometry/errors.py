# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exceptions of the geometry kernel.

``GeometryError`` carries a dotted ``code`` that follows ``fenolite.core.errors.ISSUE_CODE`` and the
points it is about; ``BackendUnavailable`` carries an ``Issue`` (an optional extra is missing or an
operation is outside a backend's scope). The CLI exit code for either is chosen by the first command
that uses geometry.
"""

from __future__ import annotations

from fenolite.core.coords import Point
from fenolite.core.errors import ISSUE_CODE, FenoliteError, Issue

DEGENERATE = "geometry.degenerate"
OUT_OF_RANGE = "geometry.out-of-range"
OPEN_CONTOUR = "geometry.open-contour"
BRANCHING_CONTOUR = "geometry.branching-contour"
BACKEND_UNAVAILABLE = "geometry.backend-unavailable"
GEOMETRY_CODES = frozenset({DEGENERATE, OUT_OF_RANGE, OPEN_CONTOUR, BRANCHING_CONTOUR})


def format_point(p: Point) -> str:
    return f"({p.x}, {p.y})"


class GeometryError(FenoliteError):
    """A geometric input or result that the kernel cannot represent (see ``GEOMETRY_CODES``)."""

    def __init__(self, message: str, *, code: str = DEGENERATE, points: tuple[Point, ...] = ()) -> None:
        if not ISSUE_CODE.match(code) or not code.startswith("geometry."):
            raise ValueError(f"invalid geometry error code {code!r}")
        self.code = code
        self.message = message
        self.points = points
        super().__init__(f"{code}: {message}")


class BackendUnavailable(FenoliteError):
    """A boolean backend or optional package cannot serve the request; ``issue`` says why and how."""

    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        super().__init__(f"{issue.code}: {issue.message}" + (f" ({issue.hint})" if issue.hint else ""))


def backend_unavailable(
    message: str, *, where: str = "", hint: str = "pip install 'fenolite[geo]'"
) -> BackendUnavailable:
    return BackendUnavailable(
        Issue(code=BACKEND_UNAVAILABLE, severity="error", message=message, where=where, hint=hint)
    )


__all__ = [
    "BACKEND_UNAVAILABLE",
    "BRANCHING_CONTOUR",
    "DEGENERATE",
    "GEOMETRY_CODES",
    "OPEN_CONTOUR",
    "OUT_OF_RANGE",
    "BackendUnavailable",
    "GeometryError",
    "backend_unavailable",
    "format_point",
]
