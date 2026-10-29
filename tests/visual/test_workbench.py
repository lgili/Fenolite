# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The workbench of the viewer page (change c0245): frame budgets, and later the shell, layouts, keymaps,
selection, linked messages and provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _budget import SCRIPT, summary
from _visual import job, run

pytestmark = pytest.mark.needs_browser


def test_budget_baseline(stress_page: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Task 0.2: the page's frame, cursor and open times on the stress board, printed for the record."""
    (reply,) = run([job("budget", stress_page, tmp_path, script=SCRIPT, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["prims"] > 20_000
    assert result["frame_p95_ms"] > 0 and result["open_ms"] > 0
    (tmp_path / "budget.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with capsys.disabled():
        print(f"\nc0245 budget baseline: {summary(result)}")


EVENTS = """
const r = cv.getBoundingClientRect();
const at = (x, y) => { const [X, Y] = w2s(x, y);
return { clientX: r.left + X, clientY: r.top + Y, bubbles: true, view: window }; };
const click = (x, y) => { cv.dispatchEvent(new MouseEvent("mousemove", at(x, y)));
cv.dispatchEvent(new MouseEvent("mousedown", at(x, y)));
cv.dispatchEvent(new MouseEvent("mouseup", at(x, y))); };
const key = (k, o) => window.dispatchEvent(new KeyboardEvent("keydown", Object.assign({ key: k,
  bubbles: true, cancelable: true }, o || {})));
const pad = label => S.pads.find(p => p.label === label);
const settle = () => new Promise(ok => setTimeout(ok, 50));
const groupOf = id => { const f = findPanel(id); return f ? f[0] : null; };
"""


def _act(page: Path, tmp_path: Path, script: str, *, width: int = 1100, height: int = 700) -> dict:
    (reply,) = run(
        [job("workbench", page, tmp_path, script=EVENTS + script, shot="", width=width, height=height)],
        tmp_path,
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_shell(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "The frame of a board": eleven menus, seven status fields, today's panels in the docks."""
    script = """
    const p = pad("R1-1"); click(p.x, p.y); await settle();
    const menus = [...document.querySelectorAll("#menubar .menubtn")].map(b => b.textContent);
    const fields = ["coord", "sDelta", "sGrid", "sNet", "cur", "sTool",
      "sEvidence"].map(id => $(id).textContent);
    const docked = ["projects", "pcb", "findings", "notes", "properties", "messages",
      "layers"].map(id => [id, groupOf(id)]);
    return { menus, fields, docked, title: $("fname").textContent, info: $("info").textContent,
      compsInPcb: $("pPcb").contains($("compList")), netsInPcb: $("pPcb").contains($("netList")) };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["menus"] == [
        "File",
        "Edit",
        "View",
        "Place",
        "Design",
        "Roles",
        "Route",
        "Tools",
        "Reports",
        "Window",
        "Help",
    ]
    assert all(result["fields"]), result["fields"]
    assert dict(result["docked"]) == {
        "projects": "left",
        "pcb": "left",
        "findings": "left",
        "notes": "right",
        "properties": "right",
        "messages": "bottom",
        "layers": "left",
    }
    assert result["compsInPcb"] and result["netsInPcb"]
    assert "Net" in result["info"] and result["title"] == "two_layer.kicad_pcb"


def test_menu_runs_its_command(pages: dict[str, Path], tmp_path: Path) -> None:
    """A menu entry shows its key and runs the command the key runs."""
    script = """
    document.querySelector('#menubar [data-menu="View"]').click(); await settle();
    const items = [...document.querySelectorAll(".menu .mitem")].map(b => [b.dataset.cmd,
      b.querySelector(".mkey").textContent]);
    document.querySelector('.menu [data-cmd="view.units"]').click(); await settle();
    return { items, unit: $("bUnit").textContent, open: !!document.querySelector(".menu") };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    keys = dict(result["items"])
    assert keys["view.units"] == "Q" and keys["view.fit"] == "F" and keys["view.flip"] == "B"
    assert result["unit"] == "mil" and result["open"] is False


def test_docks(pages: dict[str, Path], tmp_path: Path) -> None:
    """Panels move by their panel menu, tabs switch by arrows, a dock edge resizes by arrows."""
    script = """
    const head = [...document.querySelectorAll("#dockBottom .pgroup")].find(g => g.contains($("pMessages")));
    head.querySelector(".pmenu").click(); await settle();
    const item = [...document.querySelectorAll(".menu .mitem")]
      .find(b => b.textContent.includes("Move to Right Dock"));
    item.click(); await settle();
    const moved = groupOf("messages");
    const tab = document.querySelector('[data-tab="pcb"]'); tab.focus();
    tab.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); await settle();
    const active = findPanel("pcb")[2].active;
    const edge = document.querySelector("#side > .dsplit"); const before = LAYOUT.docks.left.size;
    edge.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    return { moved, active, before, after: LAYOUT.docks.left.size,
      canvas: $("wrap").getBoundingClientRect().width };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["moved"] == "right"
    assert result["active"] == "layers"
    assert result["after"] == result["before"] + 10


def test_layout(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A layout survives a reload": the layout kept in the browser, then Reset Layout."""
    script = """
    movePanel("messages", "right", 0); await settle();
    const stored = JSON.parse(localStorage.getItem("fenolite.view.layout.board"));
    LAYOUT = null; setWorkspace("board", true); await settle();
    const afterReload = groupOf("messages");
    runCommand("window.reset-layout"); await settle();
    return { schema: stored.schema, afterReload, afterReset: groupOf("messages") };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result == {"schema": "fenolite.view_layout.v0", "afterReload": "right", "afterReset": "bottom"}


def test_narrow_drawer_holds_every_dock(pages: dict[str, Path], tmp_path: Path) -> None:
    """At 390 px every dock collapses into the drawer; Escape closes it."""
    script = """
    $("bSidebar").click(); await settle();
    const holds = ["pProjects", "pProperties", "pMessages"].map(id => $("side").contains($(id)));
    const docks = [getComputedStyle($("dockRight")).display, getComputedStyle($("dockBottom")).display];
    key("Escape"); await settle();
    return { holds, docks, closed: getComputedStyle($("side")).display,
      canvas: $("wrap").getBoundingClientRect().width };
    """
    result = _act(pages["blink_project"], tmp_path, script, width=390)
    assert result == {"holds": [True, True, True], "docks": ["none", "none"], "closed": "none", "canvas": 390}


def test_float(tmp_path: Path) -> None:
    """Task 2.5: a served panel window shows that panel alone and follows the selection of the others."""
    import shutil
    import threading

    from fenolite.backends import registry
    from fenolite.view import server
    from fenolite.view.project import load_tree
    from fenolite.view.scene import build_scene

    board = tmp_path / "board.kicad_pcb"
    shutil.copy(
        Path(__file__).resolve().parents[1] / "data" / "kicad" / "board" / "two_layer.kicad_pcb", board
    )

    def build(path: Path) -> dict:
        backend = registry.for_path(path)
        return build_scene(backend.read(path).design, backend, name=path.name, data=path.read_bytes())  # type: ignore[union-attr]

    live = server.Live(load_tree(board), build)
    httpd = server.serve(live, 0)
    stop = threading.Event()
    thread = threading.Thread(target=server.run, args=(live, httpd), kwargs={"until": stop}, daemon=True)
    thread.start()
    script = """
    const shown = [...$("side").querySelectorAll(".panel-body")].map(e => e.dataset.panel);
    new BroadcastChannel("fenolite-view").postMessage({ net: "GND" });
    await new Promise(ok => setTimeout(ok, 200));
    return { float: document.body.classList.contains("float"), shown, info: $("info").textContent,
      canvas: getComputedStyle($("wrap")).display, title: document.title };
    """
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/panel/properties"
        (reply,) = run(
            [job("float", tmp_path / "none.html", tmp_path, script=script, shot="", url=url)], tmp_path
        )
    finally:
        stop.set()
        thread.join(timeout=10)
        httpd.server_close()
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["float"] is True and result["shown"] == ["properties"] and result["canvas"] == "none"
    assert "GND" in result["info"] and result["title"].startswith("Properties")
