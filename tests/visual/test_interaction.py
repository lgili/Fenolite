# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interaction tests of the viewer page (capability viewer-visual-tests; change c0191): selection,
measurement, unit switch and cross-probe, by mouse and key events on the canvas of the page of the authored
`blink` project."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

EVENTS = """
const r = cv.getBoundingClientRect();
const at = (x, y) => {
  const [X, Y] = w2s(x, y);
  return { clientX: r.left + X, clientY: r.top + Y, bubbles: true, view: window };
};
const click = (x, y) => {
  cv.dispatchEvent(new MouseEvent("mousedown", at(x, y)));
  cv.dispatchEvent(new MouseEvent("mouseup", at(x, y)));
};
const key = k => window.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true }));
const pad = label => S.pads.find(p => p.label === label);
const settle = () => new Promise(ok => setTimeout(ok, 50));
"""


def _act(pages: dict[str, Path], tmp_path: Path, script: str) -> Any:
    (reply,) = run(
        [job("interaction", pages["blink_project"], tmp_path, script=EVENTS + script, shot="")], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_selection(pages: dict[str, Path], tmp_path: Path) -> None:
    found = _act(
        pages, tmp_path, 'const p = pad("R1-1"); click(p.x, p.y); await settle(); return $("info").innerText;'
    )
    assert "R1" in found and "Net:" in found


def test_measurement_snaps_to_pad_centres(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const a = pad("R1-1"), b = pad("R1-2"); key("m");
    click(a.x + 0.01, a.y); click(b.x, b.y - 0.01); await settle();
    return { text: $("coord").textContent, d: Math.hypot(a.x - b.x, a.y - b.y) };
    """
    found = _act(pages, tmp_path, script)
    assert f"{found['d']:.3f} mm" in found["text"]  # snapped to the two centres, not the clicks
    assert not math.isclose(found["d"], 0)


def test_unit_switch(pages: dict[str, Path], tmp_path: Path) -> None:
    script = 'key("q"); await settle(); return { unit: $("bUnit").textContent, one: fmtLen(25.4) };'
    assert _act(pages, tmp_path, script) == {"unit": "mil", "one": "1000.00 mil"}


def test_cross_probe(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const p = pad("U1-1"); const e = at(p.x, p.y);
    cv.dispatchEvent(new MouseEvent("dblclick", e));
    for (let k = 0; k < 100 && !(S.kind === "schematic" && SCH.selComp >= 0); k++) await settle();
    return { doc: DOC.name, kind: S.kind, ref: SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : null };
    """
    assert _act(pages, tmp_path, script) == {"doc": "blink.SchDoc", "kind": "schematic", "ref": "U1"}


def test_a_table_survives_a_resize(pages: dict[str, Path], tmp_path: Path) -> None:
    """A resize of the view's area fits the view, and a table scene (c0190) has nothing to fit: the page must
    not fail (seen once in CI, where the resize observer fired after the output job's page opened)."""
    script = (
        "fitted = false; resize(); await settle(); return S.kind;"  # what the ResizeObserver of #wrap calls
    )
    (reply,) = run([job("table", pages["output_job"], tmp_path, script=EVENTS + script, shot="")], tmp_path)
    assert reply["errors"] == [] and reply["result"] == "table"


@pytest.mark.parametrize("tag", ("input", "select", "textarea", "editable-child"))
def test_shortcuts_leave_form_controls_alone(pages: dict[str, Path], tmp_path: Path, tag: str) -> None:
    """The global M shortcut must not run during form navigation or text editing (c0233)."""
    script = """
    const host = document.createElement(TAG === "editable-child" ? "div" : TAG);
    let target = host;
    if (TAG === "editable-child") {
      host.contentEditable = "true"; target = document.createElement("span");
      target.textContent = "edit here"; host.appendChild(target);
    }
    document.body.appendChild(host); host.focus();
    target.dispatchEvent(new KeyboardEvent("keydown", {key: "m", bubbles: true}));
    const inForm = st.measure;
    host.remove(); key("m");
    return {inForm, outside: st.measure};
    """.replace("TAG", repr(tag))
    assert _act(pages, tmp_path, script) == {"inForm": False, "outside": True}


@pytest.mark.parametrize("modifier", ("ctrlKey", "metaKey", "altKey", "isComposing", "prevented"))
def test_shortcuts_respect_browser_and_composition(
    pages: dict[str, Path], tmp_path: Path, modifier: str
) -> None:
    script = """
    const opts = {key: "m", bubbles: true, cancelable: true};
    if (MODIFIER !== "prevented") opts[MODIFIER] = true;
    const e = new KeyboardEvent("keydown", opts);
    if (MODIFIER === "prevented") e.preventDefault();
    window.dispatchEvent(e);
    const modified = st.measure;
    window.dispatchEvent(new KeyboardEvent("keydown", {key: "M", shiftKey: true, bubbles: true}));
    return {modified, edge: st.edge};
    """.replace("MODIFIER", repr(modifier))
    assert _act(pages, tmp_path, script) == {"modified": False, "edge": True}


@pytest.mark.parametrize("width", (390, 760, 1100))
def test_sidebar_and_toolbar_fit_the_viewport(pages: dict[str, Path], tmp_path: Path, width: int) -> None:
    script = """
    const size = () => ({
      canvas: $("wrap").getBoundingClientRect().width,
      sidebar: getComputedStyle($("side")).display,
      sidebarWidth: $("side").getBoundingClientRect().width,
      toggle: getComputedStyle($("bSidebar")).display,
      expanded: $("bSidebar").getAttribute("aria-expanded"),
      toolbarWidth: $("top").clientWidth, toolbarContent: $("top").scrollWidth,
      right: $("dockRight").getBoundingClientRect().width,
        bottom: $("dockBottom").getBoundingClientRect().height
    });
    const initial = size(); $("bSidebar").click(); await settle(); const opened = size();
    key("Escape"); await settle(); const closed = size();
    return {initial, opened, closed};
    """
    (reply,) = run(
        [job("narrow", pages["blink_project"], tmp_path, script=EVENTS + script, shot="", width=width)],
        tmp_path,
    )
    assert reply["errors"] == [], reply["errors"]
    initial, opened, closed = (reply["result"][key] for key in ("initial", "opened", "closed"))
    if width <= 760:
        assert initial["sidebar"] == closed["sidebar"] == "none"
        assert initial["expanded"] == closed["expanded"] == "false"
        assert opened["sidebar"] == "flex" and opened["expanded"] == "true"
        assert initial["toggle"] != "none"
        assert opened["sidebarWidth"] <= width - 32
        for state in (initial, opened, closed):
            assert state["canvas"] == width
            assert state["toolbarContent"] <= state["toolbarWidth"]
    else:  # scenario "Desktop remains unchanged" (c0245): the left dock keeps 260 px, the right dock is shown
        assert initial["sidebar"] == "flex" and initial["sidebarWidth"] == 260
        assert initial["toggle"] == "none" and initial["right"] == 240 and initial["bottom"] > 0
        assert initial["canvas"] == width - 260 - 240


@pytest.mark.parametrize("scene", ("table", "unloaded"))
def test_sidebar_escape_without_a_cad_scene(pages: dict[str, Path], tmp_path: Path, scene: str) -> None:
    """Navigation remains dismissible on non-CAD documents and while a scene is loading."""
    script = """
    const initialKind = S.kind;
    if (SCENE === "unloaded") S = null;
    $("bSidebar").click(); await settle();
    const opened = $("bSidebar").getAttribute("aria-expanded");
    key("Escape"); await settle();
    return {initialKind, opened, closed: $("bSidebar").getAttribute("aria-expanded"),
      display: getComputedStyle($("side")).display, focused: document.activeElement.id};
    """.replace("SCENE", repr(scene))
    (reply,) = run(
        [job("sidebar", pages["output_job"], tmp_path, script=EVENTS + script, shot="", width=390)],
        tmp_path,
    )
    assert reply["errors"] == [], reply["errors"]
    assert reply["result"] == {
        "initialKind": "table",
        "opened": "true",
        "closed": "false",
        "display": "none",
        "focused": "bSidebar",
    }


def test_unbound_combination_passes_through(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "An unbound combination passes through" (c0245): Alt+M runs nothing and is not prevented."""
    script = """
    const e = new KeyboardEvent("keydown", { key: "m", code: "KeyM", altKey: true, bubbles: true,
      cancelable: true });
    window.dispatchEvent(e);
    return { measure: st.measure, prevented: e.defaultPrevented };
    """
    assert _act(pages, tmp_path, script) == {"measure": False, "prevented": False}
