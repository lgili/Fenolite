# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The colours of the viewer per native tool (capability native-themes, change c0178).

Two palettes, ``KICAD`` and ``ALTIUM``, are authored for Fenolite in the manner of each tool's look: a dark
board with red front and blue back copper, a cream schematic with green wires for KiCad; a black board for
Altium. No value is taken from either tool's built-in themes (``LEGAL.md``, block A). ``read_kicad_theme``
reads a KiCad colour theme file of the user (``docs/formats/kicad/color-theme.md``), so that a KiCad project
can be drawn in the user's own colours. Standard library only.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

from fenolite.core.errors import FormatError

Palette = dict[str, Any]

KICAD: Palette = {
    "name": "kicad",
    "board": {
        "background": "#04122b",
        "board": "#02091a",
        "layers": {
            "F.Cu": "#c43c3a",
            "B.Cu": "#4b7cc2",
            "F.SilkS": "#ece6a4",
            "B.SilkS": "#e0afa4",
            "F.Mask": "#cf62f2",
            "B.Mask": "#18ead8",
            "F.Paste": "#b39f9a",
            "B.Paste": "#16b9b9",
            "F.CrtYd": "#f02cd6",
            "B.CrtYd": "#30dff2",
            "F.Fab": "#acacac",
            "B.Fab": "#5d6184",
            "Edge.Cuts": "#cdcfc8",
            "Dwgs.User": "#bdbdbd",
            "Cmts.User": "#5b92d6",
            "Eco1.User": "#b2d27e",
            "Eco2.User": "#d6c25a",
            "View.Drill": "#d8d8d0",
        },
        "inner": ["#7fc37e", "#c97e36", "#52c4c6", "#d3638c", "#9a7fd0", "#c2c25a"],
        "opacity": {"F.Mask": 0.4, "B.Mask": 0.4, "F.Paste": 0.9, "B.Paste": 0.9},
    },
    "schematic": {
        "background": "#f4f2ea",
        "grid": "#b7b7b2",
        "worksheet": "#8a2a2a",
        "wire": "#1d8f30",
        "bus": "#2a46c4",
        "junction": "#1d8f30",
        "component_outline": "#8a1212",
        "component_body": "#fcfac4",
        "pin": "#8a1212",
        "pin_name": "#106b6b",
        "pin_number": "#a51818",
        "reference": "#127070",
        "value": "#127070",
        "fields": "#7d227d",
        "label_local": "#151515",
        "label_global": "#8a1a1a",
        "label_hier": "#76591a",
        "net_name": "#2e2e2e",
        "no_connect": "#22228c",
        "sheet": "#8a2222",
        "sheet_background": "#fcfaee",
        "sheet_name": "#127070",
        "sheet_filename": "#76591a",
        "sheet_label": "#76591a",
        "note": "#2a2ab8",
    },
}
"""Fenolite's palette in the manner of KiCad's default look."""

ALTIUM: Palette = {
    "name": "altium",
    "board": {
        "background": "#000000",
        "board": "#000000",
        "layers": {
            "F.Cu": "#e8302c",
            "B.Cu": "#2f52e8",
            "F.SilkS": "#f2ea30",
            "B.SilkS": "#9c9a26",
            "F.Mask": "#8a3c98",
            "B.Mask": "#c24cc2",
            "F.Paste": "#8c8c8c",
            "B.Paste": "#8a4e4e",
            "F.CrtYd": "#e0e0e0",
            "B.CrtYd": "#a0a0a0",
            "F.Fab": "#c8b896",
            "B.Fab": "#8896c8",
            "Edge.Cuts": "#d6c84a",
            "View.Drill": "#c8c8c8",
        },
        "inner": ["#c2a628", "#3ca86e", "#c27a2b", "#7f5fbf", "#5fa35f", "#bf5f9f"],
        "mechanical": "#c445c4",
        "opacity": {"F.Mask": 0.5, "B.Mask": 0.5},
    },
    "schematic": {"background": "#fffcf8", "workspace": "#4a4d52"},
}
"""Fenolite's palette in the manner of Altium Designer's look; an Altium sheet keeps its records' colours."""

PALETTES = {"kicad": KICAD, "altium": ALTIUM}
BOARD_KEYS: dict[str, str] = {
    "background": "background",
    "f_silks": "F.SilkS",
    "b_silks": "B.SilkS",
    "f_mask": "F.Mask",
    "b_mask": "B.Mask",
    "f_paste": "F.Paste",
    "b_paste": "B.Paste",
    "f_crtyd": "F.CrtYd",
    "b_crtyd": "B.CrtYd",
    "f_fab": "F.Fab",
    "b_fab": "B.Fab",
    "edge_cuts": "Edge.Cuts",
    "dwgs_user": "Dwgs.User",
    "cmts_user": "Cmts.User",
    "eco1_user": "Eco1.User",
    "eco2_user": "Eco2.User",
    "plated_hole": "View.Drill",
}
"""Keys of a theme file's ``board`` object and the palette slot each fills (``color-theme.md``)."""
_COLOR = re.compile(r"^\s*rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)\s*$")


def palette(name: str) -> Palette:
    """A copy of the palette ``name`` (``kicad`` or ``altium``)."""
    return copy.deepcopy(PALETTES[name])


