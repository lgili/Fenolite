# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a Draftsman document (capability draftsman-viewer, scenario "A drawing of a panel"; change
c0180, task 2.1; ``H-A-DWF-GEOM``).

The drawings here are built in the test from the reader's dataclasses, with values of this test.
"""

from __future__ import annotations

from pathlib import Path

from _draftsman import DOCUMENT, stored

from fenolite.backends.altium.read.dwfdraw import BoardCopy, Drawing, Item, Page, Part, Stadium, Style
from fenolite.view.drawing import (
    PANEL_NOTE,
    UM,
    drawing_scene,
    fill_parameters,
    holds_panel,
    sheet_scene,
    stadium,
    summary,
)

HEIGHT = 400.0
OUTLINE = ((0.0, 0.0), (96.0, 0.0), (96.0, 48.0), (0.0, 48.0))


def view(side: str, location: tuple[float, float], scale: float = 2.0) -> Item:
    return Item(
        "BoardAssemblyViewData",
        {
            "id": side,
            "location": location,
            "scale": scale,
            "side": side,
            "rotation": "Ccw0",
            "title": "=ViewSide",
            "show_title": True,
            "title_font": "",
            "title_color": "#000000",
            "layer": -1,
            "line": "l1",
            "component_line": "",
            "size": (0.0, 0.0),
        },
    )


def drawing(*items: Item, panel: bool = False) -> Drawing:
    part = Part(
        "R1", "10k", "Top", (((1.0, 1.0), (9.0, 1.0)),), ((5.0, 5.0),), (1.0, 1.0, 8.0, 8.0), (), 10.0, -2.0
    )
    flat = Part("R2", "10k", "Bottom", (), (), (20.0, 30.0, 4.0, 4.0))
    frames = {"Back": (0.0, 20.0, 96.0, 46.0), "Right": (96.0, 20.0, 48.0, 46.0)}
    board = BoardCopy(OUTLINE, (), (0.0, 0.0, 96.0, 48.0), 6.0, (), (), (part, flat), (), frames)
    page = Page(600.0, HEIGHT, (10.0, 10.0, 10.0, 10.0), (False, 0, 0), items)
    return Drawing(
        (page,),
        lines={"l1": Style(color="#123456", thickness=1.0)},
        board=board,
        is_panel=panel,
        parameters={"revision": "B"},
    )


def scene_of(*items: Item, panel: bool = False) -> dict:
    found = drawing(*items, panel=panel)
    return sheet_scene(found, found.pages[0], name="test")


def test_top_view_lower_left_corner() -> None:
    """With the sheet's Y up, the board's lower-left corner lands at the view's location, scaled."""
    scene = scene_of(view("Top", (100.0, 50.0)))
    outline = scene["prims"][0]
    assert outline["k"] == "l" and outline["c"] == "#123456"
    assert outline["p"][:2] == [round(100 * UM), round((HEIGHT - 50) * UM)]
    assert outline["p"][2:4] == [round((100 + 96 * 2) * UM), round((HEIGHT - 50) * UM)]
    (comp,) = scene["comps"]
    assert comp["ref"] == "R1"
    title = [p for p in scene["prims"] if p["k"] == "t" and p["s"] == "Top"]
    assert title and title[0]["y"] > round((HEIGHT - 50) * UM)  # below the view


def test_bottom_view_is_mirrored() -> None:
    scene = scene_of(view("Bottom", (100.0, 50.0), 1.0))
    outline = scene["prims"][0]
    assert outline["p"][:2] == [round((100 + 96) * UM), round((HEIGHT - 50) * UM)]
    assert [c["ref"] for c in scene["comps"]] == ["R2"]  # R1 is on top


def test_text_in_its_box() -> None:
    text = Item(
        "Text",
        {
            "id": "t",
            "rect": (10.0, 20.0, 100.0, 12.0),
            "rotation": "Ccw0",
            "text": "Rev =Revision",
            "font": "",
            "color": "#000000",
            "h": "Left",
            "v": "Top",
        },
    )
    (prim,) = [p for p in scene_of(text)["prims"] if p["k"] == "t"]
    assert prim["s"] == "Rev B" and prim["y"] == round((HEIGHT - 32) * UM) and prim["v"] == "top"
    assert fill_parameters("=Unknown and =Revision", {"revision": "B"}) == "=Unknown and B"


def test_panel_note() -> None:
    """Scenario "A drawing of a panel"."""
    assert PANEL_NOTE in scene_of(panel=True)["meta"]["notes"]
    assert PANEL_NOTE not in scene_of()["meta"]["notes"]


def test_stadium() -> None:
    track = stadium(Stadium((0.0, 0.0), 10.0, 2.0, 1.0, (1.0, 0.0)))
    xs, ys = [p[0] for p in track], [p[1] for p in track]
    assert round(min(xs), 6) == -5 and round(max(xs), 6) == 5 and round(max(ys), 6) == 1
    square = stadium(Stadium((0.0, 0.0), 4.0, 4.0, 0.0, (0.0, 1.0)))
    assert len(square) == 4


