# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored c0369 scene contracts: never bridge bad geometry or invent missing facts."""

import copy
import json

import pytest

from fenolite.view.export import _json
from fenolite.view.proposals import overlay


def reply():
    return {
        "command": "route",
        "result": {
            "mode": "propose",
            "proposals": [
                {
                    "id": "p-1",
                    "kind": "connection",
                    "net": "SIGNAL",
                    "subject": "connection:S:A~B",
                    "ends": [
                        {"kind": "pad", "name": "A-1", "layers": ["F.Cu"], "at": [-1500, 2500]},
                        {"kind": "pad", "name": "B-1", "layers": ["B.Cu"], "at": [10_000, 0]},
                    ],
                    "candidates": [
                        {
                            "id": "c-1",
                            "source": "external:future-router",
                            "relaxed": ["outline-only"],
                            "bundle": "b-one",
                            "tool": {"version": "authored", "deterministic": False},
                            "facts": {"length": None, "open": {"before": 1, "after": 0}},
                            "geometry": [
                                {
                                    "kind": "track",
                                    "layer": "F.Cu",
                                    "width": 250_000,
                                    "points": [[0, 0], [10_000, 0]],
                                },
                                {
                                    "kind": "via",
                                    "at": [10_000, 0],
                                    "diameter": 600_000,
                                    "drill": 300_000,
                                    "layers": ["F.Cu", "B.Cu"],
                                },
                            ],
                        }
                    ],
                }
            ],
            "bundles": [{"id": "b-one", "members": ["c-1"], "fingerprint": "authored"}],
            "external": {"requested": ["future-router"], "refusals": []},
        },
    }


def shown(raw):
    return overlay(raw, {})["proposals"][0]["candidates"][0]


def test_known_geometry_of_unknown_family_is_preserved_with_no_score():
    raw = reply()
    snapshot = copy.deepcopy(raw)
    scene = overlay(raw, {})
    subject = scene["proposals"][0]
    candidate = subject["candidates"][0]
    assert candidate["source"] == "external:future-router"
    assert candidate["polylines"] == [{"layer": "F.Cu", "width": 250, "points": [[0, 0], [10, 0]]}]
    assert candidate["vias"] == [{"at": [10, 0], "diameter": 600, "drill": 300, "layers": ["F.Cu", "B.Cu"]}]
    assert subject["ends"][0]["at"] == [-2, 2]  # exact ties-to-even, including negatives
    assert candidate["facts"] == snapshot["result"]["proposals"][0]["candidates"][0]["facts"]
    assert candidate["facts"]["length"] is None and "score" not in candidate
    assert candidate["tool"]["deterministic"] is False and candidate["bundle"] == "b-one"
    assert scene["bundles"] == raw["result"]["bundles"]
    candidate["facts"]["open"]["after"] = 999
    scene["bundles"][0]["members"].clear()
    assert raw == snapshot


@pytest.mark.parametrize("invalid", [None, True, [True, 0], [1.1, 0], ["0", 0], [10**30, 0], [0]])
def test_malformed_middle_point_does_not_join_the_good_points(invalid):
    raw = reply()
    geometry = raw["result"]["proposals"][0]["candidates"][0]["geometry"]
    geometry[0]["points"] = [[0, 0], invalid, [10_000, 0]]
    candidate = shown(raw)
    assert candidate["polylines"] == [] and candidate["unknown_geometry"] is True
    assert len(candidate["vias"]) == 1


@pytest.mark.parametrize("bad_width", [None, -1, True, 0, "250000", 250.5])
def test_malformed_width_is_unknown_geometry(bad_width):
    raw = reply()
    raw["result"]["proposals"][0]["candidates"][0]["geometry"][0]["width"] = bad_width
    assert shown(raw)["polylines"] == []


def test_unsupported_geometry_and_absent_facts_remain_unknown():
    raw = reply()
    given = raw["result"]["proposals"][0]["candidates"][0]
    given.pop("facts")
    given["geometry"] = [{"kind": "unrecognized", "points": [[1, 2], [3, 4]]}]
    candidate = shown(raw)
    assert candidate["polylines"] == [] and candidate["vias"] == []
    assert "facts" not in candidate and candidate["unknown_geometry"] is True


def test_unresolved_subject_keeps_endpoint_and_reason_without_candidate():
    raw = reply()
    subject = raw["result"]["proposals"][0]
    subject["candidates"] = []
    subject["reason"] = "external-unsupported"
    scene = overlay(raw, {})
    assert scene["proposals"][0]["reason"] == "external-unsupported"
    assert len(scene["proposals"][0]["ends"]) == 2
    assert scene["proposals"][0]["box"] is not None


def test_untrusted_tool_reason_and_family_are_data_in_safe_embedded_json():
    payload = '</script><img src=x onerror="alert(1)">'
    raw = reply()
    candidate = raw["result"]["proposals"][0]["candidates"][0]
    candidate["source"] = payload
    candidate["facts"]["unknown"] = payload
    raw["result"]["proposals"][0]["reason"] = payload
    scene = overlay(raw, {})
    serialized = _json(scene)
    assert "</script" not in serialized.lower()
    assert json.loads(serialized)["proposals"][0]["reason"] == payload
    assert payload in shown(raw)["facts"]["unknown"]


def test_large_integer_rounding_does_not_pass_through_float():
    raw = reply()
    value = 9_000_000_000_000_501
    raw["result"]["proposals"][0]["candidates"][0]["geometry"][0]["points"] = [[value, -value], [0, 0]]
    assert shown(raw)["polylines"][0]["points"][0] == [9_000_000_000_001, -9_000_000_000_001]


def test_invalid_subject_text_is_unknown_instead_of_becoming_an_object_child():
    raw = reply()
    raw["result"]["proposals"][0]["subject"] = {"unsafe": "object"}
    raw["result"]["proposals"][0]["reason"] = ["unexpected"]
    subject = overlay(raw, {})["proposals"][0]
    assert "subject" not in subject and "reason" not in subject
    assert subject["candidates"]
