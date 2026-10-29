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
