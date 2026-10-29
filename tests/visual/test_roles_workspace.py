# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Net Roles workspace of the viewer (change c0245, capability roles-workspace), on c0222's `bad` buck."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import MAX_RATIO, job, run

pytestmark = pytest.mark.needs_browser

READY = (
    "await new Promise(ok => { const t = () => WS === 'roles' && rolesData() ? ok() : setTimeout(t, 20);"
    " t(); });\n"
)
SIZE = {"width": 1400, "height": 860}


def _act(page: Path, tmp_path: Path, script: str) -> Any:
    (reply,) = run([job("roles", page, tmp_path, script=READY + script, shot="", **SIZE)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_panels(buck_roles_page: Path, tmp_path: Path) -> None:
    """Scenario "The workspace of the bad buck": a row per net, the groups, the role findings in Messages."""
    script = """
    const cells = tr => [...tr.children].map(td => td.textContent.trim());
    const nets = [...$("roleBody").querySelectorAll("tr")].map(cells);
    ROLES.tab = "groups"; buildRoles();
    const groups = [...$("roleBody").querySelectorAll("tr")].map(tr => tr.dataset.group);
    const messages = [...$("msgBody").querySelectorAll("tr[data-key]")]
      .map(tr => tr.children[1].textContent.replace("?", "").trim());
    return { nets, groups, messages, title: $("titleState").textContent,
      workspace: document.body.dataset.workspace,
      panel: findPanel("netroles")[0], view: getComputedStyle($("rolesView")).display };
    """
    result = _act(buck_roles_page, tmp_path, script)
    sw = next(row for row in result["nets"] if row[1] == "SW")
    assert (
        len(result["nets"]) == 12
        and sw[0] == "SW"
        and sw[2].startswith("switch_node")
        and sw[4].endswith("declared")
    )
    gh = next(row for row in result["nets"] if row[1] == "GH")
    assert gh[0] == "GT" and gh[3] == "high" and gh[4].endswith("inferred")
    assert sorted(result["groups"]) == ["gate_Q1", "gate_Q2", "hot_SW", "kelvin_R12"]
    assert len(result["messages"]) == 13 and "roles.kelvin-outer" in result["messages"]
    assert result["workspace"] == "roles" and result["panel"] == "left" and result["view"] != "none"
    assert "8 pending" in result["title"]


def test_properties(buck_roles_page: Path, tmp_path: Path) -> None:
    """Scenario "The switch node explained" on the inferred gate net GH and the hot loop hot_SW: the rule and
    pads of the role, each measure's analysis, each limit's source."""
    script = """
    selectRoleNet("GH"); ROLES.ptab = "role"; showRoleProps(); const role = $("info").textContent;
    selectRoleGroup("hot_SW"); ROLES.ptab = "measures"; showRoleProps();
    const measures = $("info").textContent;
    const values = [...$("info").querySelectorAll("[data-value]")].map(e => [e.textContent,
      e.dataset.source]);
    return { role, measures, values, status: $("sNet").textContent };
    """
    result = _act(buck_roles_page, tmp_path, script)
    assert "inferred · rule GD-1" in result["role"] and "Q1-2 + U1-7" in result["role"]
    assert "loop_areas on simulated" in result["measures"]
    source = dict(result["values"])
    assert any(s == "profile default, H-G-ROLE-LOOP-RATIO" for _, s in result["values"]), source
    assert any(s.startswith("loop_areas on simulated") for _, s in result["values"])
    assert result["status"] == "Net SW · switch_node"


def test_provenance_in_the_workspace(buck_roles_page: Path, tmp_path: Path) -> None:
    """Scenario "No value without a source" (board-viewer): every value shown names its source and evidence,
    and the status bar reads INFERRED."""
    script = """
    selectRoleGroup("hot_SW"); ROLES.ptab = "measures"; showRoleProps();
    const row = [...$("msgBody").querySelectorAll("tr[data-key]")]
      .find(t => t.textContent.includes("kelvin-outer"));
    row.click();
    await new Promise(ok => setTimeout(ok, 200)); selectRoleNet("VOUT"); ROLES.ptab = "role"; showRoleProps();
    const values = [...document.querySelectorAll("[data-value]")];
    return { count: values.length,
      bad: values.filter(e => !e.dataset.source || !e.dataset.evidence).length,
        status: $("sEvidence").textContent };
    """
    result = _act(buck_roles_page, tmp_path, script)
    assert result["count"] > 10 and result["bad"] == 0 and result["status"] == "evidence INFERRED"


def test_roles_workspace(buck_roles_page: Path, tmp_path: Path) -> None:
    """Scenario "Hot loop on the copper": the hatched loop, its area and ratio, the rest dimmed."""
    script = (
        READY
        + """
    selectRoleGroup("hot_SW"); ROLES.ptab = "measures"; showRoleProps();
    await new Promise(ok => setTimeout(ok, 300));
    """
    )
    (reply,) = run([job("roles_workspace", buck_roles_page, tmp_path, script=script, **SIZE)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    assert reply["ok"] is not None, (
        "no reference for roles_workspace: take it from the viewer job's screenshot"
    )
    assert reply["ok"], (
        f"roles_workspace: {reply.get('differing')} pixels differ "
        f"({reply.get('ratio', 0):.4%} > {MAX_RATIO:.1%}); difference image {reply.get('diff')}"
    )


PENDING = """
const until = async (f, ms) => { const end = Date.now() + (ms || 60000);
  while (!f()) { if (Date.now() > end) throw new Error("timed out");
    await new Promise(ok => setTimeout(ok, 50)); } };
const pend = () => $("pendingBody").textContent;
selectRoleNet("GH"); await act("accept");
const planned = { text: pend(), shown: findPanel("pending")[0], apply: !!$("pendApply") };
$("pendApply").click(); await until(() => !EDIT.pending && !EDIT.busy);
const gh = () => rolesData().roles.find(r => r.net === "GH").state;
const applied = { state: gh(), receipt: [...$("msgBody").querySelectorAll("tr[data-key]")]
  .some(t => t.textContent.includes("roles.write")), text: pend() };
await undoLast(); await until(() => !EDIT.busy && gh() === "inferred");
const undone = gh();
selectRoleNet("GL"); await act("accept"); await post("roles/discard", { doc: DOC.id });
await applyPending();
const stale = { again: !!$("pendAgain"), disabled: $("pendApply").disabled, text: pend() };
discardPending();
return { planned, applied, undone, stale, after: gh() };
"""


def test_pending(buck_page: Path, buck_roles_page: Path, tmp_path: Path) -> None:
    """The Pending panel of a page served with --edit: an action plans and writes nothing; Apply writes and
    logs its receipt in Messages; Ctrl+Z undoes it at once while the file is unchanged; a plan the server no
    longer holds reads FEN-4002 with Review again; an exported page offers the command line instead."""
    import shutil
    import threading

    from fenolite.cli.cmd_view import roles_payload, roles_write, scene_of
    from fenolite.view import server
    from fenolite.view.project import load_tree

    project = tmp_path / "project"
    shutil.copytree(buck_page.parent / "build", project)
    board = project / "buck_shunt_bad.kicad_pcb"
    rules = project / ".fenolite" / "rules.json"
    before = rules.read_bytes()
    from datetime import UTC, datetime
    from random import Random

    from fenolite.cli.api import Context

    ctx = Context(
        mode="json", seed=None, timestamp=datetime.now(UTC), rng=Random(0), no_backup=False, cwd=project
    )
    live = server.Live(
        load_tree(board),
        lambda path: scene_of(path),
        settings={"edit": True, "workspace": "roles"},
        roles=lambda path: roles_payload(path, None, ctx),
        roles_writer=lambda path, argv, plan_id: roles_write(path, argv, plan_id, None),
    )
    httpd = server.serve(live, 0)
    stop = threading.Event()
    thread = threading.Thread(target=server.run, args=(live, httpd), kwargs={"until": stop}, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        (reply,) = run(
            [
                job(
                    "pending",
                    tmp_path / "none.html",
                    tmp_path,
                    script=READY + PENDING,
                    shot="",
                    url=url,
                    **SIZE,
                )
            ],
            tmp_path,
        )
    finally:
        stop.set()
        thread.join(timeout=10)
        httpd.server_close()
    assert reply["errors"] == [], reply["errors"]
    result = reply["result"]
    assert "accept GH" in result["planned"]["text"] and ".fenolite/rules.json" in result["planned"]["text"]
    assert result["planned"]["shown"] == "bottom" and result["planned"]["apply"]
    assert result["applied"]["state"] == "confirmed" and result["applied"]["receipt"]
    assert "Written here" in result["applied"]["text"]
    assert result["undone"] == "inferred" and result["after"] == "inferred"
    assert result["stale"]["again"] and result["stale"]["disabled"]
    assert "not staged" in result["stale"]["text"]
    assert rules.read_bytes() == before
    readonly = _act(
        buck_roles_page,
        tmp_path,
        'selectRoleNet("GH"); const a = { kind: "accept", nets: ["GH"] };'
        ' return { line: actionLine(a), can: canWrite(), text: $("roleActions").textContent };',
    )
    assert readonly["line"].startswith("fenolite roles buck_shunt_bad.kicad_pcb --accept GH --dry-run")
    assert "copy only" in readonly["text"] and readonly["can"] is False