def test_scene_of_a_file(tmp_path: Path) -> None:
    path = tmp_path / "authored.PCBDwf"
    path.write_bytes(stored(DOCUMENT))
    scene = drawing_scene(path)
    assert scene["kind"] == "library" and scene["lib"] == "drawing" and len(scene["items"]) == 1
    found = summary(scene)
    assert found["kind"] == "drawing" and found["counts"]["sheets"] == 1 and not found["panel"]
    assert not holds_panel(path)


def _box(scene: dict, designator: str) -> list[int]:
    (found,) = [o for o in scene["objects"] if o["k"] == "comp" and ["Designator", designator] in o["info"]]
    return found["b"]


def test_side_view() -> None:
    """Change c0190: a Front view draws the board's section and each part's box from the side, in the frame
    the document stores; the board's lower face lies the frame's Y above the view's location."""
    scene = scene_of(view("Front", (100.0, 50.0), 1.0))
    section = next(p for p in scene["prims"] if p["k"] == "g" and p["f"] is not None)
    ys = sorted(set(section["p"][1::2]))
    assert ys == [round((HEIGHT - 76) * UM), round((HEIGHT - 70) * UM)]  # z 0 and -6: 50 + 20 + 6 + z
    x0, y0, x1, y1 = _box(scene, "R1")  # from 2 below the upper face to 8 above it, x 1 to 9
    assert (x0, x1) == (round(101 * UM), round(109 * UM))
    assert (y0, y1) == (round((HEIGHT - 84) * UM), round((HEIGHT - 74) * UM))
    x0, y0, x1, y1 = _box(scene, "R2")  # a bottom part without a height: 1 mm under the lower face
    assert (y0, y1) == (round((HEIGHT - 70) * UM), round((HEIGHT - 70 + 96 / 25.4) * UM))
    assert any("without a height" in note for note in scene["meta"]["notes"])
    right = scene_of(view("Right", (300.0, 50.0), 1.0))
    x0, _y0, x1, _y1 = _box(right, "R1")  # seen from the right, along the board's Y
    assert (x0, x1) == (round(301 * UM), round(309 * UM))


def test_dimension_on_a_side_view() -> None:
    dimension = Item(
        "LinearDimension",
        {
            "id": "d",
            "a": (0.0, 0.0),
            "b": (0.0, 0.0),
            "ref": (0.0, -10.0),
            "line": "l1",
            "font": "",
            "color": "#ff0000",
            "override": None,
            "prefix": "",
            "suffix": "",
            "direction": (0.0, 1.0),
            "target": "Front",
            "units": "Metric",
            "snaps": ("GI|BoardOutline|Line: 0, -6, 96, -6",) * 2,
            "offsets": ((0.0, 0.0), (0.0, 0.0)),
        },
    )
    scene = scene_of(view("Front", (100.0, 50.0), 1.0), dimension)
    (found,) = [o for o in scene["objects"] if o["k"] == "dimension"]
    assert found["info"][0] == ["Dimension", "25.40mm"]  # the board's 96 units


def test_callout_names_its_note_element() -> None:
    """Change c0190: a callout's tag is the number of the note element it names, in that element's border."""
    note = Item(
        "Note",
        {
            "id": "n",
            "start": (300.0, 300.0),
            "width": 200.0,
            "title": "NOTES",
            "title_visible": True,
            "font": "",
            "title_font": "",
            "color": "#000000",
            "spacing": 2.0,
            "elements": [("FIRST", "."), ("SECOND", ".")],
            "element_ids": [("e1", "None"), ("e2", "Square")],
        },
    )
    callout = Item(
        "Callout",
        {
            "id": "c",
            "target": (100.0, 100.0),
            "leader": (-30.0, -30.0),
            "elbow": 8.0,
            "elbow_side": "Left",
            "font": "",
            "color": "#c00000",
            "line": "",
            "border": "",
            "source": "NoteItem",
            "note_element": "e2",
            "custom": "?",
            "prefix": "",
        },
    )
    scene = scene_of(note, callout)
    (found,) = [o for o in scene["objects"] if o["k"] == "callout"]
    assert found["info"][0] == ["Callout", "2"]
    tag = [p for p in scene["prims"] if p["k"] == "t" and p["s"] == "2" and p["c"] == "#c00000"]
    assert tag and any(p["k"] == "r" for p in scene["prims"])  # the square border of element 2
    leader = next(p for p in scene["prims"] if p["k"] == "l" and len(p["p"]) == 6)
    assert leader["p"][-2:] == [round(100 * UM), round((HEIGHT - 100) * UM)]  # it ends at the target
