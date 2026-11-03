# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native curve-configuration controls on original CC0 geometry (c0340, S-1207)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project
from _fidelity import snapshot

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, parse

pytestmark = pytest.mark.needs_kicad


def _tree(node: Atom | Node):
    if isinstance(node, Atom):
        return (
            ("number", Decimal(node.text).as_integer_ratio())
            if node.kind == AtomKind.NUMBER
            else (node.kind.value, node.value)
        )
    if node.name in {"uuid", "tstamp"}:
        return None
    return node.name, tuple(value for child in node.children if (value := _tree(child)) is not None)


def test_missing_curve_error_equals_5000_with_sensitive_10000_control(tmp_path: Path) -> None:
    version = _kicad.supported_version()
    major = int(version.split(".")[0])
    results = {}
    for name, value in (("missing", None), ("5000", 5_000), ("10000", 10_000)):
        folder = tmp_path / name
        project = curve_project(folder / "input", major, value)
        before = snapshot(project)
        board = project / "font_probe.kicad_pcb"
        environment = _kicad.oracle_env(folder / "config")
        receipts = []
        zones = []
        if major == 10:
            argv = [
                _kicad.cli(),
                "pcb",
                "drc",
                "--refill-zones",
                "--save-board",
                "--format",
                "json",
                "--output",
                str(folder / "drc.json"),
                str(board),
            ]
            done = subprocess.run(
                argv, env=environment, capture_output=True, text=True, timeout=60, check=False
            )
            assert done.returncode == 0, (argv, done.stdout, done.stderr)
            receipts.append(
                {"argv": argv, "exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
            )
            zones = [_tree(node) for node in parse(board.read_text()).nodes("zone")]
            assert len(zones) == 2
        argv = [
            _kicad.cli(),
            "pcb",
            "export",
            "dxf",
            "--use-contours",
            "--mode-single",
            "--output-units",
            "mm",
            "--exclude-refdes",
            "--exclude-value",
            "--layers",
            "F.Cu",
            "--output",
            str(folder / "geometry.dxf"),
            str(board),
        ]
        done = subprocess.run(argv, env=environment, capture_output=True, text=True, timeout=60, check=False)
        assert done.returncode == 0, (argv, done.stdout, done.stderr)
        receipts.append({"argv": argv, "exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr})
        # Compare the complete native geometry section, without time-dependent DXF header metadata.
        text = (folder / "geometry.dxf").read_text()
        start = text.index("ENTITIES")
        entities = text[start : text.index("ENDSEC", start)]
        after = snapshot(project)
        for path, digest in before.items():
            if major != 10 or path != board.name:
                assert after[path] == digest, path
        created = {path: digest for path, digest in after.items() if path not in before}
        assert set(created) <= {"font_probe.kicad_prl"}
        results[name] = {
            "version": version,
            "input_sha256": before,
            "created": created,
            "dxf_sha256": hashlib.sha256((folder / "geometry.dxf").read_bytes()).hexdigest(),
            "entities_sha256": hashlib.sha256(entities.encode()).hexdigest(),
            "regenerated_geometry_sha256": hashlib.sha256(
                json.dumps(sorted(zones), sort_keys=True).encode()
            ).hexdigest()
            if zones
            else None,
            "regenerated_zones": len(zones),
            "receipts": receipts,
        }
    assert results["missing"]["entities_sha256"] == results["5000"]["entities_sha256"]
    assert results["10000"]["entities_sha256"] != results["5000"]["entities_sha256"]
    if major == 10:
        assert (
            results["missing"]["regenerated_geometry_sha256"]
            == results["5000"]["regenerated_geometry_sha256"]
        )
        assert (
            results["10000"]["regenerated_geometry_sha256"] != results["5000"]["regenerated_geometry_sha256"]
        )
    (tmp_path / "curve-error-receipt.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
