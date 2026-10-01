# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact integer geometry: predicates, shapes, polygons, transforms, spatial index, booleans.

Stdlib-only (imports ``fenolite.core`` only). Coordinates are integer nanometres in the KiCad file
frame (X right, Y down), angles integer microdegrees. Functions that return points return integer
nanometres; exact rational results are ``Fraction``; nothing returns a ``float``. See
``docs/geometry.md``.
"""

from __future__ import annotations

from fenolite.geometry.boolean import BACKEND_ORDER, BooleanBackend, available_backends, select_backend
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.polygon import (
    Path,
    Piece,
    Polygon,
    Ring,
    area2,
    assemble_rings,
    clip_convex,
    convex_hull,
    normalize_polygons,
    polygons_intersect,
)
from fenolite.geometry.predicates import (
    FillRule,
    Location,
    SegmentRelation,
    ceil_sqrt,
    classify_segments,
    dist2_point_segment,
    dist2_segment_segment,
    floor_sqrt,
    intersection_point,
    orient2d,
    point_in_ring,
    round_point,
    segments_closer_than,
)
from fenolite.geometry.shapes import DEFAULT_TOL, MAX_BISECTION_DEPTH, Arc, BBox, Circle, Segment
from fenolite.geometry.transform import FULL_TURN, TRIG_BITS, Transform, cos_sin_fixed, rotate_point
from fenolite.geometry.vector import Point, Size, Vec, add, cross, dot, neg, norm2, sub

__all__ = [
    "BACKEND_ORDER",
    "DEFAULT_TOL",
    "FULL_TURN",
    "MAX_BISECTION_DEPTH",
    "TRIG_BITS",
    "Arc",
    "BBox",
    "BackendUnavailable",
    "BooleanBackend",
    "Circle",
    "FillRule",
    "GeometryError",
    "Location",
    "Path",
    "Piece",
    "Point",
    "Polygon",
    "Ring",
    "Segment",
    "SegmentRelation",
    "Size",
    "SpatialIndex",
    "Transform",
    "Vec",
    "add",
    "area2",
    "assemble_rings",
    "available_backends",
    "ceil_sqrt",
    "classify_segments",
    "clip_convex",
    "convex_hull",
    "cos_sin_fixed",
    "cross",
    "dist2_point_segment",
    "dist2_segment_segment",
    "dot",
    "floor_sqrt",
    "intersection_point",
    "neg",
    "norm2",
    "normalize_polygons",
    "orient2d",
    "point_in_ring",
    "polygons_intersect",
    "rotate_point",
    "round_point",
    "segments_closer_than",
    "select_backend",
    "sub",
]
