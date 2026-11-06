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

The way back (change c0449): ``footprint_models`` reads each ``model`` child of a KiCad board footprint, finds
its STEP file beside the project, and gives the Altium write a ``pcbdoc.FootprintModel``: the pose that is the
inverse of ``placement`` (``altium_pose``), and the outline and heights of the placed model's box
(``stepbox.model_box``), or the reason it has no record.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath, PureWindowsPath

from fenolite.backends import step, stepbox
from fenolite.backends.altium import pcbdoc
from fenolite.backends.base import BodyForm, BodyModel, BodyShape
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.pcb import read_model_ref
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import ComponentBody, FootprintInstance, ModelRef
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
    """``<library>.3dshapes/<footprint>_<sha12>.step``: the folder beside the library, ``footprint`` (the
    footprint's name, or an embedded model's own name, ``model_stem``) with characters outside
    ``[A-Za-z0-9_.-]`` replaced by ``_``, and the first 12 hex digits of the SHA-256 of the model's bytes."""
    return f"{library}{FOLDER_SUFFIX}/{_stem(footprint)}_{hashlib.sha256(data).hexdigest()[:12]}.step"


def model_stem(name: str) -> str:
    """The name an extracted embedded model is filed under: the record's ``NAME`` without its STEP
    extension (``Belago1.1 v3.step`` → ``Belago1.1 v3``); empty when the record names none. A footprint
    whose name is that of another part keeps its model's own name, so the file does not seem to hold the
    other part's model (change c0449, task 4.3)."""
    stem = name.strip()
    lower = stem.lower()
    for suffix in (".step", ".stp"):
        if lower.endswith(suffix):
            return stem[: -len(suffix)].strip()
    return stem


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
    documents: Mapping[str, tuple[Iterable[BodyModel], Iterable[BodyForm]]] | None = None,
    frames: Mapping[str, FootprintInstance] | None = None,
) -> Placed:
    """The placements of ``footprints``' embedded models (bodies of kind ``model``, matched to ``models`` by
    the body's locator) and of a generated STEP model per footprint for its other bodies, matched to
    ``forms`` by locator; ``name_of`` gives a footprint's name in the library ``library``.

    A body read from another document (an Embedded Board Array's copy, change c0428) is matched to the
    models and forms of ``documents`` under its provenance's file name, and its model is placed in the frame
    of ``frames[footprint.id]``, the footprint it was copied from: a copy moves a footprint and its models
    together, so their relative pose is the source's."""
    default = ({model.locator: model for model in models}, {form.locator: form for form in forms})
    held = {
        file: ({m.locator: m for m in found}, {f.locator: f for f in shapes})
        for file, (found, shapes) in (documents or {}).items()
    }
    frames = frames or {}
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
        frame = frames.get(footprint.id, footprint)
        for body in footprint.bodies:
            where = body.provenance.locator if body.provenance is not None else ""
            by_locator, form_of = held.get(body.provenance.file if body.provenance else "", default)
            form = form_of.get(where)
            shape: BodyShape = form.shape if form is not None else body.kind
            if body.kind == "model":
                model = by_locator.get(where)
                if model is None:
                    lost[body.id] = NO_DATA
                    shape = "model"
                else:
                    path = model_file(library, model_stem(model.name) or name, model.data)
                    files[path] = model.data
                    found.append(placement(model, frame, "${KIPRJMOD}/" + path))
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


# --- the way back: a KiCad model in an Altium document (change c0449) --------------------------------------

STEP_MAGIC = b"ISO-10303-21"
UNREAD = "the model child holds no path, uses at in place of offset, or holds a value that is no number"
KICAD_EMBEDDED = "the model is embedded in the KiCad file (kicad-embed://), which Fenolite does not read"
VARIABLE = "the model path names a variable other than KIPRJMOD; only files of the project are read"
MISSING = "the model file is not found in the project folder"
NOT_FOUND = "the model file is not found at its path"
"""The reason of an absolute path, or of a path that climbs out of the project folder, whose file is absent
(change c0458; a file inside the folder that is absent is ``MISSING``)."""
NOT_STEP = "the model file is no STEP text; an Altium body embeds a STEP model"
SCALED = "the model is scaled; an Altium body holds no scale"
NO_GEOMETRY = "the STEP model holds no edge whose box Fenolite can measure"
HIDDEN = "the model is hidden in KiCad; Altium has no hidden model and shows it"
_PROJECT = re.compile(r"^(?:\$\{KIPRJMOD\}|\$\(KIPRJMOD\))(?:[/\\]+|$)")
_VARIABLE = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)")
_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9_. ()+-]+")


def model_path(path: str, root: Path) -> Path | str:
    """The file that the model path ``path`` of a board in the project folder ``root`` names, as KiCad reads
    it (``docs/formats/kicad/libraries.md``, "3D models"; change c0458), or the reason it names none:
    ``${KIPRJMOD}`` (or ``$(KIPRJMOD)``) is ``root``, a relative path is read from ``root``, an absolute
    path where it is, and a path that climbs out of ``root`` is followed. Another variable and a KiCad
    embedded file are not read; an absent file is ``MISSING`` inside ``root`` and ``NOT_FOUND`` elsewhere."""
    if path.startswith("kicad-embed://"):
        return KICAD_EMBEDDED
    rest = _PROJECT.sub("", path, count=1).replace("\\", "/")
    if _VARIABLE.search(rest):
        return VARIABLE
    if not rest:
        return MISSING
    base = root.resolve()
    if re.match(r"^[A-Za-z]:/", rest) or rest.startswith("//"):
        written = Path(PureWindowsPath(rest))
        if not written.is_absolute():  # a Windows path read on another system names no file here
            return NOT_FOUND
        target = written.resolve()
    elif rest.startswith("/"):
        target = Path(rest).resolve()
    else:
        target = (base / PurePosixPath(rest)).resolve()
    if target.is_file():
        return target
    return MISSING if target.is_relative_to(base) else NOT_FOUND


