# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Body models placed in a scene (capability board-viewer, "Body models"; change c0193)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.backends.base import BodyModel
from fenolite.core.coords import Point
from fenolite.view.meshes import mesh_key
from fenolite.view.models import attach_models, placed_box, placement

MESH: dict[str, Any] = {"v": "", "i": "", "c": "", "bbox": [-1.0, -2.0, 0.0, 1.0, 2.0, 1.0], "tri": 0}
"""A model 2 mm by 4 mm by 1 mm, centred on its origin, standing on z = 0."""


def _scene(side: str = "top") -> dict[str, Any]:
    ring = [-2000, -1000, 2000, -1000, 2000, 1000, -2000, 1000]  # 4 mm by 2 mm, micrometres
    body = {"locator": "L#0", "side": side, "ring": ring, "z0": 0, "z1": 1000, "zs": [0, 1000]}
    return {"board3d": {"thickness": 1600}, "bodies": [body]}


def _model(rotation: tuple[int, int, int] = (0, 0, 0)) -> BodyModel:
    return BodyModel(
        locator="L#0", name="m.step", format="step", data=b"m", position=Point(0, 0), rotation=rotation
    )


def test_fit() -> None:
    """Scenario "Placement and fit"."""
    scene = _scene()
    counts = attach_models(scene, [_model()], {mesh_key(b"m"): MESH})
    body = scene["bodies"][0]
    assert counts["fitted"] == 1 and body["render"] == "fitted" and "turned 90°" in body["fit"]
    assert list(scene["meshes"]) == [mesh_key(b"m")]
    scene = _scene()
    counts = attach_models(scene, [_model((0, 0, 90_000_000))], {mesh_key(b"m"): MESH})
    assert (
        counts["model"] == 1
        and scene["bodies"][0]["render"] == "model"
        and len(scene["bodies"][0]["m"]) == 16
    )


def test_bottom_is_a_half_turn_about_x_below_the_face() -> None:
    m = placement(_model(), "bottom", 1.6)
    box = placed_box(m, MESH["bbox"])
    assert box[2] == pytest.approx(-1.0) and box[5] == pytest.approx(0.0)  # below the bottom face
    assert box[0] == pytest.approx(-1.0) and box[4] == pytest.approx(2.0)  # x kept, y turned
    scene = _scene("bottom")
    assert attach_models(scene, [_model((0, 0, 90_000_000))], {mesh_key(b"m"): MESH})["model"] == 1


def test_no_model_and_no_mesh_stay_extruded() -> None:
    scene = _scene()
    assert (
        attach_models(scene, [], {})["outline"] == 1 and scene["bodies"][0]["fit"] == "no model in the file"
    )
    scene = _scene()
    counts = attach_models(scene, [_model()], {})
    assert counts["unmeshed"] == 1 and scene["bodies"][0]["render"] == "outline" and scene["meshes"] == {}
