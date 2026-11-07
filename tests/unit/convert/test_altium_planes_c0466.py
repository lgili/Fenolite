# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Internal planes of an Altium document through KiCad and back (change c0466): the planes' rows are
``power`` rows named after the planes, the board property ``Fenolite.Altium.Planes`` carries their nets,
pull-backs and Split Plane polygons, and the conversion back writes them as planes again. The documents
here are authored for Fenolite with the writer; the public rows are read from the corpus cache."""

from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest
from _altium_board6 import at, bare_spec

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.libboard import MULTIPLE_NETS, StackSpec, valid_stack
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.kicad import boardcarrier
from fenolite.convert import altium_planes, convert_project
from fenolite.convert.sources import read_source
from fenolite.model.board import Track

LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
LEFT = (at(0, 0), at(25, 0), at(25, 30), at(0, 30))
RIGHT = (at(25, 0), at(50, 0), at(50, 30), at(25, 30))
PULLBACK = 762_000
"""30 mil: the first plane's pull-back, beside the 20 mil the writer writes by default."""


def _document(tmp_path: Path) -> Path:
    """A four-layer document with one track on each net. Internal Plane 1 is ``(Multiple Nets)``, named
    ``Ground Plane``, with a pull-back of 30 mil and splits on ``GND`` (left half) and ``VCC`` (right
    half); Internal Plane 2 is on ``VCC``, the board outline its one Split Plane polygon."""
    ids = rec.copper_stack(LAYERS, ("In1.Cu", "In2.Cu"))
    stack = StackSpec.default(ids, (MULTIPLE_NETS, "VCC"))
    stack = StackSpec(
        stack.copper, stack.thicknesses, stack.dielectrics, stack.plane_nets, pullbacks=(PULLBACK,)
    )
    spec = bare_spec(
        copper_layers=LAYERS,
        stack=stack,
        nets=("GND", "SIG", "VCC"),
        plane_splits={39: (("GND", LEFT), ("VCC", RIGHT))},
        copper_names={39: "Ground Plane"},
        tracks=tuple(
            Track(id=f"trk_{net}", start=at(5, y), end=at(20, y), width=254_000, layer="F.Cu", net_id=net)
            for net, y in (("GND", 5), ("SIG", 10), ("VCC", 15))
        ),
    )
    path = tmp_path / "source" / "planes.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(pcbdoc.write_pcbdoc(spec, filename=path.name))
    return path


def _fields(document: PcbDocument) -> dict[str, str]:
    return {key: value or "" for key, value in document.board.record.fields}


def _splits(document: PcbDocument) -> list[tuple[str, str, tuple[tuple[Fraction, Fraction], ...]]]:
    """The Split Plane polygons: layer, net name and vertices moved to the outline's low corner."""
    names = [net.name or "" for net in document.nets]
    corner = (min(v.x for v in document.board.outline), min(v.y for v in document.board.outline))
    return sorted(
        (
            polygon.layer or "",
            names[polygon.net] if polygon.net is not None else "",
            tuple((v.x - corner[0], v.y - corner[1]) for v in polygon.vertices),
        )
        for polygon in document.polygons
        if polygon.polygon_type == "Split Plane"
    )


def _chain(document: PcbDocument) -> list[tuple[int, str]]:
    names = {layer.id: layer.name for layer in document.board.layers}
    return [(layer, names.get(layer, "")) for layer in document.board.copper_chain]


def _pullbacks(fields: dict[str, str]) -> set[str]:
    return {value for key, value in fields.items() if key.endswith("PULLBACKDISTANCE")}


def _round_trip(tmp_path: Path, source: Path, edit: bool = False) -> tuple[str, PcbDocument, object]:
    """``source`` converted to KiCad and back: the KiCad board text, the written document and the report of
    the way back. ``edit`` makes ``In1.Cu`` a ``signal`` row before the way back."""
    kicad = convert_project(read_source(source), to="kicad", allow_lossy=True)
    folder = tmp_path / "kicad"
    folder.mkdir()
    for name, data in kicad.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    board = folder / kicad.read_back
    text = board.read_text("utf-8")
    if edit:
        text = re.sub(r'\(4 "In1\.Cu" power "[^"]*"\)', '(4 "In1.Cu" signal)', text)
        board.write_text(text, "utf-8")
    back = convert_project(read_source(board), to="altium", allow_lossy=True)
    (name, written), *_ = [(n, data) for n, data in back.files.items() if n.endswith(".PcbDoc")]
    path = tmp_path / "back" / Path(name).name
    path.parent.mkdir()
    path.write_bytes(written)
    return text, read_pcbdoc(written), back.report


