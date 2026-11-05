# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The 3D models and the bodies of an Altium board, placed for the derived KiCad library (capability
design-conversion, "Model placement of imported footprints" and "Generated models of imported bodies";
changes c0223 and c0423; ``docs/conversion.md``, "3D models").

``models3d.body_models`` (c0193) gives each embedded model with its bytes and its pose in the board frame
(``H-A-BODY-MODEL-PLACE``). Here it becomes a ``ModelPlacement`` in its footprint's own frame, the offset and
the turns that make KiCad's pose (``H-K-MODEL-POSE``) equal to the source's, on either side and for any turn.
A body that no embedded model carries becomes a STEP file of ``backends.step``: its prism, cylinder or
sphere, placed with offset and rotation 0. Nothing is read or written here: the caller gives the models and
the body forms and writes the files.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends import step
from fenolite.backends.base import BodyForm, BodyModel, BodyShape
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import ComponentBody, FootprintInstance
from fenolite.model.library import ModelPlacement

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-BODY-MODEL-PLACE", "H-K-MODEL-POSE"))
KIND = "model"
BODY_KIND = "body"
FOLDER_SUFFIX = ".3dshapes"
PLACED = "the embedded model is extracted beside the library and placed in the library footprint"
NO_DATA = "the body names a model that the document does not embed"
CARRIED = "carried by its embedded model"
GENERATED = "written as a generated STEP model"
PRISM = "written as the prism over its outline: {why}"
NOT_CYLINDER = "a cylinder whose outline is no square or that is turned about X or Y"
NOT_SPHERE = "a sphere whose outline side differs from its height span"
UNKNOWN = "the body's geometry is not proved (its projection or heights); no model is written"
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")
HALF_TURN = FULL_TURN // 2
UDEG = 1_000_000
FIT = 1_000
"""How far, in nm, the sides of a cylinder's or sphere's outline box may differ from each other and from a
sphere's height span: the box is the square around the shape (``pcb-bodies.md``, S-1604)."""
LOCK = 1e-9
"""Below this ``cos β`` the turns about X and Z are one: X is taken as 0 (design, Decision 2)."""

Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class Placed:
    """What ``place_models`` gives: per footprint instance id its placements, the model files (path below
    the project → bytes), and the report rows, body id → reason, of models placed and lost (kind ``model``)
    and of bodies changed and lost (kind ``body``)."""

    placements: Mapping[str, tuple[ModelPlacement, ...]] = field(default_factory=lambda: {})
    files: Mapping[str, bytes] = field(default_factory=lambda: {})
    changed: Mapping[str, str] = field(default_factory=lambda: {})
    lost: Mapping[str, str] = field(default_factory=lambda: {})
    bodies_changed: Mapping[str, str] = field(default_factory=lambda: {})
    bodies_lost: Mapping[str, str] = field(default_factory=lambda: {})


def model_file(library: str, footprint: str, data: bytes) -> str:
    """``<library>.3dshapes/<footprint>_<sha12>.step``: the folder beside the library, the footprint's name
    with characters outside ``[A-Za-z0-9_.-]`` replaced by ``_``, and the first 12 hex digits of the
    SHA-256 of the model's bytes."""
    return f"{library}{FOLDER_SUFFIX}/{_stem(footprint)}_{hashlib.sha256(data).hexdigest()[:12]}.step"


def _stem(footprint: str) -> str:
    return _UNSAFE.sub("_", footprint) or "model"


def _turn(udeg: int) -> int:
    """``udeg`` brought into (−180°, 180°]."""
    turn = udeg % FULL_TURN
    return turn - FULL_TURN if turn > HALF_TURN else turn


def _axis(axis: int, udeg: int) -> Matrix:
    """The turn about axis ``axis`` (0 x, 1 y, 2 z) by ``udeg``, counter-clockwise seen from the axis."""
    angle = math.radians(udeg / UDEG)
    c, s = math.cos(angle), math.sin(angle)
    if axis == 0:
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == 1:
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _times(a: Matrix, b: Matrix) -> Matrix:
    rows = [tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)]
    return (rows[0], rows[1], rows[2])  # type: ignore[return-value]


