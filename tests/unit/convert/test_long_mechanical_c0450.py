# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tracks, arcs and fills on Mechanical 17 to 32 keep their layer through KiCad (change c0450, task 4.4).

The source is authored: the two-layer board written as an Altium document, with tracks, an arc and a fill
added in the long form that Altium saves for Mechanical 17 to 32 (``pcb-records.md``, "Long forms"): the
layer byte of Mechanical 16 (72) and the long layer id of the layer; some free, some of the first
component. Its ``Board6`` names Mechanical 20 and enables it and Mechanical 31.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord, FillRecord, TrackRecord
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source

MIL = rec.UNITS_PER_MIL
NAME = "Bottom Assembly"
"""An authored name of Mechanical 20."""


def _long(record: bytes, long: int) -> bytes:
    """``record`` (a short track or arc of the writer) in the long form: five zero bytes, the long layer id,
    the restriction byte 0 and three zero bytes after the short form."""
    body = record[5:] + bytes(5) + struct.pack("<IB", long, 0) + bytes(3)
    return record[:1] + struct.pack("<I", len(body)) + body


def _authored() -> dict[str, list[bytes]]:
    mech = {n: rec.LONG_MECHANICAL + n for n in (20, 21, 31)}
    tracks = [
        _long(rec.track_record(72, (0, 0), (100 * MIL, 0), 10 * MIL), mech[20]),
        _long(rec.track_record(72, (0, 50 * MIL), (100 * MIL, 50 * MIL), 10 * MIL), mech[20]),
        _long(rec.track_record(72, (0, 80 * MIL), (90 * MIL, 80 * MIL), 8 * MIL, component=0), mech[31]),
    ]
    arc = rec.ArcGeometry(200 * MIL, 200 * MIL, 40 * MIL, 0.0, 90.0)
    arcs = [_long(rec.arc_record(72, arc, 10 * MIL), mech[21])]
    fills = [
        rec.fill_record(72, mech[20], (300 * MIL, 300 * MIL), (340 * MIL, 320 * MIL), 0.0),
        rec.fill_record(72, mech[20], (10 * MIL, 10 * MIL), (30 * MIL, 20 * MIL), 0.0, component=0),
    ]
    return {"Tracks6": tracks, "Arcs6": arcs, "Fills6": fills}


def _board6(text: str) -> str:
    """``Board6`` text with Mechanical 20 named and enabled and Mechanical 31 enabled (``LAYERV7_3`` and
    ``LAYERV7_14``, as Altium lists Mechanical 17 to 32)."""
    text = text.replace("|LAYERV7_3NAME=Mechanical 20|", f"|LAYERV7_3NAME={NAME}|")
    for index in (3, 14):
        text = text.replace(f"|LAYERV7_{index}MECHENABLED=FALSE|", f"|LAYERV7_{index}MECHENABLED=TRUE|")
    return text


def _document(tmp_path: Path) -> Path:
    design = two_layer()
    written = lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]
    streams = open_compound(written).as_dict()
    for storage, records in _authored().items():
        (count,) = struct.unpack_from("<I", streams.get(f"{storage}/Header", bytes(4)))
        streams[f"{storage}/Header"] = struct.pack("<I", count + len(records))
        streams[f"{storage}/Data"] = streams.get(f"{storage}/Data", b"") + b"".join(records)
    text = _board6(streams["Board6/Data"][4:].rstrip(b"\x00").decode("latin-1")).encode("latin-1") + b"\x00"
    streams["Board6/Data"] = struct.pack("<I", len(text)) + text
    path = tmp_path / "altium" / f"{design.header.name}.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


_AT = {TrackRecord: 41, ArcRecord: 52, FillRecord: 42}


def _layers(document: bytes) -> Counter[tuple[str, int, int, bool]]:
    """The records on mechanical layers above 12 per kind, layer byte, mechanical number (the long layer id
    of a long form, else the byte's) and whether a component owns them."""
    doc = read_pcbdoc(document)
    found: Counter[tuple[str, int, int, bool]] = Counter()
    for kind, items in (("track", doc.tracks), ("arc", doc.arcs), ("fill", doc.fills)):
        for item in items:
            if not isinstance(item, TrackRecord | ArcRecord | FillRecord) or item.prefix.layer < 69:
                continue
            body, at = item.raw[5:], _AT[type(item)]
            long = struct.unpack_from("<I", body, at)[0] if len(body) >= at + 4 else None
            number = long - rec.LONG_MECHANICAL if long and long >> 16 == 0x0102 else item.prefix.layer - 56
            found[(kind, item.prefix.layer, number, item.prefix.component is not None)] += 1
    return found