def theme_for(backend: str) -> str:
    """The palette of a document read by ``backend``: ``altium`` for the Altium backend, else ``kicad``."""
    return "altium" if backend == "altium" else "kicad"


def _color(value: Any, where: str) -> tuple[str, float]:
    match = _COLOR.match(value) if isinstance(value, str) else None
    if match is None:
        raise FormatError(f"{where}: {value!r} is not an rgb() or rgba() colour", locator=where)
    r, g, b = (min(255, int(match.group(k))) for k in (1, 2, 3))
    alpha = float(match.group(4)) if match.group(4) else 1.0
    return f"#{r:02x}{g:02x}{b:02x}", max(0.0, min(alpha, 1.0))


def read_kicad_theme(path: Path) -> Palette:
    """The ``kicad`` palette with the colours of the KiCad colour theme file at ``path``. ``FormatError``
    when the file is not a JSON object of the documented form."""
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise FormatError(f"{path.name} is not a JSON file: {exc}", file=path.name) from exc
    if not isinstance(data, dict):
        raise FormatError(f"{path.name} is not a JSON object", file=path.name)
    doc = cast("dict[str, Any]", data)
    out = palette("kicad")
    meta: Any = doc.get("meta", {})
    name = cast("dict[str, Any]", meta).get("name") if isinstance(meta, dict) else None
    out["name"] = f"kicad:{path.name}"
    out["title"] = str(name or path.stem)
    board: Any = doc.get("board", {})
    schematic: Any = doc.get("schematic", {})
    if not isinstance(board, dict) or not isinstance(schematic, dict):
        raise FormatError(f"{path.name}: 'board' and 'schematic' are objects", file=path.name)
    board_keys = cast("dict[str, Any]", board)
    schematic_keys = cast("dict[str, Any]", schematic)
    layers: dict[str, str] = out["board"]["layers"]
    opacity: dict[str, float] = out["board"]["opacity"]
    for key, value in board_keys.items():
        if key == "copper" and isinstance(value, dict):
            for side, colour in cast("dict[str, Any]", value).items():
                hexa, alpha = _color(colour, f"board.copper.{side}")
                if side in ("f", "b"):
                    layer = "F.Cu" if side == "f" else "B.Cu"
                    layers[layer], opacity[layer] = hexa, alpha
                elif re.fullmatch(r"in\d+", side):
                    layers[f"In{side[2:]}.Cu"] = hexa
        elif key in BOARD_KEYS:
            hexa, alpha = _color(value, f"board.{key}")
            slot = BOARD_KEYS[key]
            if slot == "background":
                out["board"]["background"] = out["board"]["board"] = hexa
            else:
                layers[slot], opacity[slot] = hexa, alpha
    roles: dict[str, str] = out["schematic"]
    for key, value in schematic_keys.items():
        if key in roles or key in ("component_body", "sheet_background"):
            roles[key] = _color(value, f"schematic.{key}")[0]
    return out


def settings_folders() -> list[Path]:
    """The KiCad user settings folders that may hold a ``colors`` folder, majors 10 down to 6
    (``color-theme.md``)."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "kicad"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Preferences" / "kicad"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kicad"
    return [base / f"{major}.0" for major in range(10, 5, -1)]


def find_kicad_theme(name: str, cwd: Path) -> Path | None:
    """The theme file ``name``: a path to a file, else ``<name>.json`` in a ``colors`` folder of the user
    settings; ``None`` when there is none."""
    given = Path(name) if Path(name).is_absolute() else cwd / name
    if given.is_file():
        return given
    stem = name[:-5] if name.endswith(".json") else name
    for folder in settings_folders():
        found = folder / "colors" / f"{stem}.json"
        if found.is_file():
            return found
    return None


def apply_board_theme(scene: dict[str, Any], theme: Palette) -> dict[str, Any]:
    """Set the layer colours of a board scene from ``theme`` and record the theme in ``scene["theme"]``."""
    board = theme["board"]
    layers: dict[str, str] = board["layers"]
    inner: list[str] = board.get("inner", [])
    count = 0
    for layer in scene["layers"]:
        lid: str = layer["id"]
        if lid in layers:
            layer["color"] = layers[lid]
        elif layer["kind"] == "copper" and inner:
            layer["color"] = inner[count % len(inner)]
            count += 1
        elif layer["kind"] == "mechanical" and "mechanical" in board:
            layer["color"] = board["mechanical"]
        if lid in board.get("opacity", {}):
            layer["alpha"] = board["opacity"][lid]
    scene["theme"] = {"name": theme["name"], "background": board["background"], "board": board["board"]}
    scene["meta"]["notes"] = [*scene["meta"]["notes"], colour_note(theme)]
    return scene


def colour_note(theme: Palette) -> str:
    """The note that names the palette a scene is drawn in."""
    name: str = theme["name"]
    if name.startswith("kicad:"):
        return f"Colours: the KiCad theme {theme.get('title', name[6:])} ({name[6:]})."
    if name == "kicad":
        return "Colours: Fenolite's palette in the manner of KiCad; pass --theme to use your own KiCad theme."
    return "Colours: Fenolite's palette in the manner of Altium Designer."


__all__ = [
    "ALTIUM",
    "KICAD",
    "PALETTES",
    "Palette",
    "apply_board_theme",
    "colour_note",
    "find_kicad_theme",
    "palette",
    "read_kicad_theme",
    "settings_folders",
    "theme_for",
]
