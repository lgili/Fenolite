# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged viewer page (capability board-viewer, "Viewer page"): self-contained, and a standalone page
carries its tree and scenes unchanged."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fenolite.backends import registry
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.base import BoardFrame
from fenolite.view.export import DATA_MARK, LIVE_MARK, embedded, page, template
from fenolite.view.project import load_tree
from fenolite.view.scene import build_scene
from fenolite.view.schematic import build_schematic_scene

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SHEET = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.SchDoc"


def test_template_is_self_contained() -> None:
    html = template()
    assert DATA_MARK in html and LIVE_MARK in html
    assert re.search(r"https?://", html) is None, "the page loads nothing from the network"
    for element in ("tree", "tablist", "ls", "cv", "gl", "status"):
        assert f'id="{element}"' in html, element


def test_standalone_page_round_trips() -> None:
    """Scenario "Standalone page round-trips"."""
    backend = registry.for_path(BOARD)
    assert backend is not None and isinstance(backend, BoardFrame)
    scene = build_scene(backend.read(BOARD).design, backend, name=BOARD.name, data=BOARD.read_bytes())
    scene["texts"].append(["F.SilkS", 0, 0, 1000, 667, 150, 0.0, "left", "bottom", False, "</script>", -1])
    tree = load_tree(BOARD).to_json()
    html = page(tree, {"doc1": scene}, open_id="doc1")
    assert '</script>"' not in html
    data = embedded(html)
    assert data is not None
    assert data["project"] == tree and data["scenes"]["doc1"] == scene and data["open"] == "doc1"
    assert re.search(r"https?://", html.replace(tree["name"], "")) is None


def test_schematic_scene_round_trips() -> None:
    """Scenario "A schematic scene round-trips through the export" (c0177)."""
    data = SHEET.read_bytes()
    scene = build_schematic_scene(read_schematic(data, file=SHEET.name), name=SHEET.name, data=data)
    tree = load_tree(SHEET).to_json()
    html = page(tree, {"doc1": scene}, open_id="doc1")
    back = embedded(html)
    assert back is not None and back["scenes"]["doc1"] == scene
    assert re.search(r"https?://", html.replace(tree["name"], "")) is None


def test_schematic_interaction_is_in_the_page() -> None:
    """Scenario "The page holds the interaction" (c0177)."""
    html = template()
    for name in ("drawSch", "navList", "sheetTabs", "selNet", "crossProbe", "schDouble", "toMMsch"):
        assert name in html, name
    assert 'class="sch-only' in html and "board-only" in html


def test_the_page_reads_the_theme() -> None:
    """Scenario "The page reads the theme" (c0178)."""
    html = template()
    for name in ("S.theme", "sheet.workspace", 'sheet.text === "stroke"', "drawStrokeText", "l.alpha"):
        assert name in html, name


