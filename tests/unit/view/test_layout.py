# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout documents of the workbench (change c0245, decision 4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.view.layout import SCHEMA, LayoutError, parse_layout, read_layout


def _layout(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": SCHEMA,
        "workspace": "board",
        "docks": {
            "left": {"size": 260, "groups": [{"panels": ["projects"], "active": "projects", "size": 2}]},
            "right": {"size": 240, "groups": [{"panels": ["properties", "messages"], "active": "messages"}]},
            "bottom": {"size": 132, "groups": []},
        },
        "closed": ["notes"],
    }
    return base | over


def test_a_layout_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(_layout()), encoding="utf-8")
    layout = read_layout(path)
    assert layout["docks"]["right"]["groups"][0] == {
        "panels": ["properties", "messages"],
        "active": "messages",
        "size": 1,
        "collapsed": False,
    }
    assert layout["closed"] == ["notes"] and parse_layout(layout) == layout


def test_sizes_are_clamped() -> None:
    docks = _layout()["docks"]
    assert isinstance(docks, dict)
    docks["left"]["size"] = 5000
    docks["bottom"]["size"] = 1
    layout = parse_layout(_layout(docks=docks))
    assert layout["docks"]["left"]["size"] == 600 and layout["docks"]["bottom"]["size"] == 60


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"schema": "other"}, "schema"),
        ({"workspace": "kitchen"}, "workspace"),
        ({"docks": []}, "docks"),
        ({"closed": ["projects"]}, "closed"),
        ({"closed": ["no spaces"]}, "panel name"),
    ],
)
def test_bad_layouts_are_refused(over: dict[str, object], message: str) -> None:
    with pytest.raises(LayoutError, match=message):
        parse_layout(_layout(**over))


def test_a_panel_in_two_places_is_refused() -> None:
    docks = _layout()["docks"]
    assert isinstance(docks, dict)
    docks["bottom"]["groups"] = [{"panels": ["projects"]}]
    with pytest.raises(LayoutError, match="two places"):
        parse_layout(_layout(docks=docks))


def test_not_json(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(LayoutError, match="JSON"):
        read_layout(path)
