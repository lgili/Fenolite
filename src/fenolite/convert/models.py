# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The embedded 3D models of an Altium board, extracted and placed for the derived KiCad library
(capability design-conversion, "Model placement of imported footprints"; change c0223; ``docs/conversion.md``,
"3D models").

``models3d.body_models`` (c0193) gives each embedded model with its bytes and its placement in the board
frame (``H-A-BODY-MODEL-PLACE``). Here a model of a top-side part becomes a ``ModelPlacement`` in its
footprint's own frame: the offset of the model from the footprint, its height above the face, and its turn
about Z less the footprint's. Nothing is read or written here: the caller gives the models and writes the
files.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from fenolite.backends.base import BodyModel
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import FootprintInstance
from fenolite.model.library import ModelPlacement

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-BODY-MODEL-PLACE", "H-K-MODEL-PLACE"))
KIND = "model"
FOLDER_SUFFIX = ".3dshapes"
PLACED = "the embedded model is extracted beside the library and placed in the library footprint"
BOTTOM = "a model of a bottom-side part is not placed: the flip of its placement is not measured"
TILTED = "a model turned about X or Y is not placed: the order of KiCad's turns is not measured"
NO_DATA = "the body names a model that the document does not embed"
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True, slots=True)
class Placed:
    """What ``place_models`` gives: per footprint instance id its placements, the model files (path below
    the project → bytes) and the report rows (kind ``model``: body id → reason) of models placed and lost."""

    placements: Mapping[str, tuple[ModelPlacement, ...]] = field(default_factory=lambda: {})
    files: Mapping[str, bytes] = field(default_factory=lambda: {})
    changed: Mapping[str, str] = field(default_factory=lambda: {})
    lost: Mapping[str, str] = field(default_factory=lambda: {})


def model_file(library: str, footprint: str, data: bytes) -> str:
    """``<library>.3dshapes/<footprint>_<sha12>.step``: the folder beside the library, the footprint's name
    with characters outside ``[A-Za-z0-9_.-]`` replaced by ``_``, and the first 12 hex digits of the
    SHA-256 of the model's bytes."""
    stem = _UNSAFE.sub("_", footprint) or "model"
    return f"{library}{FOLDER_SUFFIX}/{stem}_{hashlib.sha256(data).hexdigest()[:12]}.step"


def placement(model: BodyModel, footprint: FootprintInstance, path: str) -> ModelPlacement | str:
    """The placement of ``model`` in the frame of the top-side ``footprint``, or the reason it has none."""
    if footprint.side != "top":
        return BOTTOM
    rx, ry, rz = model.rotation
    if rx % FULL_TURN or ry % FULL_TURN:
        return TILTED
    local = Transform.placement(footprint.position, footprint.rotation).inverse().apply(model.position)
    turn = (rz - footprint.rotation) % FULL_TURN
    if turn > FULL_TURN // 2:
        turn -= FULL_TURN
    return ModelPlacement(path=path, offset=(local.x, local.y, model.z), rotation=(0, 0, turn))


def place_models(
    footprints: Iterable[FootprintInstance],
    models: Iterable[BodyModel],
    library: str,
    name_of: Callable[[FootprintInstance], str],
) -> Placed:
    """The placements of the embedded models of ``footprints``' bodies of kind ``model``, matched to
    ``models`` by the body's locator; ``name_of`` gives a footprint's name in the library ``library``."""
    by_locator = {model.locator: model for model in models}
    placements: dict[str, tuple[ModelPlacement, ...]] = {}
    files: dict[str, bytes] = {}
    changed: dict[str, str] = {}
    lost: dict[str, str] = {}
    for footprint in footprints:
        found: list[ModelPlacement] = []
        for body in footprint.bodies:
            if body.kind != "model":
                continue
            where = body.provenance.locator if body.provenance is not None else ""
            model = by_locator.get(where)
            if model is None:
                lost[body.id] = NO_DATA
                continue
            path = model_file(library, name_of(footprint), model.data)
            placed = placement(model, footprint, "${KIPRJMOD}/" + path)
            if isinstance(placed, str):
                lost[body.id] = placed
                continue
            files[path] = model.data
            found.append(placed)
            changed[body.id] = PLACED
        if found:
            placements[footprint.id] = tuple(found)
    return Placed(placements, files, changed, lost)


__all__ = [
    "BOTTOM",
    "EVIDENCE",
    "KIND",
    "NO_DATA",
    "PLACED",
    "TILTED",
    "Placed",
    "model_file",
    "place_models",
    "placement",
]
