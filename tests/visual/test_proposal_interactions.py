# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored c0369 functional Chromium interactions; these are not CI golden references."""

from pathlib import Path

import pytest
from _proposal_viewer import CANDIDATE, OTHER, proposal_page
from _visual import job, run

pytestmark = pytest.mark.needs_browser


@pytest.fixture(scope="module")
def proposals(tmp_path_factory):
    return proposal_page(tmp_path_factory.mktemp("proposal-viewer"))


def interact(proposals, tmp_path, script, **extra):
    (reply,) = run(
        [job("proposal_interaction", proposals, tmp_path, script=script, shot="", **extra)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_unknown_family_escaped_text_unknown_facts_and_no_preselected_acceptance(proposals, tmp_path):
    result = interact(
        proposals,
        tmp_path,
        """
const box = document.getElementById('proposalList');
return {hidden:sectionEl('proposals').hidden, cards:box.querySelectorAll('.proposalCandidate').length,
  payload:box.textContent.includes('</script><img'), imgs:box.querySelectorAll('img,script').length,
  injected:!!window.__proposalInjected,
  unknown:[...box.querySelectorAll('dd')].some(x=>x.textContent==='unknown'),
  focused:PROPOSALS.focused, accepted:box.querySelectorAll('.actPlan').length,
  unresolved:box.textContent.includes('No candidate. This subject remains unresolved.')};
""",
    )
    assert result == {
        "hidden": False,
        "cards": 2,
        "payload": True,
        "imgs": 0,
        "injected": False,
        "unknown": True,
        "focused": "",
        "accepted": 0,
        "unresolved": True,
    }


def test_candidate_visibility_changes_canvas_without_changing_geometry_or_other_choice(proposals, tmp_path):
    result = interact(
        proposals,
        tmp_path,
        """
const c = S.proposals.proposals[0].candidates[0], line = c.polylines[0].points;
const point = [line[0][0]*0.75+line[1][0]*0.25,line[0][1]];
const sample = () => { const [X,Y]=w2s(...point);
  return Array.from(ctx.getImageData(Math.round(X*dpr)-3,Math.round(Y*dpr)-3,6,6).data).join(','); };
const before=sample(), original=JSON.stringify(S.proposals);
document.querySelector('[aria-label="Show candidate CANDIDATE"]').click();
const after=sample();
return {changed:before!==after, same:original===JSON.stringify(S.proposals),
  hidden:PROPOSALS.hidden.has('CANDIDATE'),
  other:!PROPOSALS.hidden.has('OTHER'), originals:S.prims.length>0};
""".replace("CANDIDATE", CANDIDATE).replace("OTHER", OTHER),
    )
    assert result == {"changed": True, "same": True, "hidden": True, "other": True, "originals": True}


def test_keyboard_focus_cross_probes_and_preserves_measurement(proposals, tmp_path):
    result = interact(
        proposals,
        tmp_path,
        "st.measure=true; st.mpts=[[1,1],[2,2]]; return {};",
        keys=[{"selector": f'[aria-label="Focus candidate {CANDIDATE}"]', "key": "Enter"}],
        afterKeysScript="""
return {focused:PROPOSALS.focused, net:S.nets[st.selNet], expected:S.proposals.proposals[0].net,
  measure:st.measure, points:st.mpts, active:document.activeElement.getAttribute('aria-label')};
""",
    )
    assert result["focused"] == CANDIDATE
    assert result["net"] == result["expected"]
    assert result["measure"] is True and result["points"] == [[1, 1], [2, 2]]
    assert result["active"] == f"Focus candidate {CANDIDATE}"


def test_inspection_preview_is_not_a_golden(proposals: Path, tmp_path: Path):
    # A local preview is useful for review; c0369 task 6 still requires the pinned CI artifact.
    (reply,) = run(
        [
            job(
                "proposal_preview",
                proposals,
                tmp_path,
                script="sectionEl('proposals').scrollIntoView(); return {readonly:!LIVE};",
                ref=tmp_path / "no-reference.png",
            )
        ],
        tmp_path,
    )
    assert reply["errors"] == [] and reply["result"]["readonly"] is True
    assert (tmp_path / "proposal_preview.png").is_file()


def test_malformed_bundle_text_is_inspectable_without_crashing_or_becoming_writable(proposals, tmp_path):
    result = interact(
        proposals,
        tmp_path,
        """
S.proposals.bundles=[{id:{unexpected:'object'},fingerprint:{unexpected:'object'},members:['missing']}];
buildProposals();
const box=document.querySelector('.proposalBundle');
return {text:box.textContent, controls:box.querySelectorAll('[data-proposal-action]').length,
  rest:document.querySelectorAll('.proposalCandidate').length};
""",
    )
    assert "unknown bundle" in result["text"]
    assert "inspection only" in result["text"]
    assert result["controls"] == 0 and result["rest"] == 2
