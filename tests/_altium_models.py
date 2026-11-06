# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored Altium PCB document with every kind of component body (change c0423): embedded STEP models
turned about X, Y and Z on the top and on the bottom, extruded bodies, cylinders, spheres and a cylinder
that does not fit its outline.

The document is written by Fenolite's own PCB writer from the blink sample's footprints (extruded bodies,
``pcb-bodies.md``, "Written form of an extruded body"); then each body record's property text is changed to
its kind (``MODEL.MODELTYPE`` 1, 2 or 3, S-1604; the model keys of "Embedded models and their placement",
S-0816) and a ``Models`` storage is added whose streams hold one authored STEP prism, deflated with ``zlib``.
Every value is authored for Fenolite; nothing comes from another board or tool.

``case(name)`` gives a body's authored pose so that a test computes the source's placement from the facts
of ``pcb-bodies.md`` alone, without Fenolite's reader.
"""

from __future__ import annotations

import dataclasses
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from _altium import blink_pcbdoc_spec

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.pcbdoc import Frame, PcbDocSpec, PlacedComponent, place_body, write_pcbdoc
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.step import Prism, write_solids
from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody

MIL = 25_400
"""One mil in nm; every authored length is a whole number of mils, so the document's units hold it exactly."""
UNITS = rec.UNITS_PER_MIL
NAME = "models.PcbDoc"
MODEL_NAME = "marker.step"
MODEL_ID = "{0C423000-0000-4000-8000-000000000001}"
MODEL_CHECKSUM = "-423449"
"""The authored ``CHECKSUM`` of the model's record (change c0449): a negative 32-bit decimal, as some saved
ones are; body ``n`` that names the model holds ``MODEL.CHECKSUM`` ``body_checksum(n)``, another value."""
MARKER = ((0, 0), (120, 0), (0, 40))
"""The authored model: a prism over this triangle (mil, model frame, Y up), from 20 mil to 100 mil. Its six
vertices are distinct under every turn, so a pose is read back from them alone."""
MARKER_Z = (20, 100)


@dataclass(frozen=True, slots=True)
class Case:
    """One authored component: its designator, place (mm, KiCad frame), turn (degrees) and side, and its
    body: ``shape`` is ``model``, ``extruded``, ``cylinder`` or ``sphere``; ``outline`` the body's outline
    in the footprint frame (mil, Y down); ``standoff``/``overall`` its heights (mil); for a model the
    offset of the model from the component (mil, the document's Y up), ``dz`` (mil) and the turns
    (degrees)."""

    ref: str
    at: tuple[float, float]
    rotation: int
    side: str
    shape: str
    outline: tuple[tuple[int, int], ...] = ((-40, -40), (40, -40), (40, 40), (-40, 40))
    standoff: int = 0
    overall: int = 60
    offset: tuple[int, int] = (0, 0)
    dz: int = 0
    turns: tuple[int, int, int] = (0, 0, 0)
    projection: int | None = None


L_SHAPE = ((-60, -30), (60, -30), (60, 10), (0, 10), (0, 40), (-60, 40))
CASES: tuple[Case, ...] = (
    Case("M1", (106, 105), 0, "top", "model"),
    Case("M2", (114, 105), 30, "top", "model", offset=(20, -12), dz=8, turns=(90, 0, 0)),
    Case("M3", (122, 105), 90, "top", "model", turns=(0, 90, 45)),
    Case("M4", (130, 105), 0, "top", "model", dz=20, turns=(30, 40, 50)),
    Case("M5", (106, 115), 0, "bottom", "model"),
    Case("M6", (114, 115), 45, "bottom", "model", offset=(-16, 24), turns=(90, 0, 30)),
    Case("M7", (122, 115), 180, "bottom", "model", dz=12, turns=(20, 70, 110)),
    Case("M8", (130, 115), 270, "bottom", "model", turns=(0, -90, 0)),
    Case("E1", (138, 105), 0, "top", "extruded", outline=L_SHAPE, standoff=4, overall=50),
    Case("E2", (138, 115), 45, "bottom", "extruded", outline=L_SHAPE, standoff=0, overall=70),
    Case("C1", (106, 125), 0, "top", "cylinder", outline=((-20, -20), (20, -20), (20, 20), (-20, 20))),
    Case("C2", (114, 125), 90, "bottom", "cylinder", outline=((-30, -30), (30, -30), (30, 30), (-30, 30))),
    Case("S1", (122, 125), 0, "top", "sphere", standoff=-40, overall=40),
    Case(
        "S2",
        (130, 125),
        30,
        "bottom",
        "sphere",
        outline=((-30, -30), (30, -30), (30, 30), (-30, 30)),
        standoff=0,
        overall=60,
    ),  # fmt: skip
    Case("K1", (138, 125), 0, "top", "cylinder", outline=((-40, -20), (40, -20), (40, 20), (-40, 20))),
)
UNKNOWN = Case("X1", (146, 125), 0, "top", "extruded", projection=1)
"""A top body with projection 1: its interval is not proved (``pcb-bodies.md``, c0387), so it is a loss."""


