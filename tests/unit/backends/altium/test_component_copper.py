# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper of an Altium component keeps its net through KiCad (change c0454)."""

import dataclasses
from collections import Counter
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.design import Design

MM = 1_000_000
TOP = 1
NET = "VCC"
PATCH = (Point(-MM, -MM), Point(MM, -MM), Point(MM, MM), Point(-MM // 2, MM), Point(-MM, MM // 2))
"""A copper patch of the first footprint, in its frame: five vertices, so it stays a polygon."""


def _with_copper(*, netted: bool = True) -> Design:
    """The two-layer board whose first footprint holds a filled copper polygon on ``F.Cu``, of the net of its
    first pad when ``netted``."""
    design = two_layer()
    assert design.board is not None
    net_id = next(net.id for net in design.circuit.nets if net.name == NET) if netted else None
    first, *rest = design.board.footprints
    patch = Graphic(
        id="gra-patch", kind="polygon", layer="F.Cu", points=PATCH, width=0, filled=True, net_id=net_id
    )
    first = dataclasses.replace(first, graphics=(*first.graphics, patch))
    board = dataclasses.replace(design.board, footprints=(first, *rest))
    return dataclasses.replace(design, board=board)


def _copper(document: bytes) -> Counter[tuple[int, str | None, str]]:
    """The regions of the top layer by layer, net name and owner."""
    doc = read_pcbdoc(document)
    found: Counter[tuple[int, str | None, str]] = Counter()
    for region in doc.regions:
        if isinstance(region, RegionRecord) and region.prefix.layer == TOP:
            owner = "free" if region.prefix.component is None else "component"
            found[(region.prefix.layer, doc.net_name(region.prefix.net), owner)] += 1
    return found


def _altium(tmp_path: Path, design: Design) -> Path:
    written = lower.write_design(design, allow_lossy=True)
    path = tmp_path / "altium" / f"{design.header.name}.PcbDoc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(written.files[path.name])
    return path


def _net_of(design: Design, graphic: Graphic) -> str | None:
    return next((net.name for net in design.circuit.nets if net.id == graphic.net_id), None)


def _top_copper(design: Design) -> list[Graphic]:
    assert design.board is not None
    return [g for fp in design.board.footprints for g in fp.graphics if g.layer == "F.Cu"]


def test_the_writer_writes_netted_footprint_copper_with_its_net() -> None:
    """Scenario "A component region comes back with its net"."""
    written = lower.write_design(_with_copper(), allow_lossy=True)
    document = written.files[f"{two_layer().header.name}.PcbDoc"]
    assert _copper(document)[(TOP, NET, "component")] == 1


def test_netless_footprint_copper_stays_lost() -> None:
    """Copper of a footprint without net-tie groups and without a net is not written: on a pad it would
    short the pad. The write reports it lost under ``footprint-copper``."""
    written = lower.write_design(_with_copper(netted=False), allow_lossy=True)
    document = written.files[f"{two_layer().header.name}.PcbDoc"]
    assert not [key for key in _copper(document) if key[2] == "component"]
    (lossy,) = [i for i in written.issues if i.where == "footprint-copper"]
    assert lossy.code == "altium.not-lowered" and lossy.message.startswith("1 footprint-copper item(s)")
    assert lossy.message.endswith("it would be copper")


def test_import_gives_component_copper_its_net_id(tmp_path: Path) -> None:
    """Scenario "A component region of a net"."""
    back = AltiumBackend().read(_altium(tmp_path, _with_copper())).design
    (patch,) = _top_copper(back)
    assert patch.kind == "polygon" and patch.filled and _net_of(back, patch) == NET


def test_kicad_keeps_footprint_copper_net(tmp_path: Path) -> None:
    """Scenario "A footprint copper polygon round trip": the conversion to KiCad writes ``(net …)`` on the
    ``fp_poly``, and the board read back gives the footprint's graphic that net."""
    source = read_source(_altium(tmp_path, _with_copper()))
    conversion = convert_project(source, to="kicad", allow_lossy=True)
    pcb = parse(conversion.files[conversion.read_back].decode())
    nets = [
        poly.find("net")
        for fp in pcb.nodes("footprint")
        for poly in fp.nodes("fp_poly")
        if (layer := poly.find("layer")) is not None and layer.atoms()[0].value == "F.Cu"
    ]
    assert len(nets) == 1 and nets[0] is not None and nets[0].atoms()[0].value == NET
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    read = read_source(folder / conversion.read_back).design
    projected = fpitems.with_graphic_nets(fpitems.with_footprint_items(read).design)
    (patch,) = _top_copper(projected)
    assert _net_of(projected, patch) == NET
    # the round trip writes it back as a region of its component and net
    again = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in again.files.items() if name.endswith(".PcbDoc"))
    assert _copper(document)[(TOP, NET, "component")] == 1
    rows = {row.kind: row for row in again.report.rows}
    assert rows["footprint-copper"].lost == 0
