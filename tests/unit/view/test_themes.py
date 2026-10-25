# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The palettes of the native tools and the KiCad theme file (capability native-themes, change c0178)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError
from fenolite.view import themes

ROOT = Path(__file__).resolve().parents[3]
KICAD_BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM_BOARD = ROOT / "tests" / "data" / "altium" / "board6" / "board6.PcbDoc"


def _layer(scene: dict[str, object], lid: str) -> dict[str, object]:
    return next(layer for layer in scene["layers"] if layer["id"] == lid)  # type: ignore[union-attr,index]


def test_each_backend_gets_its_palette() -> None:
    """Scenario "Each backend gets its palette"."""
    kicad = scene_of(KICAD_BOARD)
    assert kicad["theme"]["name"] == "kicad"
    assert kicad["theme"]["background"] == themes.KICAD["board"]["background"]
    assert _layer(kicad, "F.Cu")["color"] == themes.KICAD["board"]["layers"]["F.Cu"]
    altium = scene_of(ALTIUM_BOARD)
    assert altium["theme"]["name"] == "altium"
    assert _layer(altium, "F.Cu")["color"] == themes.ALTIUM["board"]["layers"]["F.Cu"]
    assert themes.theme_for("altium") == "altium" and themes.theme_for("kicad") == "kicad"


def test_palettes_are_copies() -> None:
    one = themes.palette("kicad")
    one["board"]["layers"]["F.Cu"] = "#000000"
    assert themes.KICAD["board"]["layers"]["F.Cu"] != "#000000"


def _theme_file(tmp_path: Path, body: object) -> Path:
    path = tmp_path / "mine.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_an_authored_theme_file(tmp_path: Path) -> None:
    """Scenario "An authored theme file"."""
    path = _theme_file(
        tmp_path,
        {
            "meta": {"name": "Mine", "filename": "mine", "version": 0},
            "board": {
                "background": "rgb(1, 2, 3)",
                "copper": {"f": "rgba(200, 10, 20, 0.8)", "in1": "rgb(9, 9, 9)"},
                "f_mask": "rgba(10, 200, 10, 0.4)",
                "unknown_key": "rgb(0, 0, 0)",
            },
            "schematic": {"wire": "rgb(0, 128, 0)", "component_body": "rgb(255, 255, 200)"},
        },
    )
    theme = themes.read_kicad_theme(path)
    assert theme["name"] == "kicad:mine.json" and theme["title"] == "Mine"
    board = theme["board"]
    assert board["background"] == "#010203" and board["layers"]["F.Cu"] == "#c80a14"
    assert board["opacity"]["F.Cu"] == pytest.approx(0.8) and board["layers"]["In1.Cu"] == "#090909"
    assert board["layers"]["F.Mask"] == "#0ac80a" and board["opacity"]["F.Mask"] == pytest.approx(0.4)
    assert theme["schematic"]["wire"] == "#008000" and theme["schematic"]["component_body"] == "#ffffc8"
    assert board["layers"]["B.Cu"] == themes.KICAD["board"]["layers"]["B.Cu"]
    assert theme["schematic"]["bus"] == themes.KICAD["schematic"]["bus"]
    scene = scene_of(KICAD_BOARD, theme)
    assert scene["theme"]["name"] == "kicad:mine.json" and _layer(scene, "F.Cu")["color"] == "#c80a14"
    assert _layer(scene, "F.Cu")["alpha"] == pytest.approx(0.8)


@pytest.mark.parametrize(
    "body",
    [[1, 2], {"schematic": [1]}, {"board": {"background": "blue"}}, {"schematic": {"wire": 3}}],
)
def test_a_malformed_theme_file(tmp_path: Path, body: object) -> None:
    with pytest.raises(FormatError):
        themes.read_kicad_theme(_theme_file(tmp_path, body))
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(FormatError):
        themes.read_kicad_theme(tmp_path / "bad.json")


def test_a_theme_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        themes, "settings_folders", lambda: [tmp_path / "kicad" / "10.0", tmp_path / "kicad" / "9.0"]
    )
    colors = tmp_path / "kicad" / "9.0" / "colors"
    colors.mkdir(parents=True)
    (colors / "mine.json").write_text("{}", encoding="utf-8")
    assert themes.find_kicad_theme("mine", tmp_path / "elsewhere") == colors / "mine.json"
    assert themes.find_kicad_theme("other", tmp_path) is None
    (tmp_path / "local.json").write_text("{}", encoding="utf-8")
    assert themes.find_kicad_theme("local.json", tmp_path) == tmp_path / "local.json"