def _round_trip(tmp_path: Path) -> tuple[bytes, bytes]:
    source = _document(tmp_path)
    conversion = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    return source.read_bytes(), document


def _fields(document: bytes) -> dict[str, str]:
    text = open_compound(document).as_dict()["Board6/Data"][4:].rstrip(b"\x00").decode("latin-1")
    return dict(re.findall(r"\|([^=|\r]+)=([^|\r]*)", text))


def test_the_import_names_the_layer_of_the_long_id(tmp_path: Path) -> None:
    """The import puts a record with the byte of Mechanical 16 and the long id of Mechanical 20 on
    ``Mech.20``, as Altium shows it (S-1588), and names the layer after the board record."""
    design = read_source(_document(tmp_path)).design
    assert design.board is not None
    lines = Counter(g.layer for g in design.board.graphics if g.layer.startswith("Mech."))
    owned = Counter(g.layer for fp in design.board.footprints for g in fp.graphics if g.layer == "Mech.31")
    assert lines["Mech.20"] == 3 and lines["Mech.21"] == 1 and owned["Mech.31"] == 1
    assert "Mech.16" not in lines
    (layer,) = [layer for layer in design.board.layers if layer.name == "Mech.20"]
    assert dict(layer.ext["altium"].payload)["altium_name"] == NAME


def test_the_round_trip_keeps_the_long_ids(tmp_path: Path) -> None:
    """Scenario "Mechanical layers above 16 keep their long id": per kind, layer byte and long layer id,
    the document written back from KiCad holds as many records as the source; each keeps the byte 72."""
    source, document = _round_trip(tmp_path)
    before, after = _layers(source), _layers(document)
    assert before[("track", 72, 20, False)] == 2 and before[("fill", 72, 20, False)] == 1
    assert before[("fill", 72, 20, True)] == 1
    assert {k: v for k, v in after.items() if k[2] > 16} == {k: v for k, v in before.items() if k[2] > 16}


def test_a_component_fill_keeps_its_long_id(tmp_path: Path) -> None:
    """A filled rectangle of a component on Mechanical 20 that is not tagged as a fill is written as a fill
    record with its long id, since a region record names no layer above Mechanical 16 (row ``-08``: five
    component fills on Mechanical 20)."""
    design = read_source(_document(tmp_path)).design
    written = lower.write_design(design, allow_lossy=True, rewrite=True)
    document = next(data for name, data in written.files.items() if name.endswith(".PcbDoc"))
    assert _layers(document)[("fill", 72, 20, True)] == 1


def test_the_round_trip_keeps_the_names_and_flags(tmp_path: Path) -> None:
    """The name and the enabled flags of Mechanical 17 to 32 come back: Mechanical 20 named and enabled,
    Mechanical 21 and 31 enabled (something lies on them), and both in the mechanical layer set."""
    _source, document = _round_trip(tmp_path)
    fields = _fields(document)
    assert fields["LAYERV7_3NAME"] == NAME
    assert [fields[f"LAYERV7_{i}MECHENABLED"] for i in (3, 4, 14)] == ["TRUE"] * 3
    assert fields["LAYERV7_0MECHENABLED"] == "FALSE"
    layers = fields["LAYERSET5LAYERS"].split(",")
    assert {"Mechanical20", "Mechanical21", "Mechanical31"} <= set(layers)


def test_the_writer_writes_the_long_form() -> None:
    """A track of the writer on a long id is the 49-byte form with the byte 72 and that long id."""
    record = rec.track_record(rec.mechanical_id(24), (0, 0), (MIL, 0), MIL)
    body = record[5:]
    assert len(body) == 49 and body[0] == 72
    assert struct.unpack_from("<I", body, 41)[0] == rec.LONG_MECHANICAL + 24
    assert rec.mechanical_number(rec.mechanical_id(24)) == 24 and rec.mechanical_id(16) == 72
