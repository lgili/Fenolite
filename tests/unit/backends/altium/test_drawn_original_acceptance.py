# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The original example states its actual pull-down and unused inputs (c0276)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import _drawn
import pytest

from fenolite.api import run
from fenolite.backends.altium.read import sch


def test_original_example_has_a_real_ground_return_and_only_unused_input_marks() -> None:
    code = _drawn.design("example")
    assert len(code.parts) == 4
    assert code.parts["child/R3"].connections["2"].name == "GND"
    assert code.parts["U1"].no_connects == {"11", "12"}
    assert all(not part.no_connects for path, part in code.parts.items() if path != "U1")
    assert not (code.parts["U1"].no_connects & code.parts["U1"].connections.keys())
    value = _drawn.drawn("example")
    root = value.sheet("root")
    assert root is not None
    points = _drawn.pins(value, "example")[("root", "symbol", 0)]
    assert Counter(root.no_connects) == Counter(p.at for p in points if p.number in {"11", "12"})
    assert any(label.text == "IN" and label.at in root.wires[0] for label in root.labels)


@pytest.mark.parametrize("form", ("binary", "ascii"))
def test_original_example_native_records_preserve_all_pins_and_exact_marker_scope(
    tmp_path: Path, form: str
) -> None:
    result = run(
        "build", str(_drawn.folder("example") / "design.py"), "--target", "altium",
        "--altium-format", form, "--out", str(tmp_path / "out"), "--confirm",
        seed=1, timestamp="2026-11-03T00:00:00Z",
    )  # fmt: skip
    assert result.exit_code == 0, (result.error, result.envelope)
    docs = [sch.read_schematic(p.read_bytes()) for p in (tmp_path / "out").glob("*.SchDoc")]
    pins = [p for doc in docs for p in doc.of_type(sch.Pin)]
    markers = [m for doc in docs for m in doc.no_ercs()]
    assert len(pins) == 38 and len(markers) == 2
    assert all(m.active and m.suppress_all for m in markers)
    assert Counter(m.location for m in markers) == Counter(
        p.hot_end for p in pins if p.designator in {"11", "12"}
    )
    assert any(label.text == "IN" for doc in docs for label in doc.of_type(sch.NetLabel))
    circuit = json.loads((tmp_path / "out/.fenolite/circuit.json").read_text())
    refs = {c["id"]: c["ref"] for c in circuit["components"]}
    memberships = {
        net["name"]: {(refs[p["component_id"]], p["pin"]) for p in net["members"]} for net in circuit["nets"]
    }
    assert memberships["GND"] == {("U1", "10"), ("R3", "2")}
    assert memberships["VCC"] == {("U1", "9"), ("R1", "2")}
    assert len(refs) == 4 and sum(len(c["pins"]) for c in circuit["components"]) == 38


def test_native_receipt_preserves_every_completed_observation_and_operator_history() -> None:
    path = Path(__file__).resolve().parents[4] / "docs/evidence/altium-drawn-example-native.json"
    value = json.loads(path.read_text())
    assert value["native_version"] == "24.5.2.23" and value["sources"][0] == "S-1295"
    assert value["task_6_4_passed"] is True
    assert value["full_gate_passed"] is value["evidence_promoted"] is False
    assert value["cases"][0]["compiler_messages"] == {"[Error]": 3, "[Warning]": 2}
    assert len(value["cases"][0]["name_differences"]) == 1
    positive = value["cases"][1:]
    assert len(positive) == 4
    for case in positive:
        assert case["all_pins"] == 38 and case["groups"] == 33 and case["connectivity_equal"]
        assert not case["name_differences"] and case["compiler_messages"] == {"[Info]": 1}
    assert len({case["all_pin_partition_sha256"] for case in positive}) == 1
    assert len(value["saved_documents"]) == len(value["marker_comparisons"]) == 4
    assert all(item["positions_flags_exact"] for item in value["marker_comparisons"])
    pending = value["historical_incomplete_ascii_saved"]
    assert pending["observed_pins"] is None and pending["expected_pins"] == 38
    assert pending["cad_failure_claimed"] is False
    assert pending["retry_performed"] is True
    assert pending["requires_conscious_stop_and_io_control_before_retry"] is True
    repair = value["operator_io_repair"]
    assert repair["manual_stop_confirmed_by_user"] and repair["main_enabled"]
    assert repair["modal_count"] == repair["active_stage_content_reads"] == 0
    assert repair["io_control"]["observed_win32_error"] == 32
    assert repair["io_control"]["all_passed"] and not repair["io_control"]["native_app_touched"]
    assert repair["io_control"]["marker_existence_checks"] == 1000
    assert repair["final_marker_exists"] and not repair["final_marker_content_read"]
    assert repair["already_completed_native_cases_repeated"] == 0
    assert positive[-1]["save_reopen_done"]
    assert sum(len(item["files"]) for item in value["original_input_maps"]) == 45
