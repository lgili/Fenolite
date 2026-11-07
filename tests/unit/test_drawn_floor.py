# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent complete graph/name and original-floor controls (c0347)."""

from __future__ import annotations

import copy

import _drawn_floor as floor
import pytest

from fenolite.core.errors import FormatError


@pytest.mark.parametrize("version", [20230121, 20230221, 20230819])
def test_only_actual_old_schematic_gets_expected_reader_refusal(version: int) -> None:
    data = f"(kicad_sch (version {version}) (generator fenolite))".encode()
    record = floor.original_refusal(data)
    assert record["status"] == "refused" and record["expectation"] == "original-reader-floor"
    assert record["format"] == version and record["input_sha256"] == floor.digest(data)
    assert record["refusal"] == {"stage": "read", "type": "UnsupportedFormatError", "code": "FEN-3003"}


@pytest.mark.parametrize(
    "data", [b"(kicad_sch (version 20260306))", b"(kicad_sch (version 20990101))", b"(kicad_pcb (version 1))"]
)
def test_supported_future_or_other_kind_is_not_a_floor_expectation(data: bytes) -> None:
    with pytest.raises(ValueError, match="not a schematic reader-floor"):
        floor.original_refusal(data)


def test_malformed_input_and_generic_reader_failure_never_become_floor(monkeypatch) -> None:
    with pytest.raises(FormatError):
        floor.original_refusal(b"(kicad_sch")

    def bad_reader(*args, **kwargs):
        raise FormatError("planted semantic failure")

    monkeypatch.setattr(floor.sch, "read_schematic", bad_reader)
    with pytest.raises(FormatError, match="planted semantic failure"):
        floor.original_refusal(b"(kicad_sch (version 20230121))")


def test_missing_expected_refusal_is_a_failure(monkeypatch) -> None:
    monkeypatch.setattr(floor.sch, "read_schematic", lambda *args, **kwargs: None)
    with pytest.raises(AssertionError, match="without refusal"):
        floor.original_refusal(b"(kicad_sch (version 20230121))")


@pytest.mark.parametrize("change", ["missing-pin", "extra-pin", "partition", "name", "missing-proof"])
def test_full_bridge_rejects_planted_pin_partition_and_name_changes(change: str) -> None:
    graph = {"AUTHORED_A": {("R1", "1"), ("R2", "1")}, "AUTHORED_B": {("R1", "2")}}
    before = floor.signature(graph)
    assert floor.bridge_equal(before, floor.signature(dict(reversed(list(graph.items())))))
    changed = copy.deepcopy(graph)
    if change == "missing-pin":
        changed["AUTHORED_A"].remove(("R2", "1"))
    elif change == "extra-pin":
        changed["AUTHORED_A"].add(("R3", "1"))
    elif change == "partition":
        changed["AUTHORED_A"].update(changed.pop("AUTHORED_B"))
    elif change == "name":
        changed["PLANTED"] = changed.pop("AUTHORED_A")
    after = floor.signature(changed)
    if change == "missing-proof":
        del after["pins_sha256"]
    assert not floor.bridge_equal(before, after)


def test_upgrade_needs_all_three_complete_pin_and_name_comparisons() -> None:
    comparison = {
        "equal": True,
        "naming_equal": True,
        "name_differences": 0,
        "native_only_pins": 0,
        "drawn_unlisted_pins": 0,
    }
    report = {
        "status": "equal",
        **{k: dict(comparison) for k in ("partition", "lowered_partition", "lowered_native_partition")},
    }
    assert floor.census_equal(report)
    for key in ("partition", "lowered_partition", "lowered_native_partition"):
        for field, value in (
            ("equal", False),
            ("naming_equal", False),
            ("native_only_pins", 1),
            ("drawn_unlisted_pins", 1),
            ("name_differences", 1),
        ):
            bad = copy.deepcopy(report)
            bad[key][field] = value
            assert not floor.census_equal(bad)
        bad = copy.deepcopy(report)
        del bad[key]
        assert not floor.census_equal(bad)


@pytest.mark.parametrize(
    "defect",
    [
        "none",
        "input-digest",
        "output-digest",
        "from-version",
        "to-version",
        "tool",
        "tool-version",
        "future-output",
        "changed-copy",
        "changed-source",
    ],
)
def test_probe_requires_provenance_and_immutable_sources(defect: str, monkeypatch, tmp_path) -> None:
    import dataclasses
    from types import SimpleNamespace

    import _drawn_corpus
    import _erc
    from _drawn_corpus import Input

    from fenolite.importer import upgrade
    from fenolite.importer.source import Upgrade

    original = b"(kicad_sch (version 20230121))"
    after = b"(kicad_sch (version 20260306))"
    path = tmp_path / "authored.kicad_sch"
    path.write_bytes(original)
    cli = SimpleNamespace(path=tmp_path / "kicad-cli", version=lambda: "10.0.6")
    monkeypatch.setattr(_erc, "netlist", lambda *a, **k: {"AUTH": {("R1", "1")}})
    comparison = {
        "equal": True,
        "naming_equal": True,
        "name_differences": 0,
        "native_only_pins": 0,
        "drawn_unlisted_pins": 0,
    }
    monkeypatch.setattr(
        _drawn_corpus,
        "measure",
        lambda *a, **k: {
            "status": "equal",
            **{
                key: dict(comparison)
                for key in ("partition", "lowered_partition", "lowered_native_partition")
            },
        },
    )

    def fake_upgrade(copy, kind):
        output = b"(kicad_sch (version 20990101))" if defect == "future-output" else after
        receipt = Upgrade(
            file=copy.name,
            tool="kicad-cli",
            tool_version="10.0.6",
            from_version=20230121,
            to_version=20260306,
            sha256_before=floor.digest(original),
            sha256_after=floor.digest(output),
        )
        fields = {
            "input-digest": ("sha256_before", "0" * 64),
            "output-digest": ("sha256_after", "0" * 64),
            "from-version": ("from_version", 20230221),
            "to-version": ("to_version", 20250114),
            "tool": ("tool", "not-kicad-cli"),
            "tool-version": ("tool_version", "9.0.9"),
        }
        if defect in fields:
            name, value = fields[defect]
            receipt = dataclasses.replace(receipt, **{name: value})
        if defect == "changed-copy":
            copy.write_bytes(b"changed")
        if defect == "changed-source":
            path.write_bytes(b"changed")
        return output, receipt

    monkeypatch.setattr(upgrade, "upgrader", lambda *a, **k: fake_upgrade)
    result = floor.probe(
        tmp_path,
        path.name,
        path.name,
        (Input("authored", path.name, floor.digest(original)),),
        cli,
        ident="authored",
        major=10,
        code_commit="authored-code",
        manifest_sha256="authored-manifest",
    )
    assert result["status"] == ("upgraded/equal" if defect == "none" else "partial")
    assert result["originals_unchanged"] is (defect != "changed-source")
    if defect != "changed-source":
        assert path.read_bytes() == original
