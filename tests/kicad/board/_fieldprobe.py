# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field probes of change c0030 (capability kicad-oracle, "Footprint fields pass the field oracle"): the
``field-*`` rows of ``_probes.PROBES``.

They run before the model knows fields (design Decision 15): every board is written as text here, with no
model and no writer, and judged by ``pcb drc``. A probe board holds one footprint per canary, each with a
``Reference`` (and sometimes a ``Value``) of ten characters in 1 mm text near an edge of the outline or of a
cut-out. Only ``silk_edge_clearance`` violations are judged, each matched to its field by the uuid of the
``property`` node. The project file sets ``min_silk_clearance`` to 0.1 mm (0 for ``field-edge-zero``), and
every "no violation" verdict sits in a report whose crossing control fires.

Stop rule: an outcome that contradicts the frame of ``design-model`` "Footprint fields" stops change c0030
until its design is amended (``H-K-FIELD-FRAME``, ``H-K-FIELD-JUSTIFY``, ``H-K-FIELD-DRC``,
``H-K-FIELD-OUTSIDE``).
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.cli import KicadCli
from fenolite.core.coords import Point
from fenolite.geometry.transform import Transform

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = 1_000_000
WIDTH, HEIGHT = 120, 100
JUDGED = "silk_edge_clearance"
TOLERANCE = 10
"""Nanometres per axis between a DRC item position and the expected anchor."""
GAP = 0.325
"""0.25 mm plus half of the 0.15 mm stroke: how far outside a cut-out the anchors of ``field-cutout`` lie."""
LAYERS = (
    '(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (5 "F.SilkS" user "F.Silkscreen")'
    ' (7 "B.SilkS" user "B.Silkscreen") (1 "F.Mask" user) (3 "B.Mask" user) (25 "Edge.Cuts" user)'
    ' (31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard") (35 "F.Fab" user)'
    ' (33 "B.Fab" user))'
)
"""The layer rows of the authored fixture ``tests/data/kicad/board/two_layer.kicad_pcb``."""


@dataclass(frozen=True)
class Field:
    """One ``property`` of a probe footprint: local position, stored angle, and its extra children."""

    name: str
    local: tuple[float, float]
    angle: int = 0
    justify: str = ""
    hidden: bool = False
    unlocked: bool = False
    silk: bool = True


@dataclass(frozen=True)
class Canary:
    """A footprint of the probe board and what its fields are expected to give."""

    key: str
    at: tuple[float, float]
    rotation: int
    bottom: bool
    fields: tuple[Field, ...]
    expect: tuple[int, ...]
    """Expected ``silk_edge_clearance`` count per field, in field order."""


def _reference(n: int) -> str:
    return f"REF{n:07d}"


def field_uuid(n: int, k: int) -> str:
    return f"f1e1d000-0000-4000-8000-{n:06d}{k:06d}"


