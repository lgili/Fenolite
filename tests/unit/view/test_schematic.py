# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of an Altium schematic sheet (capability schematic-viewer, change c0177)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fenolite.backends.altium.adapter.connectivity import local_nets
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.read.sch import (
    Bus,
    BusEntry,
    Component,
    NetLabel,
    Pin,
    Port,
    PowerPort,
    SchDocument,
    SheetEntry,
    SheetSymbol,
    read_schematic,
)
from fenolite.view.schematic import FENOLITE_DRAWINGS, SCHEMA, build_schematic_scene, summary

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "altium"
TREE_IO = DATA / "tree" / "tree_io.SchDoc"
SAMPLE = DATA / "sample" / "altium_sample.SchDoc"
HEADER = "|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT={n}"


def _scene(path: Path) -> tuple[SchDocument, dict[str, Any]]:
    data = path.read_bytes()
    document = read_schematic(data, file=path.name)
    return document, build_schematic_scene(document, name=path.name, data=data)


def _authored(*records: str) -> tuple[SchDocument, dict[str, Any]]:
    sheet = "|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|SYSTEMFONT=1|SHEETSTYLE=0"
    lines = [HEADER.format(n=len(records) + 1), sheet, *records]
    data = ("\r\n".join(lines) + "\r\n").encode("latin-1")
    document = read_schematic(data, file="authored.SchDoc")
    return document, build_schematic_scene(document, name="authored.SchDoc", data=data)


def _kinds(scene: dict[str, Any]) -> list[str]:
    return [obj["k"] for obj in scene["objects"]]


def _top(document: SchDocument, cls: type) -> int:
    return sum(1 for record in document.of_type(cls) if record.owner is None)


def test_counts() -> None:
    """Scenario "Counts of an Altium sheet"."""
    document, scene = _scene(TREE_IO)
    kinds = _kinds(scene)
    assert scene["schema"] == SCHEMA and scene["kind"] == "schematic"
    assert len(scene["comps"]) == _top(document, Component) > 0
    assert kinds.count("wire") == len([w for w in document.wires() if w.points]) > 0
    assert kinds.count("bus") == _top(document, Bus) > 0
    assert kinds.count("entryline") == _top(document, BusEntry) > 0
    assert kinds.count("label") == _top(document, NetLabel) > 0
    assert kinds.count("power") == _top(document, PowerPort) > 0
    assert kinds.count("port") == _top(document, Port) > 0
    assert kinds.count("sheet") == _top(document, SheetSymbol) > 0
    assert kinds.count("entry") == len(document.of_type(SheetEntry)) > 0
    shown = [
        child
        for component in document.components()
        for child in document.shown_children(component)
        if isinstance(child, Pin) and not child.hidden
    ]
    assert kinds.count("pin") == len(shown) > 0
    meta = scene["meta"]
    assert meta["name"] == TREE_IO.name and len(meta["sha256"]) == 64 and meta["backend"] == "altium"
    assert meta["evidence"] == "INFERRED" and FENOLITE_DRAWINGS in meta["notes"]
    assert summary(scene)["counts"] == meta["counts"] and summary(scene)["kind"] == "schematic"
    json.dumps(scene)


def test_frame_is_the_a4_area() -> None:
    _, scene = _scene(TREE_IO)
    sheet = scene["sheet"]
    assert (sheet["w"], sheet["h"], sheet["style"]) == (292_100, 193_040, "A4")
    assert sheet["color"] == "#fffcf8" and sheet["grid"] == 2_540 and sheet["border"] is True
    x0, y0, x1, y1 = scene["bounds"]
    assert x0 <= 0 and y0 <= 0 and x1 >= sheet["w"] and y1 >= sheet["h"]


