# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated footprints of a board hole, ``Fenolite_Holes:NPTH_…`` and ``PTH_…`` (``docs/dsl.md``,
"Holes"; capability kicad-file-backend, "Board holes as generated footprints in a conversion"; changes
c0102 and c0170).

The builder lived in ``fenolite.dsl.holes``, which builds a ``Design.hole()`` part; change c0170 moves it
here, built from model types alone, so a conversion to KiCad gives a model ``Hole`` the footprint a script
would (the KiCad backend may not import ``dsl``). ``fenolite.dsl.holes`` re-exports it, and its ids are
those the DSL footprint builder gave, so a script's files keep their bytes.

The footprint holds one pad at its origin, unnumbered and not plated, or numbered ``1`` with copper; the
flags that keep it out of the position file and the bill of materials; and a courtyard on both sides.
Every length is the caller's, in nanometres; no size is shipped.
"""

from __future__ import annotations

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length
from fenolite.model.board import Graphic, GraphicKind, Pad, Padstack
from fenolite.model.library import FootprintDef

HOLE_LIBRARY = "Fenolite_Holes"
"""The library of the generated hole footprints and symbols."""
HOLE_FLAGS: tuple[str, ...] = ("exclude_from_pos_files", "exclude_from_bom")
COURTYARD_LAYERS: tuple[str, ...] = ("F.CrtYd", "B.CrtYd")
COURTYARD_STROKE = 50_000
"""The pen of the courtyard, 0.05 mm, as KiCad's library draws courtyards."""
NAMESPACE = "fenolite.dsl"
"""The namespace of the ids: that of the DSL footprint builder, which made these footprints first."""
HOLE_LAYERS: tuple[str, ...] = ("*.Cu", "*.Mask")


def _mm(value: int) -> str:
    return format_length(value, "mm").removesuffix("mm")


def _half(value: int) -> int:
    """Half of ``value``, rounded up: a courtyard is never smaller than asked."""
    return (value + 1) // 2


def check_sizes(
    drill: Nm, length: Nm | None = None, pad: Nm | None = None, courtyard: Nm | None = None
) -> None:
    """``ValueError`` naming the argument at fault unless ``drill`` is positive, ``length`` above
    ``drill`` (a slot of that overall length), ``pad`` above ``drill`` (the width of its copper) and
    ``courtyard`` at least the width of the hole and of its copper."""
    if drill <= 0:
        raise ValueError("drill must be a positive length")
    if length is not None and length <= drill:
        raise ValueError("length is the overall length of a slot and must be above drill")
    if pad is not None and pad <= drill:
        raise ValueError("pad is the width of the copper and must be above drill")
    if courtyard is not None and courtyard < (pad or drill):
        raise ValueError("courtyard must be at least the width of the hole and of its copper")


def hole_name(hole: Nm, slot: Nm | None, copper: Nm | None, yard: Nm | None) -> str:
    """``NPTH_<d>mm`` or ``NPTH_Slot_<d>x<l>mm``, ``PTH_…_Pad_<p>mm`` with copper, and ``_Courtyard_<c>mm``
    when the courtyard is given: every size of the definition is in its name."""
    size = f"{_mm(hole)}mm" if slot is None else f"Slot_{_mm(hole)}x{_mm(slot)}mm"
    name = f"NPTH_{size}" if copper is None else f"PTH_{size}_Pad_{_mm(copper)}mm"
    return name if yard is None else f"{name}_Courtyard_{_mm(yard)}mm"


def hole_footprint(
    drill: Nm,
    *,
    length: Nm | None = None,
    pad: Nm | None = None,
    courtyard: Nm | None = None,
    plated: bool = False,
) -> FootprintDef:
    """The footprint of a hole of ``drill``: round, or a slot of overall length ``length`` along the
    footprint's X axis; not plated, or with copper ``pad`` wide; its courtyard ``courtyard`` wide, by
    default as wide as the copper, or as the hole. ``plated`` without ``pad`` is a plated hole whose copper
    is the hole itself (an imported free hole; change c0170), named ``PTH_…_Pad_<d>mm``, which a script
    cannot declare. ``ValueError`` as ``check_sizes``."""
    check_sizes(drill, length, pad, courtyard)
    if plated and pad is None:
        pad = drill
    name = hole_name(drill, length, pad, courtyard)
    lib_id = f"{HOLE_LIBRARY}:{name}"
    width = pad if pad is not None else drill
    long = width if length is None else length + width - drill
    number = "" if pad is None else "1"
    pad_key = f"{lib_id}:pad:{number}" + (":1" if pad is None else "")
    hole = Pad(
        id=derived_id("pad", NAMESPACE, pad_key),
        number=number,
        shape="circle" if length is None else "oval",
        size=Size(long, width),
        position=Point(0, 0),
        kind="np_thru_hole" if pad is None else "thru_hole",
        drill=drill,
        layers=HOLE_LAYERS,
        padstack=None
        if length is None
        else Padstack(
            id=derived_id("pst", NAMESPACE, f"{pad_key}:padstack"), hole_shape="slot", hole_length=length
        ),
    )
    wide = courtyard if courtyard is not None else width
    graphics: list[Graphic] = []
    for layer in COURTYARD_LAYERS:
        if length is None:
            kind: GraphicKind = "circle"
            points = (Point(0, 0), Point(_half(wide), 0))
        else:
            x, y = _half(long + wide - width), _half(wide)
            kind, points = "rect", (Point(-x, -y), Point(x, y))
        graphics.append(
            Graphic(
                id=derived_id("gfx", NAMESPACE, f"{lib_id}:graphic:{len(graphics)}"),
                kind=kind,
                layer=layer,
                points=points,
                width=COURTYARD_STROKE,
            )
        )
    return FootprintDef(
        id=derived_id("fpd", NAMESPACE, lib_id),
        name=name,
        library=HOLE_LIBRARY,
        flags=HOLE_FLAGS,
        pads=(hole,),
        graphics=tuple(graphics),
    )


__all__ = [
    "COURTYARD_LAYERS",
    "COURTYARD_STROKE",
    "HOLE_FLAGS",
    "HOLE_LAYERS",
    "HOLE_LIBRARY",
    "check_sizes",
    "hole_footprint",
    "hole_name",
]
