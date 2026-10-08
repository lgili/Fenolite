# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sample with component bodies of the Altium PCB document (change c0121, capability altium-build,
"Component bodies in an Altium build"): the blink design named ``body2`` on two copper layers, whose three
footprints hold four component bodies.

Every value here is authored for this sample; none comes from another project. Positions are those of
the blink script (``U1`` and ``R1`` on the top side, ``D1`` on the bottom side); each outline is in the
frame of its footprint, in millimetres, as seen from the top:

| body | footprint | side | layer of the model | overall height | standoff | outline | name |
|---|---|---|---|---|---|---|---|
| 1 | ``U1`` | top | none (Mechanical 13 by the rule) | 2.5 mm | 0 | a rectangle 7 mm by 7 mm | none |
| 2 | ``D1`` | bottom | ``B.Fab`` (Mechanical 14) | 1 mm | 0 | a rectangle 4 mm by 3 mm | ``LED`` |
| 3 | ``R1`` | top | ``Mech.13`` (Mechanical 13) | 4 mm | 0.5 mm | six points, an L | ``STANDOFF`` |
| 4 | ``U1`` | top | none | 1.6 mm | 0 | a rectangle | ``MODEL`` |

Bodies 1 to 3 are extruded and are written with ``--altium-bodies extruded``. Body 4 is of kind ``model``:
it names a 3D model, which the design model holds by name only, so it is reported and not written. The
footprint definition of ``U1`` holds one extruded body of its own (the rectangle of body 1), which is
written into the PCB library. The committed files under ``tests/data/altium/body2/`` are the build with
bodies; nothing in them was opened in Altium (``H-A-PCBX-BODY-OPEN`` is pending).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

from _altium import BLINK, blink_resolver, blink_tree
from _buildhelp import MARKS as BLINK_MARKS

from fenolite.backends.altium.pcbrecords import BodyForm
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Placement, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.board import ComponentBody, FootprintInstance
from fenolite.model.design import Design as ModelDesign

NAME = "body2"
MM = 1_000_000
FILES = tuple(f"{NAME}.{suffix}" for suffix in ("PcbDoc", "PcbLib", "PrjPcb", "SchDoc", "SchLib"))
BODY_OWNER = "U1"
"""The component whose footprint definition holds a body of its own, written into the PCB library."""


def _points(*pairs: tuple[float, float]) -> tuple[Point, ...]:
    return tuple(Point(round(x * MM), round(y * MM)) for x, y in pairs)


_SQUARE = _points((-3.5, -3.5), (3.5, -3.5), (3.5, 3.5), (-3.5, 3.5))
_LED = _points((-2, -1.5), (2, -1.5), (2, 1.5), (-2, 1.5))
_ELL = _points((-1.5, -1), (1.5, -1), (1.5, 0), (0.5, 0), (0.5, 1), (-1.5, 1))
_INNER = _points((-3, -3), (3, -3), (3, 3), (-3, 3))
BODIES: tuple[tuple[str, str, str, str, int, int, tuple[Point, ...], str, str], ...] = (
    ("b1", "U1", "extruded", "", 2_500_000, 0, _SQUARE, "", ""),
    ("b2", "D1", "extruded", "B.Fab", 1_000_000, 0, _LED, "LED", ""),
    ("b3", "R1", "extruded", "Mech.13", 4_000_000, 500_000, _ELL, "STANDOFF", ""),
    ("b4", "U1", "model", "", 1_600_000, 0, _INNER, "MODEL", "body2_qfp32.step"),
)
"""(key, component, kind, layer, height, standoff, outline in the footprint frame, name, model)."""
WRITTEN = ("b2", "b3", "b1")
"""The keys of the bodies that are written, in the order of the document: by component (``D1``, ``R1``,
``U1`` in path order gives b2, b3, b1; the document's order is that of its components)."""
TABLE: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("U1", "Top", "Mechanical 13", "2.5 mm", "0 mm", ""),
    ("D1", "Bottom", "Mechanical 14", "1 mm", "0 mm", "LED"),
    ("R1", "Top", "Mechanical 13", "4 mm", "0.5 mm", "STANDOFF"),
)
"""What step X8 reads in Altium for bodies 1 to 3: footprint, board side, layer, overall height, standoff
height, identifier."""


