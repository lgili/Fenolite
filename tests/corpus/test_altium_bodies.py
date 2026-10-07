# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The saved form of a component body over the public corpus (capability altium-pcb-writer, "Body facts
before body code"; change c0121; ``H-A-PCBX-BODY-FORM``, ``H-A-PCBX-BODY-2D``).

The eight public PCB documents and the four public PCB libraries of the manifest (use ``rta``) are read
with Fenolite's own readers, and every row of "Written form of an extruded body" of
``docs/formats/altium/pcb-bodies.md`` is held over their extruded bodies (``MODEL.MODELTYPE=0``): what
every record holds is asserted on every record, and what has exceptions is counted and compared with the
numbers of ``PINNED``, which are the numbers of the page. A number that moves fails on purpose: the page
is then corrected with it.

The test prints and records counts and value forms only: no name, no coordinate and no identifier of a
file. The heavy row ``altium-third-party-pcbdoc-08`` runs with ``FENOLITE_HEAVY=1``; it holds 1217 of the
1272 extruded bodies, so a run without it holds the rows over 55 bodies of four documents.
"""

from __future__ import annotations

import re
import struct
import tomllib
from collections import Counter
from fractions import Fraction
from functools import cache
from typing import Any
from urllib.parse import urlparse

import pytest
from _boards import census
from _corpus import MANIFEST, CorpusItem, heavy_enabled, manifest_items, require

from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import BODY, RawPrimitive
from fenolite.backends.altium.read.pcbprops import parse_mil

pytestmark = pytest.mark.needs_corpus
DOCUMENTS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id]
LIBRARIES = [item for item in manifest_items("rta") if "-pcblib-" in item.id]
MINIMUM_REPOSITORIES = 3
"""``H-A-PCBX-BODY-FORM`` asks for extruded bodies from at least three repositories."""
PLAIN, SHAPE, MODELS = "ComponentBodies6", "ShapeBasedComponentBodies6", "Models"
SAVED_KEYS = (
    "V7_LAYER", "NAME", "KIND", "SUBPOLYINDEX", "UNIONINDEX", "ARCRESOLUTION", "ISSHAPEBASED",
    "CAVITYHEIGHT", "STANDOFFHEIGHT", "OVERALLHEIGHT", "BODYPROJECTION", "ARCRESOLUTION", "BODYCOLOR3D",
    "BODYOPACITY3D", "IDENTIFIER", "TEXTURE", "TEXTURECENTERX", "TEXTURECENTERY", "TEXTURESIZEX",
    "TEXTURESIZEY", "TEXTUREROTATION", "MODELID", "MODEL.CHECKSUM", "MODEL.EMBED", "MODEL.NAME",
    "MODEL.2D.X", "MODEL.2D.Y", "MODEL.2D.ROTATION", "MODEL.3D.ROTX", "MODEL.3D.ROTY", "MODEL.3D.ROTZ",
    "MODEL.3D.DZ", "MODEL.MODELTYPE", "MODEL.EXTRUDED.MINZ", "MODEL.EXTRUDED.MAXZ",
)  # fmt: skip
"""The 35 keys of a saved extruded body, in order (``ARCRESOLUTION`` twice). The writer's
``pcbrecords.BODY_KEYS`` is compared with the rows of the page by a unit test; this tuple is the corpus
side of the same rows, written before the writer existed."""
OPTIONAL_KEYS = frozenset({"MODEL.SNAPCOUNT", "BODYOVERRIDECOLOR"})
"""Keys that a few saved records hold beside ``SAVED_KEYS``; the writer writes neither."""
CONSTANTS: dict[str, str] = {
    "NAME": " ",
    "KIND": "0",
    "SUBPOLYINDEX": "-1",
    "UNIONINDEX": "0",
    "CAVITYHEIGHT": "0mil",
    "BODYOPACITY3D": "1.000",
    "TEXTURE": "",
    "MODEL.EMBED": "FALSE",
    "MODEL.NAME": "",
    "MODEL.3D.ROTX": "0.000",
    "MODEL.3D.ROTY": "0.000",
    "MODEL.3D.ROTZ": "0.000",
    "MODEL.3D.DZ": "0mil",
    "MODEL.MODELTYPE": "0",
}
"""Key → the one value that every extruded body of the corpus holds."""
MIL = re.compile(r"-?\d+(\.\d{1,4})?mil")
GUID = re.compile(r"\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}")
REAL = re.compile(r" \d\.\d{14}E[+-]\d{4}")
"""The form of ``TEXTUREROTATION``: a leading space, one digit, 14 decimals and a four-digit exponent."""
WRITTEN_COLOR, WRITTEN_ROTATION = "12632256", " 0.00000000000000E+0000"
"""The two values that are Fenolite's choice among those that saved records hold."""
KINDS: dict[str, tuple[int, int, int, int]] = {
    "altium-third-party-pcbdoc-01": (247, 2, 245, 68),
    "altium-third-party-pcbdoc-02": (42, 0, 42, 26),
    "altium-third-party-pcbdoc-03": (50, 5, 45, 21),
    "altium-third-party-pcbdoc-04": (33, 30, 3, 3),
    "altium-third-party-pcbdoc-05": (23, 0, 23, 12),
    "altium-third-party-pcbdoc-06": (27, 0, 27, 18),
    "altium-third-party-pcbdoc-07": (24, 18, 6, 5),
    "altium-third-party-pcbdoc-08": (1302, 1217, 85, 60),
}
"""Row id → the records of each body storage, the extruded bodies (``MODEL.MODELTYPE=0``), the bodies
that name a model (``MODEL.MODELTYPE=1``) and the entries of the ``Models`` storage."""
PINNED: dict[str, dict[str, int]] = {
    "altium-third-party-pcbdoc-01": {
        "counter_clockwise": 1,
        "extruded": 2,
        "first_repeated": 1,
        "layer_69": 2,
        "model": 245,
        "model_standoff_above": 50,
        "model_standoff_below": 32,
        "model_standoff_zero": 163,
        "optional_MODEL.SNAPCOUNT": 2,
        "pad_ids": 745,
        "shape_based": 1,
        "side_bottom": 2,
        "standoff_above_zero": 1,
        "texture_rotation_of_component": 2,
        "texturecenterx_zero": 1,
        "texturecentery_zero": 2,
        "texturesizex_zero": 2,
        "texturesizey_zero": 2,
        "vertices_21": 1,
        "vertices_4": 1,
    },
    "altium-third-party-pcbdoc-02": {
        "model": 42,
        "model_standoff_above": 17,
        "model_standoff_below": 9,
        "model_standoff_zero": 16,
        "pad_ids": 143,
    },
    "altium-third-party-pcbdoc-03": {
        "counter_clockwise": 5,
        "extruded": 5,
        "layer_57": 5,
        "model": 45,
        "model_standoff_above": 1,
        "model_standoff_below": 11,
        "model_standoff_zero": 33,
        "pad_ids": 385,
        "side_top": 5,
        "texture_rotation_of_component": 5,
        "texturecenterx_zero": 5,
        "texturecentery_zero": 5,
        "vertices_5": 3,
        "vertices_6": 2,
    },
    "altium-third-party-pcbdoc-04": {
        "centre_halves": 16,
        "centre_with_a_half": 16,
        "color_written": 20,
        "counter_clockwise": 12,
        "extruded": 30,
        "flip_pair": 30,
        "layer_69": 30,
        "model": 3,
        "model_standoff_below": 2,
        "model_standoff_zero": 1,
        "pad_ids": 53,
        "side_top": 30,
        "texture_rotation_of_component": 27,
        "texturecenterx_zero": 28,
        "texturecentery_zero": 28,
        "texturesizex_zero": 30,
        "texturesizey_zero": 30,
        "vertices_4": 27,
        "vertices_6": 3,
    },
    "altium-third-party-pcbdoc-05": {
        "model": 23,
        "model_standoff_below": 7,
        "model_standoff_zero": 16,
        "pad_ids": 100,
    },
    "altium-third-party-pcbdoc-06": {
        "model": 27,
        "model_standoff_below": 4,
        "model_standoff_zero": 23,
        "pad_ids": 106,
    },
    "altium-third-party-pcbdoc-07": {
        "centre_halves": 6,
        "centre_with_a_half": 6,
        "color_written": 12,
        "counter_clockwise": 15,
        "extruded": 18,
        "flip_pair": 18,
        "layer_69": 3,
        "layer_70": 15,
        "model": 6,
        "model_standoff_below": 3,
        "model_standoff_zero": 3,
        "pad_ids": 116,
        "side_bottom": 15,
        "side_top": 3,
        "texture_rotation_of_component": 3,
        "texturecenterx_zero": 18,
        "texturecentery_zero": 18,
        "texturesizex_zero": 18,
        "texturesizey_zero": 18,
        "vertices_4": 18,
    },
    "altium-third-party-pcbdoc-08": {
        "centre_halves": 676,
        "centre_turned": 6,
        "centre_with_a_half": 653,
        "color_written": 804,
        "counter_clockwise": 600,
        "extruded": 1217,
        "flip_pair": 729,
        "identifier": 2,
        "layer_69": 729,
        "layer_72": 488,
        "layer_above_16": 488,
        "model": 85,
        "model_standoff_above": 14,
        "model_standoff_below": 25,
        "model_standoff_zero": 46,
        "optional_BODYOVERRIDECOLOR": 3,
        "pad_ids": 2136,
        "side_bottom": 488,
        "side_top": 729,
        "standoff_above_zero": 3,
        "texture_rotation_of_component": 759,
        "texture_rotation_written": 115,
        "texturecenterx_zero": 1173,
        "texturecentery_zero": 1174,
        "texturesizex_zero": 1215,
        "texturesizey_zero": 1215,
        "vertices_4": 1217,
        "without_component": 4,
    },
}
"""Row id → the counts of the rows that are not the same in every record."""
TOTALS: dict[str, int] = {
    "centre_halves": 698,
    "centre_turned": 6,
    "centre_with_a_half": 675,
    "color_written": 836,
    "counter_clockwise": 633,
    "extruded": 1272,
    "first_repeated": 1,
    "flip_pair": 777,
    "identifier": 2,
    "layer_57": 5,
    "layer_69": 764,
    "layer_70": 15,
    "layer_72": 488,
    "layer_above_16": 488,
    "model": 476,
    "model_standoff_above": 82,
    "model_standoff_below": 93,
    "model_standoff_zero": 301,
    "optional_BODYOVERRIDECOLOR": 3,
    "optional_MODEL.SNAPCOUNT": 2,
    "pad_ids": 3784,
    "shape_based": 1,
    "side_bottom": 505,
    "side_top": 767,
    "standoff_above_zero": 4,
    "texture_rotation_of_component": 796,
    "texture_rotation_written": 115,
    "texturecenterx_zero": 1225,
    "texturecentery_zero": 1227,
    "texturesizex_zero": 1265,
    "texturesizey_zero": 1265,
    "vertices_21": 1,
    "vertices_4": 1263,
    "vertices_5": 3,
    "vertices_6": 5,
    "without_component": 4,
}
"""The sums of ``PINNED`` over the eight documents that the page states."""
ACROSS = {"model_ids": 77, "checksums": 77, "shapes": 53, "shapes_shared": 24, "checksums_shared": 17}
"""Over the 1272 extruded bodies of the five documents together (needs the heavy row): the distinct
``MODELID`` values, the distinct ``MODEL.CHECKSUM`` values (one per ``MODELID``), the distinct shapes (the
two sides of the outline's box in either order, the standoff and the overall height), the shapes that
hold more than one checksum, and the checksums that more than one shape holds."""


