# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Classes of every kind, xSignals and differential pairs through KiCad, and internal planes counted lost on
the way to KiCad (change c0461). Every record here is authored for Fenolite, in the form of the public rows
(``pcb-records.md``, "Storages through KiCad")."""

from __future__ import annotations

import struct
from pathlib import Path

from _altium_board6 import bare_spec
from _convert import two_layer

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.libboard import StackSpec
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.convert import altium_storages as storages
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import PLANE_KIND, PLANE_REASON
from fenolite.convert.report import ConversionReport
from fenolite.convert.sources import read_source

HEAD = b"|SELECTION=FALSE|LAYER=MULTILAYER|LOCKED=FALSE|POLYGONOUTLINE=FALSE|USERROUTED=TRUE|UNIONINDEX=0"
GROUP = HEAD + b"|NAME=Fen_Group|KIND=1|SUPERCLASS=FALSE|M0=R1|M1=D1|SELECTED=FALSE|UNIQUEID=AAAAAAAA\x00"
CELLS = HEAD + b"|NAME=Cell|KIND=5|SUPERCLASS=FALSE|M0=Fen_Group|M1=Gone|SELECTED=FALSE|UNIQUEID=BBBBBBBB\x00"
PAIRS = HEAD + b"|NAME=Fen_Pairs|KIND=6|SUPERCLASS=FALSE|M0=Fen_LED|SELECTED=FALSE|UNIQUEID=CCCCCCCC\x00"
CELL_NETS = HEAD + b"|NAME=CELL|KIND=0|SUPERCLASS=FALSE|M0=GND|SELECTED=FALSE|UNIQUEID=DDDDDDDD\x00"
SIGNALS = HEAD + b"|NAME=Fen_Signals|KIND=10|SUPERCLASS=FALSE|M0=LED_PP1|SELECTED=FALSE|UNIQUEID=EEEEEEEE\x00"
PAIR_HEAD = b"|SELECTION=FALSE|LAYER=TOP|LOCKED=FALSE|POSITIVENETNAME=LED_A"
PAIR = PAIR_HEAD + b"|NEGATIVENETNAME=GND|NAME=Fen_LED\x00"
LOST_PAIR = PAIR_HEAD + b"|NEGATIVENETNAME=NONE|NAME=Fen_X\x00"
XSIGNALS = (
    b"|PINPAIRCOUNT=1|PINPAIRNAME0=LED_PP1|PINPAIRCOLOR0=7709086|PINPAIROVERRIDECOLORFORDRAW0=FALSE"
    b"|PINPAIRPINS0=R1-1,D1-2,U9-1"
)
"""Authored records: a component class, a class of component classes whose second member names nothing, a
class of differential pairs, a net class whose name differs from ``Cell`` in case alone, an xSignal class,
a differential pair of two nets of the board, one of a net the board does not hold, and one xSignal (its
third pin names no part of the board: an Altium-saved document holds such pins, row ``-04``)."""


def _record(text: bytes) -> bytes:
    return struct.pack("<I", len(text)) + text


def _append(streams: dict[str, bytes], name: str, *records: bytes) -> None:
    (count,) = struct.unpack_from("<I", streams.get(f"{name}/Header", b"\0\0\0\0"))
    streams[f"{name}/Header"] = struct.pack("<I", count + len(records))
    streams[f"{name}/Data"] = streams.get(f"{name}/Data", b"") + b"".join(_record(r) for r in records)


def _document(tmp_path: Path) -> Path:
    """The two-layer board written as an Altium document, with the authored records of the module."""
    design = two_layer()
    written = lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]
    streams = open_compound(written).as_dict()
    _append(streams, "Classes6", CELL_NETS, GROUP, CELLS, PAIRS)
    _append(streams, "SignalClasses", SIGNALS)
    _append(streams, "DifferentialPairs6", PAIR, LOST_PAIR)
    board = streams["Board6/Data"]
    text = board[4:].replace(b"|PINPAIRCOUNT=0", XSIGNALS)
    streams["Board6/Data"] = struct.pack("<I", len(text)) + text
    path = tmp_path / "altium" / f"{design.header.name}.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


def _round_trip(tmp_path: Path, source: Path) -> tuple[dict[str, bytes], ConversionReport, ConversionReport]:
    """The streams of the document written back, the report to KiCad and the report back."""
    there = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    for name, data in there.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / there.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    return open_compound(document).as_dict(), there.report, back.report


def _names(data: bytes) -> list[tuple[str, str]]:
    return [(f.get("KIND", ""), f.get("NAME", "")) for f in map(storages.fields, storages.records(data))]


def test_every_class_kind_survives_the_round_trip(tmp_path: Path) -> None:
    """Scenario "Classes of every kind survive the round trip": each authored record comes back byte for
    byte, ``Cell`` beside the net class ``CELL``, a member that names nothing included; the writer's own
    sheet class and its empty ``Default`` net class are not written beside them."""
    streams, _, back = _round_trip(tmp_path, _document(tmp_path))
    classes = storages.records(streams["Classes6/Data"])
    for record in (GROUP, CELLS, PAIRS):
        assert classes.count(_record(record)) == 1
    names = _names(streams["Classes6/Data"])
    assert ("0", "CELL") in names and ("5", "Cell") in names
    assert ("0", "Default") not in names
    assert [name for kind, name in names if kind == "1"] == ["two_layer", "Fen_Group"]  # the source's own
    assert struct.unpack_from("<I", streams["Classes6/Header"])[0] == len(classes)
    signals = storages.records(streams["SignalClasses/Data"])
    assert [storages.fields(r)["NAME"] for r in signals] == ["All xSignals", "Fen_Signals"]
    assert signals[1] == _record(SIGNALS)
    assert struct.unpack_from("<I", streams["SignalClasses/Header"])[0] == 2
    assert storages.pin_pair_fields(streams["Board6/Data"]) == [
        ("PINPAIRCOUNT", "1"),
        ("PINPAIRNAME0", "LED_PP1"),
        ("PINPAIRCOLOR0", "7709086"),
        ("PINPAIROVERRIDECOLORFORDRAW0", "FALSE"),
        ("PINPAIRPINS0", "R1-1,D1-2,U9-1"),
    ]
    assert storages.records(streams["DifferentialPairs6/Data"]) == [_record(PAIR)]
    row = back.row(storages.KIND)
    assert row is not None and row.lost == 1
    (reason,) = row.reasons
    assert (reason.reason, reason.ids) == (storages.PAIR_REASON, ("DifferentialPairs6:Fen_X",))


def test_the_kicad_board_carries_the_classes(tmp_path: Path) -> None:
    """The conversion to KiCad carries the classes that are no net class, the xSignal classes, the
    xSignals and the differential pairs."""
    there = convert_project(read_source(_document(tmp_path)), to="kicad", allow_lossy=True)
    from fenolite.backends.kicad import boardcarrier

    found = storages.from_carried(boardcarrier.carried(there.files[there.read_back].decode()))
    assert {storages.KEPT_CLASSES, storages.KEPT_SIGNAL_CLASSES, storages.PIN_PAIRS} <= set(found)
    assert storages.DIFFERENTIAL_PAIRS in found
    kept = _names(found[storages.KEPT_CLASSES].data)
    assert ("0", "CELL") not in kept  # the model holds the net classes
    assert {("1", "Fen_Group"), ("5", "Cell"), ("6", "Fen_Pairs")} <= set(kept)


def test_c0450_carrier_reads_as_the_kept_classes() -> None:
    """A KiCad board that c0450 wrote holds ``Classes6.Component``: it reads as ``Classes6.Kept``."""
    storage = storages.Storage(struct.pack("<I", 1), _record(GROUP))
    found = storages.from_carried({"Fenolite.Altium.Classes6.Component": storages.packed(storage)})
    assert found == {storages.KEPT_CLASSES: storage}


def test_an_internal_plane_is_counted_lost_on_the_way_to_kicad(tmp_path: Path) -> None:
    """Scenario "A split plane is counted lost": the plane of a four-layer document, its one Split Plane
    polygon on ``GND``, is a ``plane`` loss of the conversion to KiCad, a refused kind."""
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    stack = StackSpec.default(rec.copper_stack(layers, ("In1.Cu",)), ("GND",))
    spec = bare_spec(copper_layers=layers, stack=stack, nets=("GND", "SIG"))
    path = tmp_path / "plane.PcbDoc"
    path.write_bytes(pcbdoc.write_pcbdoc(spec, filename=path.name))
    report = convert_project(read_source(path), to="kicad", allow_lossy=True).report
    row = report.row(PLANE_KIND)
    assert row is not None and (row.source, row.lost) == (1, 1)
    (reason,) = row.reasons
    assert reason.reason == PLANE_REASON and reason.ids[0].endswith(":polygon-0")
    assert PLANE_KIND in report.refused


def test_no_plane_no_plane_row(tmp_path: Path) -> None:
    report = convert_project(read_source(_document(tmp_path)), to="kicad", allow_lossy=True).report
    assert report.row(PLANE_KIND) is None