def test_pin_runs_from_its_body_to_its_hot_end() -> None:
    document, scene = _scene(SAMPLE)
    height = scene["sheet"]["h"]
    pin = next(
        child for c in document.components() for child in document.shown_children(c) if isinstance(child, Pin)
    )
    body = (round(pin.location[0].nm() / 1000), height - round(pin.location[1].nm() / 1000))
    end = (round(pin.hot_end[0].nm() / 1000), height - round(pin.hot_end[1].nm() / 1000))
    lines = [p["p"] for p in scene["prims"] if p["k"] == "l" and scene["objects"][p["o"]]["k"] == "pin"]
    assert [*body, *end] in lines


def test_wires_carry_their_nets() -> None:
    """Scenario "Wires carry their nets"."""
    document, scene = _scene(SAMPLE)
    groups = part_groups(document)
    expected = sorted(
        sorted(f"{groups[p.group].ref}-{p.designator}" for p in net.pins)
        for net in local_nets(document, groups)
    )
    found = sorted(sorted(net["pins"]) for net in scene["nets"] if net["pins"])
    assert found == expected
    wires = [obj for obj in scene["objects"] if obj["k"] == "wire"]
    assert wires and all(obj["net"] >= 0 for obj in wires)
    labels = [k for k, obj in enumerate(scene["objects"]) if obj["k"] == "label"]
    assert labels
    for index in labels:
        label = scene["objects"][index]
        name = next(value for key, value in label["info"] if key == "Net Label")
        assert scene["nets"][label["net"]]["name"] == name
        text = next(p for p in scene["prims"] if p["o"] == index and p["k"] == "t")
        under = {
            scene["objects"][p["o"]]["net"]
            for p in scene["prims"]
            if p["k"] == "l" and scene["objects"][p["o"]]["k"] == "wire" and _on(text["x"], text["y"], p["p"])
        }
        assert under == {label["net"]}, name


def _on(x: int, y: int, flat: list[int]) -> bool:
    """Whether (x, y) lies on the polyline ``flat`` (wires are horizontal or vertical)."""
    for i in range(0, len(flat) - 2, 2):
        x1, y1, x2, y2 = flat[i : i + 4]
        if min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2) and (x1 == x2 or y1 == y2):
            return True
    return False


GRAPHICS = (
    "|RECORD=13|OWNERPARTID=-1|LOCATION.X=100|LOCATION.Y=100|CORNER.X=200|CORNER.Y=100|COLOR=128|LINESTYLE=1",
    "|RECORD=6|OWNERPARTID=-1|LOCATIONCOUNT=3|X1=100|Y1=200|X2=150|Y2=250|X3=200|Y3=200|COLOR=128|ENDLINESHAPE=2",
    "|RECORD=7|OWNERPARTID=-1|LOCATIONCOUNT=3|X1=300|Y1=200|X2=350|Y2=250|X3=400|Y3=200|ISSOLID=T|AREACOLOR=255",
    "|RECORD=14|OWNERPARTID=-1|LOCATION.X=300|LOCATION.Y=100|CORNER.X=400|CORNER.Y=150|ISSOLID=T|AREACOLOR=11599871",
    "|RECORD=10|OWNERPARTID=-1|LOCATION.X=450|LOCATION.Y=100|CORNER.X=550|CORNER.Y=150|CORNERXRADIUS=5|CORNERYRADIUS=5",
    "|RECORD=8|OWNERPARTID=-1|LOCATION.X=600|LOCATION.Y=100|RADIUS=20|SECONDARYRADIUS=10",
    "|RECORD=12|OWNERPARTID=-1|LOCATION.X=650|LOCATION.Y=100|RADIUS=20|STARTANGLE=0.000|ENDANGLE=90.000",
    "|RECORD=11|OWNERPARTID=-1|LOCATION.X=700|LOCATION.Y=100|RADIUS=20|SECONDARYRADIUS=10|ENDANGLE=180.000",
    "|RECORD=9|OWNERPARTID=-1|LOCATION.X=750|LOCATION.Y=100|RADIUS=20|ENDANGLE=90.000|ISSOLID=T|AREACOLOR=255",
    "|RECORD=5|OWNERPARTID=-1|LOCATIONCOUNT=4|X1=100|Y1=300|X2=120|Y2=340|X3=160|Y3=340|X4=180|Y4=300",
    "|RECORD=4|OWNERPARTID=-1|LOCATION.X=100|LOCATION.Y=400|TEXT=A note|FONTID=1|JUSTIFICATION=4",
    "|RECORD=28|OWNERPARTID=-1|LOCATION.X=300|LOCATION.Y=400|CORNER.X=500|CORNER.Y=500|TEXT=One~1Two|FONTID=1|WORDWRAP=T",
)


