# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native class enforcement follows exact PCB spelling, including hierarchical names (c0352)."""

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

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("raw_source", (False, True))
def test_exact_generated_and_native_source_names_enforce_same_class(tmp_path: Path, raw_source: bool) -> None:
    target = int(_kicad.supported_version().split(".")[0])
    original = mb.bench_design(target=target, board_wide=False)
    cls = NetClass(id="cls_00000000-0000-4000-8000-000000003559", name="PROBE", clearance=203_200)
    nets = tuple(
        dataclasses.replace(net, name="/12Vext", netclass_id=cls.id) if net.name == "P_CLR_A" else net
        for net in original.circuit.nets
    )
    design = dataclasses.replace(
        original,
        circuit=dataclasses.replace(
            original.circuit, nets=nets, netclasses=(*original.circuit.netclasses, cls)
        ),
    )
    files = write_triad(design, name=mb.NAME, target=target)
    if raw_source:
        # Authored source control changes only the exact string net-name atom, not routing or ids.
        assert '"{slash}12Vext"' in files["bench.kicad_pcb"]
        files["bench.kicad_pcb"] = files["bench.kicad_pcb"].replace('"{slash}12Vext"', '"/12Vext"')
        project = _json.loads(files["bench.kicad_pro"])
        for pattern in project["net_settings"]["netclass_patterns"]:
            if pattern["netclass"] == "PROBE":
                pattern["pattern"] = "/12Vext"
        files["bench.kicad_pro"] = _json.dumps(project)
    result = KicadCli(Path(_kicad.cli())).run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "drc.json", "bench.kicad_pcb"],
        files={name: data.encode() for name, data in files.items()},
    )
    assert result.ok and "drc.json" in result.outputs, (result.returncode, result.stderr)
    report = read_drc_report(result.outputs["drc.json"].decode())
    assert mb.canary_fired(report, original)
    assert mb.judge_item(report, kind="clearance", design=original) == "present"
    (tmp_path / "native-name-receipt.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "raw_source": raw_source,
                "input_sha256": {
                    name: hashlib.sha256(data.encode()).hexdigest() for name, data in files.items()
                },
                "report_sha256": hashlib.sha256(result.outputs["drc.json"]).hexdigest(),
                "probe_uuids": mb.item_uuids(original, "clearance"),
                "outcome": "present",
                "canary": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
