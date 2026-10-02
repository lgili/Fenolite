# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project synthesis (capability kicad-file-backend, "Project files are synthesised and preserved";
kicad-version-gating, "Project file versions"; change c0010)."""

from __future__ import annotations

import pytest
from _prodesigns import design

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.pro import (
    PATTERN_ENTRY_PATHS,
    UNSAFE_PATTERN_CHARS,
    read_project_text,
    synthesize_project,
    template,
)
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.errors import ConsistencyError, Issue

HV = design({"HV": 2_000_000}, {"+3V3": "HV", "Net-(R1-Pad1)": "HV", "GND": None})


def test_synthesis_for_target_10() -> None:
    data = read_project_text(synthesize_project(HV, target=10, board_name="bench"))
    assert data["meta"]["filename"] == "bench.kicad_pro"
    classes = data["net_settings"]["classes"]
    assert [c["name"] for c in classes] == ["Default", "HV"] and classes[1]["clearance"] == JsonNumber("2")
    assert data["net_settings"]["netclass_patterns"] == [
        {"netclass": "HV", "pattern": "+3V3"},
        {"netclass": "HV", "pattern": "Net-(R1-Pad1)"},
    ]


@pytest.mark.parametrize("target", [9, 10])
def test_no_key_outside_the_template(target: int) -> None:
    data = read_project_text(synthesize_project(HV, target=target, board_name="b"))
    allowed = _json.key_paths(template(target)) | PATTERN_ENTRY_PATHS
    assert _json.key_paths(data) <= allowed
    assert not any(
        p.startswith("/net_settings/netclass_patterns/*") for p in _json.key_paths(template(target))
    )


@pytest.mark.parametrize(("target", "pair"), [(9, ("3", "4")), (10, ("3", "5"))])
def test_synthesised_versions_follow_the_target(target: int, pair: tuple[str, str]) -> None:
    data = read_project_text(synthesize_project(design({}, {}), target=target, board_name="b"))
    assert (data["meta"]["version"].text, data["net_settings"]["meta"]["version"].text) == pair


def test_unsafe_net_name_refused() -> None:
    unsafe = design({"HV": 2_000_000}, {"CLK*": "HV"})
    with pytest.raises(LossyWriteError) as caught:
        synthesize_project(unsafe, target=10, board_name="b")
    assert "CLK*" in caught.value.issues[0].message and caught.value.droppable is True
    found: list[Issue] = []
    data = read_project_text(
        synthesize_project(unsafe, target=10, board_name="b", allow_lossy=True, issues=found)
    )
    assert [i.code for i in found] == ["kicad.project.dropped-pattern"]
    assert data["net_settings"]["netclass_patterns"] == []
    assert UNSAFE_PATTERN_CHARS == {"*", "?"}


def test_over_matching_name_refused() -> None:
    with pytest.raises(LossyWriteError) as caught:
        synthesize_project(design({"HV": 1}, {"D[0]": "HV", "D0": None}), target=10, board_name="b")
    (issue,) = caught.value.issues
    assert issue.code == "kicad.project.pattern-unsafe" and caught.value.droppable is True
    assert "D[0]" in issue.message and "D0" in issue.message
    found: list[Issue] = []
    text = synthesize_project(
        design({"HV": 1}, {"D[0]": "HV", "D0": "HV"}), target=10, board_name="b", issues=found
    )
    assert (
        found == []
        and {"netclass": "HV", "pattern": "D[0]"}
        in read_project_text(text)["net_settings"]["netclass_patterns"]
    )


def test_default_class_updates_the_first_entry() -> None:
    data = read_project_text(synthesize_project(design({"Default": 300_000}, {}), target=10, board_name="b"))
    (default,) = data["net_settings"]["classes"]
    assert default["name"] == "Default" and default["clearance"] == JsonNumber("0.3")


def test_unknown_netclass_is_a_caller_bug() -> None:
    broken = design({"HV": 1}, {"A": "HV"})
    import dataclasses

    broken = dataclasses.replace(broken, circuit=dataclasses.replace(broken.circuit, netclasses=()))
    with pytest.raises(ConsistencyError, match="model.unknown-netclass"):
        synthesize_project(broken, target=10, board_name="b")