def _id(prefix: str, key: str) -> str:
    return derived_id(prefix, "dsl", f"body2:{key}")


def body(key: str) -> ComponentBody:
    """The model body ``key`` of ``BODIES``."""
    (row,) = [row for row in BODIES if row[0] == key]
    _key, _ref, kind, layer, height, standoff, outline, name, model = row
    return ComponentBody(
        id=_id("bdy", key),
        kind=kind,  # type: ignore[arg-type]
        height=height,
        standoff=standoff,
        outline=outline,
        layer=layer,
        model=model,
        name=name,
    )


def library_body() -> ComponentBody:
    """The body of the footprint definition of ``BODY_OWNER``: the rectangle of body 1, with its own id."""
    return dataclasses.replace(body("b1"), id=_id("bdy", "library"))


def body2_script() -> str:
    """The sample's script: the blink example renamed ``body2``."""
    source = BLINK.read_text(encoding="utf-8")
    assert BLINK_MARKS in source
    source = source.replace(BLINK_MARKS, "")
    old = 'Design("blink")'
    assert old in source
    return source.replace(old, f'Design("{NAME}")')


def body2_design() -> Design:
    namespace: dict[str, object] = {}
    exec(compile(body2_script(), str(BLINK), "exec"), namespace)  # noqa: S102
    design = namespace["design"]
    assert isinstance(design, Design)
    return design


def body2_placements(rotation: int = 0) -> Mapping[str, Placement]:
    """The script's placements, each turned by ``rotation`` microdegrees more."""
    return {
        path: dataclasses.replace(place, rotation=(place.rotation + rotation) % 360_000_000)
        for path, place in placements(body2_design()).items()
    }


def body2_model(rotation: int = 0, *, keys: tuple[str, ...] | None = None) -> ModelDesign:
    """The sample's model: the script's model with one footprint instance per component, placed as the
    script places it and turned by ``rotation`` more, holding the bodies of ``BODIES`` (``keys`` picks
    some of them)."""
    model = to_model(body2_design())
    assert model.board is not None and not model.board.footprints
    placed = body2_placements(rotation)
    footprints: list[FootprintInstance] = []
    for component in sorted(model.circuit.components, key=lambda c: c.ref):
        place = placed[component.ref]
        footprints.append(
            FootprintInstance(
                id=_id("fp", component.ref),
                component_id=component.id,
                lib_ref=component.lib_footprint_ref,
                position=place.at,
                rotation=place.rotation,
                side=place.side,
                locked=place.locked,
                bodies=tuple(
                    body(row[0])
                    for row in BODIES
                    if row[1] == component.ref and (keys is None or row[0] in keys)
                ),
            )
        )
    return dataclasses.replace(model, board=dataclasses.replace(model.board, footprints=tuple(footprints)))


def body2_build(
    root: Path,
    model: ModelDesign | None = None,
    *,
    rotation: int = 0,
    bodies: str = "extruded",
    body_form: BodyForm = "saved",
    library: bool = True,
) -> BuildOutput:
    """The Altium build of ``model`` (the sample by default) in a blink tree under ``root``, with
    ``--altium-bodies`` ``bodies``. ``library`` gives the footprint definition of ``BODY_OWNER`` its
    body."""
    project = root / "examples" / "blink_2layer"
    if not project.is_dir():
        project = blink_tree(root)
    resolver = blink_resolver(root, project)
    built = body2_model(rotation) if model is None else model
    authored = {}
    if library:
        (owner,) = [c for c in built.circuit.components if c.ref == BODY_OWNER]
        link = owner.lib_footprint_ref or resolver.symbol(owner.lib_symbol_ref).footprint
        authored[link] = dataclasses.replace(resolver.footprint(link), bodies=(library_body(),))
    requested = body2_placements(rotation)
    return build_altium(
        built,
        name=NAME,
        resolver=resolver,
        placed=tuple(requested),
        placements=requested,
        authored_footprints=authored,
        bodies=bodies,
        body_form=body_form,
    )


def project_files(output: BuildOutput) -> dict[str, bytes]:
    """The five project files of a build (without the ``.fenolite/`` cache)."""
    return {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}