def _num(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _property(n: int, k: int, field: Field, bottom: bool) -> str:
    side = "B" if bottom else "F"
    layer = f"{side}.SilkS" if field.silk else f"{side}.Fab"
    value = _reference(n) if field.name == "Reference" else f"VAL{n:07d}"
    hide = " (hide yes)" if field.hidden else ""
    unlocked = " (unlocked yes)" if field.unlocked else ""
    justify = f" (justify {field.justify})" if field.justify else ""
    return (
        f'(property "{field.name}" "{value}" (at {_num(field.local[0])} {_num(field.local[1])} {field.angle})'
        f'{unlocked} (layer "{layer}"){hide} (uuid "{field_uuid(n, k)}")'
        f" (effects (font (size 1 1) (thickness 0.15)){justify}))"
    )


def _footprint(n: int, canary: Canary) -> str:
    layer = "B.Cu" if canary.bottom else "F.Cu"
    names = {f.name for f in canary.fields}
    fields = list(canary.fields)
    if "Value" not in names:
        fields.append(
            Field("Value", (0, 0), canary.rotation, "mirror" if canary.bottom else "", True, silk=False)
        )
    properties = " ".join(_property(n, k, f, canary.bottom) for k, f in enumerate(fields))
    angle = f" {canary.rotation}" if canary.rotation else ""
    return (
        f'(footprint "Probe:Field" (layer "{layer}") (uuid "{field_uuid(n, 999)}")'
        f" (at {_num(canary.at[0])} {_num(canary.at[1])}{angle}) {properties}"
        " (attr board_only exclude_from_pos_files exclude_from_bom))"
    )


def _rect(n: int, x0: float, y0: float, x1: float, y1: float) -> str:
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lines = []
    for k, (a, b) in enumerate(zip(corners, [*corners[1:], corners[0]], strict=True)):
        lines.append(
            f"(gr_line (start {_num(a[0])} {_num(a[1])}) (end {_num(b[0])} {_num(b[1])})"
            f' (stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{field_uuid(900 + n, k)}"))'
        )
    return " ".join(lines)


CUTOUTS: tuple[tuple[float, float, float, float], ...] = (
    (60, 40, 63, 41.5),
    (60, 55, 63, 56.5),
    (60, 70, 63, 71.5),
    (60, 85, 63, 86.5),
)
"""Cut-outs of the size of the ``Mini_R_0603`` courtyard (3 mm by 1.5 mm), one per ``field-cutout``
footprint."""


def _cut(index: int, fields: tuple[Field, ...], expect: tuple[int, ...], bottom: bool = False) -> Canary:
    x0, y0, x1, y1 = CUTOUTS[index]
    return Canary(f"cutout-{index}", ((x0 + x1) / 2, (y0 + y1) / 2), 0, bottom, fields, expect)


def canaries() -> tuple[Canary, ...]:
    """Every canary of the probe board; ``key`` starts with the probe it belongs to."""
    cross = Field("Reference", (-10, 0))
    return (
        # anchors: a centred Reference whose anchor lies on or near an edge, at 0°, 30° and 90°
        Canary("frame-top-0", (10, 10), 0, False, (cross,), (1,)),
        Canary("frame-top-30", (6, 20), 30, False, (Field("Reference", (-5, 0), 30),), (1,)),
        Canary("frame-top-90", (30, 10), 90, False, (Field("Reference", (10, 0), 90),), (1,)),
        Canary("frame-bottom-0", (10, 30), 0, True, (Field("Reference", (-10, 0), 0, "mirror"),), (1,)),
        Canary("frame-bottom-30", (6, 38), 30, True, (Field("Reference", (-5, 0), 30, "mirror"),), (1,)),
        Canary("frame-bottom-90", (45, 10), 90, True, (Field("Reference", (10, 0), 90, "mirror"),), (1,)),
        # angle: on a footprint at 90° the stored angle is the board angle (anchor 2 mm below the top edge)
        Canary("angle-0", (60, 10), 90, False, (Field("Reference", (8, 0), 0),), (0,)),
        Canary("angle-90", (75, 10), 90, False, (Field("Reference", (8, 0), 90),), (1,)),
        # justification: anchor 1 mm inside the left edge, and 0.5 mm below the top edge
        Canary("justify-left", (10, 50), 0, False, (Field("Reference", (-9, 0), 0, "left"),), (0,)),
        Canary("justify-right", (10, 54), 0, False, (Field("Reference", (-9, 0), 0, "right"),), (1,)),
        Canary("justify-top", (90, 10), 0, False, (Field("Reference", (0, -9.5), 0, "top"),), (0,)),
        Canary("justify-bottom", (105, 10), 0, False, (Field("Reference", (0, -9.5), 0, "bottom"),), (1,)),
        # mirror reverses the horizontal sense, on either side
        Canary(
            "mirror-bottom-left", (10, 58), 0, True, (Field("Reference", (-9, 0), 0, "left mirror"),), (1,)
        ),
        Canary(
            "mirror-bottom-right", (10, 62), 0, True, (Field("Reference", (-9, 0), 0, "right mirror"),), (0,)
        ),
        Canary("mirror-top-left", (10, 66), 0, False, (Field("Reference", (-9, 0), 0, "left mirror"),), (1,)),
        Canary(
            "mirror-top-right", (10, 70), 0, False, (Field("Reference", (-9, 0), 0, "right mirror"),), (0,)
        ),
        # keep-upright: stored 180°, left-justified, anchor 1 mm inside the left edge
        Canary("upright-kept", (10, 74), 0, False, (Field("Reference", (-9, 0), 180, "left"),), (0,)),
        Canary(
            "upright-unlocked",
            (10, 78),
            0,
            False,
            (Field("Reference", (-9, 0), 180, "left", unlocked=True),),
            (1,),
        ),
        # a hidden field that crosses the edge
        Canary("hidden", (10, 82), 0, False, (Field("Reference", (-10, 0), hidden=True),), (0,)),
        # cut-outs: anchors 0.325 mm outside the box, justified away; then two controls
        _cut(
            0,
            (Field("Reference", (0, -0.75 - GAP), 0, "bottom"), Field("Value", (0, 0.75 + GAP), 0, "top")),
            (0, 0),
        ),
        _cut(
            1,
            (Field("Reference", (-1.5 - GAP, 0), 0, "right"), Field("Value", (1.5 + GAP, 0), 0, "left")),
            (0, 0),
        ),
        _cut(2, (Field("Reference", (0, -0.75 + 0.1), 0, "bottom"),), (1,)),
        _cut(
            3,
            (
                Field("Reference", (-1.5 - GAP, 0), 0, "left mirror"),
                Field("Value", (-1.5 - GAP, 0.0), 0, "right mirror"),
            ),
            (0, 1),
            bottom=True,
        ),
    )


def board_text(found: Sequence[Canary]) -> str:
    """A 9.0-format board (both majors load it) holding the outline, the cut-outs and one footprint per
    canary."""
    outline = _rect(0, 0, 0, WIDTH, HEIGHT)
    cuts = " ".join(
        _rect(1 + i, *box) for i, box in enumerate(CUTOUTS) if any(c.key == f"cutout-{i}" for c in found)
    )
    footprints = " ".join(_footprint(n, canary) for n, canary in enumerate(found, start=1))
    return (
        '(kicad_pcb (version 20241229) (generator "fenolite-tests") (generator_version "9.0")'
        f' (general (thickness 1.6)) (paper "A4") {LAYERS} (setup (pad_to_mask_clearance 0))'
        f' (net 0 "") {footprints} {outline} {cuts})\n'
    )


def project_text(clearance_mm: float) -> str:
    """A project file that sets only the board's minimum silkscreen clearance."""
    return json.dumps({"board": {"design_settings": {"rules": {"min_silk_clearance": clearance_mm}}}}) + "\n"


def anchor(canary: Canary, field: Field) -> Point:
    """``at + R(θ)·local``, with no further mirror on the bottom side (the frame of ``H-K-FIELD-FRAME``)."""
    at = Point(round(canary.at[0] * MM), round(canary.at[1] * MM))
    local = Point(round(field.local[0] * MM), round(field.local[1] * MM))
    return Transform.placement(at, canary.rotation * MM).apply(local)


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def drc(text: str, clearance_mm: float) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "fields.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        project = Path(tmp) / "fields.kicad_pro"
        project.write_text(project_text(clearance_mm), encoding="utf-8")
        return runner().drc(board, files={project.name: project}).report


@dataclass(frozen=True)
class Hit:
    """One ``silk_edge_clearance`` item of a field: its description and report position."""

    description: str
    position: Point


def hits(report: DrcReport) -> dict[str, list[Hit]]:
    """Property uuid → the ``silk_edge_clearance`` items that name it."""
    found: dict[str, list[Hit]] = {}
    for violation in report.violations:
        if violation.type != JUDGED:
            continue
        for item in violation.items:
            found.setdefault(item.uuid, []).append(Hit(item.description, item.position))
    return found


@cache
def observed() -> dict[str, tuple[list[Hit], ...]] | None:
    """Canary key → the hits of each of its fields, on the probe board with 0.1 mm clearance."""
    found = canaries()
    report = drc(board_text(found), 0.1)
    if report is None:
        return None
    by_uuid = hits(report)
    return {
        canary.key: tuple(by_uuid.get(field_uuid(n, k), []) for k in range(len(canary.fields)))
        for n, canary in enumerate(found, start=1)
    }


def _group(prefix: str) -> list[tuple[int, Canary]]:
    return [(n, c) for n, c in enumerate(canaries(), start=1) if c.key.startswith(prefix)]


def counts_outcome(prefix: str) -> str:
    """``present`` when every field of the group gives its expected count, ``different`` otherwise."""
    found = observed()
    if found is None:
        return "reject"
    for _, canary in _group(prefix):
        if tuple(len(h) for h in found[canary.key]) != canary.expect:
            return "different"
    return "present"


def frame_outcome(prefix: str) -> str:
    """``present`` when each Reference of the group gives one violation whose item names the field and lies
    within ``TOLERANCE`` of ``anchor``; ``absent`` when none fires; ``different`` otherwise."""
    found = observed()
    if found is None:
        return "reject"
    group = _group(prefix)
    if not any(found[canary.key][0] for _, canary in group):
        return "absent"
    for n, canary in group:
        (field,) = canary.fields
        got = found[canary.key][0]
        want = anchor(canary, field)
        if len(got) != 1 or got[0].description != f"Reference field of {_reference(n)}":
            return "different"
        if abs(got[0].position.x - want.x) > TOLERANCE or abs(got[0].position.y - want.y) > TOLERANCE:
            return "different"
    return "present"


def hidden_outcome() -> str:
    """``absent`` when the hidden crossing field is not reported while the visible control is."""
    found = observed()
    if found is None:
        return "reject"
    if len(found["frame-top-0"][0]) != 1:
        return "inconclusive"
    return "present" if found["hidden"][0] else "absent"


@cache
def edge_zero_outcome() -> str:
    """Whether the crossing control is reported when ``min_silk_clearance`` is 0."""
    control = next(c for c in canaries() if c.key == "frame-top-0")
    report = drc(board_text((control,)), 0)
    if report is None:
        return "reject"
    return "present" if hits(report).get(field_uuid(1, 0)) else "absent"


def field_probes() -> Probes:
    both = (9, 10)
    return {
        "field-frame-top": (lambda: frame_outcome("frame-top"), both),
        "field-frame-bottom": (lambda: frame_outcome("frame-bottom"), both),
        "field-angle": (lambda: counts_outcome("angle"), both),
        "field-justify": (lambda: counts_outcome("justify"), both),
        "field-mirror": (lambda: counts_outcome("mirror"), both),
        "field-upright": (lambda: counts_outcome("upright"), both),
        "field-hidden": (hidden_outcome, both),
        "field-edge-zero": (edge_zero_outcome, both),
        "field-cutout": (lambda: counts_outcome("cutout"), both),
    }


EXPECTED: dict[str, str] = {
    "field-frame-top": "present",
    "field-frame-bottom": "present",
    "field-angle": "present",
    "field-justify": "present",
    "field-mirror": "present",
    "field-upright": "present",
    "field-hidden": "absent",
    "field-cutout": "present",
}
"""What the design's Context reports; ``field-edge-zero`` depends on the major and is only recorded."""
EDGE_ZERO = {9: "absent", 10: "present"}

__all__ = [
    "EDGE_ZERO",
    "EXPECTED",
    "Canary",
    "Field",
    "anchor",
    "board_text",
    "canaries",
    "field_probes",
    "field_uuid",
    "observed",
]