def marker_step() -> bytes:
    """The authored model file: the marker prism, in mm, Y up."""
    ring = tuple((x * MIL, y * MIL) for x, y in MARKER)
    return write_solids("marker", [Prism(ring, MARKER_Z[0] * MIL, MARKER_Z[1] * MIL, "body")])


def body_checksum(index: int) -> str:
    """The authored ``MODEL.CHECKSUM`` of body record ``index`` (from 0) when it names the model."""
    return str(423000 + index)


def case(ref: str) -> Case:
    found = [c for c in (*CASES, UNKNOWN) if c.ref == ref]
    assert len(found) == 1, ref
    return found[0]


def _mm(value: float) -> int:
    return round(value * 1_000_000)


def _spec(cases: tuple[Case, ...]) -> PcbDocSpec:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    template = next(c for c in spec.components if c.ref == "R1")
    frame = Frame.of(spec.outline)
    components: list[PlacedComponent] = []
    bodies = []
    for index, item in enumerate(cases):
        at = Point(_mm(item.at[0]), _mm(item.at[1]))
        component = dataclasses.replace(
            template,
            ref=item.ref,
            unique_id=f"C0423{index:03d}",
            record_unique_id=f"R0423{index:03d}",
            at=at,
            rotation=item.rotation * 1_000_000,
            side=item.side,  # type: ignore[arg-type]
            pad_nets={},
        )
        components.append(component)
        body = ComponentBody(
            id=f"bdy-{item.ref}",
            kind="extruded",
            height=max(item.overall, 1) * MIL,
            standoff=max(item.standoff, 0) * MIL,
            outline=tuple(Point(x * MIL, y * MIL) for x, y in item.outline),
            layer="Mech.13",
            name=item.ref,
        )
        placed = place_body(
            body,
            component=index,
            at=at,
            rotation=component.rotation,
            bottom=item.side == "bottom",
            frame=frame,
        )
        assert not isinstance(placed, str), placed
        bodies.append(placed)
    return dataclasses.replace(spec, components=tuple(components), bodies=tuple(bodies), nets=())


