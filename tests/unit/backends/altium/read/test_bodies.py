# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component-body records (capability altium-import, "Component body records"; change c0043): framing, the
typed keys, byte identity on authored records, and what the module imports."""

from __future__ import annotations

import ast
import re
import struct
import sys
from fractions import Fraction
from pathlib import Path

import _altium_records as rec

from fenolite.backends.altium.read import bodies
from fenolite.backends.altium.read.bodies import BodyRecord, encode, read_bodies
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
MODULE = ROOT / "src" / "fenolite" / "backends" / "altium" / "read" / "bodies.py"
PAGE = ROOT / "docs" / "formats" / "altium" / "pcb-bodies.md"


def test_an_authored_body_is_framed_and_typed() -> None:
    fields = {"IDENTIFIER": "85,49", "OVERALLHEIGHT": "62.992mil", "STANDOFFHEIGHT": "3.937mil",
              "BODYPROJECTION": "1", "MODEL.NAME": "part.step", "MODEL.EMBED": "TRUE",
              "MODELID": "{12345678-0000-0000-0000-000000000000}"}  # fmt: skip
    data = rec.body_bytes(component=3, layer=57, fields=fields)
    issues: list[Issue] = []
    (body,) = read_bodies(data, storage="ComponentBodies6", issues=issues)
    assert issues == [] and body.framed and body.raw == data and body.tail == b""
    assert (body.index, body.layer, body.component, body.shape_based) == (0, 57, 3, False)
    assert body.overall_height == Fraction(629_920) and body.standoff_height == Fraction(39_370)
    assert (body.body_projection, body.identifier, body.model_name) == (1, "U1", "part.step")
    assert body.model_embedded is True and body.model_id == "{12345678-0000-0000-0000-000000000000}"
    assert [(v.x, v.y) for v in body.outline] == [(0.0, 0.0), (1e7, 0.0), (1e7, 5e6), (0.0, 5e6)]
    assert body.properties.get("V7_LAYER") == "MECHANICAL13" and body.closing is None and body.holes == ()


def test_a_body_without_a_component_and_untyped_values() -> None:
    data = rec.body_bytes(component=None, fields={"OVERALLHEIGHT": "tall", "MODEL.EMBED": "maybe"})
    (body,) = read_bodies(data)
    assert body.component is None and body.overall_height is None and body.model_embedded is None
    assert body.identifier == "" and body.model_name == ""


def test_the_shape_based_form_stores_one_more_vertex() -> None:
    data = rec.body_bytes(shape_based=True)
    (body,) = read_bodies(data, shape_based=True, storage="ShapeBasedComponentBodies6")
    assert body.framed and body.shape_based and len(body.outline) == 4 and body.closing is not None
    assert (body.outline[1].x, body.outline[1].y) == (10_000_000, 0) and body.tail == b""
    assert encode((body,)) == data


def test_byte_identity_on_authored_streams() -> None:
    stream = b"".join(
        [
            rec.body_bytes(component=0),
            rec.body_bytes(component=1, points=[(0, 0), (9, 0), (9, 9)], tail=b"\x01\x02\x03"),
            rec.body_bytes(component=None, fields={"IDENTIFIER": "plain text"}),
        ]
    )
    found = read_bodies(stream, storage="ComponentBodies6")
    assert encode(found) == stream and encode(list(found)) == stream
    assert [b.index for b in found] == [0, 1, 2] and found[1].tail == b"\x01\x02\x03"
    assert found[2].identifier == "plain text"
    assert read_bodies(b"") == () and encode(()) == b""


def test_what_does_not_frame_is_returned_raw_with_a_warning() -> None:
    good = rec.body_bytes()
    short = b"\x0c" + struct.pack("<I", 10) + bytes(10)
    count = rec.body_bytes()[:-8]  # the vertex count runs past the subrecord
    count = b"\x0c" + struct.pack("<I", len(count) - 5) + count[5:]
    track = b"\x04" + struct.pack("<I", 4) + bytes(4)
    for bad in (short, count, track):
        issues: list[Issue] = []
        found = read_bodies(good + bad + good, storage="ComponentBodies6", issues=issues)
        assert encode(found) == good + bad + good
        assert [b.framed for b in found] == [True, False, True] and found[1].layer is None
        assert [(i.code, i.severity) for i in issues] == [("altium.pcb-read.short-record", "warning")]
        assert issues[0].where == "ComponentBodies6/Data#1"


def test_trailing_bytes_are_kept() -> None:
    good = rec.body_bytes()
    issues: list[Issue] = []
    found = read_bodies(good + good[:20], issues=issues)
    assert encode(found) == good + good[:20] and [b.framed for b in found] == [True, False]
    assert len(issues) == 1 and issues[0].code == "altium.pcb-read.short-record"


def test_the_module_imports_only_core_and_the_readers() -> None:
    for node in ast.walk(ast.parse(MODULE.read_text(encoding="utf-8"))):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names = [node.module or ""]
        for name in names:
            if name.split(".")[0] == "fenolite":
                assert name.startswith(("fenolite.core", "fenolite.backends.altium.read")), name
            else:
                assert name == "__future__" or name.split(".")[0] in sys.stdlib_module_names, name
                assert name.split(".")[0] not in {"subprocess", "os", "shutil", "tempfile", "socket"}, name


def test_every_typed_key_is_a_sourced_row_of_the_fact_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    table = text[text.index("## Typed keys") : text.index("## Mapping to the model")]
    rows = [line for line in table.splitlines() if line.startswith("| `")]
    assert len(rows) == len(bodies.TYPED_KEYS)
    for key in bodies.TYPED_KEYS:
        (row,) = [line for line in rows if line.startswith(f"| `{key}` ")]
        assert re.search(r"\bS-\d{4}\b", row) and "H-A-IMP-BODY" in row, key
    views = {name for name, value in vars(BodyRecord).items() if isinstance(value, property)}
    assert views == {"standoff_height", "overall_height", "body_projection", "identifier", "model_name",
                     "model_id", "model_embedded"}  # fmt: skip
