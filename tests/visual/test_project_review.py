# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project review uses recorded evidence and existing markers in Chromium (c0239)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from _visual import _cli, browser_missing, job, run

pytestmark = pytest.mark.needs_browser
ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "tests/data/kicad/board/two_layer.kicad_pcb"


@pytest.fixture
def review_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if reason := browser_missing():
        pytest.skip(reason)
    monkeypatch.chdir(tmp_path)
    reply = {
        "command": "check",
        "input": {"path": BOARD.name, "sha256": hashlib.sha256(BOARD.read_bytes()).hexdigest()},
        "evidence": {"level": "INFERRED"},
        "issues": [
            {
                "code": "kicad.drc.clearance",
                "severity": "error",
                "message": "Review the gap",
                "where": "@10,12",
                "hint": "Compare the gap with the declared rule <safe>",
            },
            {
                "code": "copper.clearance-unset",
                "severity": "info",
                "message": "Only shorts judged",
                "hint": "Declare a clearance rule",
            },
        ],
        "result": {
            "stages": [
                {
                    "name": "drc.kicad",
                    "status": "errors",
                    "evidence": {"level": "INFERRED"},
                    "summary": {"limits": {"clearance": 20}},
                },
                {"name": "erc.kicad", "status": "skipped", "reason": "no-schematic", "evidence": {}},
                {"name": "copper.clearance", "status": "ok", "evidence": {"level": "INFERRED"}},
            ]
        },
    }
    (tmp_path / "check.json").write_text(json.dumps(reply), encoding="utf-8")
    args = (
        "view",
        str(BOARD),
        "--check",
        "check.json",
        "--no-models",
        "--no-review",
        "--export",
        "review.html",
        "--json",
    )
    plan = _cli(*args, "--dry-run")["result"]["plan_id"]
    _cli(*args, "--confirm", "--plan", plan)
    return tmp_path / "review.html"


def test_recorded_status_filters_and_locate(review_page: Path, tmp_path: Path) -> None:
    script = """
    $("bProjectReview").click();
    const card = id => $("reviewCards").querySelector(`[data-card="${id}"]`).textContent;
    const states = {drc:card("drc"),erc:card("erc"),convert:card("convert")};
    const initial = $("reviewCount").textContent;
    $("reviewNext").click();
    const next = $("reviewDetail").textContent;
    $("reviewPrevious").click();
    const previous = $("reviewDetail").textContent;
    $("reviewSeverity").value = "info"; $("reviewSeverity").dispatchEvent(new Event("change"));
    const info = $("reviewDetail").textContent;
    $("reviewSearch").value = "no matching rule"; $("reviewSearch").dispatchEvent(new Event("input"));
    const empty = {text:$("reviewCount").textContent,disabled:$("reviewNext").disabled};
    $("reviewSearch").value = ""; $("reviewSearch").dispatchEvent(new Event("input"));
    $("reviewSeverity").value = "error"; $("reviewSeverity").dispatchEvent(new Event("change"));
    const hint = $("reviewDetail").textContent;
    const unsafe = $("reviewDetail").querySelector("safe");
    st.checks = false; $("reviewDetail").querySelector("button").click();
    return {states,initial,next,previous,info,empty,hint,unsafe:!!unsafe,
      hidden:$("projectReview").hidden, selected:st.selFinding, markers:st.checks};
    """
    (reply,) = run([job("review", review_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert "Failed" in result["states"]["drc"] and "lower bounds" in result["states"]["drc"]
    assert "Limited" in result["states"]["erc"] and "no-schematic" in result["states"]["erc"]
    assert "Not run" in result["states"]["convert"] and "2 of 2" in result["initial"]
    assert "Only shorts judged" in result["next"] and "Review the gap" in result["previous"]
    assert "No position" in result["info"] and "Declare a clearance rule" in result["info"]
    assert result["empty"]["disabled"] and "no matches" in result["empty"]["text"]
    assert "<safe>" in result["hint"] and not result["unsafe"]
    assert result["hidden"] and result["selected"] == 0 and result["markers"]


@pytest.mark.parametrize("width", (390, 1100))
def test_review_keyboard_close_and_narrow_bounds(review_page: Path, tmp_path: Path, width: int) -> None:
    script = """
    if (matchMedia("(max-width:760px)").matches) $("bSidebar").click();
    $("bProjectReview").focus(); $("bProjectReview").click();
    const panel = $("projectReview"), r = panel.getBoundingClientRect();
    $("reviewSearch").focus();
    $("reviewSearch").dispatchEvent(new KeyboardEvent("keydown", {key:"m",bubbles:true}));
    const measuring = st.measure;
    $("reviewSearch").dispatchEvent(new KeyboardEvent("keydown",
      {key:"Escape",bubbles:true,cancelable:true}));
    return {x:r.x,right:r.right,width:r.width,measuring,hidden:panel.hidden,
      expanded:$("bProjectReview").getAttribute("aria-expanded"),focus:document.activeElement.id};
    """
    (reply,) = run(
        [job("review-width", review_page, tmp_path, script=script, shot="", width=width)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["x"] >= 0 and result["right"] <= width and result["width"] <= 380
    assert not result["measuring"] and result["hidden"] and result["expanded"] == "false"
    assert result["focus"] == ("bSidebar" if width <= 760 else "bProjectReview")


def test_review_does_not_keep_previous_document_results(review_page: Path, tmp_path: Path) -> None:
    script = """
    $("bProjectReview").click();
    const original = DOC;
    await openDoc({...original,id:"missing",name:"missing.SchDoc",present:false});
    const notRead = $("reviewScope").textContent;
    const findingCount = REVIEW.items.length;
    await openDoc(original);
    const restored = $("reviewCards").querySelector('[data-card="drc"]').textContent;
    return {notRead,findingCount,restored};
    """
    (reply,) = run([job("review-doc", review_page, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert "not been read" in result["notRead"] and result["findingCount"] == 0
    assert "Failed" in result["restored"]