def test_units() -> None:
    """Scenario "Unit conversions" (c0179): the page's own conversion functions, run in Node when it is
    installed."""
    html = template()
    for name in (
        "function fmtLen",
        "function fmtNm",
        '"bUnit"',  # the toolbar's unit button (c0300: rendered by panels/toolbar.tsx)
        "function snap(",
        "function measureClick",
    ):
        assert name in html, name
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the definitions are checked, not run")
    start = html.index("const MIL_MM")
    end = html.index("function fmtPair")
    code = html[start:end].replace("let UNIT = (() =>", "let UNIT = 'mm'; const _u = (() =>")
    script = code + (
        "const out = []; UNIT = 'mm'; out.push(fmtLen(1.2), fmtNm(254000));"
        "UNIT = 'mil'; out.push(fmtLen(1.2), fmtNm(254000)); console.log(JSON.stringify(out));"
    )
    done = subprocess.run(
        [node, "-e", "const localStorage = { getItem: () => null };" + script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    assert json.loads(done.stdout) == ["1.200 mm", "0.254 mm", "47.24 mil", "10.00 mil"]


def test_libraries_in_the_page() -> None:
    html = template()
    for name in ("function loadLibrary", "function openItem", 'id="libList"', "function toUnits", "padInfo"):
        assert name in html, name


def test_live_page_has_no_data() -> None:
    html = page(live=True)
    assert "const LIVE = true;" in html and embedded(html) is None


def test_review_panels_in_the_page() -> None:
    """Change c0187: the Components and Nets panels, the filter, Find similar, highlight modes and links."""
    html = template()
    for name in (
        'id="compList"',
        'id="netList"',
        'id="hlMode"',
        'id="bSimilar"',
        "function vlist",
        "function clearQuery",
    ):
        assert name in html, name
    assert "HL_ALPHA[st.hl]" in html and 'rel="noopener noreferrer"' in html


def test_check_findings_in_the_page() -> None:
    """Change c0188: markers and the Messages panel of `--check`."""
    html = template()
    for name in (
        'id="msgList"',
        "function drawCheck",
        "function buildMessages",
        "function checkToMM",
        "SEV_COLOR",
    ):
        assert name in html, name


def test_snap() -> None:
    """Scenario "Snap targets in the page" (change c0193): the measurement snaps to points, then edges, unless
    Alt is held, and the findings are listed by group with the body models drawn in 3D."""
    html = template()
    for name in (
        "function snapEdge(",
        "function buildEdges(",
        "function buildFindings(",
        "function buildMeshes(",
        "function pick3D(",
    ):
        assert name in html, name
    assert "snap(x, y, e.altKey)" in html and "measureClick(e.offsetX, e.offsetY, e.altKey)" in html


# ---- c0300: the shell (tokens, command registry, toolbar, palette)


def _style(html: str) -> str:
    return html[html.index("<style>") + len("<style>") : html.index("</style>")]


TOKEN_BLOCKS = (
    ("dark", r":root \{([^}]*)\}"),
    (
        "light-system",
        r"@media \(prefers-color-scheme: light\) \{\s*:root:not\(\[data-theme=dark\]\) \{([^}]*)\}\s*\}",
    ),
    ("light", r":root\[data-theme=light\] \{([^}]*)\}"),
)
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\b(?:white|black)\b(?!-)")


def _tokens(css: str) -> tuple[dict[str, dict[str, str]], str]:
    """The three colour token blocks of the stylesheet, and the stylesheet without them."""
    found: dict[str, dict[str, str]] = {}
    rest = css
    for name, pattern in TOKEN_BLOCKS:
        match = re.search(pattern, rest)
        assert match is not None, f"token block {name} is missing"
        found[name] = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", match.group(1)))
        rest = rest[: match.start()] + rest[match.end() :]
    return found, rest


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")[:6]
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_tokens_in_both_themes_with_contrast() -> None:
    """Scenario "Tokens and contrast" (c0300): every token in both themes, each text and surface pair at
    4.5:1, and no colour literal in a chrome rule outside the token blocks."""
    blocks, rest = _tokens(_style(template()))
    names = set(blocks["dark"])
    wanted = {
        "--surface-0",
        "--text-1",
        "--accent",
        "--focus",
        "--ok",
        "--warn",
        "--err",
        "--info",
        "--emphasis",
    }
    assert wanted <= names
    for name, block in blocks.items():
        assert set(block) == names, (name, names ^ set(block))
    assert blocks["light-system"] == blocks["light"]
    texts = ("--text-1", "--text-2", "--text-3", "--accent", "--ok", "--warn", "--err", "--info")
    for name, block in blocks.items():
        for text in texts:
            for surface in ("--surface-0", "--surface-1", "--surface-2", "--surface-3"):
                ratio = _contrast(block[text], block[surface])
                assert ratio >= 4.5, f"{name}: {text} on {surface} is {ratio:.2f}:1"
        assert _contrast(block["--accent-text"], block["--accent-bg"]) >= 4.5, name
        for badge in ("--err", "--warn"):  # a count badge: the panel colour on a severity
            assert _contrast(block["--surface-1"], block[badge]) >= 4.5, (name, badge)
    leftover = [m.group(0) for m in COLOUR.finditer(rest)]
    assert leftover == [], f"colour literals outside the token blocks: {leftover}"
    assert re.search(r"--space-1:\s*4px", rest) and re.search(r"--text-md:\s*13px", rest)


def _block(html: str, start: str, end: str) -> str:
    return html[html.index(start) : html.index(end)]


def test_registry_commands_have_icons_and_unique_shortcuts() -> None:
    """Design decision 2 (c0300): each command of the registry has a title, an icon of the icon set and a
    shortcut no other command has; the keydown listener looks the shortcuts up in it."""
    html = template()
    icon_block = _block(html, "// ---- icons (c0300)", "// ---- end icons")
    icons = set(re.findall(r"^\s*(\w+): \"M", icon_block, re.M))
    registry = _block(html, "// ---- commands (c0300)", "// ---- end commands")
    commands = re.findall(
        r'\{ id: "([\w.]+)", title: "([^"]+)", group: "(\w+)", icon: "(\w+)", keys: \[([^\]]*)\]', registry
    )
    assert len(commands) >= 25
    ids = [c[0] for c in commands]
    assert len(ids) == len(set(ids))
    keys: list[str] = []
    for cid, title, _group, icon, spec in commands:
        assert title and icon in icons, (cid, icon)
        keys += re.findall(r'"([^"]+)"', spec)
    assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)
    assert 'icon: "printer"' in registry and "share.print." in registry  # Print at each scale
    assert {"Mod+K", "?", "D", "F", "B", "M", "Shift+M", "N", "Q", "Shift+S", "Escape"} <= set(keys)
    assert "commandForKey(e)" in html and "function keyMatches(" in html


def test_toolbar_groups_and_no_duplicate_controls() -> None:
    """Scenario "No duplicate labels" (c0300), statically: the three groups in order, the duplicate Fit and
    Clear controls and the SHA-256 of the status bar gone, the print scale in the Export menu."""
    html = template()
    toolbar = _block(html, "function Toolbar()", "function refreshToolbar()")
    groups = re.findall(r'"aria-label": "(View|Tools|Share)"', toolbar)
    assert groups == ["View", "Tools", "Share"]
    labels = re.findall(r'\btext: "([^"]+)"', toolbar)
    assert len(labels) == len(set(labels)), labels
    for gone in ('id="printScale"', 'id="bClear"', 'id="gen"', "SHA-256 ${"):
        assert gone not in html, gone
    assert "Print, or save as PDF" in html and '"bQClear"' in html and "Clear filter" in html


def test_palette_match_ranking_under_node() -> None:
    """Scenario "Ranking under Node" (c0300): prefix matches before word starts before other subsequences, and
    a query of ">" lists commands only."""
    html = template()
    code = _block(html, "// ---- palette (c0300)", "// ---- end palette")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    items = [
        {"kind": "command", "label": "Fit to the window"},
        {"kind": "part", "label": "R10"},
        {"kind": "part", "label": "PR1"},
        {"kind": "net", "label": "GND_R1"},
        {"kind": "part", "label": "R1"},
        {"kind": "command", "label": "Review mark"},
        {"kind": "doc", "label": "board.kicad_pcb"},
    ]
    script = code + (
        f"const items = {json.dumps(items)}; const L = q => paletteMatch(q, items).map(i => i.label);"
        "console.log(JSON.stringify({r1: L('r1'), cmd: L('>'), net: L('#r1'),"
        " part: L('@r'), none: L('zzz')}));"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True, timeout=60
    )
    out = json.loads(done.stdout)
    assert out["r1"][:2] == ["R1", "R10"]  # prefixes, the shorter first
    assert out["r1"].index("GND_R1") < out["r1"].index("PR1")  # a word start before a subsequence
    assert out["cmd"] == ["Fit to the window", "Review mark"]
    assert out["net"] == ["GND_R1"] and out["part"] == ["R1", "R10", "PR1"] and out["none"] == []


# ---- c0301: the dock, the inspector, the layers panel, the net emphasis


def test_dock_and_layer_list_in_the_page() -> None:
    """Design decisions 1, 4 and 5 (c0301): the dock with the Properties body `info`, the Layers panel
    `layerList`, the view cube, the emphasis of a picked net and Dim at 0.22."""
    html = template()
    for element in (
        "dock",
        "dockResize",
        "dockProps",
        "info",
        "infoEmpty",
        "dockLayers",
        "layerList",
        "dock3d",
        "cube",
    ):
        assert f'id="{element}"' in html, element
    assert 'id="bar3d"' not in html and "HL_ALPHA = { dim: 0.22" in html
    draw = _block(html, "function paintEmphasis(", "function draw()")
    assert "--emphasis" in html and "ZONE_FILL_ALPHA" in draw and "lighten(" not in draw
    assert "function camPreset(" in html and "front: [" in html and "function drawCube(" in html


def test_inspector_model_under_node() -> None:
    """Scenario "Missing values are left out" (c0301): an authored pad without a drill gives no drill row,
    every row has a copy control, and "Copy all" lists the rows as label: value lines."""
    html = template()
    code = _block(html, "// ---- inspector model (c0301)", "// ---- end inspector model")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = code + (
        "const f = {len: v => v.toFixed(3) + ' mm', nm: v => (v / 1e6).toFixed(3) + ' mm',"
        " pair: (a, b) => a.toFixed(3) + ' × ' + b.toFixed(3) + ' mm',"
        " xy: (a, b) => a.toFixed(3) + ', ' + b.toFixed(3) + ' mm',"
        " area: a => a.toFixed(3) + ' mm²'};"
        "const pad = {number: '1', shape: 'rect', kind: 'smd', w: 900000, h: 950000, x: 1.5, y: 2, rot: 90,"
        " layers: ['F.Cu', 'F.Mask'], drill: null, mask: 50000, mask_src: 'the pad'};"
        "const s = padSection(pad, f, id => id === 'F.Cu' ? 'Top Layer' : id);"
        "const empty = padSection({}, f, id => id);"
        "const m = imodel('pad', 'R1 · pad 1', [s, isection('Nothing', [irow('a', null), irow('b', '')])]);"
        "const part = partSection({ref: 'R1', value: '', footprint: 'R_0603', side: 'top', x: 1, y: 2,"
        " rotation: 0, bbox: null}, null, [['Datasheet', 'https://example.invalid/r']], f);"
        "console.log(JSON.stringify({rows: s.rows, empty, sections: m.sections.length, text: modelText(m),"
        " part: part.rows.map(r => [r.label, r.value, r.link || null])}));"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True, timeout=60
    )
    out = json.loads(done.stdout)
    labels = [r["label"] for r in out["rows"]]
    assert "Drill" not in labels and "Slot length" not in labels and "Paste expansion" not in labels
    assert labels[:4] == ["Number", "Shape", "Mounting", "Size"] and "Mask opening" in labels
    assert all(r["copy"] is True for r in out["rows"])
    assert dict((r["label"], r["value"]) for r in out["rows"])["Layers"] == "Top Layer, F.Mask"
    assert out["empty"] is None and out["sections"] == 1
    assert "Size: 0.900 × 0.950 mm" in out["text"] and out["text"].startswith("R1 · pad 1")
    assert ["Value", "", None] not in out["part"] and ["Rotation", "0°", None] in out["part"]
    assert ["Datasheet", "https://example.invalid/r", "https://example.invalid/r"] in out["part"]


# ---- c0305: the net roles


def test_roles_panel_and_overlays_in_the_page() -> None:
    """Design decisions 4 and 5 (c0305): the Net roles section, the role overlays drawn after the check
    markers, the role copper under a pick's emphasis, and the Roles commands of the registry."""
    html = template()
    assert 'data-sect="roles"' in html and 'id="roleList"' in html
    draw = html[html.index("function draw()") :]
    assert "paintRoleCopper(ord" in draw and re.search(r"drawCheck\(\);\s*drawRoles\(\);", draw)
    registry = _block(html, "// ---- commands (c0300)", "// ---- end commands")
    for command in (
        "roles.colors",
        "roles.loops",
        "roles.kelvin",
        "roles.findings",
        "roles.run",
        "act.confirmRole",
    ):
        assert f'id: "{command}"' in registry, command


def test_role_section_under_node() -> None:
    """Scenario "The role of a gate net" (c0305): the Role section of an inferred gate row lists its kind,
    state, rule, pads and gate loop, and leaves out the current the reply does not hold."""
    html = template()
    code = _block(html, "// ---- inspector model (c0301)", "// ---- end inspector model")
    code += _block(html, "// ---- roles model (c0305)", "// ---- end roles model")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = code + (
        "const f = {area: a => a.toFixed(3) + ' mm²'};"
        "const row = {net: 'GH', kind: 'gate', state: 'inferred', source: 'inferred', rule: 'GD-1',"
        " confidence: 'high', pads: ['Q1-2', 'U1-7'], milliamps: null, working_mv: null, sensitive: false};"
        "const data = {kinds: {gate: 2, power: 5}, groups: ["
        " {name: 'gate_Q1', type: 'gate', pads: ['U1-7', 'Q1-2', 'Q1-1', 'U1-6'], origin: 'inferred'},"
        " {name: 'hot_SW', type: 'hot', pads: ['C1-1', 'Q1-3'], net: 'SW', area_nm2: 180020750000000,"
        "  bound_nm2: 46125625000000, ratio_permille: 3902, origin: 'inferred'}]};"
        "const padNet = p => ({'U1-7': 'GH', 'Q1-2': 'GH'})[p] || 'X';"
        "const groups = groupsOfNet(data, 'GH', padNet);"
        "const s = roleSection(row, groups, f);"
        "const power = roleSection({net: 'VIN', kind: 'power', state: 'declared', milliamps: 2000,"
        " working_mv: 48000}, [], f);"
        "const loop = groupSection(data.groups[1], f);"
        "const pairs = x => x.rows.map(r => [r.label, r.value]);"
        "console.log(JSON.stringify({rows: pairs(s), power: pairs(power), loop: pairs(loop),"
        " legend: roleLegend(data), none: roleSection(null, [], f)}));"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True, timeout=60
    )
    out = json.loads(done.stdout)
    rows = dict(out["rows"])
    assert rows["Kind"] == "gate" and rows["State"] == "inferred" and rows["Rule"] == "GD-1"
    assert rows["Evidence pads"] == "Q1-2, U1-7" and rows["Groups"] == "gate_Q1 (gate loop)"
    assert "Current" not in rows and "Working voltage" not in rows and "Sensitive" not in rows
    assert ["Current", "2 A"] in out["power"] and ["Working voltage", "48 V"] in out["power"]
    loop = dict(out["loop"])
    assert loop["Loop area"] == "180.021 mm²" and loop["Area to bound"] == "3.90" and loop["Net"] == "SW"
    assert [k["kind"] for k in out["legend"]] == ["power", "gate"] and out["legend"][0]["glyph"] == "P"
    assert out["none"] is None
