# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Own files read (capability altium-pcb-reader, "Own files read", change c0041): every committed
``.PcbLib`` and ``.PcbDoc`` under ``tests/data/altium/`` is read by the product reader and by the
independent test reader ``tests/_altium_pcb_read.py``, with equal values, rebuilt streams and no issue.
Since change c0121 a file may hold component bodies: both readers decode them and must agree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _altium_pcb_read as independent
import pytest

from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import TYPED_STORAGES, read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import (
    BODY,
    ArcRecord,
    PadRecord,
    Primitive,
    RawPrimitive,
    TextRecord,
    TrackRecord,
    ViaRecord,
)

DATA = Path(__file__).resolve().parents[4] / "data" / "altium"
LIBRARIES = sorted(p for p in DATA.rglob("*") if p.suffix.lower() == ".pcblib")
DOCUMENTS = sorted(p for p in DATA.rglob("*") if p.suffix.lower() == ".pcbdoc")


def _net(value: int | None) -> int:
    return 0xFFFF if value is None else value


def _my_body(record: BodyRecord) -> tuple[Any, ...]:
    assert record.framed and record.tail == b"" and not record.holes
    component = 0xFFFF if record.component is None else record.component
    keys = [(key, record.properties.get_all(key)[n]) for key, n in _numbered(record.properties.keys())]
    return ("body", record.layer, component, keys, [(int(v.x), int(v.y)) for v in record.outline])


def _numbered(keys: tuple[str, ...]) -> list[tuple[str, int]]:
    """Each key with the number of its earlier uses (``ARCRESOLUTION`` is written twice)."""
    seen: dict[str, int] = {}
    out: list[tuple[str, int]] = []
    for key in keys:
        out.append((key, seen.get(key, 0)))
        seen[key] = seen.get(key, 0) + 1
    return out


def _mine(item: Primitive) -> tuple[Any, ...]:
    if isinstance(item, RawPrimitive):  # a component body of a library footprint (change c0121)
        assert item.type == BODY
        (record,) = read_bodies(item.raw)
        return _my_body(record)
    pre = (item.prefix.layer, _net(item.prefix.net), _net(item.prefix.component))
    if isinstance(item, TrackRecord):
        return ("track", *pre, item.x1, item.y1, item.x2, item.y2, item.width)
    if isinstance(item, ArcRecord):
        return ("arc", *pre, item.cx, item.cy, item.radius, item.start_angle, item.end_angle, item.width)
    if isinstance(item, PadRecord):
        corners = item.corner_percentages or ()
        shapes = item.alternate_shapes or ()
        sizes = (item.size_top, item.size_mid, item.size_bottom)
        kinds = (item.shape_top, item.shape_mid, item.shape_bottom)
        return ("pad", *pre, item.name, item.x, item.y, sizes, item.hole, kinds, item.rotation,
                int(item.plated), item.hole_shape, shapes, corners)  # fmt: skip
    if isinstance(item, TextRecord):
        return ("text", *pre, item.x, item.y, item.height, item.rotation, item.short_text, item.is_designator)
    assert isinstance(item, ViaRecord)
    return ("via", *pre, item.x, item.y, item.diameter, item.hole, item.start_layer, item.end_layer)


def _theirs(item: Any) -> tuple[Any, ...]:
    pre = (item.prefix.layer, item.prefix.net, item.prefix.component)
    if isinstance(item, independent.BodyRecord):
        return ("body", item.prefix.layer, item.prefix.component, item.keys, item.vertices)
    if isinstance(item, independent.Track):
        return ("track", *pre, item.x1, item.y1, item.x2, item.y2, item.width)
    if isinstance(item, independent.ArcRecord):
        return ("arc", *pre, item.cx, item.cy, item.radius, item.start, item.end, item.width)
    if isinstance(item, independent.PadRecord):
        return ("pad", *pre, item.name, item.x, item.y, item.sizes, item.hole, item.shapes, item.rotation,
                item.plated, item.hole_shape, item.alternate_shapes, item.corners)  # fmt: skip
    if isinstance(item, independent.TextRecord):
        designator = bool(item.is_designator) if item.wide_index is not None else None
        return ("text", *pre, item.x, item.y, item.height, item.rotation, item.text, designator)
    assert isinstance(item, independent.ViaRecord)
    return ("via", *pre, item.x, item.y, item.diameter, item.hole, item.start_layer, item.end_layer)