def _repository(url: str) -> tuple[str, ...]:
    parts = [part for part in urlparse(url).path.split("/") if part and part != "media"]
    return tuple(parts[:2])


def _repositories() -> dict[str, tuple[str, ...]]:
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    return {row["id"]: _repository(row["url"]) for row in rows}


def _sub(record: BodyRecord) -> bytes:
    """The subrecord of a body: its bytes after the type byte and the length word."""
    return record.raw[5:]


def _points(record: BodyRecord) -> list[tuple[int, int]]:
    assert all(float(v.x).is_integer() and float(v.y).is_integer() for v in record.outline)
    return [(int(v.x), int(v.y)) for v in record.outline]


def _towards_zero(twice: int) -> Fraction:
    """Half of ``twice`` in whole units, a half rounded towards zero."""
    half = abs(twice) // 2
    return Fraction(half if twice >= 0 else -half)


def _model_ids(data: bytes) -> tuple[int, set[str], set[int]]:
    """The records of ``Models/Data``, their ``ID`` values and the numbers of keys they hold."""
    at, ids, sizes, count = 0, set[str](), set[int](), 0
    while at + 4 <= len(data):
        (length,) = struct.unpack_from("<I", data, at)
        text = data[at + 4 : at + 4 + length].rstrip(b"\0").decode("latin-1")
        fields = dict(piece.split("=", 1) for piece in text.split("|") if "=" in piece)
        ids.add(fields.get("ID", ""))
        sizes.add(len(fields))
        at += 4 + length
        count += 1
    assert at == len(data)
    return count, ids, sizes