@dataclass(frozen=True, slots=True)
class AltiumPose:
    """Where an Altium body puts a KiCad model (change c0449): ``position`` (board frame), ``z`` the rise and
    ``rotation`` the ``MODEL.3D.ROT*`` turns; ``outline`` the four corners of the placed model's box in the
    board frame and ``standoff`` and ``height`` its lowest and highest Z above the face."""

    position: Point
    z: int
    rotation: tuple[int, int, int]
    outline: tuple[Point, ...]
    standoff: int
    height: int


def _is_one(text: str) -> bool:
    try:
        return Decimal(text) == 1
    except InvalidOperation:
        return False


def altium_pose(ref: ModelRef, footprint: FootprintInstance, box: stepbox.Box) -> AltiumPose:
    """The inverse of ``placement`` (design, Decision 2): the model origin is the footprint's placement of
    the offset (Y negated on the bottom), the rise is the offset's Z, and the turns are those of
    ``Rz(−θ')·R`` with ``θ'`` the footprint's rotation on the bottom and its negation on the top, exactly
    ``γ ± θ`` for a turn about Z alone. The box's eight corners turned by ``R`` and moved by the offset give,
    in KiCad's footprint frame with Y up, the rectangle and the two heights (Decision 3); the rectangle is
    placed as the footprint's pads are."""
    bottom = footprint.side == "bottom"
    ox, oy, oz = ref.offset
    place = Transform.placement(footprint.position, footprint.rotation)
    position = place.apply(Point(ox, -oy if bottom else oy))
    rx, ry, rz = ref.rotation
    if rx % FULL_TURN == 0 and ry % FULL_TURN == 0:
        rotation = (0, 0, _turn(rz - footprint.rotation if bottom else rz + footprint.rotation))
    else:
        theta = footprint.rotation if bottom else -footprint.rotation
        rotation = turns(_times(_axis(2, -theta), rotation_matrix(ref.rotation)))
    matrix = rotation_matrix(ref.rotation)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for x in (box[0], box[3]):
        for y in (box[1], box[4]):
            for z in (box[2], box[5]):
                q = [matrix[i][0] * x + matrix[i][1] * y + matrix[i][2] * z for i in range(3)]
                xs.append(q[0] + ox)
                ys.append(q[1] - oy)
                zs.append(q[2] + oz)
    x0, x1, y0, y1 = round(min(xs)), round(max(xs)), round(min(ys)), round(max(ys))
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    outline = tuple(place.apply(Point(x, y if bottom else -y)) for x, y in corners)
    return AltiumPose(position, oz, rotation, outline, round(min(zs)), round(max(zs)))


def model_name(path: Path) -> str:
    """The file name a written model keeps: characters the record does not take become ``_``."""
    return _NAME_UNSAFE.sub("_", path.name) or "model.step"


def footprint_models(
    footprints: Iterable[FootprintInstance], root: Path
) -> dict[str, tuple[pcbdoc.FootprintModel, ...]]:
    """Per footprint instance id, its ``model`` children as the Altium write takes them (change c0449):
    each child whose STEP file the project folder ``root`` holds, unscaled and with a box, as a model with
    its pose, outline and heights; every other child with its reason. A model's id is
    ``<footprint id>/model/<n>``, ``n`` counting the footprint's children from 0."""
    boxes: dict[bytes, stepbox.Box | None] = {}
    found: dict[str, tuple[pcbdoc.FootprintModel, ...]] = {}
    for footprint in footprints:
        made: list[pcbdoc.FootprintModel] = []
        for n, node in enumerate(fpitems.model_nodes(footprint)):
            ident = f"{footprint.id}/model/{n}"
            ref = read_model_ref(node)
            if ref is None:
                made.append(pcbdoc.FootprintModel(ident, reason=UNREAD))
                continue
            file = model_path(ref.name, root)
            if isinstance(file, str):
                made.append(pcbdoc.FootprintModel(ident, reason=file))
                continue
            if not all(_is_one(factor) for factor in ref.scale):
                made.append(pcbdoc.FootprintModel(ident, reason=SCALED))
                continue
            data = file.read_bytes()
            if not data.lstrip().startswith(STEP_MAGIC):
                made.append(pcbdoc.FootprintModel(ident, reason=NOT_STEP))
                continue
            key = hashlib.sha256(data).digest()
            if key not in boxes:
                boxes[key] = stepbox.model_box(data)
            box = boxes[key]
            if box is None:
                made.append(pcbdoc.FootprintModel(ident, reason=NO_GEOMETRY))
                continue
            pose = altium_pose(ref, footprint, box)
            model = pcbdoc.EmbeddedModel(data, model_name(file), pose.position, pose.z, pose.rotation)
            made.append(
                pcbdoc.FootprintModel(
                    ident,
                    model,
                    pose.outline,
                    pose.standoff,
                    pose.height,
                    changed=HIDDEN if ref.hidden else "",
                )
            )
        if made:
            found[footprint.id] = tuple(made)
    return found


__all__ = [
    "AltiumPose",
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
    "altium_pose",
    "body_solid",
    "footprint_models",
    "model_name",
    "model_path",
    "model_file",
    "place_models",
    "placement",
    "rotation_matrix",
    "turns",
]
