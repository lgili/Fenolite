# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing actions of the page in Chromium, with stubbed routes (capability board-viewer, "Writing actions are
opt-in", "Plan review before a write", "Confirm by plan", "Receipt and undo"; change c0246)."""

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
const OFFER = {enabled:true, token:"t".repeat(32), receipts:[], actions:{
  silk:{title:"Silkscreen", command:"silk", available:true, options:{
    designators:{type:"boolean", default:false, label:"place the designators"},
    clip:{type:"boolean", default:false, label:"cut silkscreen"}}},
  waive:{title:"Waive a DRC finding", command:"check", available:true, note:"stored as a KiCad DRC exclusion",
    options:{finding:{type:"finding", required:true}, reason:{type:"reason", required:true}}}}};
const WRITE = {path:"two_layer.kicad_pcb", kind:"kicad_pcb", bytes:5883, sha256:"a".repeat(64),
  replaces:"b".repeat(64)};
const PREVIEW = {kind:"board", added:[], removed:[], moved:[{ref:"R1", from:[10000,10000], to:[12000,10000]}],
  changes:[{kind:"moved", text:"R1 moved by 2.000 mm", box:[10000,10000,12000,10000]}],
  counts:{added:0, removed:0, moved:1, changed:0, zone:0}, old:{name:"x", sha256:""}};
const ISSUE = {code:"silk.no-place", severity:"warning", message:"D1 keeps its text"};
let planReply = null, confirmReply = null, plans = 0;
const plan = (extra) => ({job:"p1", kind:"plan", state:"done", command:"silk", action:"silk", doc:DOC.id,
  exit:0, progress:[], envelope:{issues:[ISSUE], evidence:{level:"INFERRED"}}, preview:PREVIEW,
  plan:{plan_id:"0123456789abcdef", writes:[WRITE], issues:[ISSUE], evidence:{level:"INFERRED"},
    confirmable:true}, ...extra});
window.fetch = async (url, init) => {
  const u = String(url), headers = init && init.headers || {};
  calls.push([u, init && init.method || "GET", headers["X-Fenolite-Action"] || null,
    headers["X-Fenolite-Token"] || null]);
  if (u.startsWith("actions?")) return reply(200, OFFER);
  if (u === "runs") return reply(200, {enabled:false, reason:"stub", commands:{}});
  if (u === "action/plan") { plans++; return reply(202, {job:"p1"}); }
  if (u === "action/confirm") return reply(202, {job:"c1"});
  if (u === "run/p1") return reply(200, planReply);
  if (u === "run/c1") return reply(200, confirmReply);
  if (u.startsWith("scene/")) return reply(200, JSON.parse(JSON.stringify(RAWSCENE)));
  return reply(404, {});
};
const until = async test => {
  for (let k = 0; k < 100; k++) { if (test()) return true; await new Promise(r => setTimeout(r, 50)); }
  return false;
};
const RAWSCENE = await unpackScene(EMBED.scenes[DOC.id]);
$("bProjectReview").click();
await until(() => ACTS.enabled && !$("actionPanel").hidden);
const openSilk = () => {
  const d = $("actionPanel").querySelector('details[data-action="silk"]'); d.open = true;
  d.querySelector('[data-opt="designators"]').checked = true; d.querySelector(".actPlan").click(); };
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
    live = tmp_path / "live.html"
    live.write_text(
        html.replace("const LIVE = false;", "window.setInterval = () => 0; const LIVE = true;"), "utf-8"
    )
    return live