def test_every_graphic_kind() -> None:
    """Scenario "Every graphic kind"."""
    _, scene = _authored(*GRAPHICS)
    kinds = [p["k"] for p in scene["prims"] if p.get("role") not in ("zone",)]
    for kind, count in (("l", 2), ("g", 1), ("r", 2), ("e", 1), ("a", 3), ("b", 1), ("x", 1)):
        assert kinds.count(kind) >= count, kind
    arcs = [p for p in scene["prims"] if p["k"] == "a"]
    assert [p.get("pie", False) for p in arcs] == [False, False, True]
    assert {(p["rx"], p["ry"]) for p in arcs} == {(5_080, 5_080), (5_080, 2_540)}
    round_rect = next(p for p in scene["prims"] if p["k"] == "r" and "rr" in p)
    assert round_rect["rr"] == [1_270, 1_270]
    frame = next(p for p in scene["prims"] if p["k"] == "x")
    assert frame["s"] == "One\nTwo" and frame["wrap"] is True
    note = next(p for p in scene["prims"] if p["k"] == "t" and p["s"] == "A note")
    assert (note["h"], note["v"]) == ("center", "center")
    line = next(p for p in scene["prims"] if p["k"] == "l" and p.get("d"))
    assert line["d"] == 1 and line["c"] == "#800000"


def test_a_parameter_that_names_another() -> None:
    """Scenario "A parameter that names another"."""
    records = (
        "|RECORD=1|OWNERPARTID=-1|LOCATION.X=200|LOCATION.Y=300|LIBREFERENCE=RES|PARTCOUNT=2|CURRENTPARTID=1",
        "|RECORD=14|OWNERINDEX=1|OWNERPARTID=1|LOCATION.X=200|LOCATION.Y=300|CORNER.X=260|CORNER.Y=320|ISSOLID=T",
        "|RECORD=34|OWNERINDEX=1|OWNERPARTID=-1|NAME=Designator|TEXT=R1|LOCATION.X=200|LOCATION.Y=330|FONTID=1",
        "|RECORD=41|OWNERINDEX=1|OWNERPARTID=-1|NAME=Comment|TEXT==Value|LOCATION.X=200|LOCATION.Y=280|FONTID=1",
        "|RECORD=41|OWNERINDEX=1|OWNERPARTID=-1|NAME=Value|TEXT=10k|ISHIDDEN=T|LOCATION.X=200|LOCATION.Y=270",
        "|RECORD=41|OWNERINDEX=1|OWNERPARTID=-1|NAME=Secret|TEXT=never shown|ISHIDDEN=T",
        "|RECORD=41|OWNERPARTID=-1|NAME=Title|TEXT=Main",
        "|RECORD=4|OWNERPARTID=-1|LOCATION.X=500|LOCATION.Y=500|TEXT==Title|FONTID=1",
        "|RECORD=4|OWNERPARTID=-1|LOCATION.X=500|LOCATION.Y=450|TEXT==Missing|FONTID=1",
    )
    _, scene = _authored(*records)
    texts = [p["s"] for p in scene["prims"] if p["k"] == "t"]
    assert "10k" in texts and "Main" in texts and "=Missing" in texts and "R1" in texts
    assert "never shown" not in texts and "Main" not in [t for t in texts if t.startswith("Title")]
    comp = scene["comps"][0]
    assert comp["ref"] == "R1" and comp["comment"] == "10k" and comp["params"]["Value"] == "10k"
    sheet = scene["sheet"]
    assert (sheet["w"], sheet["h"]) == (292_100, 193_040)
    assert any("no area colour" in note for note in scene["meta"]["notes"])
