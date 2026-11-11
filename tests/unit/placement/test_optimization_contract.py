# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The optimization protocol is opt-in and keeps candidate identity tied to exact poses."""

import json
from pathlib import Path

import jsonschema
import pytest

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.model.canonical import dumps, loads
from fenolite.placement.constraints import PlacementRequest
from fenolite.placement.optimization_contract import OptimizationRequest, ProposedPose, candidate_id

REQUEST = {
    "schema": "fenolite.placement-optimization.v0",
    "selected": ["first", "second"],
    "budget": {"evaluations": 40, "beam_width": 4},
    "rotations": [{"footprint_id": "first", "rotations": [0, 90_000_000]}],
}


def test_roundtrip_and_legacy_request():
    root = Path(__file__).resolve().parents[3]
    schema_path = root / "schemas"
    schema = json.loads((schema_path / "fenolite.placement-optimization.v0.json").read_text())
    jsonschema.validate(REQUEST, schema)
    request = loads(json.dumps(REQUEST), OptimizationRequest)
    assert loads(dumps(request), OptimizationRequest) == request
    legacy = loads('{"schema":"fenolite.placement-request.v0"}', PlacementRequest)
    assert legacy.constraints.pitch > 0
    with pytest.raises(FormatError):
        loads(dumps(legacy), OptimizationRequest)


@pytest.mark.parametrize(
    "invalid",
    [
        {"selected": ["first", "first"]},
        {"budget": {"evaluations": 0, "beam_width": 4}},
        {"rotations": [{"footprint_id": "outside", "rotations": [0]}]},
        {"rotations": [{"footprint_id": "first", "rotations": [360_000_000]}]},
        {"seed": True},
    ],
)
def test_invalid_inputs_refused(invalid):
    with pytest.raises(FormatError):
        loads(json.dumps(REQUEST | invalid), OptimizationRequest)


def test_candidate_identity_binds_input_and_geometry():
    a = ProposedPose("first", Point(1, 2), 0, "top")
    b = ProposedPose("second", Point(3, 4), 90_000_000, "top")
    ident = candidate_id("a" * 64, (a, b))
    assert ident == candidate_id("a" * 64, (b, a))
    assert ident != candidate_id("b" * 64, (a, b))
    assert ident != candidate_id("a" * 64, (a, ProposedPose("second", b.position, 0, "top")))
    with pytest.raises(ValueError, match="one pose"):
        candidate_id("a" * 64, (a, a))
