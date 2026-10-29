# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic browser request races (c0235); all scenes come from the authored blink project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

SETUP = """
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => {
  resolve = yes; reject = no;
}); return {promise, resolve, reject}; };
const a = allDocs().find(d => d.kind === "pcb" && d.viewable);
const b = allDocs().find(d => d.kind === "schematic" && d.viewable);
const originalSceneOf = sceneOf;
const sa = await sceneOf(a), sb = await sceneOf(b);
const named = (sc, name) => ({...sc, meta: {...sc.meta, name}});
const reply = (version, updated) => ({ok:true, json:async () => ({version, updated})});
"""


def _act(pages: dict[str, Path], tmp_path: Path, script: str, *, live: bool = False) -> Any:
    page = pages["blink_project"]
    if live:
        # Keep authored startup scenes; enable live fetches and drive polls explicitly in the test.
        html = page.read_text(encoding="utf-8")
        assert "const LIVE = false;" in html
        html = html.replace("const LIVE = false;", "window.setInterval = () => 0; const LIVE = true;")
        page = tmp_path / "live.html"
        page.write_text(html, encoding="utf-8")
    (result,) = run([job("navigation", page, tmp_path, script=SETUP + script, shot="")], tmp_path)
    assert result["errors"] == [], result["errors"]
    return result["result"]


@pytest.mark.parametrize("outcome", ("success", "failure", "empty"))
def test_older_navigation_cannot_cover_new_document(
    pages: dict[str, Path], tmp_path: Path, outcome: str
) -> None:
    script = """
const pending = deferred();
sceneOf = d => d.id === a.id ? pending.promise : Promise.resolve(sb);
const old = openDoc(a); await openDoc(b);
if (OUTCOME === "failure") pending.reject(new Error("old read failed"));
else pending.resolve(OUTCOME === "empty" ? null : sa);
await old;
return {selected:DOC.name, displayed:S.meta.name, card:$("doccard").style.display};
""".replace("OUTCOME", repr(outcome))
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "card": "none",
    }


def test_reselecting_same_document_keeps_latest_request(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
const pending = deferred(); let reads = 0;
sceneOf = d => d.id === b.id ? Promise.resolve(sb)
  : ++reads === 1 ? pending.promise : Promise.resolve(named(sa,"new A"));
const old = openDoc(a); await openDoc(b); await openDoc(a);
pending.resolve(named(sa,"old A")); await old;
return {selected:DOC.name, displayed:S.meta.name};
"""
    assert _act(pages, tmp_path, script) == {"selected": "blink.PcbDoc", "displayed": "new A"}


@pytest.mark.parametrize("old_first", (False, True))
def test_older_decode_cannot_poison_cache(pages: dict[str, Path], tmp_path: Path, old_first: bool) -> None:
    script = """
const first = deferred(), second = deferred();
unpackScene = raw => raw.order === 1 ? first.promise : second.promise;
SCENES.delete(a.id); RAW.set(a.id,{order:1}); const old = sceneOf(a);
RAW.set(a.id,{order:2}); const current = sceneOf(a);
let rawKept = true;
if (OLD_FIRST) { first.resolve(named(sa,"old A")); await old; rawKept = RAW.has(a.id); }
second.resolve(named(sa,"new A")); await current;
if (!OLD_FIRST) { first.resolve(named(sa,"old A")); await old; }
await openDoc(a);
return {cached:SCENES.get(a.id).meta.name, displayed:S.meta.name, rawKept};
""".replace("OLD_FIRST", str(old_first).lower())
    assert _act(pages, tmp_path, script) == {"cached": "new A", "displayed": "new A", "rawKept": True}


@pytest.mark.parametrize("outcome", ("success", "failure"))
def test_poll_of_previous_document_cannot_change_current_status(
    pages: dict[str, Path], tmp_path: Path, outcome: str
) -> None:
    script = """
await openDoc(a); st.version="a0";
const pending = deferred(); window.fetch = () => pending.promise;
const old = poll(); await openDoc(b); st.version="b0"; $("live").textContent="B status";
if (OUTCOME === "failure") pending.reject(new Error("old request failed"));
else pending.resolve(reply("a1","old update"));
await old;
return {selected:DOC.name, displayed:S.meta.name, version:st.version, status:$("live").textContent};
""".replace("OUTCOME", repr(outcome))
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "version": "b0",
        "status": "B status",
    }


@pytest.mark.parametrize("old_fails", (False, True))
@pytest.mark.parametrize("new_version", ("a0", "a2"))
def test_out_of_order_polls_keep_newest_reply(
    pages: dict[str, Path], tmp_path: Path, old_fails: bool, new_version: str
) -> None:
    script = """
await openDoc(a); st.version="a0";
const first=deferred(), second=deferred(); let reads=0, loads=0;
window.fetch = () => ++reads === 1 ? first.promise : second.promise;
sceneOf = async () => { loads++; return sa; };
const old=poll(), current=poll(); second.resolve(reply(NEW_VERSION,"new update")); await current;
if (OLD_FAILS) first.reject(new Error("old poll failed")); else first.resolve(reply("a1","old update"));
await old;
return {version:st.version,status:$("live").textContent,loads};
""".replace("NEW_VERSION", repr(new_version)).replace("OLD_FAILS", str(old_fails).lower())
    assert _act(pages, tmp_path, script) == {
        "version": new_version,
        "status": "live · updated new update",
        "loads": int(new_version != "a0"),
    }


def test_navigation_during_poll_refresh_stays_current(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(a); st.version="a0";
const pending=deferred(), entered=deferred();
window.fetch=async () => reply("a1","A update");
sceneOf = d => { if (d.id === a.id) { entered.resolve(); return pending.promise; }
  return Promise.resolve(sb); };
const old=poll(); await entered.promise; await openDoc(b); st.version="b0"; $("live").textContent="B status";
pending.resolve(sa); await old;
return {selected:DOC.name,displayed:S.meta.name,version:st.version,status:$("live").textContent};
"""
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "version": "b0",
        "status": "B status",
    }