def _prefix_holds(record: BodyRecord) -> None:
    """The binary fields that every body record of the corpus holds, of both kinds."""
    sub = _sub(record)
    assert record.framed and record.tail == b"" and not record.holes
    assert sub[1:3] == b"\x0c\x00" and sub[3:7] == b"\xff" * 4
    assert sub[9:13] == b"\xff" * 4 and sub[13:18] == bytes(5)


@cache
def measure(item: CorpusItem) -> dict[str, Any]:
    """Every row over one document: the asserted rows are asserted here, the counted ones returned under
    ``counts``; ``pairs`` and ``shapes`` are for the comparison across documents and are never printed."""
    path = require(item)
    document = read_pcbdoc(path.read_bytes(), file=path.name)
    storages = {name.lower(): streams for name, streams in document.storages.items()}
    plain_streams, shape_streams = storages[PLAIN.lower()], storages[SHAPE.lower()]
    plain = read_bodies(plain_streams["Data"], storage=PLAIN)
    shape = read_bodies(shape_streams["Data"], shape_based=True, storage=SHAPE)
    assert struct.unpack("<I", plain_streams["Header"]) == (len(plain),)
    assert struct.unpack("<I", shape_streams["Header"]) == (len(shape),)
    models = storages[MODELS.lower()]
    entries, model_ids, key_counts = _model_ids(models["Data"])
    assert sum(1 for name in models if name.isdigit()) == entries and key_counts <= {9}
    assert struct.unpack("<I", models["Header"]) == (entries,)
    for empty in ("modelsnoembed", "textures"):
        assert storages[empty]["Data"] == b"" and storages[empty]["Header"] == bytes(4)
    unique = document.parts.get("UniqueIDPrimitiveInformation", ((), b""))[0]
    assert all(b"PRIMITIVEOBJECTID=Pad" in raw for raw in unique)
    counts: Counter[str] = Counter({"pad_ids": len(unique)})
    pairs: set[tuple[str, str]] = set()
    shapes: set[tuple[tuple[int, int, str, str], str]] = set()
    for a, b in zip(plain, shape, strict=True):
        _prefix_holds(a)
        _prefix_holds(b)
        keys = a.properties
        # the twin: the same 18 bytes, the same text, the same component, at the same index
        assert _sub(a)[:18] == _sub(b)[:18] and keys.raw == b.properties.raw and a.component == b.component
        # the text: 7-bit ASCII without a leading bar, a line end or a bar at its end, closed by one NUL
        text = keys.raw[4:]
        assert text.endswith(b"\0") and text[:1] != b"|" and text[-2:-1] != b"|" and max(text) < 128
        assert b"\r" not in text and b"\n" not in text
        points = _points(a)  # every coordinate of the plain storage is a whole number of units
        kind = keys.get("MODEL.MODELTYPE")
        assert kind in ("0", "1")
        if a.component is None:
            counts["without_component"] += 1
            assert kind == "1"
        else:
            assert a.component < len(document.components)
        if kind == "1":
            counts["model"] += 1
            assert keys.text("MODEL.NAME") and keys.get("MODEL.EMBED") == "TRUE"
            assert keys.text("MODELID") in model_ids and keys.keys()[-1] == "MODEL.MODELSOURCE"
            assert len(points) == 4
            standoff = parse_mil(keys.get("STANDOFFHEIGHT"))
            assert standoff is not None
            counts[
                "model_standoff_" + ("zero" if standoff == 0 else "above" if standoff > 0 else "below")
            ] += 1
            if a.component is not None:
                side = (document.components[a.component].layer or "").upper()
                assert keys.get("BODYPROJECTION") == {"TOP": "0", "BOTTOM": "1"}[side]
            continue
        counts["extruded"] += 1
        # keys and their order: the 35 saved keys, and in a few records one optional key more
        names = keys.keys()
        extra = [name for name in names if name in OPTIONAL_KEYS]
        assert tuple(name for name in names if name not in OPTIONAL_KEYS) == SAVED_KEYS
        assert len(extra) <= 1
        for name in extra:
            counts[f"optional_{name}"] += 1
        for name, value in CONSTANTS.items():
            assert keys.get_all(name) == (value,), name
        assert keys.get_all("ARCRESOLUTION") == ("0.5mil", "0.5mil")
        # layer: 56 + n for Mechanical n up to 16; a layer above 16 lies on the byte 72
        layer = _sub(a)[0]
        (number,) = re.fullmatch(r"MECHANICAL(\d+)", keys.text("V7_LAYER")).groups()  # type: ignore[union-attr]
        assert layer == (56 + int(number) if int(number) <= 16 else 72)
        counts[f"layer_{layer}"] += 1
        counts["layer_above_16"] += int(number) > 16
        # heights and the two keys that repeat them
        standoff_text, overall_text = keys.text("STANDOFFHEIGHT"), keys.text("OVERALLHEIGHT")
        assert MIL.fullmatch(standoff_text) and MIL.fullmatch(overall_text)
        standoff, overall = parse_mil(standoff_text), parse_mil(overall_text)
        assert standoff is not None and overall is not None and overall > standoff >= 0
        assert keys.get("MODEL.EXTRUDED.MINZ") == standoff_text
        assert keys.get("MODEL.EXTRUDED.MAXZ") == overall_text
        counts["standoff_above_zero"] += standoff > 0
        # the side of the component
        component = document.components[a.component]  # type: ignore[index]
        side = (component.layer or "").upper()
        assert keys.get("BODYPROJECTION") == {"TOP": "0", "BOTTOM": "1"}[side]
        counts[f"side_{side.lower()}"] += 1
        counts["flip_pair"] += (layer, side) in ((69, "TOP"), (70, "BOTTOM"))
        # identity keys: a GUID that names no entry of Models, and an unsigned 32-bit checksum, never 0
        model_id, checksum = keys.text("MODELID"), keys.text("MODEL.CHECKSUM")
        assert GUID.fullmatch(model_id) and model_id not in model_ids
        assert checksum.isdigit() and 0 < int(checksum) < 2**32
        pairs.add((model_id, checksum))
        xs, ys = [x for x, _ in points], [y for _, y in points]
        width, height = sorted((max(xs) - min(xs), max(ys) - min(ys)))
        shapes.add(((width, height, standoff_text, overall_text), checksum))
        # values with exceptions, counted
        counts["shape_based"] += keys.get("ISSHAPEBASED") == "TRUE"
        assert keys.get("ISSHAPEBASED") in ("TRUE", "FALSE")
        assert keys.text("BODYCOLOR3D").isdigit()
        counts["color_written"] += keys.get("BODYCOLOR3D") == WRITTEN_COLOR
        identifier = keys.text("IDENTIFIER")
        assert identifier == "" or re.fullmatch(r"\d+(,\d+)*", identifier)
        counts["identifier"] += bool(identifier)
        for name in ("TEXTURECENTERX", "TEXTURECENTERY", "TEXTURESIZEX", "TEXTURESIZEY"):
            value = parse_mil(keys.get(name))
            assert value is not None and abs(value) <= 4  # within 0.0004 mil of 0
            counts[f"{name.lower()}_zero"] += keys.get(name) == "0mil"
        rotation = keys.text("TEXTUREROTATION")
        assert REAL.fullmatch(rotation) and float(rotation) in (0, 45, 90, 180, 270, 360)
        counts["texture_rotation_written"] += rotation == WRITTEN_ROTATION
        turn = (float(rotation) - (component.rotation or 0.0)) % 360
        counts["texture_rotation_of_component"] += min(turn, 360 - turn) < 1e-6
        # the outline and its twin
        counts[f"vertices_{len(points)}"] += 1
        counts["first_repeated"] += points[0] == points[-1]
        turned_points = points[1:] + points[:1]
        doubled = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, turned_points, strict=True))
        counts["counter_clockwise"] += doubled > 0
        assert b.closing is not None
        if keys.get("ISSHAPEBASED") == "FALSE":
            assert not any(v.is_round for v in (*b.outline, b.closing))
            assert _points(b) == points and (int(b.closing.x), int(b.closing.y)) == points[0]
        # MODEL.2D.X/Y: the centre of the outline's box, a half unit rounded towards zero
        turned = keys.get("MODEL.2D.ROTATION")
        assert turned in ("0.000", "360.000")
        centre = (parse_mil(keys.get("MODEL.2D.X")), parse_mil(keys.get("MODEL.2D.Y")))
        box = (_towards_zero(min(xs) + max(xs)), _towards_zero(min(ys) + max(ys)))
        if turned == "0.000":
            assert centre == box
            counts["centre_with_a_half"] += bool((min(xs) + max(xs)) % 2 or (min(ys) + max(ys)) % 2)
            counts["centre_halves"] += (min(xs) + max(xs)) % 2 + (min(ys) + max(ys)) % 2
        else:
            assert centre != box
            counts["centre_turned"] += 1
    assert len(pairs) == len({model_id for model_id, _ in pairs}) == len({c for _, c in pairs})
    return {
        "bodies": (len(plain), len(shape)),
        "entries": entries,
        "counts": {name: count for name, count in sorted(counts.items()) if count},
        "pairs": pairs,
        "shapes": shapes,
    }


