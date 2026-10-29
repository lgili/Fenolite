# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The viewer's shell in Chromium (change c0268): the grouped toolbar, the command palette, the shortcut
sheet, the side bar sections, the theme, "About this document" and the retry of a failed read, on the exported
page of the authored `two_layer.kicad_pcb`."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

HELP = """
const settle = () => new Promise(ok => setTimeout(ok, 50));
const press = (el, key, extra = {}) => el.dispatchEvent(new KeyboardEvent("keydown", {key, bubbles: true,
  cancelable: true, ...extra}));
const type = async text => { const i = $("palInput"); i.value = text; i.dispatchEvent(new Event("input",
  {bubbles: true})); await settle(); };
"""


def _act(pages: dict[str, Path], tmp_path: Path, script: str, **extra: Any) -> Any:
    (reply,) = run(
        [job("shell", pages["kicad_board"], tmp_path, script=HELP + script, shot="", **extra)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_toolbar_groups_icons_and_labels(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "No duplicate labels": three groups in order, an icon and an accessible name on every button,
    no label twice, and the print scale reached from the Export menu."""
    script = """
    const groups = [...$("top").querySelectorAll(".tgroup[aria-label]")]
      .map(g => g.getAttribute("aria-label"));
    const buttons = [...$("top").querySelectorAll("button")].filter(b => b.offsetParent !== null);
    const bare = buttons.filter(b => !b.querySelector("svg") || !b.getAttribute("aria-label")).map(b => b.id);
    const labels = buttons.map(b => b.getAttribute("aria-label"));
    $("bExport").click(); await settle();
    const menu = [...document.querySelectorAll(".menu [role^=menuitem]")].map(b => b.textContent);
    const tips = buttons.filter(b => b.dataset.keys).map(b => b.id + ":" + b.dataset.keys);
    return {groups, bare, labels, menu, tips, gone: ["printScale", "bClear", "gen"].filter(id => $(id))};
    """
    found = _act(pages, tmp_path, script, width=1440, height=900)
    assert found["groups"] == ["View", "Tools", "Share"]
    assert found["bare"] == [] and found["gone"] == []
    assert len(found["labels"]) == len(set(found["labels"])), found["labels"]
    assert "Save as SVG" in found["menu"] and "1:1" in found["menu"] and "10:1" in found["menu"]
    assert "bFit:F" in found["tips"] and "bMeasure:M" in found["tips"]


def test_palette_jumps_to_a_part_from_a_text_field(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Jump to a part from a text field" and "The palette chord in a text field"."""
    script = """
    $("query").focus(); press($("query"), "k", {ctrlKey: true}); await settle();
    const opened = $("palette").open, focus = document.activeElement.id;
    await type("r1"); const first = $("palList").querySelector("[aria-selected=true]").textContent;
    const before = view.s; press($("palInput"), "Enter"); await settle();
    return {opened, focus, first, closed: !$("palette").open,
      sel: st.selComp >= 0 ? S.comps[st.selComp].ref : null,
      zoomed: view.s !== before, after: document.activeElement === document.body};
    """
    found = _act(pages, tmp_path, script)
    assert found["opened"] and found["focus"] == "palInput" and found["first"].startswith("R1")
    assert found["closed"] and found["sel"] == "R1" and found["zoomed"] and found["after"]


def test_palette_nets_commands_and_the_mac_chord(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    IS_MAC = true; press(window, "k", {ctrlKey: true}); await settle(); const ctrlOnMac = $("palette").open;
    press(window, "k", {metaKey: true}); await settle(); const cmd = $("palette").open;
    const net = S.nets.findIndex(n => n === "GND") >= 0 ? "GND" : S.nets.find(Boolean);
    await type("#" + net.toLowerCase()); press($("palInput"), "Enter"); await settle();
    const picked = st.selNet >= 0 ? S.nets[st.selNet] : null;
    IS_MAC = false; press(window, "k", {ctrlKey: true}); await settle(); view.s = 99;
    await type(">fit"); const kinds = [...$("palList").querySelectorAll(".palGroup")].map(g => g.textContent);
    press($("palInput"), "Enter"); await settle();
    press(window, "k", {ctrlKey: true}); await settle(); press($("palInput"), "Escape"); await settle();
    return {ctrlOnMac, cmd, net, picked, kinds, fitted: view.s !== 99, closed: !$("palette").open};
    """
    found = _act(pages, tmp_path, script)
    assert not found["ctrlOnMac"] and found["cmd"]
    assert found["picked"] == found["net"]
    assert found["kinds"] == ["Commands"] and found["fitted"]


def test_plain_keys_in_the_search_field_are_text(pages: dict[str, Path], tmp_path: Path) -> None:
    """A plain K or M typed in the search field is text, not a shortcut; Ctrl+K opens the palette."""
    script = """
    $("search").focus(); press($("search"), "m"); const measuring = st.measure;
    press($("search"), "k", {ctrlKey: true}); await settle();
    return {measuring, opened: $("palette").open};
    """
    assert _act(pages, tmp_path, script) == {"measuring": False, "opened": True}


def test_shortcut_sheet_lists_the_registry(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    press(window, "?", {shiftKey: true}); await settle();
    const text = $("shortcuts").textContent, open = $("shortcuts").open;
    return {open, text, n: COMMANDS.filter(c => c.keys.length).every(c => text.includes(c.title))};
    """
    found = _act(pages, tmp_path, script)
    assert found["open"] and found["n"] and "Measure" in found["text"] and "Ctrl K" in found["text"]


def test_sections_collapse_and_zero_groups_fold(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Zero groups fold but remain", and the open state of a section across a reload."""
    script = """
    const groups = S.meta.findings || [];
    const listed = [...$("overlays").querySelectorAll(".fg")].map(r => r.querySelector(".ft").textContent);
    const zero = $("ovZero"); const zeroText = zero ? zero.textContent : null;
    if (zero) zero.click(); await settle();
    const zeros = [...$("overlays").querySelectorAll(".fg.zero .fn")].map(n => n.textContent);
    const comps = document.querySelector('details.sect[data-sect="components"]');
    comps.querySelector("summary").click(); await settle();
    return {groups: groups.length, listed, zeroText, zeros, open: comps.open,
      count: comps.querySelector(".count").textContent, sorts: [...$("compSort").options].map(o => o.value)};
    """
    reload = "return document.querySelector('details.sect[data-sect=\"components\"]').open;"
    found = _act(pages, tmp_path, script, reloadScript=reload)
    before = found["before"]
    assert before["groups"] > len(before["listed"]) and before["zeroText"]
    assert re.match(r"\d+ groups? with no findings", before["zeroText"])
    assert before["zeros"] and set(before["zeros"]) == {"0"}
    assert before["open"] is False and before["count"].isdigit()
    assert before["sorts"] == ["ref", "value", "footprint"]
    assert found["after"] is False  # the closed section stays closed after the reload


def test_component_sort_is_natural(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const refs = () => [...$("compList").querySelectorAll(".vrow b")].map(b => b.textContent);
    const byRef = refs(); $("compSort").value = "footprint"; $("compSort").dispatchEvent(new Event("change"));
    const byFootprint = refs();
    return {byRef, byFootprint, natural: [...byRef].sort((a, b) => a.localeCompare(b, undefined,
      {numeric: true}))};
    """
    found = _act(pages, tmp_path, script)
    assert found["byRef"] == found["natural"] and sorted(found["byFootprint"]) == sorted(found["byRef"])


def test_theme_switch_keeps_the_board_colours(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "The light shell keeps the board's colours"."""
    script = """
    const bg = () => getComputedStyle($("top")).backgroundColor;
    const dark = bg(); $("bTheme").click(); await settle(); $("themeLight").click(); await settle();
    const px = cv.getContext("2d").getImageData(2, 2, 1, 1).data;
    return {dark, light: bg(), attr: document.documentElement.dataset.theme, px: [...px].slice(0, 3),
      theme: S.theme.background};
    """
    reload = "const top = getComputedStyle($('top')).backgroundColor;"
    reload += "return {attr: document.documentElement.dataset.theme, top};"
    found = _act(pages, tmp_path, script, reloadScript=reload)
    before, after = found["before"], found["after"]
    assert before["dark"] != before["light"] and before["light"] == "rgb(255, 255, 255)"
    assert before["attr"] == "light" and after == {"attr": "light", "top": "rgb(255, 255, 255)"}
    want = [int(before["theme"][i : i + 2], 16) for i in (1, 3, 5)]
    assert all(abs(a - b) <= 2 for a, b in zip(before["px"], want, strict=True)), (before["px"], want)


def test_about_holds_the_digest(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "The digest moves to the popover"."""
    script = """
    const status = $("status").textContent; $("bAbout").click(); await settle();
    return {status, hash: $("aboutHash").textContent, evidence: $("aboutEvidence").textContent,
      sha: S.meta.sha256,
      open: $("about").open};
    """
    found = _act(pages, tmp_path, script)
    assert re.search(r"[0-9a-f]{12}", found["status"]) is None
    assert found["open"] and found["hash"] == found["sha"] and re.fullmatch(r"[0-9a-f]{64}", found["hash"])
    assert found["evidence"] and found["evidence"] != "UNKNOWN"


def test_retry_a_failed_read(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A failed read can be retried"."""
    script = """
    const original = sceneOf, d = DOC; let calls = 0;
    sceneOf = doc => ++calls === 1 ? Promise.reject(new Error("stub read failure")) : original(doc);
    invalidateScene(d.id); RAW.set(d.id, SCENES.get(d.id) || S);
    const shown = await openDoc(d);
    const card = {display: $("doccard").style.display, text: $("doctext").textContent,
      retry: !!$("docRetry")};
    $("docRetry").click(); for (let k = 0; k < 100 && $("doccard").style.display !== "none";
      k++) await settle();
    return {shown, card, calls, after: $("doccard").style.display, doc: DOC.id === d.id,
      kind: S.kind ?? "board"};
    """
    found = _act(pages, tmp_path, script)
    assert found["shown"] == 0 and found["card"]["display"] == "flex" and found["card"]["retry"]
    assert "stub read failure" in found["card"]["text"]
    assert found["calls"] == 2 and found["after"] == "none" and found["doc"]
