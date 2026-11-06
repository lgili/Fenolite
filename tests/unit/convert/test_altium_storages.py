# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium storages without a model entity travel through KiCad as board properties (change c0450)."""

import struct
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_storages as storages
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source

UNION = b"|UNIONINDEX=1|NAME=Fenolite union\x00"
GROUP = b"|SELECTION=FALSE|NAME=Fenolite_Group|KIND=1|SUPERCLASS=FALSE|M0=R1\x00"
GUID = b"|PRIMITIVEINDEX=0|GUID={00000000-0000-0000-0000-000000000000}\x00"
"""An authored union name, an authored component class and an authored primitive GUID."""


def _record(text: bytes) -> bytes:
    return struct.pack("<I", len(text)) + text


def _document(tmp_path: Path) -> Path:
    """The two-layer board written as an Altium document, with an authored ``UnionNames`` storage, an
    authored component class in ``Classes6`` and one ``PrimitiveGuids`` record."""
    design = two_layer()
    written = lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]
    streams = open_compound(written).as_dict()
    streams["UnionNames/Header"] = struct.pack("<I", 1)
    streams["UnionNames/Data"] = _record(UNION)
    (count,) = struct.unpack_from("<I", streams["Classes6/Header"])
    streams["Classes6/Header"] = struct.pack("<I", count + 1)
    streams["Classes6/Data"] += _record(GROUP)
    streams["PrimitiveGuids/Header"] = struct.pack("<I", 1)
    streams["PrimitiveGuids/Data"] = _record(GUID)
    path = tmp_path / "altium" / f"{design.header.name}.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


def test_a_storage_value_round_trips() -> None:
    storage = storages.Storage(b"\x01\x00\x00\x00", _record(UNION))
    assert storages.unpacked(storages.packed(storage)) == storage
    assert storages.unpacked(b"\x09\x00\x00\x00") is None  # a header longer than the bytes


def test_only_carried_storage_names_are_storages() -> None:
    """A board's other carried properties, the rule records of change c0434 among them, are no storage."""
    storage = storages.Storage(b"\x01\x00\x00\x00", _record(UNION))
    found = storages.from_carried(
        {
            "Fenolite.Altium.UnionNames": storages.packed(storage),
            "Fenolite.Altium.Rules6": b"rule records",
            "Fenolite.Altium.BoardRegions": b"\x00",
        }
    )
    assert found == {"UnionNames": storage}


def test_kicad_board_holds_the_carried_storages(tmp_path: Path) -> None:
    """The conversion to KiCad writes ``UnionNames`` and the component class as board properties and counts
    the ``PrimitiveGuids`` storage lost under ``altium-storage``."""
    conversion = convert_project(read_source(_document(tmp_path)), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode()
    found = {
        name: data for name, data in boardcarrier.carried(text).items() if name != "Fenolite.Altium.Rules6"
    }
    assert set(found) == {"Fenolite.Altium.UnionNames", "Fenolite.Altium.Classes6.Component"}
    # one write of every carried property (``with_carried``): right after ``setup``, in name order
    lines = [line.lstrip() for line in text.splitlines()]
    names = [line.split('"')[1] for line in lines if line.startswith('(property "Fenolite.')]
    assert names == sorted(boardcarrier.carried(text))
    assert boardcarrier.with_carried(text, boardcarrier.carried(text)) == text
    union = storages.unpacked(found["Fenolite.Altium.UnionNames"])
    assert union is not None and union.data == _record(UNION)
    classes = storages.unpacked(found["Fenolite.Altium.Classes6.Component"])
    assert classes is not None
    # the component classes that are no super class: the sheet class the writer made, and the authored one
    names = [storages.fields(record)["NAME"] for record in storages.records(classes.data)]
    assert names == ["two_layer", "Fenolite_Group"]
    row = next(row for row in conversion.report.rows if row.kind == storages.KIND)
    assert (row.source, row.written, row.lost) == (3, 2, 1)
    (reason,) = row.reasons
    assert reason.ids == ("PrimitiveGuids",) and reason.reason == storages.INDEX_BOUND_REASON


def test_a_union_name_survives_the_round_trip(tmp_path: Path) -> None:
    """Scenario "A union name survives the round trip": the document written back holds the source's
    ``UnionNames`` streams and the authored component class, once."""
    conversion = convert_project(read_source(_document(tmp_path)), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    streams = open_compound(document).as_dict()
    assert streams["UnionNames/Header"] == struct.pack("<I", 1)
    assert streams["UnionNames/Data"] == _record(UNION)
    classes = storages.records(streams["Classes6/Data"])
    assert classes.count(_record(GROUP)) == 1
    names = [storages.fields(record)["NAME"] for record in classes]
    assert names.count("two_layer") == 1  # the writer's own sheet class is not written twice
    assert struct.unpack_from("<I", streams["Classes6/Header"])[0] == len(classes)
    assert "PrimitiveGuids/Data" not in streams
