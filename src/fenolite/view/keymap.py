# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keymaps of the viewer's workbench (change c0245, decision 5; board-viewer, "Keymaps").

The page holds three keymaps: ``fenolite`` (each command's own keys), ``altium`` and ``kicad``, given over
it in ``ui/shell/keymaps.js``. A keymap file, canonical JSON of the schema ``fenolite.view_keymap.v0``, names
one of them as its base and binds commands to keys over it: ``{"schema", "base", "bindings": {"view.fit":
["F", "V F"], ...}}``. A key is a chord (``Shift+M``, ``Ctrl+Z``, ``+``, ``Escape``) or a sequence of
chords separated by spaces (``V F``). The keys a browser keeps for itself (``reserved`` in the same file)
may not be bound. This module checks a file for ``fenolite view --keymap FILE``; the page checks the same
when a person edits a binding.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any, cast

SCHEMA = "fenolite.view_keymap.v0"
BUILT_IN = ("fenolite", "altium", "kicad")
MODIFIERS = ("Ctrl", "Meta", "Alt", "Shift")
COMMAND_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+")
KEY_NAME = re.compile(r"[A-Za-z0-9]|[^\sA-Za-z0-9+]|\+|[A-Z][A-Za-z]+[0-9]*|F[0-9]{1,2}")
BINDINGS_LIMIT = 4


class KeymapError(ValueError):
    """A keymap file that cannot be used; the message names the first problem."""


def data() -> dict[str, Any]:
    """The keymap data of the page (``KEYMAP_DATA`` of ``ui/shell/keymaps.js``), read as JSON."""
    text = resources.files("fenolite.view").joinpath("ui", "shell", "keymaps.js").read_text(encoding="utf-8")
    start = text.index("const KEYMAP_DATA = ") + len("const KEYMAP_DATA = ")
    end = text.index("\n};\n", start) + 2
    return cast("dict[str, Any]", json.loads(text[start:end]))


def norm_chord(chord: str) -> str:
    """One chord with its modifiers in a fixed order and a letter in upper case; raises ``KeymapError``."""
    if chord == "+":
        key, mods = "+", []
    elif len(chord) > 1 and chord.endswith("++"):
        key, mods = "+", chord[:-2].split("+")
    else:
        *mods, key = chord.split("+")
    if not key or not KEY_NAME.fullmatch(key):
        raise KeymapError(f"{chord!r}: not a key")
    folded = {m.lower() for m in mods}
    if len(folded) != len(mods) or not folded <= {m.lower() for m in MODIFIERS}:
        raise KeymapError(f"{chord!r}: modifiers are Ctrl, Meta, Alt and Shift, once each")
    if len(key) == 1 and key.isalpha():
        key = key.upper()
    return "+".join([m for m in MODIFIERS if m.lower() in folded] + [key])


def norm_key(spec: str) -> str:
    """A key or a sequence of up to three chords, normalised."""
    chords = spec.split()
    if not 1 <= len(chords) <= 3:
        raise KeymapError(f"{spec!r}: one chord, or a sequence of up to three")
    return " ".join(norm_chord(c) for c in chords)


def reserved() -> frozenset[str]:
    """The chords no keymap may bind."""
    return frozenset(norm_chord(k) for k in cast("list[str]", data()["reserved"]))


def parse_keymap(raw: object) -> dict[str, Any]:
    """The keymap ``raw`` (decoded JSON) holds: its base and its bindings, normalised. Raises
    ``KeymapError``."""
    if not isinstance(raw, dict):
        raise KeymapError("a keymap is a JSON object")
    doc = cast("dict[str, Any]", raw)
    if doc.get("schema") != SCHEMA:
        raise KeymapError(f"schema: expected {SCHEMA!r}")
    base = doc.get("base", "fenolite")
    if base not in BUILT_IN:
        raise KeymapError(f"base: one of {', '.join(BUILT_IN)}")
    bindings_in = doc.get("bindings", {})
    if not isinstance(bindings_in, dict):
        raise KeymapError("bindings: an object of command ids and lists of keys")
    kept = reserved()
    bindings: dict[str, list[str]] = {}
    for command, keys in sorted(cast("dict[object, object]", bindings_in).items(), key=lambda kv: str(kv[0])):
        if not isinstance(command, str) or not COMMAND_ID.fullmatch(command):
            raise KeymapError(f"bindings: {command!r} is not a command id such as view.fit")
        if not isinstance(keys, list) or len(cast("list[object]", keys)) > BINDINGS_LIMIT:
            raise KeymapError(f"bindings.{command}: a list of at most {BINDINGS_LIMIT} keys")
        normal: list[str] = []
        for key in cast("list[object]", keys):
            if not isinstance(key, str):
                raise KeymapError(f"bindings.{command}: a key is a string")
            spec = norm_key(key)
            if spec.split()[0] in kept:
                raise KeymapError(f"bindings.{command}: {spec} belongs to the browser")
            normal.append(spec)
        bindings[command] = normal
    return {"schema": SCHEMA, "base": base, "bindings": bindings}


def read_keymap(path: Path) -> dict[str, Any]:
    """The keymap of ``path``. Raises ``KeymapError`` (also for a file that is not JSON)."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KeymapError(f"not a readable JSON file: {exc}") from exc
    return parse_keymap(raw)


__all__ = ["BUILT_IN", "SCHEMA", "KeymapError", "data", "norm_key", "parse_keymap", "read_keymap", "reserved"]