def test_rows_exist() -> None:
    assert [item.id for item in DOCUMENTS] == sorted(KINDS) and len(LIBRARIES) == 4
    assert sorted(PINNED) == sorted(KINDS)


def test_form_pinned_numbers_are_those_of_the_page() -> None:
    """The sums of the pinned rows are the numbers that the page and the hypothesis row state: 1272
    extruded bodies of five documents of three repositories, 1265 of them of one repository. Reads the
    manifest and this module only."""
    total: Counter[str] = Counter()
    for counts in PINNED.values():
        total.update(counts)
    assert dict(sorted(total.items())) == TOTALS
    assert sum(k[0] for k in KINDS.values()) == 1748 and sum(k[3] for k in KINDS.values()) == 213
    assert (sum(k[1] for k in KINDS.values()), sum(k[2] for k in KINDS.values())) == (1272, 476)
    repositories = _repositories()
    per_repository: Counter[tuple[str, ...]] = Counter()
    for row, kinds in KINDS.items():
        if kinds[1]:
            per_repository[repositories[row]] += kinds[1]
    assert len(per_repository) == MINIMUM_REPOSITORIES and sorted(per_repository.values()) == [2, 5, 1265]
    assert sum(1 for kinds in KINDS.values() if kinds[1]) == 5


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_form_of_document(item: CorpusItem, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "The rows hold over the public documents", one document: every asserted row holds on
    every body, and the counted rows give the pinned numbers. Prints the bodies of each kind."""
    found = measure(item)
    counts = found["counts"]
    kinds = (found["bodies"][0], counts.get("extruded", 0), counts.get("model", 0), found["entries"])
    census("altium-bodies", item.id, {"kinds": list(kinds), "counts": counts})
    with capsys.disabled():
        print(
            f"\n{item.id}: {kinds[0]} bodies in each storage, {kinds[1]} extruded, {kinds[2]} that name a "
            f"model, {kinds[3]} entries of Models"
        )
    assert found["bodies"][0] == found["bodies"][1]
    assert kinds == KINDS[item.id]
    assert counts == PINNED[item.id]


def test_form_centre_is_the_middle_of_the_box() -> None:
    """``H-A-PCBX-BODY-2D``: exact on every extruded body whose ``MODEL.2D.ROTATION`` is ``0.000`` (asserted
    in ``measure``); here the documents that ran are counted against the pinned numbers."""
    ran = [item for item in DOCUMENTS if item.path.is_file() and (heavy_enabled() or not item.heavy)]
    if not ran:
        pytest.skip("no PCB document of the corpus is cached")
    for item in ran:
        counts = measure(item)["counts"]
        exact = counts.get("extruded", 0) - counts.get("centre_turned", 0)
        pinned = PINNED[item.id]
        assert exact == pinned.get("extruded", 0) - pinned.get("centre_turned", 0)
        assert counts.get("centre_halves", 0) == pinned.get("centre_halves", 0)


def test_form_identity_keys_do_not_follow_from_the_shape() -> None:
    """Why ``MODELID`` and ``MODEL.CHECKSUM`` are stand-ins: over the five documents together, one checksum
    per ``MODELID``, and the checksum is no function of the outline's box and the heights. Needs the
    heavy row, which holds 1217 of the 1272 bodies."""
    if not heavy_enabled():
        pytest.skip("needs the heavy corpus row: set FENOLITE_HEAVY=1")
    pairs: set[tuple[str, str]] = set()
    shapes: set[tuple[tuple[int, int, str, str], str]] = set()
    for item in DOCUMENTS:
        found = measure(item)
        pairs |= found["pairs"]
        shapes |= found["shapes"]
    by_shape: dict[tuple[int, int, str, str], set[str]] = {}
    by_checksum: dict[str, set[tuple[int, int, str, str]]] = {}
    for shape, checksum in shapes:
        by_shape.setdefault(shape, set()).add(checksum)
        by_checksum.setdefault(checksum, set()).add(shape)
    assert {
        "model_ids": len({model_id for model_id, _ in pairs}),
        "checksums": len({checksum for _, checksum in pairs}),
        "shapes": len(by_shape),
        "shapes_shared": sum(1 for found in by_shape.values() if len(found) > 1),
        "checksums_shared": sum(1 for found in by_checksum.values() if len(found) > 1),
    } == ACROSS
    assert len(pairs) == ACROSS["model_ids"]


def test_form_of_the_library_body(capsys: pytest.CaptureFixture[str]) -> None:
    """The four public libraries hold one body, in one footprint beside 2 pads and 21 tracks, and it names
    a model: no extruded body of a saved library was read (``H-A-PCBX-BODY-LIB`` stays ``INFERRED``)."""
    found: list[tuple[str, BodyRecord, Counter[str]]] = []
    footprints = 0
    for item in LIBRARIES:
        path = require(item)
        library = read_pcblib(path.read_bytes(), file=path.name)
        footprints += len(library.footprints)
        for footprint in library.footprints:
            kinds = Counter(type(primitive).__name__ for primitive in footprint.primitives)
            for primitive in footprint.primitives:
                if isinstance(primitive, RawPrimitive) and primitive.type == BODY:
                    assert len(primitive.subrecords) == 1
                    (record,) = read_bodies(primitive.raw, storage=footprint.storage)
                    found.append((item.id, record, kinds))
                    # the body is the last primitive, the stream's header counts it, and the footprint's
                    # list of unique ids names the pads only
                    assert footprint.primitives[-1] is primitive
                    assert footprint.streams["Header"] == struct.pack("<I", len(footprint.primitives))
                    assert sorted(footprint.unique_ids) == [0, 1]
                    unique = footprint.streams["UniqueIDPrimitiveInformation/Data"]
                    assert unique.count(b"PRIMITIVEOBJECTID=") == unique.count(b"PRIMITIVEOBJECTID=Pad") == 2
    with capsys.disabled():
        print(f"\nlibraries: {footprints} footprints, {len(found)} body record(s)")
    assert footprints == 12
    ((row, record, kinds),) = found
    assert row == "altium-third-party-pcblib-03"
    assert dict(kinds) == {"PadRecord": 2, "TrackRecord": 21, "RawPrimitive": 1}
    _prefix_holds(record)
    keys = record.properties
    assert record.component is None and _sub(record)[7:9] == b"\xff\xff"
    assert (
        keys.get("MODEL.MODELTYPE") == "1" and keys.get("MODEL.EMBED") == "TRUE" and keys.text("MODEL.NAME")
    )
    assert len(keys.keys()) == 34 and keys.keys()[-1] == "MODEL.MODELSOURCE"
    assert keys.keys()[:21] == SAVED_KEYS[:21] and keys.get("BODYPROJECTION") == "0"
    assert len(_points(record)) == 4