def _fields(text: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in text.rstrip(b"\0").decode("ascii").split("|"):
        if part:
            key, _sep, value = part.partition("=")
            out[key] = value
    return out


def _text(fields: dict[str, str]) -> bytes:
    return "|".join(f"{key}={value}" for key, value in fields.items()).encode("ascii") + b"\0"


def _bodies(data: bytes, components: dict[str, tuple[int, int]], cases: tuple[Case, ...]) -> bytes:
    """The body records of ``data`` with each one's keys set to its case's kind and pose."""
    first = rec.BODY_KEYS[0].encode("ascii") + b"="
    out = b""
    at = 0
    index = 0
    while at < len(data):
        kind = data[at]
        (size,) = struct.unpack_from("<I", data, at + 1)
        body = data[at + 5 : at + 5 + size]
        at += 5 + size
        start = body.index(first)
        (length,) = struct.unpack_from("<I", body, start - 4)
        fields = _fields(body[start : start + length])
        item = cases[index]
        index += 1
        x, y = components[item.ref]
        fields["STANDOFFHEIGHT"] = rec.mil_text(item.standoff * UNITS)
        fields["OVERALLHEIGHT"] = rec.mil_text(item.overall * UNITS)
        fields["MODEL.EXTRUDED.MINZ"] = fields["STANDOFFHEIGHT"]
        fields["MODEL.EXTRUDED.MAXZ"] = fields["OVERALLHEIGHT"]
        if item.projection is not None:
            fields["BODYPROJECTION"] = str(item.projection)
        types = {"extruded": "0", "model": "1", "cylinder": "2", "sphere": "3"}
        fields["MODEL.MODELTYPE"] = types[item.shape]
        if item.shape == "model":
            fields["MODELID"] = MODEL_ID
            fields["MODEL.CHECKSUM"] = body_checksum(index - 1)
            fields["MODEL.EMBED"] = "TRUE"
            fields["MODEL.NAME"] = MODEL_NAME
            fields["MODEL.2D.X"] = rec.mil_text(x + item.offset[0] * UNITS)
            fields["MODEL.2D.Y"] = rec.mil_text(y + item.offset[1] * UNITS)
            fields["MODEL.3D.DZ"] = rec.mil_text(item.dz * UNITS)
            for key, value in zip(
                ("MODEL.3D.ROTX", "MODEL.3D.ROTY", "MODEL.3D.ROTZ"), item.turns, strict=True
            ):
                fields[key] = f"{value:.3f}"
        text = _text(fields)
        body = body[: start - 4] + struct.pack("<I", len(text)) + text + body[start + length :]
        out += bytes((kind,)) + struct.pack("<I", len(body)) + body
    assert index == len(cases)
    return out


def write_document(*, unknown: bool = False) -> bytes:
    """The bytes of the authored document; ``unknown`` adds ``UNKNOWN``, a body whose geometry is not
    proved."""
    cases = (*CASES, UNKNOWN) if unknown else CASES
    written = write_pcbdoc(_spec(cases), filename=NAME)
    compound = open_compound(written)
    streams = {path: compound.read(path) for path in compound.streams()}
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    document = read_pcbdoc(written, file=NAME)
    components: dict[str, tuple[int, int]] = {}
    for record in document.components:
        assert record.x is not None and record.y is not None
        designator = dict(record.fields).get("SOURCEDESIGNATOR", "") or record.source_designator
        components[str(designator)] = (round(record.x), round(record.y))
    streams["ComponentBodies6/Data"] = _bodies(streams["ComponentBodies6/Data"], components, cases)
    model = f"EMBED=TRUE|MODELSOURCE=Undefined|ID={MODEL_ID}|ROTX=0.000|ROTY=0.000|ROTZ=0.000|DZ=0|"
    model += f"CHECKSUM={MODEL_CHECKSUM}|NAME={MODEL_NAME}"
    text = model.encode("ascii") + b"\0"
    streams["Models/Data"] = struct.pack("<I", len(text)) + text
    streams["Models/Header"] = struct.pack("<I", 1)
    streams["Models/0"] = zlib.compress(marker_step())
    return write_compound(storage_from_paths(streams))


def write_folder(folder: Path, *, unknown: bool = False) -> Path:
    """The document written into ``folder``; its path."""
    path = folder / NAME
    path.write_bytes(write_document(unknown=unknown))
    return path


def places(document: bytes) -> dict[str, tuple[int, int]]:
    """Each component's place in ``document``, in its units (Y up)."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    out: dict[str, tuple[int, int]] = {}
    for record in read_pcbdoc(document, file=NAME).components:
        assert record.x is not None and record.y is not None
        out[str(record.source_designator)] = (round(record.x), round(record.y))
    return out


def outlines(document: bytes) -> list[tuple[dict[str, str], list[tuple[float, float]]]]:
    """Each body record of ``document`` in order, read from its bytes as ``pcb-bodies.md`` gives them: its
    keys, and its outline vertices in the document's units (Y up)."""
    data = open_compound(document).read("ComponentBodies6/Data")
    first = rec.BODY_KEYS[0].encode("ascii") + b"="
    out: list[tuple[dict[str, str], list[tuple[float, float]]]] = []
    at = 0
    while at < len(data):
        (size,) = struct.unpack_from("<I", data, at + 1)
        body = data[at + 5 : at + 5 + size]
        at += 5 + size
        start = body.index(first)
        (length,) = struct.unpack_from("<I", body, start - 4)
        rest = body[start + length :]
        (count,) = struct.unpack_from("<I", rest, 0)
        points = [struct.unpack_from("<2d", rest, 4 + 16 * k) for k in range(count)]
        out.append((_fields(body[start : start + length]), [(x, y) for x, y in points]))
    return out


__all__ = [
    "CASES",
    "MARKER",
    "MARKER_Z",
    "MIL",
    "NAME",
    "UNKNOWN",
    "Case",
    "case",
    "outlines",
    "places",
    "marker_step",
    "write_document",
    "write_folder",
]