def _act(page: Path, tmp_path: Path, script: str) -> Any:
    (reply,) = run([job("actions", page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_plan_confirm_and_receipt(board_page: Path, tmp_path: Path) -> None:
    """A plan shows its files, issues and board overlay; Confirm shows the receipt and reads the board."""
    script = (
        STUB
        + """
planReply = plan({});
confirmReply = {job:"c1", kind:"confirm", state:"done", command:"silk", action:"silk", doc:DOC.id, exit:0,
  progress:[], envelope:{}, receipt:{id:"fedcba9876543210", written:[{path:"two_layer.kicad_pcb",
  sha256:"a".repeat(64)}], backup:["two_layer.kicad_pcb.bak"]}};
openSilk();
await until(() => $("planTitle").textContent.startsWith("Review the plan"));
const dialog = {open:$("planDialog").open, text:$("planBody").textContent,
  confirm:!$("planConfirm").disabled, moved:S.diff && S.diff.moved.length, diffOn:st.diff,
  changes:$("diffTitle").textContent};
const post = calls.find(c => c[0] === "action/plan");
$("planConfirm").click();
await until(() => $("planTitle").textContent.startsWith("Written"));
const receipt = $("planBody").textContent, reread = calls.filter(c => c[0].startsWith("scene/")).length;
const restored = S.diff || null;
$("planFoot").querySelector("button.primary").click();
return {dialog, post, receipt, reread, restored, closed:!$("planDialog").open};
"""
    )
    result = _act(_live(board_page, tmp_path), tmp_path, script)
    dialog = result["dialog"]
    assert dialog["open"] and dialog["confirm"] and dialog["moved"] == 1 and dialog["diffOn"]
    assert "two_layer.kicad_pcb" in dialog["text"] and "silk.no-place" in dialog["text"]
    assert "INFERRED" in dialog["text"] and "1 change" in dialog["text"] and "staged" in dialog["changes"]
    assert result["post"] == ["action/plan", "POST", "1", "t" * 32]
    assert "fedcba9876543210" in result["receipt"] and "two_layer.kicad_pcb.bak" in result["receipt"]
    assert result["reread"] >= 1 and result["restored"] is None and result["closed"]


def test_changed_file_offers_review_again(board_page: Path, tmp_path: Path) -> None:
    """``FEN-4002``: the page says the file changed and Review again plans once more."""
    script = (
        STUB
        + """
planReply = plan({});
confirmReply = {job:"c1", kind:"confirm", state:"failed", command:"silk", action:"silk", doc:DOC.id, exit:4,
  progress:[], error:{code:"FEN-4002", message:"a target changed since the plan"}, review_again:true,
  hint:"the file changed since the review: review the plan again"};
openSilk();
await until(() => !!$("planConfirm"));
$("planConfirm").click();
await until(() => $("planTitle").textContent.startsWith("The file changed"));
const text = $("planBody").textContent, before = plans;
[...$("planFoot").querySelectorAll("button")].find(b => b.textContent === "Review again").click();
await until(() => plans > before && $("planTitle").textContent.startsWith("Review the plan"));
return {text, again:plans - before};
"""
    )
    result = _act(_live(board_page, tmp_path), tmp_path, script)
    assert "FEN-4002" in result["text"] and "review the plan again" in result["text"]
    assert result["again"] == 1


def test_error_finding_disables_confirm(board_page: Path, tmp_path: Path) -> None:
    script = (
        STUB
        + """
const bad = {code:"silk.check-failed", severity:"error", message:"a designator overlaps a pad"};
planReply = plan({plan:{plan_id:"0123456789abcdef", writes:[WRITE], issues:[bad], evidence:{level:"INFERRED"},
  confirmable:false}});
openSilk();
await until(() => !!$("planConfirm"));
return {disabled:$("planConfirm").disabled, text:$("planBody").textContent};
"""
    )
    result = _act(_live(board_page, tmp_path), tmp_path, script)
    assert (
        result["disabled"]
        and "Confirm is disabled" in result["text"]
        and "silk.check-failed" in result["text"]
    )


def test_no_action_control_unless_enabled(board_page: Path, tmp_path: Path) -> None:
    """An exported page asks nothing and shows no action; a live page whose server refuses shows none."""
    exported = """
const calls = [], real = window.fetch;
window.fetch = (url, init) => { calls.push(String(url)); return real(url, init); };
$("bProjectReview").click();
await new Promise(r => setTimeout(r, 200));
return {panel:$("actionPanel").hidden, calls, dialog:$("planDialog").open};
"""
    result = _act(board_page, tmp_path, exported)
    assert result == {"panel": True, "calls": [], "dialog": False}
    refused = """
window.fetch = async url => ({ok:true, status:200, json:async () => String(url).startsWith("actions")
  ? {enabled:false, reason:"this page was served without --allow-actions", actions:{}, receipts:[]}
  : {enabled:false, commands:{}}});
$("bProjectReview").click();
await new Promise(r => setTimeout(r, 300));
return {panel:$("actionPanel").hidden, waive:!!document.getElementById("actWaive")};
"""
    assert _act(_live(board_page, tmp_path), tmp_path, refused) == {"panel": True, "waive": False}
