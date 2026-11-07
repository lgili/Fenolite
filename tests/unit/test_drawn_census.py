# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored census controls: strict node coverage, real lowering and value-free failures (c0276)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import _drawn
import _drawn_corpus as census
import pytest

from fenolite.backends.kicad.cli import KicadCli
from fenolite.model.drawn_connect import DrawnNet, DrawnNetlist

ROOT = Path(__file__).resolve().parents[2]
PINS = (("AuthoredA", "1"), ("AuthoredB", "1"))
REFS = {"AuthoredA": "A1", "AuthoredB": "B1"}


@pytest.mark.parametrize("extra", [{("C1", "1")}, {("C1", "1"), ("D1", "1")}])
def test_native_only_nodes_are_not_intersected_away(extra) -> None:
    ours = DrawnNetlist((DrawnNet("AuthoredNet", PINS),), PINS)
    report = census.partition_report(ours, REFS, {"AuthoredNet": {("A1", "1"), ("B1", "1"), *extra}})
    assert not report["equal"] and report["native_only_pins"] == len(extra)
    assert report["only_native_groups"] == report["only_drawn_groups"] == 1


def test_native_only_singleton_still_differs() -> None:
    ours = DrawnNetlist((DrawnNet("AuthoredNet", PINS),), PINS)
    report = census.partition_report(
        ours, REFS, {"AuthoredNet": {("A1", "1"), ("B1", "1")}, "Other": {("C1", "1")}}
    )
    assert not report["equal"] and report["native_only_pins"] == 1


def test_open_singletons_and_naming_are_distinct() -> None:
    opened = DrawnNetlist((), PINS, PINS)
    report = census.partition_report(opened, REFS, {})
    assert report["equal"] and report["native_groups"] == 2
    ours = DrawnNetlist((DrawnNet("AuthoredNet", PINS),), PINS)
    changed = census.partition_report(ours, REFS, {"OtherName": {("A1", "1"), ("B1", "1")}})
    assert changed["equal"] and not changed["naming_equal"] and changed["name_differences"] == 1
    assert "AuthoredNet" not in json.dumps(changed) and "OtherName" not in json.dumps(changed)


@pytest.fixture
def authored(tmp_path: Path, monkeypatch, request):
    name = getattr(request, "param", "flat")
    output = _drawn.build(name, 9)
    inputs = []
    for name, data in output.files.items():
        if not name.endswith(".kicad_sch"):
            continue
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        inputs.append(census.Input("authored-fixture", name, hashlib.sha256(data).hexdigest()))
    _, own, circuit = _drawn.resolved(output)
    refs = {c.properties["fenolite.path"]: c.ref for c in circuit.components}
    native = {
        net.name or f"AuthoredUnnamed{index}": {(refs[path], number) for path, number in net.members}
        for index, net in enumerate(own.nets)
    }
    calls = []

    def exported(cli, root, files):
        calls.append(files)
        return native

    monkeypatch.setattr(census._erc, "netlist", exported)
    args = (tmp_path, _drawn.root_name(output), inputs, KicadCli(Path("authored-stub")))
    return args, calls


@pytest.mark.parametrize("authored", _drawn.NAMES, indirect=True)
def test_real_lowering_and_closed_report(authored, tmp_path: Path) -> None:
    args, calls = authored
    before = {p.name: p.read_bytes() for p in tmp_path.rglob("*.kicad_sch")}
    report = census.measure(*args, ident="authored-flat", major=9, native_version="authored-stub")
    assert report["status"] == "equal", report
    assert len(calls) == 2
    assert all(report[key]["equal"] for key in ("partition", "lowered_partition", "lowered_native_partition"))
    assert report["counts"]["symbols"] > 0
    assert {p.name: p.read_bytes() for p in tmp_path.rglob("*.kicad_sch")} == before
    census.record(tmp_path, report)
    encoded = (tmp_path / "drawn-census.json").read_text(encoding="utf-8")
    assert json.loads(encoded) == report
    for content in ("Mini_QFP32_IC", "Mini:Mini_R", "U1", str(tmp_path), "(kicad_sch", "AuthoredNet"):
        assert content not in encoded


def test_hash_gate_precedes_parsing_and_tool(authored, tmp_path: Path) -> None:
    args, calls = authored
    target = tmp_path / args[1]
    target.write_bytes(b"Authored malformed data, no CAD parser should run.")
    report = census.measure(*args, ident="authored-flat", major=9, native_version="authored-stub")
    assert report["status"] == "invalid-cache" and not calls
    assert report["refusal"]["stage"] == "hash" and "counts" not in report


@pytest.mark.parametrize("stage", ["native-original", "lower"])
def test_refusal_is_recorded_before_strict_failure(authored, tmp_path: Path, monkeypatch, stage) -> None:
    args, _ = authored

    def refuse(*args, **kwargs):
        raise ValueError("Authored source value must not appear in committed census metadata")

    if stage == "lower":
        monkeypatch.setattr(census.kdrawn, "lower_drawn", refuse)
    else:
        monkeypatch.setattr(census._erc, "netlist", refuse)
    report = census.measure(*args, ident="authored-flat", major=9, native_version="authored-stub")
    assert report["status"] == "refused" and report["refusal"]["stage"] == stage
    census.record(tmp_path, report)
    text = (tmp_path / "drawn-census.json").read_text(encoding="utf-8")
    assert "Authored source value" not in text
    with pytest.raises(AssertionError):
        assert report["status"] == "equal"


def test_all_manifest_rows_collected_and_ci_retains_failed_reports(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "tests/kicad"))
    spec = importlib.util.spec_from_file_location(
        "drawn_census_driver", ROOT / "tests/kicad/schematic/test_drawn_corpus.py"
    )
    assert spec and spec.loader
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    rows = driver._schcorpus.rows()
    assert {r.id for r in driver.ROWS} == {r.id for r in rows if r.origin == "kicad-demos"}
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for major in (9, 10):
        assert f"name: drawn-census-kicad-{major}" in workflow
    assert workflow.count("path: /tmp/**/drawn-census.json") == 2
