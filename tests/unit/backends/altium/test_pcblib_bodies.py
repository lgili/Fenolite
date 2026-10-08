# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component bodies of a library footprint (capability altium-pcb-writer, "Component bodies of a library
footprint"; change c0121; ``H-A-PCBX-BODY-LIB``).

No extruded body of a saved library was read: the body is written in the form of a document's body with
no component. These tests hold that Fenolite's reader frames what is written and that a library without a
written body keeps its bytes; that Altium lists the body is step X8.7 of the author report.
"""

from __future__ import annotations

import dataclasses
import hashlib
import struct
from decimal import Decimal
from pathlib import Path

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.adapter.library import import_footprints
from fenolite.backends.altium.pcblib import (
    BODY_OBJECT,
    LibFootprint,
    PadExtras,
    check_footprint,
    footprint_primitives,
    write_pcblib,
)
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import BODY, PadRecord, RawPrimitive
from fenolite.backends.kicad.mod import read_footprint
from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody
from fenolite.model.library import FootprintDef

MINI = Path(__file__).resolve().parents[3] / "data" / "libs" / "Mini_v9.pretty"
MM = 1_000_000
BOX = (Point(-800_000, -400_000), Point(800_000, -400_000), Point(800_000, 400_000), Point(-800_000, 400_000))


def _body(key: str, **changes: object) -> ComponentBody:
    fields: dict[str, object] = {"id": f"bdy_{key}", "kind": "extruded", "height": 1_200_000, "outline": BOX}
    return ComponentBody(**{**fields, **changes})  # type: ignore[arg-type]


def _footprint(*bodies: ComponentBody, asked: bool = True) -> LibFootprint:
    defn = read_footprint(MINI / "Mini_R_0603.kicad_mod", library="Mini")
    assert len(defn.pads) == 2 and not defn.bodies
    defn = dataclasses.replace(defn, bodies=bodies)
    return LibFootprint(defn, _ratios(defn), texts=1, bodies=bodies if asked else ())


def _ratios(defn: FootprintDef) -> dict[str, PadExtras]:
    return {p.id: PadExtras(Decimal("0.25") if p.shape == "roundrect" else None) for p in defn.pads}


def test_footprint_with_a_body() -> None:
    """Scenario "Footprint with a body"."""
    footprint = _footprint(_body("a", name="R"))
    data = write_pcblib([footprint], filename="bodies.PcbLib")
    library = read_pcblib(data, file="bodies.PcbLib", strict=True)
    assert not [found for found in library.issues if found.severity == "error"]
    (read,) = library.footprints
    kinds = [p.type if isinstance(p, RawPrimitive) else type(p).__name__ for p in read.primitives]
    assert kinds.count(BODY) == 1 and kinds[-1] == BODY and kinds[:2] == ["PadRecord", "PadRecord"]
    assert read.streams["Header"] == struct.pack("<I", len(read.primitives))
    body = read.primitives[-1]
    assert isinstance(body, RawPrimitive)
    (record,) = read_bodies(body.raw, storage=read.storage)
    assert record.framed and record.tail == b"" and record.component is None and record.layer == 69
    assert record.properties.keys() == pcbrecords.BODY_KEYS and record.body_projection == 0
    assert record.overall_height is not None
    assert abs(record.overall_height - pcbrecords.to_units(1_200_000)) <= 1 and record.standoff_height == 0
    assert record.identifier == "R"
    # the library's frame: Y up, whole units
    assert [(v.x, v.y) for v in record.outline] == [
        (float(pcbrecords.to_units(p.x)), float(pcbrecords.to_units(-p.y))) for p in BOX
    ]
    # the list of unique ids names every primitive but the body
    unique = read.streams["UniqueIDPrimitiveInformation/Data"]
    assert unique.count(b"PRIMITIVEOBJECTID=") == len(read.primitives) - 1
    assert read.streams["UniqueIDPrimitiveInformation/Header"] == struct.pack("<I", len(read.primitives) - 1)
    assert sum(1 for p in read.primitives if isinstance(p, PadRecord)) == 2
    # without bodies the library is the library of today
    today = write_pcblib([_footprint()], filename="bodies.PcbLib")
    assert write_pcblib([_footprint(_body("a", name="R"), asked=False)], filename="bodies.PcbLib") == today
    assert today != data


def test_library_body_reads_back_to_the_definition() -> None:
    """Fenolite's import of the written library gives the body of the definition, within 2 nm."""
    wanted = _body("a", name="R", standoff=100_000)
    data = write_pcblib([_footprint(wanted)], filename="bodies.PcbLib")
    library = read_pcblib(data, file="bodies.PcbLib", strict=True)
    found = import_footprints(
        library, name="bodies", file="bodies.PcbLib", sha256=hashlib.sha256(data).hexdigest()
    )
    (definition,) = found.footprints
    (body,) = definition.bodies
    assert (body.kind, body.name, body.layer) == ("extruded", "R", "Mech.13")
    assert abs(body.height - wanted.height) <= 2 and abs(body.standoff - wanted.standoff) <= 2
    assert len(body.outline) == len(BOX)
    for a, b in zip(body.outline, BOX, strict=True):
        assert abs(a.x - b.x) <= 2 and abs(a.y - b.y) <= 2


def test_only_bodies_with_a_record_are_written() -> None:
    model = _body("m", kind="model", model="part.step")
    flat = _body("f", outline=BOX[:2])
    low = _body("l", standoff=1_200_000)
    good = _body("g")
    footprint = _footprint(model, flat, low, good)
    check = check_footprint(footprint.defn, footprint.extras, texts=1, bodies=footprint.bodies)
    assert check.bodies == (good,) and "3 component bodies" in check.extras
    primitives = footprint_primitives(footprint)
    assert [kind for kind, _record in primitives].count(BODY_OBJECT) == 1 and primitives[-1][0] == BODY_OBJECT
    # nothing asked: every body of the definition is a note, and none is written
    silent = _footprint(model, good, asked=False)
    check = check_footprint(silent.defn, silent.extras, texts=1)
    assert check.bodies == () and "2 component bodies" in check.extras
    assert BODY_OBJECT not in [kind for kind, _record in footprint_primitives(silent)]
    assert "component bod" not in " ".join(
        check_footprint(_footprint().defn, _footprint().extras, texts=1).extras
    )
