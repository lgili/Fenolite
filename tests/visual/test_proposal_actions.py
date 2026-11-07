# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0369 explicit preview/confirm interaction with authored stub routes; real writes have unit proofs."""

from pathlib import Path

import pytest
from _proposal_viewer import BUNDLE, CANDIDATE, proposal_page
from _visual import job, run

from tests.visual.test_actions import _live

pytestmark = pytest.mark.needs_browser


@pytest.mark.parametrize("bundle", [False, True])
@pytest.mark.parametrize("changed", [False, True])
def test_proposal_decision_previews_before_any_confirmation(tmp_path: Path, changed, bundle):
    exported = proposal_page(tmp_path, bundle=bundle)
    live = _live(exported, tmp_path)
    script = r"""
await new Promise(r=>setTimeout(r,150));
const calls=[], response=data=>({ok:true,status:200,json:async()=>data});
const raw=await unpackScene(EMBED.scenes[DOC.id]);
const write={path:DOC.name,bytes:123,sha256:'a'.repeat(64),replaces:S.meta.sha256};
const planned={job:'p1',kind:'plan',state:'done',command:'route',action:'route-accept',doc:DOC.id,exit:0,
  envelope:{issues:[],evidence:{level:'UNVERIFIED'}},
  plan:{plan_id:'0123456789abcdef',confirmable:true,writes:[write],issues:[],evidence:{level:'UNVERIFIED'}}};
const confirmed=CHANGED
 ? {job:'c1',state:'done',kind:'confirm',exit:4,
    error:{code:'FEN-4002',message:'board changed'},review_again:true}
 : {job:'c1',state:'done',kind:'confirm',exit:0,receipt:{id:'r1',written:[write],backup:[]}};
window.fetch=async(url,init)=>{
 const u=String(url),body=JSON.parse(init?.body||'{}'); calls.push({url:u,body});
 if(u==='action/plan')return response({job:'p1'});
 if(u==='action/confirm')return response({job:'c1'});
 if(u==='run/p1')return response(planned);
 if(u==='run/c1')return response(confirmed);
 if(u.startsWith('scene/'))return response(JSON.parse(JSON.stringify(raw)));
 if(u==='runs')return response({enabled:false,commands:{}});
 return response({enabled:true,actions:{},receipts:[]});
};
ACTS.enabled=true; ACTS.doc=DOC.id; ACTS.token='t'.repeat(32);
ACTS.offer={'route-accept':{title:'Accept route candidates',available:true},
            'route-reject':{title:'Reject route candidates',available:true}};
buildProposals();
const membersHaveButtons=!!document.querySelector('[data-candidate] [data-proposal-action]');
const unit=document.querySelector('UNIT_SELECTOR');
const inspect=[...unit.querySelectorAll('button')].find(b=>b.textContent==='Inspect whole bundle');
if(inspect)inspect.click();
const focused=PROPOSALS.focused;
const button=document.querySelector('UNIT_SELECTOR [data-proposal-action="route-accept"]');
const until=async test=>{for(let i=0;i<100;i++){
 if(test())return;await new Promise(r=>setTimeout(r,40));}throw Error('wait');};
button.click(); await until(()=>ACTS.open?.phase==='plan');
const before=calls.filter(c=>c.url==='action/confirm').length;
const request=calls.find(c=>c.url==='action/plan').body;
const shown=document.getElementById('planDialog').open &&
 document.getElementById('planConfirm').disabled===false;
document.getElementById('planConfirm').click();
await until(()=>['receipt','changed'].includes(ACTS.open?.phase));
return {before,request,shown,focused,membersHaveButtons,
  confirmed:calls.filter(c=>c.url==='action/confirm').length,
  phase:ACTS.open.phase,again:document.getElementById('planFoot').textContent.includes('Review again')};
""".replace(
        "UNIT_SELECTOR", f'[data-bundle="{BUNDLE}"]' if bundle else f'[data-candidate="{CANDIDATE}"]'
    ).replace("CHANGED", "true" if changed else "false")
    (reply,) = run([job("proposal_action", live, tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert result["before"] == 0 and result["shown"] is True
    assert result["request"]["action"] == "route-accept"
    assert result["request"]["options"] == {"candidates": [BUNDLE if bundle else CANDIDATE]}
    assert result["membersHaveButtons"] is (not bundle)
    assert result["focused"] == (BUNDLE if bundle else "")
    assert result["confirmed"] == 1
    assert result["phase"] == ("changed" if changed else "receipt")
    assert result["again"] is changed
