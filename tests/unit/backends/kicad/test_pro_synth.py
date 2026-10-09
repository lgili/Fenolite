# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project synthesis (capability kicad-file-backend, "Project files are synthesised and preserved";
kicad-version-gating, "Project file versions"; change c0010)."""

from __future__ import annotations

import dataclasses

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
from fenolite.model.design import Design

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


# --- check severities (capability kicad-file-backend, "Project files carry the check severities";
# --- change c0114) ---------------------------------------------------------------------------------


def severities_design(severities: dict[str, str]) -> Design:
    import dataclasses

    from fenolite.model.rules import RuleSet

    base = design({}, {})
    return dataclasses.replace(base, rules=RuleSet(id="rst_x", severities=severities))  # type: ignore[arg-type]


def severities_of(text_: str) -> dict[str, object]:
    return dict(_json.loads(text_)["board"]["design_settings"]["rule_severities"])  # type: ignore[index, arg-type]


@pytest.mark.parametrize("target", [9, 10])
def test_severity_synthesis_writes_a_named_key(target: int) -> None:
    """Scenario "Synthesis writes a named key": every other member equals the template's."""
    from fenolite.backends.kicad.pro import SEVERITY_KEYS, severity_key, template

    made = severities_design({"kicad.drc.silk-overlap": "ignore", "kicad.drc.via-dangling": "error"})
    found = severities_of(synthesize_project(made, target=target, board_name="b"))
    plain = severities_of(_json.dumps(template(target)))
    assert found["silk_overlap"] == "ignore" and found["via_dangling"] == "error"
    assert plain["silk_overlap"] != "ignore" and plain["via_dangling"] != "error"
    assert list(found) == list(plain)  # no key moved and none was added
    assert {k: v for k, v in found.items() if k not in ("silk_overlap", "via_dangling")} == {
        k: v for k, v in plain.items() if k not in ("silk_overlap", "via_dangling")
    }
    assert severity_key("kicad.drc.silk-overlap") == "silk_overlap" and severity_key("copper.short") is None
    assert SEVERITY_KEYS[target] == frozenset(plain) and len(SEVERITY_KEYS[10]) == 62
    assert SEVERITY_KEYS[9] == SEVERITY_KEYS[10]  # the 9 template was derived from 10's


def test_severity_without_any_keeps_the_template_text() -> None:
    assert synthesize_project(severities_design({}), target=10, board_name="b") == synthesize_project(
        design({}, {}), target=10, board_name="b"
    )


@pytest.mark.parametrize("code", ["kicad.drc.silk-overlaps", "kicad.drc.overlapping-pads", "altium.drc.x"])
def test_severity_unknown_key_refused(code: str) -> None:
    """Scenario "Unknown key refused": droppable, and dropped with a warning under ``allow_lossy``."""
    made = severities_design({code: "ignore", "kicad.drc.via-dangling": "error"})
    with pytest.raises(LossyWriteError) as caught:
        synthesize_project(made, target=10, board_name="b")
    assert caught.value.droppable is True
    assert [(i.code, i.severity) for i in caught.value.issues] == [("kicad.project.unknown-check", "error")]
    assert code in caught.value.issues[0].message and "KiCad 10.0" in caught.value.issues[0].message
    found: list[Issue] = []
    written = severities_of(
        synthesize_project(made, target=10, board_name="b", allow_lossy=True, issues=found)
    )
    assert [(i.code, i.severity) for i in found] == [("kicad.project.dropped-check", "warning")]
    assert "silk_overlaps" not in written and "x" not in written and written["via_dangling"] == "error"


def test_severity_codes_are_in_the_table() -> None:
    from fenolite.backends.kicad.proerrors import ISSUE_CODES

    assert ISSUE_CODES["kicad.project.unknown-check"] == "error"
    assert ISSUE_CODES["kicad.project.dropped-check"] == "warning"


def usb_design() -> Design:
    """The class ``USB`` with a pair gap and a pair width, holding the nets ``USB_P`` and ``USB_N``."""
    made = design({"USB": 200_000}, {"USB_P": "USB", "USB_N": "USB"})
    (usb,) = made.circuit.netclasses
    usb = dataclasses.replace(usb, diff_pair_gap=150_000, diff_pair_width=300_000)
    return dataclasses.replace(made, circuit=dataclasses.replace(made.circuit, netclasses=(usb,)))


@pytest.mark.parametrize("target", [9, 10])
def test_synthesis_writes_pair_values(target: int) -> None:
    """Scenario "Synthesis writes pair values" (change c0104); both templates hold the three keys."""
    data = read_project_text(synthesize_project(usb_design(), target=target, board_name="b"))
    default, usb = data["net_settings"]["classes"]
    base = template(target)["net_settings"]["classes"][0]
    assert usb["name"] == "USB" and usb["diff_pair_gap"] == JsonNumber("0.15")
    assert (
        usb["diff_pair_width"] == JsonNumber("0.3") and usb["diff_pair_via_gap"] == base["diff_pair_via_gap"]
    )
    for key in ("diff_pair_gap", "diff_pair_width", "diff_pair_via_gap"):
        assert default[key] == base[key]
    assert _json.key_paths(data) <= _json.key_paths(template(target)) | PATTERN_ENTRY_PATHS
