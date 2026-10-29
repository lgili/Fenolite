# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checks run from the page in Chromium, with stubbed run routes (capability board-viewer, "Run progress and
cancel", "Run results in the review" and "Runs only on request in a live server"; change c0245)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import _cli, browser_missing, job, run

pytestmark = pytest.mark.needs_browser
ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "tests/data/kicad/board/two_layer.kicad_pcb"

STUB = """
const calls = [];
const reply = (status, data) => ({ok: status < 400, status, json: async () => data});
const RUNNING = {job:"j1", state:"running", command:"check", doc:DOC.id, elapsed:1.4,
  progress:[{command:"check", event:"step", step:"drc.kicad"}]};
const EVIDENCE = "KICAD-VERIFIED(kicad-cli 10.0.7)";
const FINDING = {code:"kicad.drc.clearance", severity:"error", message:"Clearance violation",
  where:"@10,12", stage:"drc.kicad", evidence:EVIDENCE, layer:null, at:[10000,12000],
  box:[10000,12000,10000,12000]};
const STAGE = {name:"drc.kicad", state:"failed", status:"errors", evidence:EVIDENCE, reasons:[],
  counts:{error:1, warning:0, info:0}, limits:null};
const DONE = {job:"j1", state:"done", command:"check", doc:DOC.id, exit:5, elapsed:2.0, progress:[],
  envelope:{issues:[{code:"kicad.drc.clearance"}]},
  check:{findings:[FINDING], counts:{error:1, warning:0, info:0}, placed:1, notes:[], stages:[]},
  review:{note:"Recorded results.", binding:null, operation_findings:[], stages:[], cards:[
    {id:"read", title:"Read document", state:"passed", stages:[], missing:[], evidence:"INFERRED"},
    {id:"drc", title:"Board rules (DRC)", state:"failed", missing:[], stages:[STAGE]}]}};
const CANCELLED = {...RUNNING, state:"cancelled", exit:1, error:{code:"FEN-1003", message:"cancelled"}};
const OFFER = {enabled:true, busy:null, commands:{check:{options:{stages:{
  choices:["drc.kicad", "copper.clearance"], default:["copper.clearance"], altium:[]}}}}};
let reads = 0, final = DONE;
window.fetch = async (url, init) => {
  const header = init && init.headers ? init.headers["X-Fenolite-Run"] : null;
  calls.push([String(url), init && init.method || "GET", header]);
  if (url === "runs") return reply(200, OFFER);
  if (url === "run") return reply(202, {job:"j1"});
  if (url === "run/j1/cancel") { final = CANCELLED; return reply(202, {job:"j1"}); }
  if (url === "run/j1") return reply(200, ++reads < 2 ? RUNNING : final);
  return reply(404, {});
};
const until = async test => {
  for (let k = 0; k < 100; k++) { if (test()) return true; await new Promise(r => setTimeout(r, 50)); }
  return false;
};
await runsInit();
$("bProjectReview").click();
"""


@pytest.fixture
def board_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if reason := browser_missing():
        pytest.skip(reason)
    monkeypatch.chdir(tmp_path)
    args = ("view", str(BOARD), "--no-models", "--no-review", "--export", "board.html", "--json")
    plan = _cli(*args, "--dry-run")["result"]["plan_id"]
    _cli(*args, "--confirm", "--plan", plan)
    return tmp_path / "board.html"


def _live(page: Path, tmp_path: Path) -> Path:
    html = page.read_text(encoding="utf-8")
    assert "const LIVE = false;" in html
    live = tmp_path / "live.html"
    live.write_text(
        html.replace("const LIVE = false;", "window.setInterval = () => 0; const LIVE = true;"), "utf-8"
    )
    return live


def _act(page: Path, tmp_path: Path, script: str) -> Any:
    (reply,) = run([job("run", page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_run_drc_from_its_card(board_page: Path, tmp_path: Path) -> None:
    """Scenario "A failed DRC card from a run": the strip shows the progress and Cancel, then the card reads
    Failed with the stage's evidence and one marker is placed at the point."""
    script = (
        STUB
        + """
const before = $("reviewCards").querySelector('[data-card="drc"]').textContent;
$("reviewCards").querySelector('button[data-run-card="drc"]').click();
await until(() => !$("runStrip").hidden && $("runStrip").className === "running" && reads >= 1);
const strip = $("runStrip").textContent, cancel = !!$("runCancel"), disabled = $("runChecks").disabled;
await until(() => $("runStrip").className === "done");
const card = $("reviewCards").querySelector('[data-card="drc"]').textContent;
return {before, strip, cancel, disabled, card, done:$("runStrip").textContent, marker:S.check.findings[0].at,
  run:calls.find(c => c[0] === "run"), messages:$("msgTitle").textContent};
"""
    )
    result = _act(_live(board_page, tmp_path), tmp_path, script)
    assert "Not run" in result["before"]
    assert (
        "check" in result["strip"]
        and "drc.kicad" in result["strip"]
        and result["cancel"]
        and result["disabled"]
    )
    assert "Failed" in result["card"] and "KICAD-VERIFIED(kicad-cli 10.0.7)" in result["card"]
    assert result["marker"] == [10, 12] and "1 error" in result["messages"]
    assert result["run"] == ["run", "POST", "1"] and "exit 5" in result["done"]


def test_run_cancelled_changes_nothing(board_page: Path, tmp_path: Path) -> None:
    """Scenario "Cancel a blocked run" on the page: the cards stay as they were and the strip says so."""
    script = (
        STUB
        + """
const before = $("reviewCards").textContent;
$("runChecks").click();
await until(() => !!$("runCancel"));
$("runCancel").click();
await until(() => $("runStrip").className === "cancelled");
return {strip:$("runStrip").textContent, same:$("reviewCards").textContent === before, check:S.check || null};
"""
    )
    result = _act(_live(board_page, tmp_path), tmp_path, script)
    assert "nothing changed" in result["strip"] and result["same"] and result["check"] is None


def test_run_controls_absent_on_an_exported_page(board_page: Path, tmp_path: Path) -> None:
    """Scenario "An exported page": no Run control and no request to the run routes."""
    script = """
const calls = [], real = window.fetch;
window.fetch = (url, init) => { calls.push(String(url)); return real(url, init); };
await runsInit();
$("bProjectReview").click();
return {buttons:$("projectReview").querySelectorAll("button.runCard").length, panel:$("runPanel").hidden,
  calls, text:$("reviewCards").textContent};
"""
    result = _act(board_page, tmp_path, script)
    assert result["buttons"] == 0 and result["panel"] is True and result["calls"] == []
    assert "--check FILE" in result["text"]