def _udeg(radians: float) -> int:
    return _turn(round(math.degrees(radians) * UDEG))


def turns(matrix: Matrix) -> tuple[int, int, int]:
    """``(α, β, γ)`` in µdeg with ``matrix = Rz(γ) · Ry(β) · Rx(α)`` (design, Decision 2)."""
    (r00, r01, _r02), (r10, r11, _r12), (r20, r21, r22) = matrix
    cos_beta = math.hypot(r00, r10)
    beta = math.atan2(-r20, cos_beta)
    if cos_beta < LOCK:
        return (0, _udeg(beta), _udeg(math.atan2(-r01, r11)))
    return (_udeg(math.atan2(r21, r22)), _udeg(beta), _udeg(math.atan2(r10, r00)))


def rotation_matrix(rotation: tuple[int, int, int]) -> Matrix:
    """``Rz(z) · Ry(y) · Rx(x)`` of turns in µdeg, counter-clockwise seen from each axis."""
    rx, ry, rz = rotation
    return _times(_axis(2, rz), _times(_axis(1, ry), _axis(0, rx)))


def placement(model: BodyModel, footprint: FootprintInstance, path: str) -> ModelPlacement:
    """The placement of ``model`` in the frame of ``footprint`` that gives KiCad the source's pose: KiCad
    puts a point ``p`` at ``T(position, face) · Rz(θ) · F · (Rz(γ)·Ry(β)·Rx(α)·p + o)`` (``H-K-MODEL-POSE``,
    with the placement's own angles), the source at ``T(position, face) · F · (R_A·p + (0, 0, z))``, so
    ``Rz(γ)·Ry(β)·Rx(α) = F·Rz(−θ)·F·R_A`` and ``o = F·Rz(−θ)·Δ + (0, 0, z)``."""
    bottom = footprint.side == "bottom"
    local = Transform.placement(footprint.position, footprint.rotation).inverse().apply(model.position)
    offset = (local.x, -local.y if bottom else local.y, model.z)
    rx, ry, rz = model.rotation
    if rx % FULL_TURN == 0 and ry % FULL_TURN == 0:  # c0223's exact case: a turn about Z alone
        turn = rz + footprint.rotation if bottom else rz - footprint.rotation
        return ModelPlacement(path=path, offset=offset, rotation=(0, 0, _turn(turn)))
    theta = footprint.rotation if bottom else -footprint.rotation
    solved = turns(_times(_axis(2, theta), rotation_matrix(model.rotation)))
    return ModelPlacement(path=path, offset=offset, rotation=solved)


@dataclass(frozen=True, slots=True)
class _Shape:
    solid: step.Solid | None
    reason: str


