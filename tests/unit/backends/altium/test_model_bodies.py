# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Embedded model bodies of the Altium PCB document (capability altium-pcb-writer, "Embedded model bodies";
change c0449).

The written form is the one of ``docs/formats/altium/pcb-bodies.md``, "Written form of a model body"
(S-2080). That Altium opens a written model is no claim of this file (task 4.3)."""

from __future__ import annotations

import dataclasses
import re
import struct
import zlib

import pytest
from _altium import blink_pcbdoc_spec

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.pcbdoc import (
    BODY_STORAGES,
    EmbeddedModel,
    PcbDocSpec,
    PlacedBody,
    model_storage,
    write_pcbdoc,
)
from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point

MM = 1_000_000
DEG = 1_000_000
FIRST = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\n"
OTHER = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(1.,0.,0.));\nENDSEC;\n"
GUID = re.compile(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")


def _square(at: Point, half: int) -> tuple[Point, ...]:
    return (
        Point(at.x - half, at.y - half),
        Point(at.x + half, at.y - half),
        Point(at.x + half, at.y + half),
        Point(at.x - half, at.y + half),
    )


def _body(spec: PcbDocSpec, index: int, data: bytes, name: str, turn: int) -> PlacedBody:
    at = spec.components[index].at
    model = EmbeddedModel(data, name, at, dz=MM // 2, rotation=(0, 0, turn))
    return PlacedBody(
        component=index,
        layer=69,
        outline=_square(at, MM),
        height=2 * MM,
        standoff=-MM // 4,
        identifier=f"M{index}",
        model_id=pcbrecords.model_id(data),
        model=model,
    )


def _spec() -> PcbDocSpec:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec) and len(spec.components) >= 2
    bodies = (
        _body(spec, 0, FIRST, "first.step", 0),
        _body(spec, 1, FIRST, "first.step", 90 * DEG),
        _body(spec, 1, OTHER, "other (1).step", 0),
    )
    return dataclasses.replace(spec, bodies=bodies)


def _fields(record: BodyRecord) -> dict[str, str]:
    return {key: record.properties.get_all(key)[0] for key in record.properties.keys()}


def test_records_of_one_model_named_by_two_bodies() -> None:
    """Scenario "One model named by two bodies"."""
    data = write_pcbdoc(_spec(), filename="models.PcbDoc")
    document = read_pcbdoc(data, file="models.PcbDoc", strict=True)
    assert not [found for found in document.issues if found.severity == "error"]
    models = document.storages["Models"]
    records = model_records(models["Data"])
    assert models["Header"] == struct.pack("<I", 2) and len(records) == 2
    assert zlib.decompress(models["0"]) == FIRST and zlib.decompress(models["1"]) == OTHER
    assert models["0"][:2] == b"\x78\x9c"  # level 6, as saved streams are
    assert [record["ID"] for record in records] == [pcbrecords.model_id(FIRST), pcbrecords.model_id(OTHER)]
    assert all(GUID.fullmatch(record["ID"]) for record in records)
    first = records[0]
    assert list(first) == ["EMBED", "MODELSOURCE", "ID", "ROTX", "ROTY", "ROTZ", "DZ", "CHECKSUM", "NAME"]
    assert (first["EMBED"], first["MODELSOURCE"], first["CHECKSUM"]) == ("TRUE", "Undefined", "0")
    assert (first["ROTZ"], first["NAME"]) == ("0.000", "first.step")
    assert first["DZ"] == str(pcbrecords.to_units(MM // 2))  # integer file units
    assert records[1]["NAME"] == "other (1).step"
    plain_streams, shape_streams = (document.storages[name] for name in BODY_STORAGES)
    plain = read_bodies(plain_streams["Data"])
    shape = read_bodies(shape_streams["Data"], shape_based=True)
    assert len(plain) == len(shape) == 3
    assert plain_streams["Header"] == shape_streams["Header"] == struct.pack("<I", 3)
    fields = [_fields(record) for record in plain]
    assert [f["MODEL.MODELTYPE"] for f in fields] == ["1", "1", "1"]
    assert [f["MODELID"] for f in fields] == [records[0]["ID"], records[0]["ID"], records[1]["ID"]]
    assert [f["MODEL.3D.ROTZ"] for f in fields] == ["0.000", "90.000", "0.000"]
    assert fields[0]["MODEL.3D.ROTZ"] == first["ROTZ"]
    for f in fields:
        assert list(f) == list(dict.fromkeys(pcbrecords.MODEL_BODY_KEYS))  # ARCRESOLUTION twice
        assert (f["MODEL.EMBED"], f["MODEL.CHECKSUM"], f["BODYCOLOR3D"]) == ("TRUE", "0", "8421504")
        assert (f["MODEL.2D.ROTATION"], f["MODEL.MODELSOURCE"]) == ("0.000", "Undefined")
        assert f["STANDOFFHEIGHT"].startswith("-")  # a standoff below the face is kept
    for a, b in zip(plain, shape, strict=True):
        assert a.framed and b.framed and a.component == b.component


def test_records_without_a_model_keep_models_empty() -> None:
    """Scenario "No model, no entry": the storage of a spec without model bodies is the one of before."""
    spec = dataclasses.replace(_spec(), bodies=())
    storage = model_storage(spec)
    assert storage.entries == (("Header", bytes(4)), ("Data", b""))
    document = read_pcbdoc(write_pcbdoc(spec, filename="models.PcbDoc"), file="models.PcbDoc", strict=True)
    assert document.storages["Models"] == {"Header": bytes(4), "Data": b""}


def test_records_refuse_what_they_cannot_hold() -> None:
    spec = _spec()
    body = spec.bodies[0]
    assert body.model is not None
    empty = dataclasses.replace(body, model=dataclasses.replace(body.model, data=b""))
    named = dataclasses.replace(body, model=dataclasses.replace(body.model, name="a|b.step"))
    flat = dataclasses.replace(body, height=body.standoff)
    for bad, words in ((empty, "no data"), (named, "does not take"), (flat, "above its standoff")):
        with pytest.raises(ValueError, match=words):
            write_pcbdoc(dataclasses.replace(spec, bodies=(bad,)), filename="models.PcbDoc")


def test_records_turns_and_ids() -> None:
    assert pcbrecords.degrees_text(-90 * DEG) == "270.000"
    assert pcbrecords.degrees_text(360 * DEG) == "0.000"
    assert pcbrecords.degrees_text(12_345_500) == "12.346"  # half to even on the third decimal
    assert pcbrecords.degrees_text(12_344_500) == "12.344"
    assert pcbrecords.model_id(FIRST) == pcbrecords.model_id(bytes(FIRST))
    assert pcbrecords.model_id(FIRST) != pcbrecords.model_id(OTHER)