def test_writer_writes_the_carried_planes(tmp_path: Path) -> None:
    """Scenario "A (Multiple Nets) plane with two splits": the plane's net and name, its two splits on their
    nets, the outline polygon of the other plane, and the 30 mil pull-back beside the default 20 mil."""
    document = read_pcbdoc(_document(tmp_path).read_bytes())
    fields = _fields(document)
    assert (fields["PLANE1NETNAME"], fields["PLANE2NETNAME"]) == (MULTIPLE_NETS, "VCC")
    assert (fields["LAYER39NAME"], fields["LAYER40NAME"]) == ("Ground Plane", "Internal Plane 2")
    assert [(layer, net) for layer, net, _ in _splits(document)] == [
        ("PLANE1", "GND"),
        ("PLANE1", "VCC"),
        ("PLANE2", "VCC"),
    ]
    assert _pullbacks(fields) == {"20mil", "30mil"}


def test_the_writer_refuses_a_multiple_nets_plane_without_splits(tmp_path: Path) -> None:
    ids = rec.copper_stack(LAYERS, ("In1.Cu",))
    spec = bare_spec(copper_layers=LAYERS, stack=StackSpec.default(ids, (MULTIPLE_NETS,)), nets=("GND",))
    with pytest.raises(ValueError, match="not a net of the document"):
        pcbdoc.write_pcbdoc(spec, filename="bare.PcbDoc")