def _box(points: Sequence[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def body_solid(body: ComponentBody, side: str, shape: BodyShape, rotation: tuple[int, int, int]) -> _Shape:
    """The solid of ``body`` in its model frame, with the reason the report gives (design, Decision 3): the
    outline with Y up on the top and with Y as the pad frame holds it on the bottom, so that KiCad's flip
    puts it below the bottom face; ``None`` with the reason of a loss."""
    if body.projection_unknown or body.z_min is None or body.z_max is None:
        return _Shape(None, UNKNOWN)
    lo, hi = body.z_min, body.z_max
    ring = tuple((p.x, p.y if side == "bottom" else -p.y) for p in body.outline)
    if len(ring) < 3 or hi <= lo:
        return _Shape(None, "the body has no outline or no height; no model is written")
    prism = step.Prism(ring, lo, hi, "body")
    x0, y0, x1, y1 = _box(ring)
    width, depth = x1 - x0, y1 - y0
    centre = ((x0 + x1) // 2, (y0 + y1) // 2)
    rx, ry, _rz = rotation
    if shape == "cylinder":
        if abs(width - depth) > FIT or rx % HALF_TURN or ry % HALF_TURN:
            return _Shape(prism, PRISM.format(why=NOT_CYLINDER))
        return _Shape(step.cylinder(centre, (width + depth) // 4, lo, hi, "body"), GENERATED)
    if shape == "sphere":
        span = hi - lo
        if abs(width - depth) > FIT or abs(width - span) > FIT:
            return _Shape(prism, PRISM.format(why=NOT_SPHERE))
        radius = span // 2
        return _Shape(step.Sphere((centre[0], centre[1], lo + radius), radius, "body"), GENERATED)
    if shape == "model":
        return _Shape(prism, PRISM.format(why="its embedded model is missing"))
    if shape == "other":
        return _Shape(prism, PRISM.format(why="its model type is not one Fenolite knows"))
    return _Shape(prism, GENERATED)


def place_models(
    footprints: Iterable[FootprintInstance],
    models: Iterable[BodyModel],
    library: str,
    name_of: Callable[[FootprintInstance], str],
    forms: Iterable[BodyForm] = (),
) -> Placed:
    """The placements of ``footprints``' embedded models (bodies of kind ``model``, matched to ``models`` by
    the body's locator) and of a generated STEP model per footprint for its other bodies, matched to
    ``forms`` by locator; ``name_of`` gives a footprint's name in the library ``library``."""
    by_locator = {model.locator: model for model in models}
    form_of = {form.locator: form for form in forms}
    placements: dict[str, tuple[ModelPlacement, ...]] = {}
    files: dict[str, bytes] = {}
    changed: dict[str, str] = {}
    lost: dict[str, str] = {}
    bodies_changed: dict[str, str] = {}
    bodies_lost: dict[str, str] = {}
    for footprint in footprints:
        found: list[ModelPlacement] = []
        generated: list[tuple[str, step.Solid, str]] = []
        name = name_of(footprint)
        for body in footprint.bodies:
            where = body.provenance.locator if body.provenance is not None else ""
            form = form_of.get(where)
            shape: BodyShape = form.shape if form is not None else body.kind
            if body.kind == "model":
                model = by_locator.get(where)
                if model is None:
                    lost[body.id] = NO_DATA
                    shape = "model"
                else:
                    path = model_file(library, name, model.data)
                    files[path] = model.data
                    found.append(placement(model, footprint, "${KIPRJMOD}/" + path))
                    changed[body.id] = PLACED
                    bodies_changed[body.id] = CARRIED
                    continue
            made = body_solid(body, footprint.side, shape, form.rotation if form is not None else (0, 0, 0))
            if made.solid is None:
                bodies_lost[body.id] = made.reason
            else:
                generated.append((body.id, made.solid, made.reason))
        writable: list[tuple[str, step.Solid, str]] = []
        for ident, solid, reason in generated:
            try:
                step.write_solids(_stem(name), [solid])
            except ValueError as error:
                bodies_lost[ident] = f"no STEP model can be written for the body: {error}"
            else:
                writable.append((ident, solid, reason))
        generated = writable
        if generated:
            data = step.write_solids(_stem(name), [solid for _, solid, _ in generated])
            if data:
                path = model_file(library, name, data)
                files[path] = data
                found.append(ModelPlacement(path="${KIPRJMOD}/" + path))
                for ident, _, reason in generated:
                    bodies_changed[ident] = reason
        if found:
            placements[footprint.id] = tuple(found)
    return Placed(placements, files, changed, lost, bodies_changed, bodies_lost)


__all__ = [
    "BODY_KIND",
    "CARRIED",
    "EVIDENCE",
    "GENERATED",
    "KIND",
    "NOT_CYLINDER",
    "NOT_SPHERE",
    "NO_DATA",
    "PLACED",
    "PRISM",
    "UNKNOWN",
    "Placed",
    "body_solid",
    "model_file",
    "place_models",
    "placement",
    "rotation_matrix",
    "turns",
]
