# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Extruded component body records of the Altium PCB document (capability altium-pcb-writer, "Body facts
before body code" and "Extruded component body records"; change c0121).

The writer writes exactly the rows of "Written form of an extruded body" of
``docs/formats/altium/pcb-bodies.md``: ``test_facts_*`` compares ``pcbrecords.BODY_KEYS`` with the key rows
of that section in both directions. The rows themselves are held over the public corpus by
``tests/corpus/test_altium_bodies.py``; that Altium takes a written body is no claim of this file.
"""

from __future__ import annotations

import dataclasses
import re
import struct
from pathlib import Path

import pytest
from _altium import blink_pcbdoc_spec

from fenolite.backends.altium import pcbdoc, pcbrecords
from fenolite.backends.altium.pcbdoc import (
    BODY_IS_MODEL,
    BODY_NO_OUTLINE,
    BODY_STORAGES,
    Frame,
    PcbDocSpec,
    PlacedBody,
    body_problem,
    body_vertices,
    place_body,
    write_pcbdoc,
)
from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody

ROOT = Path(__file__).resolve().parents[4]
PAGE = ROOT / "docs" / "formats" / "altium" / "pcb-bodies.md"
REGISTER = ROOT / "docs" / "hypotheses.md"
SECTION = "## Written form of an extruded body"
KEY_ROW = re.compile(r"^\| `([A-Z0-9_.]+)` \(key (\d+)\): ")
STAND_INS = ("MODELID", "MODEL.CHECKSUM")
RECTANGLE = ((0, 0), (10000, 0), (10000, 5001), (0, 5001))
MM = 1_000_000


def _section() -> list[str]:
    text = PAGE.read_text(encoding="utf-8")
    assert text.count(SECTION) == 1
    rest = text.split(SECTION, 1)[1]
    end = re.search(r"^## ", rest, re.M)
    return (rest[: end.start()] if end else rest).splitlines()


def _key_rows() -> list[tuple[int, str, list[str]]]:
    """(number, key, cells) of every key row of the section."""
    rows: list[tuple[int, str, list[str]]] = []
    for line in _section():
        match = KEY_ROW.match(line)
        if match is not None:
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            rows.append((int(match.group(2)), match.group(1), cells))
    return rows


def _fields(record: BodyRecord) -> dict[str, str]:
    return {key: record.properties.get_all(key)[0] for key in record.properties.keys()}


def _record(**changes: object) -> bytes:
    fields: dict[str, object] = {
        "component": 2,
        "standoff": 0,
        "overall": 984252,
        "bottom": False,
        "identifier": "U1",
        "model_id": pcbrecords.body_model_id("bdy_1"),
    }
    return pcbrecords.body_record(69, RECTANGLE, **{**fields, **changes})  # type: ignore[arg-type]


# --- fact rows ------------------------------------------------------------------------------------------


def test_facts_keys_and_rows_agree() -> None:
    """Scenario "Keys and rows agree": every key of ``BODY_KEYS`` has exactly one row at its place, every
    key row is a key of ``BODY_KEYS``, and the rows of the two identity keys are the only stand-ins."""
    rows = _key_rows()
    assert [(number, key) for number, key, _cells in rows] == list(enumerate(pcbrecords.BODY_KEYS, start=1))
    assert len(pcbrecords.BODY_KEYS) == 35 and pcbrecords.BODY_KEYS[pcbrecords.BODY_SHORT_KEYS - 1] == (
        "TEXTUREROTATION"
    )
    registered = REGISTER.read_text(encoding="utf-8")
    for _number, key, cells in rows:
        fact, source, label, hypothesis = cells
        assert re.search(r"\bS-\d{4}\b", source), key
        assert re.fullmatch(r"H-A-PCBX-BODY-[A-Z0-9]+", hypothesis) and f"| {hypothesis} |" in registered, key
        if key in STAND_INS:
            assert "**stand-in**" in fact and hypothesis == "H-A-PCBX-BODY-OPEN" and label == "INFERRED", key
        else:
            assert "stand-in" not in fact and label.startswith("CORPUS-VERIFIED"), key


def test_facts_say_how_thin_the_evidence_is() -> None:
    """The section states the split of the records and that nothing was opened in Altium."""
    text = " ".join(" ".join(_section()).split())
    assert "1265 of the 1272 come from one repository" in text
    assert "nothing that Fenolite writes from this section was opened in Altium" in text
    assert "No extruded body of a saved library was read" in text


def test_facts_written_values_are_the_rows() -> None:
    """Each constant the writer sets is the value its row states."""
    (record,) = read_bodies(_record())
    fields = _fields(record)
    rows = {key: cells[0] for _n, key, cells in _key_rows()}
    for key, value in fields.items():
        if key in ("STANDOFFHEIGHT", "OVERALLHEIGHT", "IDENTIFIER", "MODELID", "MODEL.2D.X", "MODEL.2D.Y"):
            continue
        if key in ("MODEL.EXTRUDED.MINZ", "MODEL.EXTRUDED.MAXZ", "V7_LAYER", "BODYPROJECTION"):
            continue
        shown = "one space" if value == " " else "empty" if value == "" else f"`{value}`"
        assert shown in rows[key], (key, value)
    assert fields["MODEL.CHECKSUM"] == pcbrecords.BODY_CHECKSUM == "0"
    assert fields["BODYCOLOR3D"] == pcbrecords.BODY_COLOR


# --- the record -----------------------------------------------------------------------------------------


def test_rectangle_on_a_top_component() -> None:
    """Scenario "Rectangle on a top component"."""
    plain_bytes, shape_bytes = _record(), _record(shape_based=True)
    (plain,) = read_bodies(plain_bytes)
    (shape,) = read_bodies(shape_bytes, shape_based=True)
    assert plain.properties.raw == shape.properties.raw
    for record in (plain, shape):
        assert record.framed and record.tail == b"" and not record.holes
        assert record.properties.keys() == pcbrecords.BODY_KEYS
        assert (record.layer, record.component) == (69, 2)
        assert (record.standoff_height, record.overall_height) == (0, 984252)
        assert record.identifier == "U1" and record.model_name == "" and record.body_projection == 0
        assert [(v.x, v.y) for v in record.outline] == [(float(x), float(y)) for x, y in RECTANGLE]
    fields = _fields(plain)
    assert fields["V7_LAYER"] == "MECHANICAL13"
    assert (fields["OVERALLHEIGHT"], fields["MODEL.EXTRUDED.MAXZ"]) == ("98.4252mil", "98.4252mil")
    assert (fields["STANDOFFHEIGHT"], fields["MODEL.EXTRUDED.MINZ"]) == ("0mil", "0mil")
    assert fields["IDENTIFIER"] == "85,49" and fields["BODYPROJECTION"] == "0"
    assert (fields["MODEL.2D.X"], fields["MODEL.2D.Y"]) == ("0.5mil", "0.25mil")  # 2500.5 units round down
    assert fields["MODEL.CHECKSUM"] == "0" and fields["MODEL.MODELTYPE"] == "0"
    assert fields["MODELID"] == pcbrecords.body_model_id("bdy_1")
    assert plain_bytes[0] == shape_bytes[0] == pcbrecords.BODY == 12
    sub = plain_bytes[5:]
    assert struct.unpack_from("<I", plain_bytes, 1) == (len(sub),)
    assert sub[:18] == bytes((69, 12, 0)) + b"\xff" * 4 + struct.pack("<H", 2) + b"\xff" * 4 + bytes(5)
    assert plain_bytes.endswith(struct.pack("<2d", 0.0, 5001.0)) and len(shape_bytes) - len(plain_bytes) == (
        5 * 37 - 4 * 16
    )
    assert shape.closing is not None and (shape.closing.x, shape.closing.y) == RECTANGLE[0]
    assert not any(v.is_round for v in (*shape.outline, shape.closing))
    text = plain.properties.raw[4:]
    assert text.endswith(b"\0") and text[:1] != b"|" and max(text) < 128


def test_centre_rounds_a_half_unit_towards_zero() -> None:
    """``H-A-PCBX-BODY-2D`` as the writer applies it, on both sides of zero."""
    cases = {
        ((0, 0), (3, 0), (3, 5), (0, 5)): ("0.0001mil", "0.0002mil"),
        ((-3, -5), (0, -5), (0, 0), (-3, 0)): ("-0.0001mil", "-0.0002mil"),
        ((-1, -1), (2, -1), (2, 0), (-1, 0)): ("0mil", "0mil"),
        ((10, 20), (30, 20), (30, 60)): ("0.002mil", "0.004mil"),
    }
    for vertices, centre in cases.items():
        (record,) = read_bodies(_record_of(vertices))
        fields = _fields(record)
        assert (fields["MODEL.2D.X"], fields["MODEL.2D.Y"]) == centre, vertices


def _record_of(vertices: tuple[tuple[int, int], ...]) -> bytes:
    return pcbrecords.body_record(
        69, vertices, component=0, standoff=0, overall=1, bottom=False, model_id=pcbrecords.body_model_id("a")
    )


def test_bottom_standoff_and_no_component() -> None:
    record_bytes = _record(bottom=True, standoff=196850, overall=1574803, component=pcbrecords.NO_INDEX)
    (record,) = read_bodies(record_bytes)
    fields = _fields(record)
    assert record.component is None and fields["BODYPROJECTION"] == "1"
    assert (fields["STANDOFFHEIGHT"], fields["MODEL.EXTRUDED.MINZ"]) == ("19.685mil", "19.685mil")
    assert (fields["OVERALLHEIGHT"], fields["MODEL.EXTRUDED.MAXZ"]) == ("157.4803mil", "157.4803mil")
    (empty,) = read_bodies(_record(identifier=""))
    assert _fields(empty)["IDENTIFIER"] == "" and empty.identifier == ""


def test_short_form() -> None:
    """Scenario "Short form": 21 keys, the last ``TEXTUREROTATION``, and no model key."""
    (record,) = read_bodies(_record(form="short", model_id=""))
    keys = record.properties.keys()
    assert keys == pcbrecords.BODY_KEYS[:21] and keys[-1] == "TEXTUREROTATION"
    assert not [key for key in keys if key.startswith("MODEL")]
    assert record.framed and record.tail == b"" and record.overall_height == 984252


def test_model_id_depends_on_the_body_id_alone() -> None:
    first, again, other = (pcbrecords.body_model_id(key) for key in ("bdy_1", "bdy_1", "bdy_2"))
    assert first == again != other
    assert re.fullmatch(r"\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}", first)


@pytest.mark.parametrize(
    "changes",
    [
        {"standoff": 5, "overall": 5},
        {"standoff": -1},
        {"model_id": ""},
        {"form": "long"},
        {"component": 0x10000},
    ],
)
def test_refused_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _record(**changes)


def test_refused_layer_and_outline() -> None:
    for layer in (1, 33, 56, 73):
        with pytest.raises(ValueError, match="mechanical layer"):
            pcbrecords.body_record(
                layer, RECTANGLE, component=0, standoff=0, overall=1, bottom=False, model_id="{A}"
            )
    with pytest.raises(ValueError, match="three vertices"):
        _record_of(((0, 0), (1, 1)))


def test_layer_rule() -> None:
    """The layer rule of "What is written of a model body"."""
    layer = pcbrecords.body_layer
    assert (layer("F.Fab", bottom=False), layer("B.Fab", bottom=True)) == (69, 70)
    assert (layer("F.CrtYd", bottom=False), layer("B.CrtYd", bottom=False)) == (71, 72)
    assert [layer(f"Mech.{n}", bottom=True) for n in (1, 13, 16)] == [57, 69, 72]
    for name in ("", "F.SilkS", "F.Cu", "Mech.17", "Mech.0", "Altium.72", "User.1"):
        assert (layer(name, bottom=False), layer(name, bottom=True)) == (69, 70), name


# --- the document ---------------------------------------------------------------------------------------


def _body(key: str, outline: tuple[Point, ...], **changes: object) -> ComponentBody:
    fields: dict[str, object] = {"id": f"bdy_{key}", "kind": "extruded", "height": 2_500_000}
    return ComponentBody(outline=outline, **{**fields, **changes})  # type: ignore[arg-type]


def _box(w: int, h: int) -> tuple[Point, ...]:
    return (Point(-w, -h), Point(w, -h), Point(w, h), Point(-w, h))


def test_body_problem_reasons() -> None:
    box = _box(MM, MM)
    assert body_problem(_body("a", box)) is None
    assert body_problem(_body("b", box, kind="model", model="part.step")) == BODY_IS_MODEL
    assert body_problem(_body("c", ())) == BODY_NO_OUTLINE
    assert body_problem(_body("d", (box[0], box[1], box[0], box[1]))) == BODY_NO_OUTLINE
    equal = body_problem(_body("e", box, standoff=2_500_000))
    assert equal is not None and "2.5 mm is not above its standoff of 2.5 mm" in equal
    close = body_problem(_body("f", box, standoff=2_499_999))  # the same unit
    assert close is not None and "not above" in close
    below = body_problem(_body("g", box, standoff=-100_000))
    assert below is not None and "below the board surface" in below


def test_place_body_and_vertices() -> None:
    frame = Frame.document()
    placed = place_body(
        _body("a", _box(MM, 2 * MM), name="B1", layer="B.Fab"),
        component=1,
        at=Point(10 * MM, 20 * MM),
        rotation=90_000_000,
        bottom=True,
        frame=frame,
    )
    assert isinstance(placed, PlacedBody)
    assert (placed.component, placed.layer, placed.bottom, placed.identifier) == (1, 70, True, "B1")
    assert placed.model_id == pcbrecords.body_model_id("bdy_a") and placed.body_id == "bdy_a"
    xs, ys = sorted({p.x for p in placed.outline}), sorted({p.y for p in placed.outline})
    assert len(xs) == len(ys) == 2 and xs[1] - xs[0] == 4 * MM and ys[1] - ys[0] == 2 * MM  # turned by 90
    assert (xs[0] + xs[1], ys[0] + ys[1]) == (20 * MM, 40 * MM)
    repeated = (Point(-MM, -MM), *_box(MM, MM), Point(-MM, -MM))  # a doubled start and a closing point
    assert len(body_vertices(repeated, frame)) == 4
    tiny = place_body(
        _body("t", (Point(0, 0), Point(1, 0), Point(0, 1))), component=0, at=Point(0, 0), rotation=0,
        bottom=False, frame=frame,
    )  # fmt: skip
    assert tiny == BODY_NO_OUTLINE  # three points of the model within one unit


def _with_bodies() -> tuple[PcbDocSpec, PcbDocSpec]:
    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec) and len(spec.components) >= 2
    frame = Frame.of(spec.outline)
    bodies: list[PlacedBody] = []
    for key, index, bottom, outline in (
        ("one", 0, False, _box(MM, MM)),
        ("two", 0, False, _box(2 * MM, MM)),
        ("three", 1, True, _box(MM, 3 * MM)),
    ):
        component = spec.components[index]
        placed = place_body(
            _body(key, outline, name=key.upper()),
            component=index,
            at=component.at,
            rotation=component.rotation,
            bottom=bottom,
            frame=frame,
        )
        assert isinstance(placed, PlacedBody)
        bodies.append(placed)
    return spec, dataclasses.replace(spec, bodies=tuple(bodies))


def test_document_with_three_bodies() -> None:
    """Scenario "Document with three bodies"."""
    bare, spec = _with_bodies()
    data = write_pcbdoc(spec, filename="bodies.PcbDoc")
    document = read_pcbdoc(data, file="bodies.PcbDoc", strict=True)
    assert not [found for found in document.issues if found.severity == "error"]
    plain_streams, shape_streams = (document.storages[name] for name in BODY_STORAGES)
    plain = read_bodies(plain_streams["Data"])
    shape = read_bodies(shape_streams["Data"], shape_based=True)
    assert len(plain) == len(shape) == 3
    assert plain_streams["Header"] == shape_streams["Header"] == struct.pack("<I", 3)
    for a, b in zip(plain, shape, strict=True):
        assert a.framed and b.framed and a.properties.raw == b.properties.raw and a.component == b.component
        assert all(float(v.x).is_integer() and float(v.y).is_integer() for v in a.outline)
    assert [record.component for record in plain] == [0, 0, 1]
    assert [record.identifier for record in plain] == ["ONE", "TWO", "THREE"]
    assert [record.body_projection for record in plain] == [0, 0, 1]
    assert [record.layer for record in plain] == [69, 69, 70]
    for name in ("Models", "ModelsNoEmbed", "Textures"):
        assert document.storages[name]["Data"] == b"" and document.storages[name]["Header"] == bytes(4)
    assert len(document.pad_unique_ids) == len(document.pads)
    # without bodies the document is the document of before, and only the body storages and the board
    # record (the layers in use) differ with them
    without = write_pcbdoc(bare, filename="bodies.PcbDoc")
    assert without == write_pcbdoc(dataclasses.replace(spec, bodies=()), filename="bodies.PcbDoc")
    empty = read_pcbdoc(without, file="bodies.PcbDoc", strict=True)
    for name in BODY_STORAGES:
        assert empty.storages[name]["Data"] == b"" and empty.storages[name]["Header"] == bytes(4)


def test_document_short_form() -> None:
    _bare, spec = _with_bodies()
    data = write_pcbdoc(dataclasses.replace(spec, body_form="short"), filename="bodies.PcbDoc")
    document = read_pcbdoc(data, file="bodies.PcbDoc", strict=True)
    for name, shape_based in zip(BODY_STORAGES, (False, True), strict=True):
        records = read_bodies(document.storages[name]["Data"], shape_based=shape_based)
        assert [len(record.properties.keys()) for record in records] == [21, 21, 21]


def test_document_refuses_a_body_it_cannot_hold() -> None:
    _bare, spec = _with_bodies()
    outside = dataclasses.replace(spec.bodies[0], component=len(spec.components))
    with pytest.raises(ValueError, match="names no component"):
        write_pcbdoc(dataclasses.replace(spec, bodies=(outside,)), filename="bodies.PcbDoc")
    flat = dataclasses.replace(spec.bodies[0], outline=spec.bodies[0].outline[:2])
    with pytest.raises(ValueError, match="no outline"):
        write_pcbdoc(dataclasses.replace(spec, bodies=(flat,)), filename="bodies.PcbDoc")
    assert pcbdoc.body_mode("off") == "off" and pcbdoc.body_mode("extruded") == "extruded"
    with pytest.raises(ValueError, match="unknown body mode"):
        pcbdoc.body_mode("all")