def test_the_kicad_rows_are_power_rows_and_the_carrier_holds_the_planes(tmp_path: Path) -> None:
    """The plane rows are ``power`` rows named after the planes (S-2201), and the carrier holds each plane's
    row, net, pull-back and splits."""
    conversion = convert_project(read_source(_document(tmp_path)), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode("utf-8")
    assert '(4 "In1.Cu" power "Ground Plane")' in text
    assert '(6 "In2.Cu" power "Internal Plane 2")' in text
    carried = altium_planes.read_carrier(boardcarrier.carried(text)[altium_planes.PROPERTY])
    assert [(p.layer, p.net, p.pullback, [s.net for s in p.splits]) for p in carried.planes] == [
        ("In1.Cu", MULTIPLE_NETS, PULLBACK, ["GND", "VCC"]),
        ("In2.Cu", "VCC", 508_000, ["VCC"]),
    ]
    assert carried.corner is not None


def test_the_planes_come_back_from_kicad(tmp_path: Path) -> None:
    """Scenario "Split planes come back from KiCad", on the authored document: the chain, the names, the
    plane nets, the pull-backs and the Split Plane polygons with their nets and vertices."""
    source = _document(tmp_path)
    _, written, report = _round_trip(tmp_path, source)
    original = read_pcbdoc(source.read_bytes())
    assert (
        _chain(written)
        == _chain(original)
        == [
            (1, "Top Layer"),
            (39, "Ground Plane"),
            (40, "Internal Plane 2"),
            (32, "Bottom Layer"),
        ]
    )
    fields, before = _fields(written), _fields(original)
    assert [fields[f"PLANE{k}NETNAME"] for k in (1, 2)] == [before[f"PLANE{k}NETNAME"] for k in (1, 2)]
    assert _pullbacks(fields) == {"20mil", "30mil"}
    assert _splits(written) == _splits(original)
    assert report.row(altium_planes.KIND) is None  # type: ignore[attr-defined]


def test_a_plane_edited_away_in_kicad_is_lost(tmp_path: Path) -> None:
    """Scenario "A plane edited away in KiCad is lost": ``In1.Cu`` made a ``signal`` row is Mid-Layer 1, the
    other plane stays, and the report holds one ``plane`` loss with its reason."""
    text, written, report = _round_trip(tmp_path, _document(tmp_path), edit=True)
    assert '(4 "In1.Cu" signal)' in text
    assert [layer for layer, _ in _chain(written)] == [1, 2, 39, 32]
    assert _fields(written)["PLANE1NETNAME"] == "VCC"
    row = report.row(altium_planes.KIND)  # type: ignore[attr-defined]
    assert row is not None and row.lost == 1
    assert [r.reason for r in row.reasons] == [altium_planes.ROW_GONE]


def test_a_carrier_that_does_not_read_carries_nothing() -> None:
    assert altium_planes.read_carrier(None).planes == ()
    assert altium_planes.read_carrier(b"{not json").planes == ()
    assert altium_planes.read_carrier(b'{"schema": "other", "planes": []}').planes == ()
    broken = b'{"schema": "fenolite.altium-planes.v0", "planes": [{"layer": "In1.Cu", "net": "GND"}]}'
    assert altium_planes.read_carrier(broken).planes == ()


ROWS = {
    "altium-third-party-pcbdoc-01": [(39, "Ground Plane"), (40, "Power Plane")],
    "altium-third-party-pcbdoc-02": [(39, "GND"), (40, "POWER")],
}


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", sorted(ROWS))
def test_row_planes_survive_kicad(tmp_path: Path, row: str) -> None:
    """Scenarios "Split planes come back from KiCad" and "Single-net planes with splits come back": the
    public rows with planes (S-2250) come back with their chain, names, plane nets and Split Plane polygons,
    and the read-back holds as many ``track_width`` rules as the source (S-2251)."""
    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == row]
    source = require(item)
    _, written, _ = _round_trip(tmp_path, source)
    original = read_pcbdoc(source.read_bytes())
    assert [entry for entry in _chain(written) if entry[0] >= 39] == ROWS[row]
    fields, before = _fields(written), _fields(original)
    assert [fields[f"PLANE{k}NETNAME"] for k in (1, 2)] == [before[f"PLANE{k}NETNAME"] for k in (1, 2)]
    assert _splits(written) == _splits(original)
    (back,) = (tmp_path / "back").glob("*.PcbDoc")
    rules = [read_source(path).design.rules for path in (source, back)]
    widths = [Counter(r.kind for r in found.rules)["track_width"] for found in rules if found is not None]
    assert widths == [1, 1]


SIGNAL_ROWS = {
    "altium-third-party-pcbdoc-01": [
        (1, "Component Side"),
        (39, "Ground Plane"),
        (40, "Power Plane"),
        (32, "Solder Side"),
    ],
    "altium-third-party-pcbdoc-04": [
        (1, "Top Layer"),
        (2, "Internal Layer 1"),
        (3, "Internal Layer 2"),
        (32, "Bottom Layer"),
    ],
    "altium-third-party-pcbdoc-07": [(1, "Layer 1"), (3, "Layer 2"), (5, "Layer 3"), (32, "Layer 4")],
}
"""The written copper chain of each row (S-2254): its signal layers keep their names and their ids; row
``-07``'s inner layers are Mid-Layer 2 and 4 (ids 3 and 5), which the writer wrote as 2 and 3 before the
conversion carried them (``Fenolite.Altium.Planes``, ``signals``)."""


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", sorted(SIGNAL_ROWS))
def test_row_copper_names_survive_kicad(tmp_path: Path, row: str) -> None:
    """Scenario "Signal layer names come back from KiCad": a signal layer that the writer would name
    otherwise is a KiCad row with its Altium name as user name, and the written document names it so."""
    from _corpus import manifest_items, require

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == row]
    source = require(item)
    text, written, _ = _round_trip(tmp_path, source)
    original = read_pcbdoc(source.read_bytes())
    assert _chain(written) == _chain(original) == SIGNAL_ROWS[row]
    named = re.findall(r'\(\d+ "(?:F|B|In\d+)\.Cu" signal "([^"]*)"\)', text)
    assert named == [n for i, n in SIGNAL_ROWS[row] if i <= 32 and n not in ("Top Layer", "Bottom Layer")]


