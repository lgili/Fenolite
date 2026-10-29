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


BUDGET = {"frame_p95_ms": 52.9, "cursor_p95_ms": 4.0, "open_ms": 2500.0, "message_ms": 100.0}
"""The budgets of the `viewer` job (design, decision 7); task 0.2 set the frame budget at 52.9 ms."""
VIEWPORT = {"width": 1340, "height": 860}
"""A viewport whose canvas, beside the docks, is 840 x 606 px: the canvas of task 0.2's measurement."""


def test_budget_baseline(stress_page: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Task 0.2: the page's frame, cursor and open times on the stress board, printed for the record."""
    (reply,) = run([job("budget", stress_page, tmp_path, script=SCRIPT, shot="", **VIEWPORT)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["prims"] > 20_000
    assert result["full_p95_ms"] > 0 and result["open_ms"] > 0
    (tmp_path / "budget.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with capsys.disabled():
        print(f"\nc0245 budget: {summary(result)}")


def test_budget(stress_page: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "The budget in CI" (H-G-WB-FRAME, H-G-WB-CURSOR, H-G-WB-OPEN): within the budgets, and no
    board layer painted during pointer moves or mouse pans and zooms."""
    (reply,) = run([job("budget", stress_page, tmp_path, script=SCRIPT, shot="", **VIEWPORT)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    with capsys.disabled():
        print(f"\nc0245 budget check: {summary(result)}")
    assert (result["width"], result["height"]) == (840, 606)
    assert result["board_paints_during_moves"] == 0 and result["interactive_board_paints"] == 0
    over = {k: (round(result[k], 1), limit) for k, limit in BUDGET.items() if result[k] > limit}
    assert over == {}


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


FINDINGS = """
const finding = (code, sev, where, at, layer, evidence) => ({ code, severity: sev,
  message: code + " on " + where,
  hint: "", where, stage: "test.stage", evidence: evidence || "INFERRED", layer: layer || null, at,
    box: null });
const inject = list => { S.check = { findings: list, counts: { error: 0, warning: 0, info: 0 }, notes: [],
  explain: {} };
  for (const x of list) S.check.counts[x.severity]++; buildMessages(); draw(); };
const row = code => [...$("msgBody").querySelectorAll("tr")]
  .find(t => t.dataset.key && t.textContent.includes(code));
"""


def test_selection(buck_page: Path, tmp_path: Path) -> None:
    """Scenario "Five ways to one net": canvas, Nets panel, Net drop-down, a Messages row and the address."""
    script = (
        FINDINGS
        + """
    const sw = S.nets.indexOf("SW"), p = S.pads.find(q => q.net === "SW"), hashes = {};
    const clear = async () => { key("Escape"); await settle(); };
    click(p.x, p.y); await settle(); hashes.canvas = selectionHash(); await clear();
    $("netFilter").value = "SW"; $("netFilter").dispatchEvent(new Event("input"));
    [...$("netList").querySelectorAll(".navi")].find(d => d.textContent.startsWith("SW")).click();
    await settle();
    hashes.nets = selectionHash(); await clear();
    $("netSel").value = String(sw); $("netSel").dispatchEvent(new Event("change")); await settle();
    hashes.dropdown = selectionHash(); await clear();
    inject([finding("test.net", "warning", "SW", [p.x, p.y])]); row("test.net").click(); await settle();
    hashes.message = selectionHash(); await clear();
    applySelect("net:SW"); await settle(); hashes.address = selectionHash();
    const shown = { status: $("sNet").textContent, drop: $("netSel").value,
      list: !!$("netList").querySelector(".navi.sel"), announce: $("announce").textContent };
    await clear();
    const cleared = { status: $("sNet").textContent, drop: $("netSel").value,
      list: !!$("netList").querySelector(".navi.sel"),
      row: !!$("msgBody").querySelector('tr[aria-selected="true"]'), hash: selectionHash() };
    return { hashes, shown, cleared, sw: String(sw) };
    """
    )
    result = _act(buck_page, tmp_path, script)
    hashes = set(result["hashes"].values())
    assert len(hashes) == 1 and '"SW"' in next(iter(hashes)), result["hashes"]
    assert result["shown"] == {
        "status": "Net SW",
        "drop": result["sw"],
        "list": True,
        "announce": "Selected net SW",
    }
    assert (
        result["cleared"]["status"] == ""
        and result["cleared"]["drop"] == ""
        and not result["cleared"]["list"]
    )
    assert not result["cleared"]["row"] and '"SW"' not in result["cleared"]["hash"]


def test_linked(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Both directions": a row frames its finding on its layer; its marker selects the row."""
    script = (
        FINDINGS
        + """
    const p = pad("D1-1");
    inject([finding("test.first", "error", "R1-1", [pad("R1-1").x, pad("R1-1").y], "F.Cu"),
            finding("test.second", "warning", "D1-1", [p.x, p.y], "B.Cu")]);
    fit(); await settle(); const t0 = performance.now(); row("test.second").click();
    const ms = performance.now() - t0;
    await settle();
    const framed = { cur: st.cur, dx: Math.abs(view.cx - p.x), dy: Math.abs(view.cy - p.y),
      info: $("info").textContent };
    key("Escape"); await settle(); fit(); await settle();
    click(p.x, p.y); await settle();
    const sel = $("msgBody").querySelector('tr[aria-selected="true"]');
    return { framed, ms, picked: sel ? sel.textContent : null };
    """
    )
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["framed"]["cur"] == "B.Cu" and result["framed"]["dx"] < 1 and result["framed"]["dy"] < 1
    assert "test.second" in result["framed"]["info"]
    assert result["picked"] and "test.second" in result["picked"]
    assert result["ms"] < 100


def test_explain(pages: dict[str, Path], tmp_path: Path) -> None:
    """M11: each Messages row shows its `fenolite explain` text on demand, in the page."""
    script = (
        FINDINGS
        + """
    inject([finding("test.first", "error", "R1-1", [pad("R1-1").x, pad("R1-1").y]), finding("test.other",
      "info", "x", null)]);
    S.check.explain = { "test.first": { meaning: "What it means.", fix: "How to fix it.",
      see: "docs/x.md" } };
    buildMessages(); row("test.first").querySelector("button.why").click(); await settle();
    const shown = $("msgBody").querySelector("tr.explain").textContent;
    row("test.other").querySelector("button.why").click(); await settle();
    const fallback = [...$("msgBody").querySelectorAll("tr.explain")].map(t => t.textContent);
    return { shown, fallback, noPos: row("test.other").textContent };
    """
    )
    result = _act(pages["kicad_board"], tmp_path, script)
    assert "What it means." in result["shown"] and "How to fix it." in result["shown"]
    assert any("fenolite explain test.other" in t for t in result["fallback"])
    assert "(no position)" in result["noPos"]


def test_provenance(pages: dict[str, Path], tmp_path: Path) -> None:
    """M1 and M8 before the Net Roles workspace: every value shown names its source and evidence, and the
    status bar shows the lowest evidence level on screen."""
    script = (
        FINDINGS
        + """
    const p = pad("R1-1"); click(p.x, p.y); await settle();
    const before = $("sEvidence").textContent;
    inject([finding("test.kicad", "error", "R1-1", [p.x, p.y], "F.Cu", "KICAD-VERIFIED(kicad-cli 10.0.7)"),
            finding("test.weak", "info", "R1-2", null, null, "UNVERIFIED")]);
    row("test.kicad").click(); await settle();
    const values = [...document.querySelectorAll("[data-value]")];
    const bad = values.filter(e => !e.dataset.source || !e.dataset.evidence).map(e => e.outerHTML);
    const digits = [];
    const w = document.createTreeWalker($("info"), NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (/\\d/.test(n.nodeValue) && !n.parentElement.closest("[data-value]")) digits.push(n.nodeValue);
    }
    return { count: values.length, bad, digits, before, after: $("sEvidence").textContent,
      tool: $("sTool").textContent };
    """
    )
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["count"] > 3 and result["bad"] == [] and result["digits"] == []
    assert result["before"] == "evidence INFERRED" and result["after"] == "evidence UNVERIFIED"
    assert "kicad-cli 10.0.7" in result["tool"]


def test_keymap(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "An accelerator sequence": V then F fits the board in the altium keymap; binding Ctrl+W in the
    Keyboard panel is refused."""
    script = """
    setKeymap("altium"); view.s = 77; view.cx = 0; view.cy = 0; draw();
    key("v"); const pending = $("keyPending").textContent; key("f"); await settle();
    const fitted = view.s !== 77, after = $("keyPending").textContent;
    document.querySelector('#menubar [data-menu="View"]').click(); await settle();
    const fitKey = document.querySelector('.menu [data-cmd="view.fit"] .mkey').textContent; closeMenu(false);
    runCommand("tools.keyboard"); await settle();
    const tr = $("kmTable").querySelector('tr[data-cmd="view.fit"]'); tr.querySelector(".kmedit").click();
    const cap = $("kmTable").querySelector(".kbcapture");
    cap.dispatchEvent(new KeyboardEvent("keydown", { key: "w", code: "KeyW", ctrlKey: true, bubbles: true,
      cancelable: true }));
    return { pending, fitted, after, fitKey, message: $("kmMessage").textContent,
      keys: keysOf(CMD.get("view.fit")) };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["pending"] == "V, …" and result["fitted"] and result["after"] == ""
    assert result["fitKey"] == "V, F"
    assert "belongs to the browser" in result["message"]
    assert result["keys"] == ["V F", "V D", "F", "Shift+F"]


def test_keyboard_panel(pages: dict[str, Path], tmp_path: Path) -> None:
    """A person's binding: captured in the Keyboard panel, run by its key, saved as a keymap file, reset."""
    script = """
    runCommand("tools.keyboard"); await settle();
    $("kmTable").querySelector('tr[data-cmd="place.measure"] .kmedit').click();
    const cap = () => $("kmTable").querySelector(".kbcapture");
    cap().dispatchEvent(new KeyboardEvent("keydown", { key: "K", code: "KeyK", shiftKey: true,
      bubbles: true, cancelable: true }));
    cap().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await settle();
    const doc = keymapDoc(),
      from = $("kmTable").querySelector('tr[data-cmd="place.measure"]').children[2].textContent;
    $("wrap").focus(); key("K", { shiftKey: true }); const measuring = st.measure; key("Escape");
    $("kmReset").click(); await settle();
    return { doc, from, measuring, after: keysOf(CMD.get("place.measure")),
      stored: JSON.parse(localStorage.getItem("fenolite.view.keymap")) };
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["doc"] == {
        "schema": "fenolite.view_keymap.v0",
        "base": "fenolite",
        "bindings": {"place.measure": ["Shift+K"]},
    }
    assert result["from"] == "your change" and result["measuring"] is True
    assert result["after"] == ["M", "Shift+M"] and result["stored"]["bindings"] == {}


def test_command_search(pages: dict[str, Path], tmp_path: Path) -> None:
    """Every command by its name from the keyboard: Ctrl+K, type, Enter."""
    script = """
    key("k", { ctrlKey: true }); await settle();
    const input = document.querySelector(".cmdsearch .cs-input"); input.value = "toggle units";
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); await settle();
    return { unit: $("bUnit").textContent, open: !!document.querySelector(".cmdsearch") };
    """
    assert _act(pages["kicad_board"], tmp_path, script) == {"unit": "mil", "open": False}


def test_cursor(stress_page: Path, tmp_path: Path) -> None:
    """Task 6.1: the crosshair and a measurement in progress are drawn on the overlay; moving the mouse
    while measuring paints no board layer."""
    script = """
    const rr = cv.getBoundingClientRect(), mv = (x, y) => cv.dispatchEvent(new MouseEvent("mousemove",
      { clientX: rr.left + x, clientY: rr.top + y, bubbles: true }));
    cv.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
    toggle("measure", "bMeasure"); mv(100, 100);
    const at100 = { clientX: rr.left + 100, clientY: rr.top + 100, bubbles: true };
    cv.dispatchEvent(new MouseEvent("mousedown", at100)); cv.dispatchEvent(new MouseEvent("mouseup", at100));
    let painted = 0; const paint0 = paintCache; paintCache = function () { painted++;
    return paint0.apply(this, arguments); };
    for (let i = 0; i < 50; i++) mv(120 + i * 5, 140 + i * 3);
    paintCache = paint0;
    const ov = $("ov").getContext("2d").getImageData(0, 0, $("ov").width, $("ov").height).data;
    let inked = 0; for (let i = 3; i < ov.length; i += 4) if (ov[i]) inked++;
    return { painted, inked, coord: $("coord").textContent, points: st.mpts.length };
    """
    result = _act(stress_page, tmp_path, script, width=1340, height=860)
    assert result["painted"] == 0 and result["inked"] > 500
    assert result["points"] == 1 and result["coord"].startswith("measure:")


def test_frame(stress_page: Path, tmp_path: Path) -> None:
    """Task 6.2: a mouse pan or zoom moves the last frame at once; once the hand rests, the board drawn
    again is the board a fresh draw gives, pixel for pixel."""
    script = """
    const rr = cv.getBoundingClientRect(), cx = rr.left + rr.width / 2, cy = rr.top + rr.height / 2;
    let painted = 0; const paint0 = paintCache; paintCache = function () { painted++;
    return paint0.apply(this, arguments); };
    for (let i = 0; i < 6;
    i++) cv.dispatchEvent(new WheelEvent("wheel", { clientX: cx, clientY: cy, deltaY: -120,
      bubbles: true, cancelable: true }));
    const during = painted; paintCache = paint0;
    await new Promise(ok => setTimeout(ok, 400));
    const settled = cv.toDataURL(); draw(); const fresh = cv.toDataURL();
    return { during, same: settled === fresh, zoom: view.s };
    """
    result = _act(stress_page, tmp_path, script, width=1340, height=860)
    assert result["during"] == 0 and result["same"] is True


def test_hit(stress_page: Path, tmp_path: Path) -> None:
    """Task 6.3: the spatial index picks what the full scan picked, at 500 points over the stress board."""
    script = """
    let differ = 0, hits = 0, tGrid = 0, tScan = 0; fit();
    for (let i = 0; i < 500; i++) {
      const X = 10 + (i * 37) % (W - 20), Y = 10 + (i * 53) % (H - 20);
      let t0 = performance.now(); const a = pick(X, Y); tGrid += performance.now() - t0;
      t0 = performance.now(); const b = pickScan(X, Y); tScan += performance.now() - t0;
      if ((a && a.pr) !== (b && b.pr) || (a && a.layer) !== (b && b.layer)) differ++; if (a) hits++;
    }
    return { differ, hits, grid_ms: tGrid / 500, scan_ms: tScan / 500 };
    """
    result = _act(stress_page, tmp_path, script, width=1340, height=860)
    assert result["differ"] == 0 and result["hits"] > 100
    assert result["grid_ms"] < result["scan_ms"]


@pytest.mark.parametrize(
    "name", ("altium_sheet", "footprint_library", "symbol_library", "draftsman", "output_job")
)
def test_other_workspaces(pages: dict[str, Path], tmp_path: Path, name: str) -> None:
    """Task 10.1: the scene kinds share docks and selection; reports and changes reach Messages."""
    script = """
    const kind = workspaceOf();
    setProjectReview(true);
    const docked = findPanel("review")[0] === "right" && $("projectReview").closest(".pgroup") !== null;
    setProjectReview(false);
    if (S.kind === "table") { await tableRow(0); }
    selectionChanged(); const selected = selectionState();
    return {kind, docked, selected, messages:!!findPanel("messages")};
    """
    result = _act(pages[name], tmp_path, script)
    assert result["docked"] and result["messages"]
    assert result["kind"] in ("sheet", "library", "drawing", "table")
    if result["kind"] in ("library", "drawing"):
        assert result["selected"]["item"]


def test_compare_and_recorded_messages(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    S.diff = {changes:[{kind:"changed",text:"Authored comparison",box:[1,1,2,2]}]};
    S.project_review = {operation_findings:[{code:"convert.loss",severity:"warning",
      message:"Authored operation",
      stage:"convert",evidence:"INFERRED"}]};
    buildMessages(); $("msgBody").querySelector('[data-key="change:0"]').click();
    const change = selectionState().finding;
    $("msgBody").querySelector('[data-key="operation:0"]').click();
    return {change, operation:selectionState().finding, text:$("info").textContent};
    """
    result = _act(pages["kicad_board"], tmp_path, script)
    assert result["change"] == "change:0" and result["operation"] == "operation:0"
    assert "No position" in result["text"]


def test_table_keyboard_selection(pages: dict[str, Path], tmp_path: Path) -> None:
    """Table selection is available before any pointer action and Escape clears the shared state."""
    script = """
    loadTable({kind:"table",meta:{name:"Authored table",backend:"altium",evidence:"INFERRED"},
      columns:["Value"],rows:[["first"],["second"]],docs:[],refs:[]});
    $("tblBody").querySelector("tr").dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
    const chosen = {row:selectionState().row, announcement:$("announce").textContent,
      marked:$("tblBody").querySelector('[aria-selected="true"]').dataset.i};
    key("Escape");
    return {chosen, cleared:selectionState().row};
    """
    result = _act(pages["output_job"], tmp_path, script)
    assert result["chosen"] == {"row": 0, "announcement": "Selected row 1", "marked": "0"}
    assert result["cleared"] == -1
