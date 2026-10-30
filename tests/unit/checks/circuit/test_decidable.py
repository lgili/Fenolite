# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Decidable stages of requirement rows (change c0274; capability verification-loop, "Decidable stages of
requirement rows"). The board is authored for Fenolite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _contracts import cli

from fenolite.checks.circuit.decidable import Reach, Subject, decide, deferred_counts, reached, stage_of
from fenolite.core.requirement_table import Bound, RequirementRow, Side

SCRIPT = """\\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, amp, connect, mm, volt

design = Design("vbus")
design.board(mm(30), mm(20))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
j2 = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="OUT")
design.add(j1, j2)
gnd = design.ground("GND")
vbus = design.rail("VBUS", ground=gnd, voltage=volt("5").pct(5))
connect(vbus, j1[1], j2[1])
connect(gnd, j1[2], j2[2])
j1.place(mm(5), mm(10))  # pin 1 at (5, 11.27)
j2.place(mm(25), mm(10))
design.net_role(vbus.members["hv"], "power", current=amp(2))
p = lambda x, y: (mm(str(x)), mm(str(y)))  # noqa: E731
design.track("vbus", p(5, 11.27), p({end}, 11.27), width=mm("1.0"), net=vbus.members["hv"])
"""


def _row(check: str, status: str = "pass") -> RequirementRow:
    limit = Side(Bound("metre", Fraction_(1), None), "1 mm", "policy", "profile")
    return RequirementRow(f"{check}:N", check, "s", "width", "metre", None, limit, status)  # type: ignore[arg-type]


def Fraction_(n: int) -> Any:  # noqa: N802
    from fractions import Fraction

    return Fraction(n, 1000)


def test_the_closed_table() -> None:
    assert [stage_of(c) for c in ("circuit.rating-voltage", "roles.loop-area", "roles.gate-loop",
                                  "roles.width-current", "roles.kelvin-apart")] == [
        "build", "place", "place", "route", "route"
    ]  # fmt: skip
    subject = Subject(("J1", "J2"), ("VBUS",))
    assert reached("build", Subject(), Reach())
    assert not reached("place", subject, Reach(frozenset({"J1"})))
    assert reached("place", subject, Reach(frozenset({"J1", "J2"}), frozenset({"VBUS"})))
    assert not reached("route", subject, Reach(frozenset({"J1", "J2"}), frozenset({"VBUS"})))
    rows = decide([_row("roles.width-current"), _row("roles.loop-area", "fail")], {}, Reach())
    assert [(r.status, r.decidable) for r in rows] == [("deferred", "route"), ("fail", "place")]
    assert deferred_counts(rows) == {"route": 1}


def _built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, end: int) -> dict[str, Any]:
    script = tmp_path / "vbus.py"
    script.write_text(SCRIPT.format(end=end), encoding="utf-8")
    out = tmp_path / "out"
    code, env = cli(monkeypatch, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    code, env = cli(monkeypatch, "check", str(out), "--stages", "roles.rules,circuit.rules")
    assert code in (0, 5), env
    return {stage["name"]: stage for stage in env["result"]["stages"]} | {"issues": env["issues"]}


def test_track_width_before_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Track width before routing": the track of ``VBUS`` stops short of ``J2``."""
    stages = _built(tmp_path, monkeypatch, 15)
    rows = {r["id"]: r for r in stages["roles.rules"]["summary"]["requirements"]}
    width = rows["roles.width-current:VBUS"]
    assert (width["status"], width["decidable"]) == ("deferred", "route")
    assert not [i for i in stages["issues"] if i["code"] == "roles.width-current" and "VBUS" in i["message"]]
    assert stages["roles.rules"]["summary"]["deferred"] == {"route": 1}
    circuit = stages["circuit.rules"]["summary"]
    assert circuit["deferred"] == {} and all(r["status"] != "deferred" for r in circuit["requirements"])


def test_track_width_after_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stages = _built(tmp_path, monkeypatch, 25)
    rows = {r["id"]: r for r in stages["roles.rules"]["summary"]["requirements"]}
    assert rows["roles.width-current:VBUS"]["status"] == "pass"
    assert stages["roles.rules"]["summary"]["deferred"] == {}