def test_a_kicad_rows_user_name_names_its_altium_layer(tmp_path: Path) -> None:
    """Scenario "A KiCad row's user name names its layer": ``F.Cu`` named ``Component Side`` is written so;
    ``B.Cu`` named after another Altium layer (``Top Overlay``) keeps ``Bottom Layer``."""
    from _convert import TWO_LAYER

    text = TWO_LAYER.read_text("utf-8")
    text = text.replace('(0 "F.Cu" signal)', '(0 "F.Cu" signal "Component Side")', 1)
    text = text.replace('(2 "B.Cu" signal)', '(2 "B.Cu" signal "Top Overlay")', 1)
    board = tmp_path / "board" / TWO_LAYER.name
    board.parent.mkdir()
    board.write_text(text, "utf-8")
    back = convert_project(read_source(board), to="altium", allow_lossy=True)
    (written,) = [data for name, data in back.files.items() if name.endswith(".PcbDoc")]
    assert _chain(read_pcbdoc(written)) == [(1, "Component Side"), (32, "Bottom Layer")]


def test_inner_signal_layers_keep_their_ids() -> None:
    """Scenario "Inner signal layers keep their ids": ids given to the inner signal layers are kept when
    they rise within 2 … 31; otherwise the k-th inner signal layer is Mid-Layer k."""
    assert rec.copper_stack(LAYERS, (), {"In1.Cu": 3, "In2.Cu": 5}) == (1, 3, 5, 32)
    assert valid_stack((1, 3, 5, 32)) and not valid_stack((1, 5, 3, 32))
    assert rec.copper_stack(LAYERS, ("In2.Cu",), {"In1.Cu": 4}) == (1, 4, 39, 32)
    for wrong in (
        {"In1.Cu": 5, "In2.Cu": 3},
        {"In1.Cu": 3},
        {"In1.Cu": 1, "In2.Cu": 5},
        {"In1.Cu": 3, "In2.Cu": 32},
    ):
        assert rec.copper_stack(LAYERS, (), wrong) == (1, 2, 3, 32)


FLOW_A_ROWS = ("altium-third-party-pcbdoc-01", "altium-third-party-pcbdoc-07")
"""The rows flow A is run on: ``-01``'s two split planes (the VM finding at 60687e26d: written as
Mid-Layers) and ``-07``'s inner signal layers 3 and 5."""


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", FLOW_A_ROWS)
def test_flow_a_keeps_planes_names_and_ids(tmp_path: Path, row: str) -> None:
    """Scenario "Planes, names and ids survive flow A" (``import --to python``, ``build``, ``convert --to
    altium``): the build types the rows the script's ``Fenolite.Altium.Planes`` names as planes ``power``
    again, and the way back restores the copper names the build did not write, so the written chain, the
    plane nets and the Split Plane polygons are the source's."""
    from _corpus import manifest_items, require

    from fenolite.api import run

    stamp = "2026-11-07T00:00:00Z"

    def go(*args: str) -> None:
        planned = run(*args, "--dry-run", cwd=tmp_path, timestamp=stamp)
        assert planned.exit_code == 0, planned.error
        done = run(
            *args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=tmp_path, timestamp=stamp
        )
        assert done.exit_code == 0, done.error

    (item,) = [i for i in manifest_items("altium-pcbdoc") if i.id == row]
    source = require(item)
    go("import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
       "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    go("build", str(tmp_path / "py" / "design.py"), "--out", "b")
    (built,) = (tmp_path / "b").glob("*.kicad_pcb")
    go("convert", str(built), "--to", "altium", "--out", "alt", "--allow-lossy")
    (path,) = (tmp_path / "alt").glob("*.PcbDoc")
    written, original = read_pcbdoc(path.read_bytes()), read_pcbdoc(source.read_bytes())
    assert _chain(written) == _chain(original)
    planes = [k - 38 for k, _ in _chain(original) if k >= 39]
    fields, before = _fields(written), _fields(original)
    assert [fields[f"PLANE{k}NETNAME"] for k in planes] == [before[f"PLANE{k}NETNAME"] for k in planes]
    assert _splits(written) == _splits(original)
