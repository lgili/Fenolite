# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0246: each required KiCad job builds and reads both nominal/Range variants itself."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import _erc
import pytest
from _buildhelp import blink_variant
from _probes import major, runner

from fenolite.api import run
from fenolite.backends.kicad import erc, sch
from fenolite.backends.kicad.cli import NETLIST, KicadCli
from fenolite.backends.kicad.netlist import KicadNetlist, differences, read_netlist
from fenolite.backends.kicad.sch_netlist import own_netlist

pytestmark = pytest.mark.needs_kicad
SEED = 5
TIMESTAMP = "2026-10-29T00:00:00Z"
VALUES = {"nominal": 'ohm("330")', "range": 'ohm("330").pct(5)'}
ROOT_SHEET = "blink.kicad_sch"


def _build_pair(folder: Path, target: int) -> dict[str, dict[str, bytes]]:
    assert target in (9, 10)
    built = {}
    circuits = []
    for name, value in VALUES.items():
        script = blink_variant(folder / f"src-{name}", 'value="330")', f"value={value})")
        script.write_text(
            script.read_text().replace("from fenolite.dsl import ", "from fenolite.dsl import ohm, ")
        )
        out = folder / f"out-{name}"
        result = run(
            "build",
            str(script),
            "--out",
            str(out),
            "--confirm",
            "--kicad-version",
            str(target),
            seed=SEED,
            timestamp=TIMESTAMP,
        )
        assert result.exit_code == 0, result.error
        built[name] = {
            p.relative_to(out).as_posix(): p.read_bytes()
            for p in out.rglob("*")
            if p.is_file() and ".fenolite" not in p.relative_to(out).parts
        }
        circuits.append(json.loads((out / ".fenolite/circuit.json").read_text()))
    assert built["nominal"] == built["range"] and ROOT_SHEET in built["nominal"]
    nominal, ranged = ({c["ref"]: c for c in circuit["components"]} for circuit in circuits)
    assert "value_range" not in nominal["R1"]
    assert ranged["R1"].pop("value_range") == {
        "unit": "ohm",
        "low": {"m": 3135, "e": -1},
        "nominal": {"m": 33, "e": 1},
        "high": {"m": 3465, "e": -1},
    }
    assert circuits[0] == circuits[1]
    return built


def _export(tool: KicadCli, files: dict[str, bytes]) -> KicadNetlist:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        entries = _erc.tops(files, folder)
        result = tool.export_netlist(
            folder / ROOT_SHEET, files={k: v for k, v in entries.items() if k != ROOT_SHEET}
        )
    assert result.ok and NETLIST in result.outputs, result.stderr
    return read_netlist(result.outputs[NETLIST].decode("utf-8"), file=ROOT_SHEET)


def _measure_pair(folder: Path, target: int, tool: KicadCli) -> dict[str, KicadNetlist]:
    built = _build_pair(folder, target)
    exported = {}
    for name, files in built.items():
        native = _export(tool, files)  # Fresh I/O for EACH input, without an outcome/native cache.
        own = own_netlist(sch.read_schematic(files[ROOT_SHEET].decode("utf-8")), project="blink")
        assert differences(own, native) == (), (name, differences(own, native))
        assert next(c.value for c in native.components if c.ref == "R1") == "330Ω"
        report = _erc.run_erc(tool, ROOT_SHEET, files)
        assert report.returncode == 0 and report.loaded, (name, report.stderr)
        parsed = erc.read_erc_report(json.dumps(report.data), file="erc.json")
        assert not parsed.violations, (name, parsed.violations)
        exported[name] = native
    assert exported["nominal"] == exported["range"]
    return exported


def test_value_range_native_builds(tmp_path: Path) -> None:
    _measure_pair(tmp_path, major(), runner())
