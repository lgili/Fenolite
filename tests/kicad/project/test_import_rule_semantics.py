# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored native precedence controls before c0352 importer changes."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import _kicad
import _minimum_bench as mb
import pytest

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.triad import write_triad
from fenolite.model.circuit import NetClass
from fenolite.model.rules import Rule, Selector

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize(
    ("clearance", "floor", "named", "override", "expected"),
    (
        (150_000, "0.0762", False, False, "absent"),
        (200_000, "0.0762", False, False, "present"),
        (203_200, "0.0762", True, False, "present"),
        (203_200, "0.0762", True, True, "absent"),
        (203_200, "0.25", True, True, "absent"),
    ),
)
def test_native_default_floor_and_override_are_distinct(
    tmp_path: Path, clearance: int, floor: str, named: bool, override: bool, expected: str
) -> None:
    target = int(_kicad.supported_version().split(".")[0])
    design = mb.bench_design(target=target, board_wide=False)
    classes = tuple(
        dataclasses.replace(cls, clearance=50_000 if named else clearance) if cls.name == "Default" else cls
        for cls in design.circuit.netclasses
    )
    nets = design.circuit.nets
    if named:
        cls = NetClass(id="cls_00000000-0000-4000-8000-000000003552", name="PROBE", clearance=clearance)
        classes += (cls,)
        nets = tuple(
            dataclasses.replace(net, netclass_id=cls.id) if net.name in {"P_CLR_A", "P_CLR_B"} else net
            for net in nets
        )
    design = dataclasses.replace(
        design, circuit=dataclasses.replace(design.circuit, nets=nets, netclasses=classes)
    )
    assert design.rules is not None
    if override:
        rule = Rule(
            id="rul_00000000-0000-4000-8000-000000003552",
            name="actual_source_override",
            kind="clearance",
            selector_a=Selector("all"),
            min=76_200,
        )
        design = dataclasses.replace(
            design, rules=dataclasses.replace(design.rules, rules=(rule, *design.rules.rules))
        )
    files = write_triad(design, name=mb.NAME, target=target)
    project = _json.loads(files["bench.kicad_pro"])
    project["board"]["design_settings"]["rules"]["min_clearance"] = _json.JsonNumber(floor)
    files["bench.kicad_pro"] = _json.dumps(project)
    result = KicadCli(Path(_kicad.cli())).run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "drc.json", "bench.kicad_pcb"],
        files={name: data.encode() for name, data in files.items()},
    )
    assert result.ok and "drc.json" in result.outputs, (result.returncode, result.stderr)
    report = read_drc_report(result.outputs["drc.json"].decode())
    assert mb.canary_fired(report, design), "source DRU was not loaded"
    assert mb.judge_item(report, kind="clearance", design=design) == expected

    (tmp_path / "native-receipt.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "clearance_nm": clearance,
                "floor_mm": floor,
                "named_class": named,
                "actual_override": override,
                "input_sha256": {
                    name: hashlib.sha256(data.encode()).hexdigest() for name, data in files.items()
                },
                "native_report_sha256": hashlib.sha256(result.outputs["drc.json"]).hexdigest(),
                "probe_uuids": mb.item_uuids(design, "clearance"),
                "canary_fired": mb.canary_fired(report, design),
                "measured_outcome": mb.judge_item(report, kind="clearance", design=design),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


@pytest.mark.parametrize("preserve", (False, True))
def test_declared_source_floor_and_real_override_remain_independent(tmp_path: Path, preserve: bool) -> None:
    target = int(_kicad.supported_version().split(".")[0])
    design = mb.bench_design(target=target, board_wide=False)
    assert design.rules is not None
    override = Rule(
        id="rul_00000000-0000-4000-8000-000000003553",
        name="actual_source_override",
        kind="clearance",
        selector_a=Selector("all"),
        min=700_000,
    )
    design = dataclasses.replace(
        design, rules=dataclasses.replace(design.rules, rules=(override, *design.rules.rules))
    )
    initial = write_triad(design, name=mb.NAME, target=target)
    project = _json.loads(initial["bench.kicad_pro"])
    project["board"]["design_settings"]["rules"]["min_clearance"] = _json.JsonNumber("0.01")
    final = write_triad(
        design,
        name=mb.NAME,
        target=target,
        existing_project=_json.dumps(project),
        preserve_minimums=preserve,
    )
    value = _json.loads(final["bench.kicad_pro"])["board"]["design_settings"]["rules"]["min_clearance"]
    assert value == _json.JsonNumber("0.01" if preserve else "0.7")
    result = KicadCli(Path(_kicad.cli())).run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "drc.json", "bench.kicad_pcb"],
        files={name: data.encode() for name, data in final.items()},
    )
    assert result.ok and "drc.json" in result.outputs, (result.returncode, result.stderr)
    report = read_drc_report(result.outputs["drc.json"].decode())
    assert mb.canary_fired(report, design)
    assert mb.judge_item(report, kind="clearance", design=design) == "present"

    (tmp_path / "native-ownership-receipt.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "preserve_minimums": preserve,
                "native_floor_mm": value.text,
                "actual_rule_nm": 700_000,
                "input_sha256": {
                    name: hashlib.sha256(data.encode()).hexdigest() for name, data in final.items()
                },
                "native_report_sha256": hashlib.sha256(result.outputs["drc.json"]).hexdigest(),
                "probe_uuids": mb.item_uuids(design, "clearance"),
                "canary_fired": mb.canary_fired(report, design),
                "measured_outcome": mb.judge_item(report, kind="clearance", design=design),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
