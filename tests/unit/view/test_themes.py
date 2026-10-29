# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The palettes of the native tools and the KiCad theme file (capability native-themes, change c0178)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

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


# ---- the workbench themes and the role palette (change c0245, decision 6)

_UI = Path(__file__).resolve().parents[3] / "src" / "fenolite" / "view" / "ui"


def _tokens(theme: str) -> dict[str, str]:
    css = (_UI / "css" / "workbench.css").read_text(encoding="utf-8")
    head = ":root {" if theme == "dark" else f':root[data-ui-theme="{theme}"] {{'
    block = css[css.index(head) + len(head) :]
    block = block[: block.index("}")]
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block))


def _linear(hex_colour: str) -> list[float]:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]


def _luminance(hex_colour: str) -> float:
    r, g, b = _linear(hex_colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


TEXT_PAIRS = [
    ("text", "panel"), ("text", "panel2"), ("text", "input"), ("text", "bg"), ("text", "title-bg"),
    ("text", "tab-cur"),
    ("muted", "panel"), ("muted", "panel2"), ("muted", "input"), ("muted", "title-bg"), ("muted", "bg"),
    ("hdr-text", "hdr"), ("sel-text", "sel"), ("status-text", "status-bg"),
]  # fmt: skip
CONTROL_PAIRS = [
    ("control-edge", "panel"), ("control-edge", "panel2"), ("focus", "panel"), ("focus", "panel2"),
    ("accent", "panel"), ("err", "panel"), ("warn", "panel"),
]  # fmt: skip


@pytest.mark.parametrize("theme", ["dark", "light", "contrast"])
def test_contrast(theme: str) -> None:
    """H-G-WB-CONTRAST: text tokens reach 4.5:1 and control tokens 3:1 (WCAG 2.2 1.4.3 and 1.4.11, S-0925)."""
    tokens = _tokens(theme)
    low = [
        (a, b, round(_contrast(tokens[a], tokens[b]), 2))
        for a, b in TEXT_PAIRS
        if _contrast(tokens[a], tokens[b]) < 4.5
    ]
    low += [
        (a, b, round(_contrast(tokens[a], tokens[b]), 2))
        for a, b in CONTROL_PAIRS
        if _contrast(tokens[a], tokens[b]) < 3
    ]
    assert low == []


# The simulation matrices of severity 1.0, as Machado, Oliveira and Fernandes publish them (S-0928, their
# Table 1; open question 7 of c0245 decided to record them as published facts), applied to linear RGB.
CVD = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _lab(linear: list[float]) -> tuple[float, float, float]:
    r, g, b = (min(max(v, 0.0), 1.0) for v in linear)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _de2000(p: tuple[float, float, float], q: tuple[float, float, float]) -> float:
    """CIEDE2000 colour difference."""
    (l1, a1, b1), (l2, a2, b2) = p, q
    cbar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cbar**7 / (cbar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
    dh = h2p - h1p
    dhp = 0.0 if c1p * c2p == 0 else dh if abs(dh) <= 180 else dh - 360 if dh > 180 else dh + 360
    d_l, d_c = l2 - l1, c2p - c1p
    d_h = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))
    lbar, cbarp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbar = (h1p + h2p) / 2
    else:
        hbar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(hbar - 30))
        + 0.24 * math.cos(math.radians(2 * hbar))
        + 0.32 * math.cos(math.radians(3 * hbar + 6))
        - 0.20 * math.cos(math.radians(4 * hbar - 63))
    )
    rot = 30 * math.exp(-(((hbar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cbarp**7 / (cbarp**7 + 25**7))
    sl = 1 + 0.015 * (lbar - 50) ** 2 / math.sqrt(20 + (lbar - 50) ** 2)
    sc, sh = 1 + 0.045 * cbarp, 1 + 0.015 * cbarp * t
    rt = -math.sin(math.radians(2 * rot)) * rc
    return math.sqrt((d_l / sl) ** 2 + (d_c / sc) ** 2 + (d_h / sh) ** 2 + rt * (d_c / sc) * (d_h / sh))


def _theme_data() -> dict[str, Any]:
    text = (_UI / "shell" / "themes.js").read_text(encoding="utf-8")
    start = text.index("const THEME_DATA = ") + len("const THEME_DATA = ")
    return json.loads(text[start : text.index("\n};\n", start) + 2])


@pytest.mark.parametrize("tone", ["dark", "light"])
def test_cvd(tone: str) -> None:
    """H-G-WB-CVD: the seven role colours stay at least 12 CIEDE2000 apart, pairwise, in normal vision and
    under the protan, deutan and tritan simulation; each stands at 3:1 or more on its canvas; each has a
    glyph and a hatch of its own."""
    data = _theme_data()
    roles = data["roles"][tone]
    assert sorted(roles) == sorted(data["glyphs"]) == sorted(data["hatch"])
    assert len(set(data["glyphs"].values())) == len(roles) and len(
        set(map(str, data["hatch"].values()))
    ) == len(roles)
    worst = 99.0
    for matrix in (None, *CVD.values()):
        labs = []
        for colour in roles.values():
            lin = _linear(colour)
            if matrix is not None:
                lin = [sum(matrix[i][j] * lin[j] for j in range(3)) for i in range(3)]
            labs.append(_lab(lin))
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                worst = min(worst, _de2000(labs[i], labs[j]))
    assert worst >= 12, worst
    canvas = data["canvas"][tone]
    assert all(_contrast(c, canvas) >= 3 for c in roles.values())
