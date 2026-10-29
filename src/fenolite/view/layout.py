# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout documents of the viewer's workbench (change c0245, decision 4; board-viewer, "Docked panels and
layouts").

A layout is canonical JSON of the schema ``fenolite.view_layout.v0``: for one workspace, the three docks
(``left``, ``right``, ``bottom``), each with its size in CSS pixels and its groups of panels, and the panels
that are closed. The page keeps one per workspace in the browser and saves it as a file; ``fenolite view
--layout FILE`` hands such a file to the page. This module checks a file before the page sees it; the page
drops panel names it does not know, so a layout written by a newer page still opens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

SCHEMA = "fenolite.view_layout.v0"
WORKSPACES = ("board", "sheet", "library", "drawing", "table", "roles")
DOCKS = ("left", "right", "bottom")
SIZE = {"left": (160, 600), "right": (160, 600), "bottom": (60, 600)}
"""The smallest and largest size of each dock, in CSS pixels."""
NAME_LIMIT = 32


class LayoutError(ValueError):
    """A file that is not a layout document; the message names the first problem."""


def _panel_name(value: object, where: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > NAME_LIMIT
        or not value.replace("-", "").isalnum()
    ):
        raise LayoutError(f"{where}: a panel name is a short word of letters, digits and dashes")
    return value


def parse_layout(raw: object) -> dict[str, Any]:
    """The layout ``raw`` (decoded JSON) holds, checked: its schema, its workspace, its docks and groups.
    Sizes are clamped to their range. Raises ``LayoutError``."""
    if not isinstance(raw, dict):
        raise LayoutError("a layout is a JSON object")
    data = cast("dict[str, Any]", raw)
    if data.get("schema") != SCHEMA:
        raise LayoutError(f"schema: expected {SCHEMA!r}")
    workspace = data.get("workspace")
    if workspace not in WORKSPACES:
        raise LayoutError(f"workspace: one of {', '.join(WORKSPACES)}")
    docks = data.get("docks")
    if not isinstance(docks, dict):
        raise LayoutError("docks: an object with left, right and bottom")
    seen: set[str] = set()
    out_docks: dict[str, Any] = {}
    for name in DOCKS:
        dock = cast("dict[str, Any]", docks).get(name, {"size": SIZE[name][0], "groups": []})
        if not isinstance(dock, dict):
            raise LayoutError(f"docks.{name}: an object")
        dock = cast("dict[str, Any]", dock)
        size = dock.get("size")
        if isinstance(size, bool) or not isinstance(size, int | float):
            raise LayoutError(f"docks.{name}.size: a number of CSS pixels")
        low, high = SIZE[name]
        groups_in = dock.get("groups", [])
        if not isinstance(groups_in, list):
            raise LayoutError(f"docks.{name}.groups: a list")
        groups: list[dict[str, Any]] = []
        for index, group in enumerate(cast("list[object]", groups_in)):
            where = f"docks.{name}.groups[{index}]"
            if not isinstance(group, dict) or not isinstance(
                cast("dict[str, Any]", group).get("panels"), list
            ):
                raise LayoutError(f"{where}: an object with a list of panels")
            group = cast("dict[str, Any]", group)
            panels = [_panel_name(p, where) for p in cast("list[object]", group["panels"])]
            if not panels:
                raise LayoutError(f"{where}: at least one panel")
            for panel in panels:
                if panel in seen:
                    raise LayoutError(f"{where}: the panel {panel!r} is in two places")
                seen.add(panel)
            active = group.get("active", panels[0])
            if active not in panels:
                raise LayoutError(f"{where}.active: one of its panels")
            weight = group.get("size", 1)
            if isinstance(weight, bool) or not isinstance(weight, int | float) or not 0 < weight <= 100:
                raise LayoutError(f"{where}.size: a share above 0 and at most 100")
            groups.append(
                {
                    "panels": panels,
                    "active": active,
                    "size": weight,
                    "collapsed": bool(group.get("collapsed")),
                }
            )
        out_docks[name] = {"size": int(min(high, max(low, size))), "groups": groups}
    closed_in = data.get("closed", [])
    if not isinstance(closed_in, list):
        raise LayoutError("closed: a list of panel names")
    closed = [_panel_name(p, "closed") for p in cast("list[object]", closed_in)]
    if any(p in seen for p in closed):
        raise LayoutError("closed: a panel that is also in a dock")
    return {"schema": SCHEMA, "workspace": workspace, "docks": out_docks, "closed": closed}


def read_layout(path: Path) -> dict[str, Any]:
    """The layout document of ``path``. Raises ``LayoutError`` (also for a file that is not JSON)."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LayoutError(f"not a readable JSON file: {exc}") from exc
    return parse_layout(raw)


__all__ = ["SCHEMA", "LayoutError", "parse_layout", "read_layout"]
