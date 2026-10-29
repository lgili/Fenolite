# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The verification of a role-copper run (change c0243, decision 10; capability net-roles, "Role copper
verification", scenario "A worse result is refused")."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _rolecopper import bare_buck, cli

import fenolite.roles.copper as copper
from fenolite.core.ids import derived_id
from fenolite.model.board import Track


def test_a_worse_result_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A test planner that joins the 2 A net ``VL`` with a 0.2 mm track: the judge finds the track too
    narrow, which the board without it lacked."""
    out = bare_buck(tmp_path)

    def thin(design: Any, pads: Any, roles: Any, request: Any = None, **_: Any) -> copper.RoleCopperPlan:
        by = {f"{p.ref}-{p.number}": p for p in pads}
        net = next(n.id for n in design.circuit.nets if n.name == "VL")
        track = Track(
            id=derived_id("trk", "roles", "role.test.VL"),
            start=by["L1-2"].position,
            end=by["R12-1"].position,
            width=200_000,
            layer="F.Cu",
            net_id=net,
            locked=True,
        )
        return copper.RoleCopperPlan(tracks=(track,))

    monkeypatch.setattr(copper, "plan", thin)
    code, envelope = cli("copper", str(out), "--dry-run")
    assert code == 5, envelope
    worse = [i for i in envelope["issues"] if i["code"] == "roles.copper-worse"]
    assert worse and all(i["severity"] == "error" for i in worse)
    assert any("roles.width-current" in i["message"] for i in worse)
    result = envelope["result"]
    assert not result["changed"] and not result.get("plan")
    assert any(f["code"] == "roles.width-current" for f in result["after"])
