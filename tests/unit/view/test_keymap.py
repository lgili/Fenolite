# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keymaps of the workbench (change c0245, decision 5; board-viewer, "Keymaps")."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fenolite.view import export, keymap

UI = Path(export.__file__).resolve().parent / "ui"
DOCS = Path(__file__).resolve().parents[3] / "docs" / "viewer.md"
KEYS = re.compile(r"\bkeys: \[([^\]]*)\]")


def _command_keys() -> list[str]:
    found: list[str] = []
    for part in export.PARTS:
        if part.endswith(".js"):
            for line in (UI / part).read_text(encoding="utf-8").splitlines():
                if line.startswith("command({"):
                    for group in KEYS.findall(line):
                        found += re.findall(r'"([^"]+)"', group)
    return found


def test_reserved() -> None:
    """Task 4.1: no built-in keymap binds a key the browser keeps, and docs/viewer.md lists them all."""
    kept = keymap.reserved()
    built_in = [keymap.norm_key(k) for k in _command_keys()]
    for name, bindings in keymap.data()["maps"].items():
        for keys in bindings.values():
            built_in += [keymap.norm_key(k) for k in keys]
        assert name in keymap.BUILT_IN
    assert len(built_in) > 30
    bad = sorted({k for k in built_in if k.split()[0] in kept})
    assert bad == []
    docs = DOCS.read_text(encoding="utf-8")
    assert "## Keys the browser keeps" in docs
    for key in keymap.data()["reserved"]:
        assert f"`{key}`" in docs, key
    assert {"Ctrl+W", "Ctrl+T", "F5", "Alt+F4", "Meta+W"} <= kept


def test_a_keymap_file() -> None:
    doc = keymap.parse_keymap(
        {
            "schema": keymap.SCHEMA,
            "base": "altium",
            "bindings": {"view.fit": ["v f", "shift+f"], "edit.undo": []},
        }
    )
    assert doc == {
        "schema": keymap.SCHEMA,
        "base": "altium",
        "bindings": {"edit.undo": [], "view.fit": ["V F", "Shift+F"]},
    }


@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        ({"view.fit": ["Ctrl+W"]}, "belongs to the browser"),
        ({"view.fit": ["Hyper+F"]}, "modifiers"),
        ({"View Fit": ["F"]}, "command id"),
        ({"view.fit": ["A B C D"]}, "up to three"),
        ({"view.fit": "F"}, "list"),
    ],
)
def test_bad_keymaps_are_refused(bindings: object, message: str) -> None:
    with pytest.raises(keymap.KeymapError, match=message):
        keymap.parse_keymap({"schema": keymap.SCHEMA, "base": "fenolite", "bindings": bindings})


def test_read_keymap(tmp_path: Path) -> None:
    path = tmp_path / "keys.json"
    path.write_text(json.dumps({"schema": keymap.SCHEMA, "base": "kicad", "bindings": {}}), encoding="utf-8")
    assert keymap.read_keymap(path)["base"] == "kicad"
    path.write_text("[", encoding="utf-8")
    with pytest.raises(keymap.KeymapError, match="JSON"):
        keymap.read_keymap(path)
