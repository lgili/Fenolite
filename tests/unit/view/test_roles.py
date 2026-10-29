# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net roles of a board joined to its scene (capability board-viewer, "Role data on a board"; change
c0273), on the authored reference boards of ``examples/roles``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _roles import reference_board, roles_reply

from fenolite.cli.cmd_view import scene_of
from fenolite.core.errors import FormatError
from fenolite.view.roles import SCHEMA, aliases_of, overlay, read_reply, state_of, summary


@pytest.fixture(scope="module")
def bad_buck(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    board = reference_board("buck_shunt", "bad", tmp_path_factory.mktemp("roles") / "out")
    return board, scene_of(board), roles_reply(board)


def test_bad_buck_joined_to_its_scene(bad_buck: tuple[Path, dict[str, Any], dict[str, Any]]) -> None:
    """Scenario "The bad buck joined to its scene"."""
    board, scene, reply = bad_buck
    data = overlay(read_reply(reply), scene)
    assert data["schema"] == SCHEMA and data["document"] == board.name
    rows = reply["result"]["roles"]
    assert [{k: r[k] for k in rows[0]} for r in data["roles"]] == rows  # the reply's rows, unchanged
    for row in data["roles"]:
        assert row["state"] == state_of(row) and scene["nets"][row["net_index"]] == row["net"]
    assert sum(data["kinds"].values()) == len(rows) and set(data["kinds"]) <= {r["kind"] for r in rows}
    groups = {g["name"]: g for g in data["groups"]}
    hot = groups["hot_SW"]
    assert hot["type"] == "hot" and len(hot["points"]) == 6 and hot["net"] == "SW"
    measured = next(
        m for m in reply["result"]["measures"] if m["kind"] == "loop" and m["subject"] == "hot_SW"
    )
    assert hot["area_nm2"] == measured["values"]["area_nm2"]
    assert groups["gate_Q1"]["pads"] == ["U1-7", "Q1-2", "Q1-1", "U1-6"]
    assert groups["kelvin_R12"]["type"] == "kelvin" and len(groups["kelvin_R12"]["points"]) == 4
    found = {(f["code"], f["where"]): f for f in data["findings"]}
    kelvin = found[("roles.kelvin-outer", "kelvin_R12:R12-1")]
    pad = next(p for p in scene["pads"] if p["label"] == "R12-1")
    assert kelvin["at"] == [pad["x"], pad["y"]] and kelvin["stage"] == "roles.rules"
    assert found[("roles.loop-area", "hot_SW")]["at"] is not None
    assert len(data["findings"]) == len(reply["issues"])
    counts = data["counts"]["findings"]
    assert (
        sum(counts.values()) == len(reply["issues"])
        and data["evidence"]["level"] == reply["evidence"]["level"]
    )
    assert aliases_of(data)["hot_SW"] == hot["pads"]
    told = summary(data)
    assert told["groups"] == len(data["groups"]) and told["roles"] == data["counts"]["roles"]


def test_a_value_the_reply_lacks_is_left_out() -> None:
    """A group the reply did not measure has no area, and pads the board lacks give a note, not a point."""
    reply = {
        "command": "roles",
        "result": {
            "roles": [{"net": "N1", "kind": "power", "source": "declared"}],
            "loops": [{"name": "hot_X", "pads": ["A-1", "B-1"], "origin": "inferred"}],
        },
        "issues": [],
    }
    scene = {"nets": ["N1"], "pads": [{"label": "A-1", "x": 1, "y": 2}], "prims": [], "comps": [], "meta": {}}
    data = overlay(reply, scene)
    (group,) = data["groups"]
    assert group["points"] == [[1, 2]] and "area_nm2" not in group and "net" not in group
    assert data["roles"][0]["state"] == "declared" and data["roles"][0]["net_index"] == 0
    assert any("B-1" in note for note in data["notes"]) and data["kinds"] == {"power": 1}


def test_not_a_roles_reply() -> None:
    with pytest.raises(FormatError, match="check reply"):
        read_reply({"command": "check", "issues": [], "result": {}}, name="c.json")
    with pytest.raises(FormatError, match="role document"):
        read_reply({"schema": "fenolite.roles.v0", "nets": []}, name="b.roles.json")