def test_own_files_exist() -> None:
    assert len(LIBRARIES) >= 2 and len(DOCUMENTS) >= 2


@pytest.mark.parametrize("path", LIBRARIES, ids=lambda p: p.name)
def test_golden_libraries_agree(path: Path) -> None:
    data = path.read_bytes()
    mine, theirs = read_pcblib(data), independent.read_pcblib(data)
    assert mine.issues == ()
    assert list(mine.names) == theirs.names
    compound = open_compound(data)
    for footprint in mine.footprints:
        other = theirs.footprints[footprint.name]
        assert footprint.storage == other.storage
        assert [_mine(p) for p in footprint.primitives] == [_theirs(p) for p in other.primitives]
        ids = {int(u["PRIMITIVEINDEX"]): u["UNIQUEID"] for u in other.unique_ids}
        assert dict(footprint.unique_ids) == ids
        assert footprint.rebuild() == compound.read(f"{footprint.storage}/Data")
    assert mine.unique_id == theirs.unique_id


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_golden_documents_agree(path: Path) -> None:
    data = path.read_bytes()
    mine, theirs = read_pcbdoc(data), independent.read_pcbdoc(data)
    assert mine.issues == ()
    assert [n.name for n in mine.nets] == [n.get("NAME") for n in theirs.nets]
    assert [(c.source_designator, c.pattern, c.layer) for c in mine.components] == [
        (c.get("SOURCEDESIGNATOR"), c.get("PATTERN"), c.get("LAYER")) for c in theirs.components
    ]
    for kind, own, other in (
        ("pads", mine.pads, theirs.pads),
        ("tracks", mine.tracks, theirs.tracks),
        ("arcs", mine.arcs, theirs.arcs),
        ("texts", mine.texts, theirs.texts),
        ("vias", mine.vias, theirs.vias),
    ):
        assert [_mine(p) for p in own] == [_theirs(p) for p in other], kind
    texts = [t for t in mine.texts if isinstance(t, TextRecord)]
    plain = read_bodies(mine.storages["ComponentBodies6"]["Data"])
    shape = read_bodies(mine.storages["ShapeBasedComponentBodies6"]["Data"], shape_based=True)
    assert [_my_body(b) for b in plain] == [_my_body(b) for b in shape] == [_theirs(b) for b in theirs.bodies]
    assert [t.text for t in texts] == [
        theirs.wide_strings.get(t.wide_index or 0, t.text) for t in theirs.texts
    ]
    assert [(p.layer, p.net, p.name, p.pour_index, len(p.vertices)) for p in mine.polygons] == [
        (p.layer, p.net, p.name, p.pour_index, len(p.vertices)) for p in theirs.polygons
    ]
    assert [(c.name, str(c.kind), c.members) for c in mine.classes] == [
        (c.name, c.kind, tuple(c.members)) for c in theirs.classes
    ]
    assert [(r.kind_number, r.name, r.priority, r.scope1) for r in mine.rules] == [
        (r.kind, r.name, r.priority, r.scope) for r in theirs.rules
    ]
    assert list(mine.board.copper_chain) == theirs.copper_chain
    assert {
        k: v for k, v in mine.board.plane_nets.items() if 39 + k - 1 in theirs.copper_chain
    } == theirs.plane_nets
    compound = open_compound(data)
    for storage in TYPED_STORAGES:
        if f"{storage}/Data" in compound:
            assert mine.rebuild(storage) == compound.read(f"{storage}/Data"), storage