def test_navigation_cancels_delayed_cross_probe(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(a);
const pending=deferred(), entered=deferred();
sceneOf=d => { if (d.id === b.id) { entered.resolve(); return pending.promise; }
  return Promise.resolve(sa); };
const probing=crossProbe("U1","schematic"); await entered.promise;
await openDoc(a); pending.resolve(sb); await probing;
return {selected:DOC.name,displayed:S.meta.name,info:$("info").textContent};
"""
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.PcbDoc",
        "displayed": "blink.PcbDoc",
        "info": "",
    }


def test_late_bom_selection_does_not_filter_new_document(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
S = {refs:[["R1"]]};
const pending=deferred(); sceneOf=d => d.id === a.id ? pending.promise : Promise.resolve(sb);
const selecting=tableRow(0); await openDoc(b); $("query").value="";
pending.resolve(sa); await selecting;
return {selected:DOC.name,displayed:S.meta.name,query:$("query").value};
"""
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "query": "",
    }


def test_late_mark_does_not_move_new_document(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(b);
MARKS=[{id:"test",doc:a.name,note:"old mark",x_nm:1000000,y_nm:1000000,created:"test"}]; buildMarks();
const pending=deferred(); sceneOf=d => d.id === a.id ? pending.promise : Promise.resolve(sb);
const selecting=$("marksList").querySelector(".navi").onclick(); await openDoc(b);
const before=[view.cx,view.cy,view.s]; pending.resolve(sa); await selecting;
return {selected:DOC.name,displayed:S.meta.name,info:$("info").textContent,
  viewKept:JSON.stringify(before)===JSON.stringify([view.cx,view.cy,view.s])};
"""
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "info": "",
        "viewKept": True,
    }


def test_loading_card_identifies_new_document(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
const pending=deferred(); sceneOf=() => pending.promise;
const opening=openDoc(b);
const loading={card:$("doccard").style.display,text:$("doctext").textContent,title:$("fname").textContent};
pending.resolve(sb); await opening;
return {loading,done:$("doccard").style.display,displayed:S.meta.name};
"""
    result = _act(pages, tmp_path, script)
    assert result["loading"]["card"] == "flex"
    assert "blink.SchDoc" in result["loading"]["text"] and "Reading" in result["loading"]["text"]
    assert result["loading"]["title"] == "blink.SchDoc"
    assert result["done"] == "none" and result["displayed"] == "blink.SchDoc"


def test_startup_selection_cannot_apply_after_user_navigation(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
const pending=deferred(),entered=deferred(); let applied=0;
sceneOf=d => { if (d.id === a.id) { entered.resolve(); return pending.promise; }
  return Promise.resolve(sb); };
applySelect=() => { applied++; };
const initial=start(); await entered.promise; await openDoc(b); pending.resolve(sa); await initial;
return {selected:DOC.name,displayed:S.meta.name,applied};
"""
    assert _act(pages, tmp_path, script) == {
        "selected": "blink.SchDoc",
        "displayed": "blink.SchDoc",
        "applied": 0,
    }


@pytest.mark.parametrize("revisit", (False, True))
def test_first_poll_revalidates_displayed_scene(
    pages: dict[str, Path], tmp_path: Path, revisit: bool
) -> None:
    script = """
await openDoc(a);
if (REVISIT) { st.version="a0"; await openDoc(b); await openDoc(a); }
let loads=0; sceneOf=async () => { loads++; return named(sa,"refined A"); };
window.fetch=async () => reply("a1","refined");
await poll(); await poll();
return {displayed:S.meta.name,version:st.version,loads};
""".replace("REVISIT", str(revisit).lower())
    assert _act(pages, tmp_path, script) == {"displayed": "refined A", "version": "a1", "loads": 1}


def test_poll_waits_for_current_document_load(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
const pending=deferred(); sceneOf=() => pending.promise;
let requests=0; window.fetch=async () => { requests++; return reply("b1","B update"); };
const opening=openDoc(b); await poll(); const whileLoading=requests;
pending.resolve(sb); await opening; await poll();
return {whileLoading,requests,version:st.version,displayed:S.meta.name};
"""
    assert _act(pages, tmp_path, script) == {
        "whileLoading": 0,
        "requests": 1,
        "version": "b1",
        "displayed": "blink.SchDoc",
    }


def test_poll_does_not_restart_a_slow_refresh(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(a); st.version="a0";
const pending=deferred(),entered=deferred(); let requests=0,loads=0;
window.fetch=async () => { requests++; return reply("a1","A update"); };
sceneOf=() => { loads++; entered.resolve(); return pending.promise; };
const first=poll(); await entered.promise; const second=poll();
pending.resolve(named(sa,"refined A")); await Promise.all([first,second]);
return {requests,loads,version:st.version,displayed:S.meta.name};
"""
    assert _act(pages, tmp_path, script) == {
        "requests": 1,
        "loads": 1,
        "version": "a1",
        "displayed": "refined A",
    }


def test_building_reply_does_not_adopt_unread_version(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(a); let loads=0;
sceneOf=async () => { loads++; return named(sa,"refined A"); };
window.fetch=async () => ({ok:true,json:async () => ({version:"a1",building:true})});
await poll(); const whileBuilding={version:st.version,loads};
window.fetch=async () => reply("a1","done"); await poll();
return {whileBuilding,version:st.version,loads,displayed:S.meta.name};
"""
    assert _act(pages, tmp_path, script) == {
        "whileBuilding": {"version": None, "loads": 0},
        "version": "a1",
        "loads": 1,
        "displayed": "refined A",
    }


def test_failed_refresh_does_not_adopt_version_and_can_retry(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
await openDoc(a); let loads=0;
sceneOf=async () => { if (++loads === 1) throw new Error("cannot read current scene");
  return named(sa,"refined A"); };
window.fetch=async () => reply("a1","updated"); await poll();
const failed={version:st.version,card:$("doccard").style.display};
await poll(); return {failed,version:st.version,loads,displayed:S.meta.name,card:$("doccard").style.display};
"""
    assert _act(pages, tmp_path, script) == {
        "failed": {"version": None, "card": "flex"},
        "version": "a1",
        "loads": 2,
        "displayed": "refined A",
        "card": "none",
    }


def test_live_scene_responses_cannot_poison_cache(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
const first=deferred(),second=deferred(); let requests=0;
SCENES.delete(a.id); RAW.delete(a.id);
window.fetch=() => ++requests === 1 ? first.promise : second.promise;
const old=sceneOf(a), current=sceneOf(a);
second.resolve({ok:true,json:async () => named(sa,"new A")}); await current;
first.resolve({ok:true,json:async () => named(sa,"old A")}); await old;
await openDoc(a); return {cached:SCENES.get(a.id).meta.name,displayed:S.meta.name,requests};
"""
    assert _act(pages, tmp_path, script, live=True) == {
        "cached": "new A",
        "displayed": "new A",
        "requests": 2,
    }


def test_invalidation_prevents_old_decode_from_refilling_cache(
    pages: dict[str, Path], tmp_path: Path
) -> None:
    script = """
const pending=deferred(); unpackScene=() => pending.promise;
SCENES.delete(a.id); RAW.set(a.id,{test:true}); const old=sceneOf(a);
invalidateScene(a.id); pending.resolve(sa); await old;
return {cached:SCENES.has(a.id),rawKept:RAW.has(a.id)};
"""
    assert _act(pages, tmp_path, script) == {"cached": False, "rawKept": True}
