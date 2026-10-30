# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route proposals joined to the scene of their board (capability board-viewer, "Route proposals on a board";
change c0280), on the buck role-copper variant after phase 2."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import _roles  # noqa: F401  (puts tests/unit/roles on the path)
import pytest
from _proposals import phase2

from fenolite.cli.cmd_view import scene_of
from fenolite.cli.main import invoke
from fenolite.core.errors import FormatError
from fenolite.view.proposals import SCHEMA, ids_of, overlay, read_reply, summary

FORBIDDEN = {"score", "rank", "best", "recommended", "cost"}


def keys_in(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():  # type: ignore[union-attr]
            yield str(key)
            yield from keys_in(item)
    elif isinstance(value, list):
        for item in value:  # type: ignore[union-attr]
            yield from keys_in(item)


@pytest.fixture(scope="module")
def buck(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    built = phase2("buck_shunt", "bad", tmp_path_factory.mktemp("proposals"))
    args = ["route", built.board.name, "--router", "octilinear", "--propose", "--candidates", "2", "--json"]
    code, envelope, error = invoke(args, cwd=built.out)
    assert code == 0 and envelope is not None, error
    return built.board, scene_of(built.board), envelope


def test_the_bucks_proposals_joined_to_its_scene(buck: tuple[Path, dict[str, Any], dict[str, Any]]) -> None:
    """Scenario "The buck's proposals joined to its scene": ``fanout:GND:C3-2`` boxed around ``C3-2``, each
    via at its reply position in scene units, every facts object the reply's, no score anywhere."""
    board, scene, reply = buck
    data = overlay(read_reply(reply), scene)
    assert data["schema"] == SCHEMA and data["document"] == board.name and data["order"] == "generation"
    found = {p["subject"]: p for p in data["proposals"]}
    fanout = found["fanout:GND:C3-2"]
    pad = next(p for p in scene["pads"] if p["label"] == "C3-2")
    x0, y0, x1, y1 = fanout["box"]
    assert x0 <= pad["x"] <= x1 and y0 <= pad["y"] <= y1
    replied = {p["subject"]: p for p in reply["result"]["proposals"]}["fanout:GND:C3-2"]
    for shown, raw in zip(fanout["candidates"], replied["candidates"], strict=True):
        assert shown["id"] == raw["id"] and shown["facts"] == raw["facts"]
        vias = [g for g in raw["geometry"] if g["kind"] == "via"]
        assert [v["at"] for v in shown["vias"]] == [
            [round(v["at"][0] / 1000), round(v["at"][1] / 1000)] for v in vias
        ]
    assert not FORBIDDEN & set(keys_in(data))
    told = summary(data)
    assert told["proposals"] == len(reply["result"]["proposals"]) and told["candidates"] == sum(
        len(p["candidates"]) for p in reply["result"]["proposals"]
    )
    candidates, proposals = ids_of(data)
    assert {c["id"] for c in replied["candidates"]} <= candidates and replied["id"] in proposals


def test_a_value_the_reply_lacks_is_left_out() -> None:
    reply = {
        "command": "route",
        "result": {"mode": "propose", "proposals": [{"id": "p-1", "subject": "s", "candidates": []}]},
    }
    data = overlay(read_reply(reply), {})
    (proposal,) = data["proposals"]
    assert "reason" not in proposal and "box" not in proposal and "net" not in proposal
    assert "document" not in data and data["counts"] == {"proposals": 1, "candidates": 0}


@pytest.mark.parametrize(
    "reply",
    [
        {"command": "check", "result": {"stages": []}},
        {"command": "route", "result": {"selected": []}},
        [],
    ],
)
def test_other_replies_are_refused(reply: object) -> None:
    with pytest.raises(FormatError):
        read_reply(reply, name="r.json")
