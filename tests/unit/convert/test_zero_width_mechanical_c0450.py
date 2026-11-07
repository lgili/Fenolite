# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lines and arcs of width 0 on a mechanical layer are written (change c0450, task 4.6).

Row ``-01`` of the corpus holds 68 tracks and 1 arc of width 0 on Mechanical 1, all of components
(``pcb-records.md``, "Width 0 on mechanical layers"). The source here is authored: the two-layer board
written as an Altium document, with a free track, a component track and a component arc of width 0 added
on Mechanical 1 (id 57).
"""

from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord, TrackRecord
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import Graphic

MIL = rec.UNITS_PER_MIL
MECH_1 = 57


def _document(tmp_path: Path) -> Path:
    design = two_layer()
    written = lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]
    streams = open_compound(written).as_dict()
    arc = rec.ArcGeometry(200 * MIL, 200 * MIL, 40 * MIL, 0.0, 90.0)
    added = {
        "Tracks6": [
            rec.track_record(MECH_1, (0, 0), (100 * MIL, 0), 0),
            rec.track_record(MECH_1, (0, 80 * MIL), (90 * MIL, 80 * MIL), 0, component=0),
        ],
        "Arcs6": [rec.arc_record(MECH_1, arc, 0, component=0)],
    }
    for storage, records in added.items():
        (count,) = struct.unpack_from("<I", streams.get(f"{storage}/Header", bytes(4)))
        streams[f"{storage}/Header"] = struct.pack("<I", count + len(records))
        streams[f"{storage}/Data"] = streams.get(f"{storage}/Data", b"") + b"".join(records)
    path = tmp_path / "altium" / f"{design.header.name}.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


def _zero_width(document: bytes) -> Counter[tuple[str, bool]]:
    """The tracks and arcs of width 0 on Mechanical 1, per kind and whether a component owns them."""
    doc = read_pcbdoc(document)
    found: Counter[tuple[str, bool]] = Counter()
    for kind, items in (("track", doc.tracks), ("arc", doc.arcs)):
        for item in items:
            if isinstance(item, TrackRecord | ArcRecord) and item.prefix.layer == MECH_1 and item.width == 0:
                found[(kind, item.prefix.component is not None)] += 1
    return found


def test_lines_of_width_0_on_mechanical_1_survive_kicad(tmp_path: Path) -> None:
    """Scenario "A line of width 0 on a mechanical layer": the document written back from KiCad holds
    the free track, the component track and the component arc of width 0 on Mechanical 1."""
    source = _document(tmp_path)
    before = _zero_width(source.read_bytes())
    assert before == {("track", False): 1, ("track", True): 1, ("arc", True): 1}
    conversion = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    assert _zero_width(document) == before


def _line(layer: str, kind: str = "line", width: int = 0) -> Graphic:
    points = (Point(0, 0), Point(1_000_000, 0))
    if kind == "arc":
        points = (Point(0, 0), Point(500_000, 500_000), Point(1_000_000, 0))
    if kind == "rect":
        points = (Point(0, 0), Point(1_000_000, 1_000_000))
    return Graphic(id=f"gra-{layer}-{kind}", kind=kind, layer=layer, points=points, width=width)


def test_width_0_is_refused_off_the_mechanical_layers() -> None:
    """Width 0 is accepted for a line or an arc on a mechanical layer only: a silkscreen line, a copper
    line, an outlined rectangle on a mechanical layer and a negative width keep the refusal."""
    layers = {"Mech.1": MECH_1, "Mech.20": rec.mechanical_id(20)}
    assert pcbdoc.graphic_problem(_line("Mech.1"), layers=layers) is None
    assert pcbdoc.graphic_problem(_line("Mech.20", "arc"), layers=layers) is None
    for graphic in (
        _line("F.SilkS"),
        _line("Mech.1", "rect"),
        _line("Mech.1", width=-1),
    ):
        assert "positive width" in (pcbdoc.graphic_problem(graphic, layers=layers) or "")
    copper = pcbdoc.graphic_problem(_line("F.Cu"), layers=layers, copper=("F.Cu",))
    assert "positive width" in (copper or "")
